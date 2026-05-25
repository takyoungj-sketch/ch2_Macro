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
import os
import re
from datetime import datetime

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
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

# 전국 재처리 시 행 단위 UPSERT 비용 완화 (환경변수로 조정)
_CLEAN_UPSERT_PAGE = max(100, int(os.environ.get("CLEAN_UPSERT_PAGE_SIZE", "1500")))

# 국토부 엑셀 등: 기암리(岐岩里) ↔ 행정코드 기암리(岐岩) 같이 괄호 병기만 다른 경우
_RE_PAREN_FW = re.compile(r"（[^（）]*）")
_RE_PAREN_ASCII = re.compile(r"\([^()]*\)")

# 시도명 별칭: 거래 원장에 쓰이는 신표기 ↔ region_codes 마스터 표기
# (예: 2024 이후 거래원장 "전북특별자치도" vs region_codes "전라북도")
_SIDO_NAME_ALIASES: dict[str, str] = {
    "전북특별자치도": "전라북도",
    "강원특별자치도": "강원도",
}


def _extract_paren_content(s: str | None) -> str:
    """행정명 안 괄호 내용(주로 한자) 추출. 여러 괄호가 있으면 모두 이어 붙임.

    예: '기암리(岐岩)' → '岐岩'  / '화산리（花山）' → '花山'  / 일반 한글명 → ''.
    동명이리 disambiguation 키로만 쓰인다.
    """
    if s is None:
        return ""
    t = str(s).strip()
    if not t:
        return ""
    parts: list[str] = []
    for m in _RE_PAREN_FW.finditer(t):
        # 전각 괄호 _RE_PAREN_FW 패턴은 '（...）' 통째라 슬라이싱으로 안쪽만 취한다.
        parts.append(m.group(0)[1:-1])
    for m in _RE_PAREN_ASCII.finditer(t):
        parts.append(m.group(0)[1:-1])
    return "".join(p.strip() for p in parts if p and p.strip())


def _normalize_admin_label(s: str | None) -> str:
    """읍면동·법정리명 lookup 정규화: 전각·반각 괄호 구간(한자 병기 등) 제거 후 trim."""
    if s is None:
        return ""
    t = str(s).strip()
    if not t:
        return ""
    prev = None
    while prev != t:
        prev = t
        t = _RE_PAREN_FW.sub("", t).strip()
        t = _RE_PAREN_ASCII.sub("", t).strip()
    return t


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


def _nullable_lot_token(v: object) -> str:
    """본번·부번 등 번지 성분 문자열화 (정수처럼 보이면 불필요한 소수점 제거)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, bool):
        return ""
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        try:
            if v != v:  # NaN
                return ""
            iv = int(v)
            return str(iv) if abs(float(v) - float(iv)) < 1e-9 else str(v).strip()
        except (ValueError, OverflowError):
            return str(v).strip()
    try:
        f = float(v)
        if f != f:
            return ""
        iv = int(f)
        if abs(float(f) - float(iv)) < 1e-9:
            return str(iv)
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return ""
    return s


def _derive_lot_display(df: pd.DataFrame) -> pd.Series:
    """엑셀 「번지」 또는 API 본번·부번으로 표시용 번지 문자열."""
    idx = df.index
    lot_num = df.get("lot_number", pd.Series("", index=idx)).fillna("").astype(str).str.strip()

    mn_s = (
        df["main_number"].map(_nullable_lot_token)
        if "main_number" in df.columns
        else pd.Series("", index=idx, dtype=str)
    )
    sn_s = (
        df["sub_number"].map(_nullable_lot_token)
        if "sub_number" in df.columns
        else pd.Series("", index=idx, dtype=str)
    )

    invalid_sub = (sn_s.eq("")) | (sn_s.eq("0"))
    suffix_s = ("-" + sn_s.astype(str)).where(~invalid_sub, other="")
    assembled = mn_s.astype(str).str.cat(suffix_s)
    combined = lot_num.where(lot_num.ne(""), assembled.where(mn_s.ne(""), ""))
    return combined.astype(str).str.strip().str.slice(0, 64)


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


def _register_strong_key(
    target: dict[tuple, str],
    key: tuple,
    code: str,
    label: str,
) -> None:
    """강한 키만 등록. 동일 키에 서로 다른 코드면 경고 후 기존 유지."""
    c = str(code).strip()
    if not c or not key or all(str(x).strip() == "" for x in key if x is not None):
        return
    key_n = tuple(str(x).strip() if x is not None else "" for x in key)
    if key_n in target:
        if str(target[key_n]).strip() != c:
            log.warning(
                "region_codes %s 키 충돌(첫 코드 유지): key=%r existing=%r new=%r",
                label,
                key_n,
                target[key_n],
                c,
            )
        return
    target[key_n] = c


def build_region_lookup(engine) -> dict:
    """
    region_codes → beopjungri_code 강한 키만:
      - by_sigungu_name: (sido_name, sigungu_name, eupmyeondong_name, beopjungri_name)
      - by_sigungu_code: (sido_code 2자, sigungu_code 5자, eupmyeondong_name, beopjungri_name)

    읍면동·법정리명은 괄호 한자 병기 제거 후 키로 사용해 엑셀 원문과 행정DB 표기 차이를 흡수한다.

    약한 키 (읍면동+법정명 단독 등)는 매핑에 사용하지 않는다.
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

    by_sigungu_name: dict[tuple, str] = {}
    by_sigungu_code: dict[tuple, str] = {}
    weak_pairs: dict[tuple[str, str], set[str]] = {}
    # 동명이리 disambiguation 인덱스:
    # 정규화 키(시도명, 시군구명, 읍면, 정규화된 동·리명) → [(code, 괄호안한자, 원본명), …]
    # 동일 키에 항목이 2개 이상이면 한자 비교로 분기 (DECISIONS A안).
    disamb_by_name: dict[tuple, list[tuple[str, str, str]]] = {}
    disamb_by_code: dict[tuple, list[tuple[str, str, str]]] = {}

    for row in rows:
        sido_name, sigungu_name, eupmyeondong_name, beopjungri_name, beopjungri_code, sido_code, sigungu_code = row
        sn = str(sido_name).strip()
        sg = str(sigungu_name).strip()
        eu = str(eupmyeondong_name).strip()
        bn = str(beopjungri_name).strip()
        eu_k = _normalize_admin_label(eu)
        bn_k = _normalize_admin_label(bn)
        sc = str(sido_code).strip()[:2]
        gc = str(sigungu_code).strip().zfill(5)[:5]
        bn_hanja = _extract_paren_content(bn)

        _register_strong_key(
            by_sigungu_name,
            (sn, sg, eu_k, bn_k),
            beopjungri_code,
            "by_sigungu_name",
        )
        if sc and gc:
            _register_strong_key(
                by_sigungu_code,
                (sc, gc, eu_k, bn_k),
                beopjungri_code,
                "by_sigungu_code",
            )

        wk = (eu_k, bn_k)
        weak_pairs.setdefault(wk, set()).add(str(beopjungri_code).strip())

        # disambiguation 후보 누적: 동일 정규화 키에 여러 코드가 있으면 한자 비교로 골라낸다.
        disamb_by_name.setdefault((sn, sg, eu_k, bn_k), []).append(
            (str(beopjungri_code).strip(), bn_hanja, bn)
        )
        if sc and gc:
            disamb_by_code.setdefault((sc, gc, eu_k, bn_k), []).append(
                (str(beopjungri_code).strip(), bn_hanja, bn)
            )

    # 충돌 그룹만 남긴다(>=2 개). 단일 코드 그룹은 메모리만 차지하므로 제외.
    disamb_by_name = {k: v for k, v in disamb_by_name.items() if len(v) > 1}
    disamb_by_code = {k: v for k, v in disamb_by_code.items() if len(v) > 1}

    multi_weak = sum(1 for s in weak_pairs.values() if len(s) > 1)
    if multi_weak:
        log.warning(
            "동명이인 약한 키(읍면동명,법정명) 조합 %d개가 전국에 복수 코드 — 단독 매핑 미사용",
            multi_weak,
        )

    if disamb_by_name:
        log.info(
            "동명이리 disambiguation 그룹: name=%d, code=%d (한자 키로 분기)",
            len(disamb_by_name),
            len(disamb_by_code),
        )

    log.info(
        "region_codes 강한 lookup: name_keys=%d code_keys=%d 행=%d",
        len(by_sigungu_name),
        len(by_sigungu_code),
        len(rows),
    )
    return {
        "by_sigungu_name": by_sigungu_name,
        "by_sigungu_code": by_sigungu_code,
        "disamb_by_name": disamb_by_name,
        "disamb_by_code": disamb_by_code,
    }


def _parse_address_structured(address: str) -> tuple[str, str, str, str]:
    """
    국토부 Excel '시군구' 컬럼 전체 주소 문자열 →
    (sido_name, sigungu_name, eupmyeondong_name, beopjungri_name).

    - 법정리: ... 시·군·구 … 읍·면 가곡리 → sigungu=앞 중간 전부(시도 제외), eup=읍·면, beop=리
      마지막 토큰이 `기암리(岐岩)` 처럼 괄호 한자 병기면 `endswith("리")` 가 실패하므로,
      괄호 제거 정규화 후 `리` 여부를 판별한다.
    - 그 외(동·읍·면 단일 행정리): ... 수원시 영통동 / … 분당구 대장동
      → sigungu = parts[1:-1] 공백 결합, eup=beop=마지막 토큰(정규화)
    """
    parts = [p for p in str(address).strip().split() if p]
    if not parts:
        return "", "", "", ""

    sido = parts[0]
    last_raw = parts[-1]
    last_norm = _normalize_admin_label(last_raw) or last_raw

    if len(parts) >= 4 and last_norm.endswith("리"):
        sigungu = " ".join(parts[1:-2])
        eup = parts[-2]
        beop = last_norm
        return sido, sigungu, eup, beop

    leaf = last_norm
    if len(parts) < 2:
        return sido, "", leaf, leaf

    sigungu = " ".join(parts[1:-1])
    return sido, sigungu, leaf, leaf


def map_beopjungri_codes(df: pd.DataFrame, region_maps: dict) -> pd.DataFrame:
    """
    시군구 전체 주소(sigungu_name) 또는 (sigungu_code+sido_code + eupmyeondong_name)로
    강한 키만 매핑. 실패 시 code 공백, needs_review=True, mapping_notes 채움.
    읍면동·법정리는 괄호 병기 제거 정규화 후 lookup 한다.
    약한 키·시도 무관 fallback 은 사용하지 않는다.
    """
    by_name = region_maps.get("by_sigungu_name", {})
    by_code = region_maps.get("by_sigungu_code", {})
    disamb_by_name = region_maps.get("disamb_by_name", {})
    disamb_by_code = region_maps.get("disamb_by_code", {})

    n = len(df)
    if n == 0:
        return pd.DataFrame(
            {
                "beopjungri_code": pd.Series([], index=df.index, dtype=object),
                "needs_review": pd.Series([], index=df.index, dtype=bool),
                "mapping_notes": pd.Series([], index=df.index, dtype=object),
            }
        )

    addr = (
        df.get("sigungu_name", pd.Series("", index=df.index))
        .fillna("")
        .astype(str)
        .str.strip()
    )
    umd = (
        df.get(
            "eupmyeondong_name",
            df.get("umdNm", pd.Series("", index=df.index)),
        )
        .fillna("")
        .astype(str)
        .str.strip()
    )
    sido_code = df.get("sido_code", pd.Series("", index=df.index)).fillna("").astype(str).str.strip()
    sg_raw = df.get("sigungu_code", pd.Series("", index=df.index)).fillna("").astype(str).str.strip()

    mask_addr = addr.ne("") & addr.ne("nan")
    # 주소 파싱 (리/동 분기) — 리스트 컴프리헨션으로 iterrows 대체
    parsed = [_parse_address_structured(a) for a in addr.tolist()]
    sido_n = pd.Series([p[0] for p in parsed], index=df.index, dtype=object)
    sigungu_n = pd.Series([p[1] for p in parsed], index=df.index, dtype=object)
    eup_n = pd.Series([p[2] for p in parsed], index=df.index, dtype=object)
    beop_n = pd.Series([p[3] for p in parsed], index=df.index, dtype=object)

    only_umd = ~mask_addr & umd.ne("")
    eup_n = eup_n.where(~only_umd, umd)
    beop_n = beop_n.where(~only_umd, umd)

    sc5_list = [
        s.zfill(5)[-5:] if s and str(s).replace(" ", "").isdigit() else ""
        for s in sg_raw.tolist()
    ]
    sc2_list = sido_code.str[:2].tolist()

    sn_l = sido_n.tolist()
    sg_l = sigungu_n.tolist()
    eu_l = eup_n.tolist()
    bp_l = beop_n.tolist()
    addr_l = addr.tolist()
    umd_l = umd.tolist()

    codes: list[str] = []
    reviews: list[bool] = []
    notes: list[str] = []
    miss = 0

    for i in range(n):
        sn, sg, eu, bp = sn_l[i], sg_l[i], eu_l[i], bp_l[i]
        eu_k = _normalize_admin_label(eu)
        bp_k = _normalize_admin_label(bp)
        # 거래 원장의 동·리 한자 — disambiguation 키.
        # `bp` 는 _parse_address_structured 가 _normalize_admin_label 로 정규화한 결과라
        # 괄호 한자가 이미 제거돼 있다. 원문 addr 의 마지막 토큰에서 직접 추출한다.
        addr_tail = addr_l[i].split()[-1] if addr_l[i] else ""
        bp_hanja = _extract_paren_content(addr_tail)
        code = ""
        fallback_note = ""

        # 0) Disambiguation 우선 — 동명이리 그룹(같은 정규화 이름·다른 한자)이면 한자 일치로 분기.
        #    DECISIONS A안: region_codes 의 괄호 한자가 거래 표기 한자에 포함되면 해당 코드 선택.
        #    (region_codes 한자가 부분 표기인 경우(예: '岐岩' vs '岐岩里')도 흡수)
        if bp_hanja and sn and sg and eu_k and bp_k:
            cand = disamb_by_name.get((sn, sg, eu_k, bp_k))
            if cand:
                for c_code, c_hanja, _ in cand:
                    if c_hanja and (c_hanja in bp_hanja or bp_hanja in c_hanja):
                        code = c_code
                        fallback_note = "disambiguated_hanja"
                        break
        if not code and bp_hanja:
            s2, s5 = sc2_list[i], sc5_list[i]
            if s2 and s5 and eu_k and bp_k:
                cand = disamb_by_code.get((s2, s5, eu_k, bp_k))
                if cand:
                    for c_code, c_hanja, _ in cand:
                        if c_hanja and (c_hanja in bp_hanja or bp_hanja in c_hanja):
                            code = c_code
                            fallback_note = "disambiguated_hanja"
                            break

        if not code and sn and sg and eu_k and bp_k:
            code = by_name.get((sn, sg, eu_k, bp_k), "") or ""
        if not code:
            s2, s5 = sc2_list[i], sc5_list[i]
            if s2 and s5 and eu_k and bp_k:
                code = by_code.get((s2, s5, eu_k, bp_k), "") or ""

        # Fallback 1: 시도명 별칭 (전북특별자치도 → 전라북도 등)
        if not code and sn in _SIDO_NAME_ALIASES and sg and eu_k and bp_k:
            alias_sn = _SIDO_NAME_ALIASES[sn]
            code = by_name.get((alias_sn, sg, eu_k, bp_k), "") or ""
            if code:
                fallback_note = "sido_alias"

        # Fallback 2: 시군구가 분구 표기(예: '화성시 만세구')라 마스터에 없을 때,
        # 마지막 시군구 토큰을 한 번씩 제거하며 재시도. sigungu_code(5자리)는 동일하므로
        # 상위 통계엔 영향 없음. 신설 분구 등이 region_codes에 적재되기 전 임시 흡수.
        if not code and sg and eu_k and bp_k:
            sg_tokens = sg.split()
            current_sn = sn if sn not in _SIDO_NAME_ALIASES else _SIDO_NAME_ALIASES[sn]
            while not code and len(sg_tokens) >= 2:
                sg_tokens = sg_tokens[:-1]
                sg_trim = " ".join(sg_tokens)
                code = by_name.get((current_sn, sg_trim, eu_k, bp_k), "") or ""
                if code:
                    fallback_note = "subgu_dropped"
                    break

        if not code:
            miss += 1
            reviews.append(True)
            a = addr_l[i]
            u = umd_l[i]
            if not a or a == "nan":
                if not u:
                    note = "no_address_and_no_umd"
                else:
                    note = "no_strong_match_umd_only"
            elif not sg_l[i]:
                note = "no_strong_match_short_address"
            else:
                note = "no_strong_match"
            codes.append("")
            notes.append(note)
            continue

        codes.append(str(code).strip())
        reviews.append(False)
        notes.append(fallback_note)

    if miss:
        log.warning(
            "beopjungri_code 강한키 매핑 실패: %d건 / %d건 (region_codes·주소 형식 확인)",
            miss,
            n,
        )

    idx = df.index
    return pd.DataFrame(
        {
            "beopjungri_code": pd.Series(codes, index=idx, dtype=object),
            "needs_review": pd.Series(reviews, index=idx, dtype=bool),
            "mapping_notes": pd.Series(notes, index=idx, dtype=object),
        }
    )


_NOT_IN_LT = """NOT EXISTS (
                  SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id
              )"""


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
        where = f"WHERE r.loaded_at >= :since AND {_NOT_IN_LT}"
        params["since"] = since
    else:
        where = f"WHERE {_NOT_IN_LT}"

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

    df["needs_review"] = False
    df["mapping_notes"] = ""

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

    df["lot_display"] = _derive_lot_display(df)
    _pl_raw = partial_txt.str.slice(0, 128)
    df["partial_ownership_label"] = _pl_raw.mask(_pl_raw.eq(""), other=pd.NA)
    _dt_trim = df.get("deal_type", pd.Series("", index=df.index)).fillna("").astype(str).str.strip().str.slice(0, 128)
    df["deal_type"] = _dt_trim.mask(_dt_trim.eq(""), other=pd.NA)

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


def _prepare_land_tx_upsert(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """UPSERT용 컬럼만 복사·정규화 (NaN → None, bool·mapping_notes 정리)."""
    out = df.loc[:, cols].copy()
    for c in ("is_partial_ownership", "is_cancelled", "is_valid", "needs_review"):
        out[c] = out[c].fillna(False).astype(bool)

    def _mn(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        sm = str(v).strip()
        return sm if sm else None

    out["mapping_notes"] = out["mapping_notes"].map(_mn)
    return out


def upsert_transactions(df: pd.DataFrame) -> int:
    """정제된 DataFrame을 land_transactions 에 UPSERT 한다 (psycopg2 배치)."""
    before = len(df)
    df = df[df["total_price_10k"].notna()].copy()
    skipped = before - len(df)
    if skipped:
        log.info("total_price_10k 가 NULL/NaN 인 거래 UPSERT 제외: %d건", skipped)
    if df.empty:
        log.info("UPSERT 대상 없음")
        return 0

    cols = [
        "transaction_hash", "contract_year", "contract_month", "contract_date",
        "beopjungri_code", "sido_code", "sigungu_code",
        "land_category", "zone_type", "road_condition",
        "area_sqm", "area_category",
        "total_price_10k", "unit_price_per_sqm",
        "lot_display", "partial_ownership_label", "deal_type",
        "is_partial_ownership", "is_cancelled", "is_valid", "raw_id",
        "needs_review", "mapping_notes",
    ]
    prep = _prepare_land_tx_upsert(df, cols)
    prep = prep.astype(object).where(pd.notna(prep), None)

    engine = get_engine()
    url = engine.url
    insert_sql = """
        INSERT INTO land_transactions (
            transaction_hash, contract_year, contract_month, contract_date,
            beopjungri_code, sido_code, sigungu_code,
            land_category, zone_type, road_condition,
            area_sqm, area_category,
            total_price_10k, unit_price_per_sqm,
            lot_display, partial_ownership_label, deal_type,
            is_partial_ownership, is_cancelled, is_valid, raw_id,
            needs_review, mapping_notes
        ) VALUES %s
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
            lot_display = EXCLUDED.lot_display,
            partial_ownership_label = EXCLUDED.partial_ownership_label,
            deal_type = EXCLUDED.deal_type,
            is_partial_ownership = EXCLUDED.is_partial_ownership,
            is_cancelled = EXCLUDED.is_cancelled,
            is_valid = EXCLUDED.is_valid,
            raw_id = EXCLUDED.raw_id,
            needs_review = EXCLUDED.needs_review,
            mapping_notes = EXCLUDED.mapping_notes,
            updated_at = NOW()
    """

    inserted = 0
    page = _CLEAN_UPSERT_PAGE
    n = len(prep)
    conn = psycopg2.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=url.database,
    )
    try:
        with conn, conn.cursor() as cur:
            for start in tqdm(range(0, n, page), desc="UPSERT", total=(n + page - 1) // page):
                chunk = prep.iloc[start : start + page]
                tuples = list(chunk.itertuples(index=False, name=None))
                execute_values(cur, insert_sql, tuples, page_size=len(tuples))
                inserted += len(tuples)
    finally:
        conn.close()

    log.info("UPSERT 완료: %d건 (배치 크기 %d)", inserted, page)
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

    if args.reprocess_all:
        log.warning(
            "reprocess-all: transaction_hash 가 법정동 코드 등을 포함하므로 "
            "기존 행과 충돌하지 않고 중복이 쌓일 수 있습니다. "
            "land_transactions 를 비운 뒤 재적재합니다."
        )
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM land_transactions"))

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
        _bc = cleaned["beopjungri_code"].fillna("").astype(str).str.strip()
        needs_mapping = _bc.eq("")
        if needs_mapping.any():
            log.info("beopjungri_code 매핑 시작: %d건", needs_mapping.sum())
            lookup = build_region_lookup(engine)
            meta = map_beopjungri_codes(cleaned[needs_mapping], lookup)
            cleaned.loc[needs_mapping, "beopjungri_code"] = meta["beopjungri_code"].values
            cleaned.loc[needs_mapping, "needs_review"] = meta["needs_review"].values
            cleaned.loc[needs_mapping, "mapping_notes"] = meta["mapping_notes"].values

            # 법정동 코드가 바뀌면 transaction_hash 도 갱신 (중복·추적 일관성)
            cleaned.loc[needs_mapping, "transaction_hash"] = cleaned.loc[needs_mapping].apply(
                _make_hash, axis=1
            )

            # 매핑 후 sido_code도 보완 (beopjungri_code 앞 2자리)
            still_no_sido = cleaned["sido_code"].eq("") | cleaned["sido_code"].isna()
            cleaned.loc[still_no_sido, "sido_code"] = (
                cleaned.loc[still_no_sido, "beopjungri_code"].astype(str).str[:2]
            )
            # sigungu_code 보완 (beopjungri_code 앞 5자리)
            if "sigungu_code" not in cleaned.columns:
                cleaned["sigungu_code"] = ""
            no_sigungu = cleaned["sigungu_code"].eq("") | cleaned["sigungu_code"].isna()
            cleaned.loc[no_sigungu, "sigungu_code"] = (
                cleaned.loc[no_sigungu, "beopjungri_code"].astype(str).str[:5]
            )

            still_missing = cleaned["beopjungri_code"].fillna("").astype(str).str.strip().eq("").sum()
            n_review = int(cleaned["needs_review"].sum())
            log.info(
                "beopjungri_code 매핑 완료. 미매핑: %d건, needs_review: %d건",
                still_missing,
                n_review,
            )
        else:
            log.info("beopjungri_code 이미 존재, 매핑 생략")

        bc_empty = cleaned["beopjungri_code"].fillna("").astype(str).str.strip().eq("")
        cleaned.loc[bc_empty, "needs_review"] = True
        cleaned.loc[bc_empty, "is_valid"] = False
        idx_no_note = bc_empty & cleaned["mapping_notes"].fillna("").astype(str).str.strip().eq("")
        cleaned.loc[idx_no_note, "mapping_notes"] = "no_beopjungri_code"
    else:
        log.warning("--skip-region-map: beopjungri_code 매핑 건너뜀")

    valid = cleaned[cleaned["is_valid"] == True]
    log.info("유효 데이터: %d건 / 전체 %d건", len(valid), len(cleaned))

    upsert_transactions(cleaned)


if __name__ == "__main__":
    main()
