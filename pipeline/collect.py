"""
수집 파이프라인
국토부 토지 실거래가 공공데이터 API 또는 로컬 Excel 파일을 읽어
land_transactions_raw 테이블에 적재한다.

사용법:
    python collect.py --mode api --years 5            # API로 최근 5년 수집
    python collect.py --mode api --months 3           # API로 최근 3개월 (정기 갱신)
    python collect.py --mode excel --file raw.xlsx    # 국토부 원본 xlsx (13행 헤더 자동 처리)
    python collect.py --mode excel --directory C:/원본/토지  # 폴더 내 .xlsx 전부(전국 base 등)
    python collect.py --mode excel --file merged.xlsx --format merged
                                                      # 통합 xlsx (헤더 없음, 14컬럼)

국토부 토지 실거래 Excel 컬럼 (skiprows=13 이후):
    순번, 시군구, 번지, 지목, 용도지역, 도로조건,
    계약연월, 계약일, 계약면적, 거래금액(만원),
    지분구분, 해제사유발생일, 거래유형, 중개사소재지
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import text
from tqdm import tqdm

from db_utils import get_engine

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# 국토부 공공데이터포털 API 엔드포인트
API_BASE = "https://apis.data.go.kr/1611000/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade"

# 국토부 토지 실거래 Excel 고정 컬럼 순서 (skiprows=13 이후 header=None)
LAND_EXCEL_COLUMNS = [
    "순번", "시군구", "번지", "지목", "용도지역", "도로조건",
    "계약연월", "계약일", "계약면적", "거래금액(만원)",
    "지분구분", "해제사유발생일", "거래유형", "중개사소재지",
]

# 국토부 엑셀 컬럼명 → 내부 컬럼명 매핑 (raw JSONB 저장 키)
EXCEL_COLUMN_MAP = {
    # 국토부 토지 Excel (계약연월 통합 형식)
    "시군구": "sigungu_name",
    "번지": "lot_number",
    "지목": "land_category",
    "용도지역": "zone_type",
    "도로조건": "road_condition",
    "계약연월": "deal_ymd",          # YYYYMM → clean.py에서 year/month 분리
    "계약년월": "deal_ymd",          # Molit CSV 헤더 (연월 표기 차이)
    "계약일": "contract_day",
    "계약면적": "area_sqm",
    "거래금액(만원)": "total_price_10k",
    "지분구분": "partial_ownership_raw",   # 비어있으면 일반, '지분'이면 지분거래
    "해제사유발생일": "cancel_date",
    "거래유형": "trade_type",
    "중개사소재지": "agency_location",
    # API / 구형 엑셀 호환 (있으면 매핑)
    "본번": "main_number",
    "부번": "sub_number",
    "면적(㎡)": "area_sqm",
    "계약년도": "contract_year",
    "계약월": "contract_month",
    "해제여부": "is_cancelled_raw",
}


def collect_from_api(
    service_key: str,
    sigungu_codes: list[str],
    year_months: list[tuple[int, int]],
) -> pd.DataFrame:
    """
    국토부 API에서 시군구 코드 × 연월 조합으로 데이터를 수집한다.
    반환: 원본 컬럼 그대로의 DataFrame
    """
    all_rows = []
    for sigungu_code in tqdm(sigungu_codes, desc="시군구"):
        for year, month in tqdm(year_months, desc="연월", leave=False):
            deal_ymd = f"{year}{month:02d}"
            params = {
                "serviceKey": service_key,
                "LAWD_CD": sigungu_code,
                "DEAL_YMD": deal_ymd,
                "numOfRows": 1000,
                "pageNo": 1,
            }
            try:
                resp = requests.get(API_BASE, params=params, timeout=30)
                resp.raise_for_status()
                # XML → dict 파싱 (실제 구현 시 xml.etree.ElementTree 사용)
                rows = _parse_api_response(resp.text)
                all_rows.extend(rows)
                log.debug("수집 %s %s: %d건", sigungu_code, deal_ymd, len(rows))
            except Exception as exc:
                log.warning("API 오류 %s %s: %s", sigungu_code, deal_ymd, exc)
    return pd.DataFrame(all_rows)


def _parse_api_response(xml_text: str) -> list[dict]:
    """
    국토부 API XML 응답을 파싱해 행 목록으로 반환한다.
    실제 필드명은 API 문서 기준으로 작성.
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_text)
        items = root.findall(".//item")
        rows = []
        for item in items:
            row = {child.tag: child.text for child in item}
            rows.append(row)
        return rows
    except ET.ParseError as e:
        log.error("XML 파싱 실패: %s", e)
        return []


def collect_from_excel(file_path: str, fmt: str = "raw") -> pd.DataFrame:
    """
    로컬 Excel(xlsx) 파일을 읽어 내부 컬럼명으로 매핑된 DataFrame을 반환한다.

    fmt:
        "raw"    - 국토부 원본 xlsx (13행 헤더 → skiprows=13, header=None, 14컬럼)
        "merged" - 통합 xlsx (7.토지 통합 정제.ipynb Cell0 산출물, header 없음, 14컬럼)
        "auto"   - 확장자/구조를 보고 raw/merged 자동 판단 (첫 셀이 숫자면 merged)
    """
    log.info("Excel 파일 읽기: %s (fmt=%s)", file_path, fmt)

    if fmt == "raw":
        df = pd.read_excel(file_path, skiprows=13, header=None, dtype=str)
        df = df.iloc[:, : len(LAND_EXCEL_COLUMNS)]
        df.columns = LAND_EXCEL_COLUMNS[: len(df.columns)]

    elif fmt == "merged":
        df = pd.read_excel(file_path, header=None, dtype=str)
        df = df.iloc[:, : len(LAND_EXCEL_COLUMNS)]
        df.columns = LAND_EXCEL_COLUMNS[: len(df.columns)]

    else:  # auto
        # 첫 셀을 읽어 숫자면 'merged', 아니면 'raw' (헤더 행 존재)
        probe = pd.read_excel(file_path, nrows=1, header=None, dtype=str)
        first_cell = str(probe.iloc[0, 0]).strip()
        if first_cell.isdigit():
            log.info("auto 감지: merged 형식")
            return collect_from_excel(file_path, fmt="merged")
        else:
            log.info("auto 감지: raw 형식")
            return collect_from_excel(file_path, fmt="raw")

    df = _normalize_land_dataframe(df)
    log.info("Excel 로드 완료: %d행", len(df))
    return df


def _detect_molit_csv_skiprows(file_path: str) -> int:
    """Molit CSV: 면책·검색조건 행 뒤 'NO'/'순번' 헤더 행까지 skiprows."""
    path = Path(file_path)
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            with path.open(encoding=enc, errors="strict") as fh:
                for i, line in enumerate(fh):
                    stripped = line.strip().lstrip("\ufeff")
                    if stripped.startswith('"NO"') or stripped.startswith("NO,"):
                        return i
                    if '"시군구"' in stripped or stripped.startswith("시군구,"):
                        return max(i - 1, 0) if stripped.startswith("시군구") else i
                    if '"순번"' in stripped or stripped.startswith("순번,"):
                        return i
            break
        except UnicodeDecodeError:
            continue
    return 15


def _normalize_land_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Excel/CSV 공통: 컬럼 매핑·계약연월 분리·빈 행 제거."""
    rename_map = {k: v for k, v in EXCEL_COLUMN_MAP.items() if k in df.columns}
    if "NO" in df.columns and "순번" not in df.columns:
        rename_map["NO"] = "seq_no"
    df = df.rename(columns=rename_map)

    if "deal_ymd" in df.columns and "contract_year" not in df.columns:
        deal_ymd = df["deal_ymd"].astype(str).str.strip()
        df["contract_year"] = deal_ymd.str[:4]
        df["contract_month"] = deal_ymd.str[4:6]

    seq_col = None
    if "순번" in df.columns:
        seq_col = "순번"
    elif "seq_no" in df.columns:
        seq_col = "seq_no"
    if seq_col:
        df = df[df[seq_col].notna() & (df[seq_col].astype(str).str.strip() != "")]
    elif "area_sqm" in df.columns:
        df = df[df["area_sqm"].notna()]

    return df


def collect_from_csv(file_path: str) -> pd.DataFrame:
    """
    Molit 토지 CSV (면책·검색조건 + 헤더 + 데이터)를 읽는다.
    """
    log.info("CSV 파일 읽기: %s", file_path)
    skip = _detect_molit_csv_skiprows(file_path)
    df = None
    read_kw = {"skiprows": skip, "header": 0, "dtype": str, "on_bad_lines": "skip"}
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            df = pd.read_csv(file_path, encoding=enc, **read_kw)
            log.debug("CSV encoding=%s", enc)
            break
        except UnicodeDecodeError:
            continue
        except TypeError:
            # pandas < 1.3
            read_kw.pop("on_bad_lines", None)
            read_kw["error_bad_lines"] = False
            df = pd.read_csv(file_path, encoding=enc, **read_kw)
            log.debug("CSV encoding=%s (legacy bad lines)", enc)
            break
    if df is None:
        raise UnicodeDecodeError("csv", b"", 0, 1, "지원 인코딩으로 CSV를 읽지 못했습니다")
    df = _normalize_land_dataframe(df)
    log.info("CSV 로드 완료: %d행", len(df))
    return df


def collect_from_file(file_path: str, fmt: str = "auto") -> pd.DataFrame:
    """확장자·fmt 에 따라 Excel 또는 CSV 로드."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if fmt == "csv" or (fmt == "auto" and suffix == ".csv"):
        return collect_from_csv(str(path))
    if fmt in ("raw", "merged", "auto"):
        return collect_from_excel(str(path), fmt=fmt if fmt != "auto" else "auto")
    raise ValueError(f"지원하지 않는 format: {fmt}")


def _record_nan_to_none(rec: dict) -> dict:
    """PostgreSQL JSONB 적재 전 스칼라 NaN/NA를 JSON null(None)로 바꾼다."""
    clean: dict = {}
    for key, val in rec.items():
        try:
            if pd.api.types.is_scalar(val) and pd.isna(val):
                clean[key] = None
            else:
                clean[key] = val
        except (ValueError, TypeError):
            clean[key] = val
    return clean


_RAW_INSERT = text("""
    INSERT INTO land_transactions_raw (source_year, source_month, raw_data)
    VALUES (:year, :month, CAST(:data AS jsonb))
""")


def load_to_raw_table(
    df: pd.DataFrame,
    source_year: int,
    source_month: int,
    *,
    batch_size: int = 500,
) -> int:
    """
    DataFrame을 land_transactions_raw 테이블에 적재한다.
    SQLAlchemy executemany 형태의 배치 INSERT로 왕복 비용을 줄인다.
    반환: 신규 적재된 행 수
    """
    if df.empty:
        return 0

    engine = get_engine()
    params_list: list[dict] = []

    for _, row in df.iterrows():
        row_dict = _record_nan_to_none(row.to_dict())
        raw_json = json.dumps(row_dict, ensure_ascii=False, default=str)
        params_list.append(
            {"year": source_year, "month": source_month, "data": raw_json}
        )

    inserted = 0
    with engine.begin() as conn:
        for start in range(0, len(params_list), batch_size):
            chunk = params_list[start : start + batch_size]
            conn.execute(_RAW_INSERT, chunk)
            inserted += len(chunk)

    log.info("raw 테이블 적재 완료: %d건 (연도=%d, 월=%d)", inserted, source_year, source_month)
    return inserted


def resolve_excel_paths(*, file_arg: str | None, directory_arg: str | None) -> list[Path]:
    """--file 과 --directory 배타. .xlsx · .csv 지원."""
    if file_arg:
        out: list[Path] = []
        for part in file_arg.split(","):
            p = Path(part.strip()).expanduser().resolve()
            if not p.is_file():
                raise FileNotFoundError(f"파일이 없습니다: {p}")
            out.append(p)
        return out

    if directory_arg:
        root = Path(directory_arg).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"폴더가 없습니다: {root}")
        by_lower: dict[str, Path] = {}
        for child in root.iterdir():
            if not child.is_file():
                continue
            if child.suffix.lower() not in (".xlsx", ".csv"):
                continue
            by_lower.setdefault(child.name.lower(), child)
        return sorted(by_lower.values(), key=lambda p: p.name.lower())

    raise ValueError("내부 오류: excel 경로 미지정")


def get_year_months_for_last_n_months(n: int) -> list[tuple[int, int]]:
    """최근 n개월의 (year, month) 목록을 반환한다."""
    today = date.today()
    result = []
    for i in range(n):
        d = today.replace(day=1) - timedelta(days=1)
        for _ in range(i):
            d = d.replace(day=1) - timedelta(days=1)
        result.append((d.year, d.month))
    return list(set(result))


def get_year_months_for_last_n_years(n: int) -> list[tuple[int, int]]:
    """최근 n년의 모든 (year, month) 목록을 반환한다."""
    today = date.today()
    result = []
    for year in range(today.year - n + 1, today.year + 1):
        for month in range(1, 13):
            if year == today.year and month > today.month:
                break
            result.append((year, month))
    return result


def main():
    parser = argparse.ArgumentParser(description="국토부 토지 실거래 데이터 수집")
    parser.add_argument("--mode", choices=["api", "excel"], default="api")
    parser.add_argument("--years", type=int, default=5, help="최근 N년 수집 (api 모드)")
    parser.add_argument("--months", type=int, default=0, help="최근 N개월 수집 (정기 갱신용)")
    parser.add_argument(
        "--file",
        type=str,
        help="로컬 Excel 경로, 쉼표 구분 복수 (excel 모드, --directory 와 배타)",
    )
    parser.add_argument(
        "--directory",
        type=str,
        metavar="DIR",
        help="폴더 안의 .xlsx 전부 (excel 모드, --file 과 배타)",
    )
    parser.add_argument(
        "--format",
        choices=["raw", "merged", "auto", "csv"],
        default="auto",
        help="Excel 형식: raw=국토부 원본(skiprows=13), merged=통합xlsx, csv=Molit CSV, auto=확장자·구조 감지",
    )
    parser.add_argument(
        "--source-year",
        type=int,
        default=0,
        help="raw 적재 source_year (0=오늘 연도). historical CSV는 파일명 연도 지정 권장",
    )
    parser.add_argument(
        "--source-month",
        type=int,
        default=0,
        help="raw 적재 source_month (0=오늘 월)",
    )
    parser.add_argument("--sigungu", type=str, default="", help="쉼표 구분 시군구 코드 (미지정시 전국)")
    args = parser.parse_args()

    if args.mode == "excel":
        if args.file and args.directory:
            parser.error("--file 과 --directory 는 함께 지정할 수 없습니다")
        if not args.file and not args.directory:
            parser.error("excel 모드에는 --file 또는 --directory 가 필요합니다")
        fmt = getattr(args, "format", "auto")
        try:
            paths = resolve_excel_paths(file_arg=args.file, directory_arg=args.directory)
        except (ValueError, FileNotFoundError) as exc:
            parser.error(str(exc))
        if not paths:
            parser.error("적재할 .xlsx/.csv 파일이 없습니다.")

        today = date.today()
        default_sy = args.source_year if args.source_year > 0 else today.year
        default_sm = args.source_month if args.source_month > 0 else today.month
        total_rows = 0
        inserted = 0
        for idx, path in enumerate(paths, start=1):
            log.info("[%d/%d] 파일 처리: %s", idx, len(paths), path)
            fmt = getattr(args, "format", "auto")
            if fmt == "auto" and path.suffix.lower() == ".csv":
                fmt = "csv"
            if fmt == "csv":
                df = collect_from_csv(str(path))
            else:
                df = collect_from_excel(str(path), fmt=fmt)
            sy = default_sy
            sm = default_sm
            ym = re.search(r"_(\d{4})\.(csv|xlsx)$", path.name, re.I)
            if ym:
                sy = int(ym.group(1))
                sm = 6
            total_rows += len(df)
            inserted += load_to_raw_table(df, sy, sm)
        log.info(
            "excel 일괄 적재 종료: 파일 %d개, 데이터 행 %d건 → raw 행 %d건",
            len(paths),
            total_rows,
            inserted,
        )

    elif args.mode == "api":
        service_key = os.environ.get("MOLIT_API_KEY", "")
        if not service_key:
            log.error("환경변수 MOLIT_API_KEY 가 설정되지 않았습니다")
            return

        # 시군구 코드 목록 (전국 = DB에서 조회)
        if args.sigungu:
            sigungu_codes = [c.strip() for c in args.sigungu.split(",")]
        else:
            engine = get_engine()
            with engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT DISTINCT sigungu_code FROM region_codes ORDER BY sigungu_code")
                ).fetchall()
            sigungu_codes = [r[0] for r in rows]

        if args.months > 0:
            year_months = get_year_months_for_last_n_months(args.months)
        else:
            year_months = get_year_months_for_last_n_years(args.years)

        log.info("수집 범위: 시군구 %d개 × 연월 %d개", len(sigungu_codes), len(year_months))
        df = collect_from_api(service_key, sigungu_codes, year_months)

        if not df.empty:
            today = date.today()
            load_to_raw_table(df, today.year, today.month)
        else:
            log.warning("수집된 데이터가 없습니다")


if __name__ == "__main__":
    main()
