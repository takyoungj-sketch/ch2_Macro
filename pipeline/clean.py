"""
정제 파이프라인
land_transactions_raw 에서 원자료를 읽어 정제 후
land_transactions 테이블에 UPSERT 방식으로 적재한다.

사용법:
    python clean.py                     # 미처리 raw 데이터 전체 정제
    python clean.py --since 2025-01-01  # 특정 날짜 이후 raw 데이터만 정제
"""

from __future__ import annotations

import argparse
import hashlib
import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

from constants import (
    AREA_CATEGORIES,
    LAND_CATEGORY_COMPACT_MAP,
    PARTIAL_OWNERSHIP_FLAG_COL,
    ROAD_CONDITION_COMPACT_MAP,
    ZONE_TYPE_COMPACT_MAP,
)
from db_utils import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 원자료 컬럼명 → 정규화 컬럼명 매핑 (국토부 API 필드명 기준)
# ---------------------------------------------------------------------------
RAW_FIELD_MAP = {
    "dealYear": "contract_year",
    "dealMonth": "contract_month",
    "dealDay": "contract_day",
    "sggCd": "sigungu_code",
    "umdNm": "eupmyeondong_name",
    "landType": "land_category",
    "dealArea": "area_sqm",
    "dealAmount": "total_price_10k_raw",
    "zoning": "zone_type",
    "roadSide": "road_condition",
    "cdealType": "cancel_type",
    "cdealDay": "cancel_date",
    "dealingGbn": "deal_type",
    "dealGbn": "deal_type",
    # 지번
    "bonbun": "main_number",
    "bubun": "sub_number",
    # Excel(국토부 엑셀) 한글 헤더
    "순번": "source_row_no",
    "시군구": "sigungu_name",
    "번지": "lot_number",
    "지목": "land_category",
    "용도지역": "zone_type",
    "도로조건": "road_condition",
    "거래금액(만원)": "total_price_10k",
    "거래유형": "deal_type",
    "해제사유발생일": "cancel_date",
    "해제여부": "cancel_flag_raw",
    "계약일": "contract_day",
    "계약연월": "deal_ymd",
    "지분구분": "partial_ownership_raw",
    # collect 경유 시 보통 area_sqm 이나, 한글 키만 있는 raw 호환
    "계약면적": "area_sqm",
    "면적(㎡)": "area_sqm",
    "토지면적": "area_sqm",
}


# land_transactions_raw.raw_data 실제 키 (collect·API) 순으로 거래금액 문자열 후보.
# - Excel: collect.EXCEL_COLUMN_MAP 이 거래금액(만원) → total_price_10k 로 저장.
# - API: RAW_FIELD_MAP 이 dealAmount → total_price_10k_raw 로 저장.
PRICE_FROM_RAW_PRIORITY = (
    "total_price_10k_raw",
    "total_price_10k",
    "거래금액(만원)",
    "dealAmount",
)

# 국토부 실거래 엑셀 등에서 '미해제' 거래의 해제일/유형 칸에 자주 쓰는 부재 표기
_CANCEL_FIELD_MISSING_MARKERS = frozenset({
    "",
    "-",
    "—",
    "–",  # en dash
    "*",
    "nan",
    "nat",
    "none",
    "<na>",
    "null",
})


def _series_nonempty_meaningful(s: pd.Series) -> pd.Series:
    """공란·플레이스홀더는 False, 실제 해제 정보가 있으면 True."""
    t = s.fillna("").astype(str).str.strip().str.lower()
    return ~t.isin(_CANCEL_FIELD_MISSING_MARKERS)


def _numeric_from_area_strings(series: pd.Series | None) -> pd.Series:
    """
    면적(㎡) 문자열 파싱: 콤마·공백 제거 후 숫자 변환.
    '-', '*', 빈 문자열은 NULL(NaN).
    """
    if series is None:
        return pd.Series(dtype="float64")
    idx = series.index
    s = series.fillna("").astype(str)
    s = s.str.replace(r"\s+", "", regex=True)
    s = s.str.replace(",", "", regex=False).str.replace("，", "", regex=False)
    na_like = s.isin(["", "-", "*"])
    out = pd.to_numeric(s, errors="coerce")
    return pd.Series(out, index=idx).mask(na_like)


def _numeric_int_series(series: pd.Series | None) -> pd.Series:
    """pandas/DB 버전 차이에 덜 민감하게 정수형 결측을 object Series로 보존한다."""
    if series is None:
        return pd.Series(dtype="object")
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.map(lambda v: int(v) if pd.notna(v) else pd.NA)


def _text_series(df: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    """원본 문자열 컬럼을 엑셀 정제와 같은 방식으로 비교 가능하게 정리한다."""
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="object")
    return df[column].fillna(default).astype(str).str.strip()


def _compact_values(series: pd.Series, mapping: dict[str, str], fallback: str | None = None) -> pd.Series:
    """
    참고 노트북의 map(...).fillna(...) 패턴을 재현한다.
    fallback=None 이면 미매핑 값은 원래 값을 유지한다.
    """
    cleaned = series.fillna("").astype(str).str.strip()
    mapped = cleaned.map(mapping)
    if fallback is None:
        return mapped.fillna(cleaned)
    return mapped.fillna(fallback)


def build_region_lookup(engine) -> dict:
    """
    region_codes 테이블 전체를 메모리에 로드해 주소 → beopjungri_code 조회용 dict를 반환한다.

    키 우선순위 (중복 방지):
        1. (sido_name, eupmyeondong_name, beopjungri_name)  ← 가장 구체적
        2. (eupmyeondong_name, beopjungri_name)
        3. (sigungu_name, eupmyeondong_name)               ← 동 단위 fallback
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT sido_name, sigungu_name, eupmyeondong_name,
                       beopjungri_name, beopjungri_code, sido_code, sigungu_code
                FROM region_codes
                WHERE is_active = TRUE
            """)
        ).fetchall()

    lookup: dict[tuple, str] = {}
    code_lookup: dict[tuple, str] = {}  # (sido_code, eupmyeondong_name, beopjungri_name)

    for row in rows:
        sido_name, sigungu_name, eupmyeondong_name, beopjungri_name, beopjungri_code, sido_code, sigungu_code = row
        k1 = (sido_name, eupmyeondong_name, beopjungri_name)
        k2 = (eupmyeondong_name, beopjungri_name)
        k3 = (sigungu_name, eupmyeondong_name)
        k4 = (sido_code, eupmyeondong_name, beopjungri_name)

        # 덜 구체적인 키는 이미 등록된 게 없을 때만 삽입 (충돌 시 덮어쓰지 않음)
        lookup.setdefault(k1, beopjungri_code)
        lookup.setdefault(k2, beopjungri_code)
        lookup.setdefault(k3, beopjungri_code)
        code_lookup.setdefault(k4, beopjungri_code)

    log.info("region_codes 조회 테이블 빌드 완료: %d개 법정동/리", len(rows))
    return {"name": lookup, "code": code_lookup}


def _parse_address(address: str) -> tuple[str, str, str]:
    """
    국토부 Excel '시군구' 컬럼 주소 문자열을 파싱해
    (sido_name, eupmyeondong_name, beopjungri_name)을 반환한다.

    예:
        "충청북도 청주시 청원구 오창읍 가곡리" → ("충청북도", "오창읍", "가곡리")
        "충청북도 청주시 흥덕구 가경동"       → ("충청북도", "가경동", "가경동")
        "충청북도 충주시 이류면 문촌리"        → ("충청북도", "이류면", "문촌리")
    """
    parts = [p for p in str(address).strip().split() if p]
    if not parts:
        return "", "", ""

    sido = parts[0]

    # 마지막 토큰이 '리'로 끝나면 리 단위
    if len(parts) >= 2 and parts[-1].endswith("리"):
        eupmyeondong = parts[-2]
        beopjungri = parts[-1]
    else:
        # 동/읍/면 단위: eupmyeondong == beopjungri
        eupmyeondong = parts[-1]
        beopjungri = parts[-1]

    return sido, eupmyeondong, beopjungri


def map_beopjungri_codes(df: pd.DataFrame, lookup: dict) -> pd.Series:
    """
    DataFrame의 sigungu_name(주소 문자열) 컬럼으로 beopjungri_code를 조회해 Series로 반환한다.
    매핑 실패 행은 빈 문자열로 남긴다.
    """
    name_lookup = lookup.get("name", {})
    code_lookup = lookup.get("code", {})

    results = []
    miss_count = 0

    for _, row in df.iterrows():
        address = str(row.get("sigungu_name", ""))
        sido_code = str(row.get("sido_code", ""))

        if not address or address == "nan":
            results.append("")
            continue

        sido, eupmyeondong, beopjungri = _parse_address(address)

        # 우선순위 1: sido_name + eupmyeondong + beopjungri
        code = name_lookup.get((sido, eupmyeondong, beopjungri))

        # 우선순위 2: sido_code(2자리) + eupmyeondong + beopjungri
        if not code and sido_code:
            code = code_lookup.get((sido_code[:2], eupmyeondong, beopjungri))

        # 우선순위 3: eupmyeondong + beopjungri (시도 구분 없음)
        if not code:
            code = name_lookup.get((eupmyeondong, beopjungri))

        if not code:
            miss_count += 1

        results.append(code or "")

    if miss_count:
        log.warning(
            "beopjungri_code 매핑 실패: %d건 / 전체 %d건. "
            "region_codes 시드 적재 여부 및 주소 형식을 확인하세요.",
            miss_count, len(df),
        )

    return pd.Series(results, index=df.index)


def fetch_unprocessed_raw(since: str | None = None, reprocess_all: bool = False) -> pd.DataFrame:
    """미처리 raw 데이터를 읽어 DataFrame으로 반환한다."""
    engine = get_engine()
    where = ""
    params: dict = {}

    if reprocess_all:
        if since:
            where = "WHERE r.loaded_at >= :since"
            params["since"] = since
    elif since:
        where = "WHERE r.loaded_at >= :since AND r.id NOT IN (SELECT DISTINCT raw_id FROM land_transactions WHERE raw_id IS NOT NULL)"
        params["since"] = since
    else:
        where = "WHERE r.id NOT IN (SELECT DISTINCT raw_id FROM land_transactions WHERE raw_id IS NOT NULL)"

    query = f"""
        SELECT r.id AS raw_id, r.source_year, r.source_month, r.raw_data
        FROM land_transactions_raw r
        {where}
        ORDER BY r.id
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).fetchall()

    if not rows:
        return pd.DataFrame()

    records = []
    for row in rows:
        record = {"_raw_id": row[0], "_source_year": row[1], "_source_month": row[2]}
        record.update(row[3])  # JSONB dict
        records.append(record)

    return pd.DataFrame(records)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """원자료 DataFrame을 정제해 land_transactions 적재용 DataFrame으로 반환한다."""

    # 컬럼명 통일
    df = df.rename(columns={k: v for k, v in RAW_FIELD_MAP.items() if k in df.columns})

    if "trade_type" in df.columns and "deal_type" not in df.columns:
        df["deal_type"] = df["trade_type"]

    if "deal_ymd" in df.columns:
        deal_ymd = _text_series(df, "deal_ymd")
        if "contract_year" not in df.columns:
            df["contract_year"] = deal_ymd.str[:4]
        if "contract_month" not in df.columns:
            df["contract_month"] = deal_ymd.str[4:6]

    # 숫자형 변환
    df["contract_year"] = _numeric_int_series(df.get("contract_year"))
    df["contract_month"] = _numeric_int_series(df.get("contract_month"))

    area_src = df["area_sqm"] if "area_sqm" in df.columns else pd.Series(pd.NA, index=df.index)
    df["area_sqm"] = _numeric_from_area_strings(area_src)

    # 거래금액: collect/raw 실제 키 순으로 후보 컬럼에서 문자열 추출 후 숫자 변환
    price_src_col = next((c for c in PRICE_FROM_RAW_PRIORITY if c in df.columns), None)
    if price_src_col is None:
        log.warning(
            "거래금액 원본 컬럼 없음 (후보 %s). total_price_10k 는 NaN 처리됩니다.",
            PRICE_FROM_RAW_PRIORITY,
        )
        price_raw = pd.Series("", index=df.index, dtype=str)
    else:
        price_raw = df[price_src_col].astype(str)
    df["total_price_10k"] = pd.to_numeric(
        price_raw.str.replace(",", "", regex=False),
        errors="coerce",
    ).round(1)

    # 단가(만원/㎡) = 거래금액(만원) / 계약면적.
    # 참고 엑셀 정제 파일의 '단가' 컬럼과 같은 분석 단위다.
    _tp = df["total_price_10k"]
    _area = df["area_sqm"]
    df["unit_price_per_sqm"] = ((_tp / _area).round(1)).where(_tp.notna() & (_area > 0))

    # 면적구분
    df["area_category"] = df["area_sqm"].apply(_classify_area)

    # 참고 노트북 기준 핵심 정제: 용도지역·지목·도로조건 축약.
    # 이 값이 그대로 용도지역 × 지목 매트릭스의 행/열 키가 된다.
    df["land_category"] = _compact_values(
        _text_series(df, "land_category"),
        LAND_CATEGORY_COMPACT_MAP,
    )
    df["zone_type"] = _compact_values(
        _text_series(df, "zone_type"),
        ZONE_TYPE_COMPACT_MAP,
        fallback="기타",
    )
    df["road_condition"] = _compact_values(
        _text_series(df, "road_condition"),
        ROAD_CONDITION_COMPACT_MAP,
        fallback="-",
    )

    # 해제거래: 해제일·해제유형·해제여부 플래그 ('-', '*' 등 부재 표기는 미해제로 본다)
    cd_s = df.get("cancel_date", pd.Series("", index=df.index))
    ct_s = df.get("cancel_type", pd.Series("", index=df.index))
    cf = df.get("cancel_flag_raw", pd.Series("", index=df.index)).astype(str).str.strip()
    df["is_cancelled"] = (
        _series_nonempty_meaningful(cd_s)
        | _series_nonempty_meaningful(ct_s)
        | cf.str.upper().isin({"O", "Y", "YES", "1", "해제", "TRUE"})
    )

    # 지분거래: 지분구분 또는 거래유형/API dealingGbn 등에 '지분' 포함
    partial_txt = _text_series(df, "partial_ownership_raw")
    deal_txt = df.get("deal_type", pd.Series("", index=df.index)).astype(str)
    df[PARTIAL_OWNERSHIP_FLAG_COL] = (
        partial_txt.str.contains("지분", na=False)
        | deal_txt.str.contains("지분", na=False)
    )

    # 유효성 플래그: 참고 노트북은 해제사유발생일 '-' 만 남긴다.
    df["is_valid"] = (
        df["area_sqm"].notna()
        & df["total_price_10k"].notna()
        & (df["area_sqm"] > 0)
        & (df["total_price_10k"] > 0)
        & ~df["is_cancelled"]
    )

    # sido_code: API 모드는 sigungu_code 앞 2자리, Excel 모드는 주소에서 추출
    df["sido_code"] = df.get("sigungu_code", pd.Series("", index=df.index)).astype(str).str[:2]

    # beopjungri_code: API 모드(코드 있음) vs Excel 모드(주소 문자열 → 조회)는 main()에서 처리
    # 여기서는 기존 값 보존 (없으면 빈 문자열, clean_step2에서 채워짐)
    if "beopjungri_code" not in df.columns:
        df["beopjungri_code"] = ""
    df["beopjungri_code"] = df["beopjungri_code"].fillna("")

    # 계약일
    if "contract_day" in df.columns:
        df["contract_day"] = pd.to_numeric(df["contract_day"], errors="coerce")
    else:
        df["contract_day"] = pd.NA
    try:
        if "contract_year" in df.columns and "contract_month" in df.columns:
            df["contract_date"] = pd.to_datetime(
                {
                    "year": df["contract_year"],
                    "month": df["contract_month"],
                    "day": df["contract_day"],
                },
                errors="coerce",
            ).dt.date
        else:
            df["contract_date"] = None
    except Exception:
        df["contract_date"] = None

    # transaction_hash 생성 (중복 방지)
    df["transaction_hash"] = df.apply(_make_hash, axis=1)

    df["raw_id"] = df["_raw_id"]

    return df


def _classify_area(area: float | None) -> str | None:
    if area is None or pd.isna(area):
        return None
    for label, (lo, hi) in AREA_CATEGORIES.items():
        if (lo is None or area >= lo) and (hi is None or area < hi):
            return label
    return None


def _make_hash(row: pd.Series) -> str:
    """신고 행 고유키: 정상 신고와 해제 신고가 서로 덮어쓰지 않게 만든다."""
    region_key = row.get("beopjungri_code") or row.get("sigungu_code") or row.get("sigungu_name") or ""
    lot_key = row.get("lot_number") or "|".join(str(row.get(c, "")) for c in ["main_number", "sub_number"])
    # Excel 원본의 순번을 우선 사용한다. API 등 순번이 없으면 raw_id로 행 단위를 보존한다.
    source_row_key = row.get("source_row_no") or row.get("_raw_id") or ""
    key = "|".join(
        str(v)
        for v in [
            source_row_key,
            region_key,
            row.get("contract_year", ""),
            row.get("contract_month", ""),
            row.get("contract_day", ""),
            lot_key,
            row.get("area_sqm", ""),
            row.get("total_price_10k", ""),
            row.get("cancel_date", ""),
            row.get("cancel_type", ""),
            row.get("cancel_flag_raw", ""),
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()


def upsert_transactions(df: pd.DataFrame) -> int:
    """정제된 DataFrame을 land_transactions 에 UPSERT 한다."""
    before = len(df)
    df = df[df["total_price_10k"].notna()].copy()
    skipped = before - len(df)
    if skipped:
        log.info("total_price_10k 가 NULL/NaN 인 거래 UPSERT 제외: %d건", skipped)
    if df.empty:
        log.info("UPSERT 대상 없음")
        return 0

    engine = get_engine()
    inserted = 0
    cols = [
        "transaction_hash", "contract_year", "contract_month", "contract_date",
        "beopjungri_code", "sido_code", "sigungu_code",
        "land_category", "zone_type", "road_condition",
        "area_sqm", "area_category",
        "total_price_10k", "unit_price_per_sqm",
        "is_partial_ownership", "is_cancelled", "is_valid", "raw_id",
    ]

    with engine.begin() as conn:
        for _, row in tqdm(df.iterrows(), total=len(df), desc="UPSERT"):
            values = {c: (None if pd.isna(row.get(c)) else row.get(c)) for c in cols}
            values["is_partial_ownership"] = bool(values.get("is_partial_ownership", False))
            values["is_cancelled"] = bool(values.get("is_cancelled", False))
            values["is_valid"] = bool(values.get("is_valid", True))
            conn.execute(
                text("""
                    INSERT INTO land_transactions (
                        transaction_hash, contract_year, contract_month, contract_date,
                        beopjungri_code, sido_code, sigungu_code,
                        land_category, zone_type, road_condition,
                        area_sqm, area_category,
                        total_price_10k, unit_price_per_sqm,
                        is_partial_ownership, is_cancelled, is_valid, raw_id
                    ) VALUES (
                        :transaction_hash, :contract_year, :contract_month, :contract_date,
                        :beopjungri_code, :sido_code, :sigungu_code,
                        :land_category, :zone_type, :road_condition,
                        :area_sqm, :area_category,
                        :total_price_10k, :unit_price_per_sqm,
                        :is_partial_ownership, :is_cancelled, :is_valid, :raw_id
                    )
                    ON CONFLICT (transaction_hash) DO UPDATE SET
                        contract_year = EXCLUDED.contract_year,
                        contract_month = EXCLUDED.contract_month,
                        contract_date = EXCLUDED.contract_date,
                        beopjungri_code = EXCLUDED.beopjungri_code,
                        sido_code = EXCLUDED.sido_code,
                        sigungu_code = EXCLUDED.sigungu_code,
                        land_category = EXCLUDED.land_category,
                        zone_type = EXCLUDED.zone_type,
                        road_condition = EXCLUDED.road_condition,
                        area_sqm = EXCLUDED.area_sqm,
                        area_category = EXCLUDED.area_category,
                        total_price_10k = EXCLUDED.total_price_10k,
                        unit_price_per_sqm = EXCLUDED.unit_price_per_sqm,
                        is_partial_ownership = EXCLUDED.is_partial_ownership,
                        is_cancelled = EXCLUDED.is_cancelled,
                        is_valid = EXCLUDED.is_valid,
                        raw_id = EXCLUDED.raw_id,
                        updated_at = NOW()
                """),
                values,
            )
            inserted += 1

    log.info("UPSERT 완료: %d건", inserted)
    return inserted


def main():
    parser = argparse.ArgumentParser(description="토지 실거래 데이터 정제")
    parser.add_argument("--since", type=str, default=None, help="YYYY-MM-DD 이후 raw 데이터만 처리")
    parser.add_argument(
        "--reprocess-all",
        action="store_true",
        help="이미 처리된 raw_id도 다시 정제해 UPSERT (정제 기준 변경 후 재생성용)",
    )
    parser.add_argument(
        "--skip-region-map",
        action="store_true",
        help="beopjungri_code 주소 매핑을 건너뜀 (region_codes 미적재 환경에서 테스트용)",
    )
    args = parser.parse_args()

    log.info("미처리 raw 데이터 조회 중...")
    df = fetch_unprocessed_raw(since=args.since, reprocess_all=args.reprocess_all)

    if df.empty:
        log.info("처리할 데이터가 없습니다.")
        return

    log.info("정제 시작: %d건", len(df))
    cleaned = clean_dataframe(df)

    # clean_step2: 주소 문자열 → beopjungri_code 매핑
    if not args.skip_region_map:
        engine = get_engine()
        needs_mapping = cleaned["beopjungri_code"].eq("") | cleaned["beopjungri_code"].isna()
        if needs_mapping.any():
            log.info("beopjungri_code 매핑 시작: %d건", needs_mapping.sum())
            lookup = build_region_lookup(engine)
            mapped = map_beopjungri_codes(cleaned[needs_mapping], lookup)
            cleaned.loc[needs_mapping, "beopjungri_code"] = mapped.values

            # 매핑 후 sido_code도 보완 (beopjungri_code 앞 2자리)
            still_no_sido = cleaned["sido_code"].eq("") | cleaned["sido_code"].isna()
            cleaned.loc[still_no_sido, "sido_code"] = (
                cleaned.loc[still_no_sido, "beopjungri_code"].str[:2]
            )
            # sigungu_code 보완 (beopjungri_code 앞 5자리)
            if "sigungu_code" not in cleaned.columns:
                cleaned["sigungu_code"] = ""
            no_sigungu = cleaned["sigungu_code"].eq("") | cleaned["sigungu_code"].isna()
            cleaned.loc[no_sigungu, "sigungu_code"] = (
                cleaned.loc[no_sigungu, "beopjungri_code"].str[:5]
            )

            still_missing = cleaned["beopjungri_code"].eq("").sum()
            log.info(
                "beopjungri_code 매핑 완료. 미매핑: %d건 (region_codes 확인 필요)",
                still_missing,
            )
        else:
            log.info("beopjungri_code 이미 존재, 매핑 생략")
    else:
        log.warning("--skip-region-map: beopjungri_code 매핑 건너뜀")

    valid = cleaned[cleaned["is_valid"] == True]
    log.info("유효 데이터: %d건 / 전체 %d건", len(valid), len(cleaned))

    upsert_transactions(cleaned)


if __name__ == "__main__":
    main()
