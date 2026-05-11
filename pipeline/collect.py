"""
수집 파이프라인
국토부 토지 실거래가 공공데이터 API 또는 로컬 Excel 파일을 읽어
land_transactions_raw 테이블에 적재한다.

사용법:
    python collect.py --mode api --years 5            # API로 최근 5년 수집
    python collect.py --mode api --months 3           # API로 최근 3개월 (정기 갱신)
    python collect.py --mode excel --file raw.xlsx    # 국토부 원본 xlsx (13행 헤더 자동 처리)
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

    # 컬럼명 → 내부 키 매핑
    df = df.rename(columns={k: v for k, v in EXCEL_COLUMN_MAP.items() if k in df.columns})

    # 계약연월(YYYYMM) → contract_year / contract_month 분리
    if "deal_ymd" in df.columns and "contract_year" not in df.columns:
        deal_ymd = df["deal_ymd"].astype(str).str.strip()
        df["contract_year"] = deal_ymd.str[:4]
        df["contract_month"] = deal_ymd.str[4:6]

    # 빈 행 제거 (순번이 없거나 NaN인 행)
    if "순번" in df.columns:
        df = df[df["순번"].notna() & (df["순번"].astype(str).str.strip() != "")]
    elif "area_sqm" in df.columns:
        df = df[df["area_sqm"].notna()]

    log.info("Excel 로드 완료: %d행", len(df))
    return df


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


def load_to_raw_table(df: pd.DataFrame, source_year: int, source_month: int) -> int:
    """
    DataFrame을 land_transactions_raw 테이블에 UPSERT 방식으로 적재한다.
    반환: 신규 적재된 행 수
    """
    engine = get_engine()
    inserted = 0

    with engine.begin() as conn:
        for _, row in df.iterrows():
            row_dict = _record_nan_to_none(row.to_dict())
            raw_json = json.dumps(row_dict, ensure_ascii=False, default=str)
            conn.execute(
                text("""
                    INSERT INTO land_transactions_raw (source_year, source_month, raw_data)
                    VALUES (:year, :month, CAST(:data AS jsonb))
                """),
                {"year": source_year, "month": source_month, "data": raw_json},
            )
            inserted += 1

    log.info("raw 테이블 적재 완료: %d건 (연도=%d, 월=%d)", inserted, source_year, source_month)
    return inserted


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
    parser.add_argument("--file", type=str, help="로컬 Excel 파일 경로, 쉼표로 복수 지정 가능 (excel 모드)")
    parser.add_argument(
        "--format",
        choices=["raw", "merged", "auto"],
        default="auto",
        help="Excel 형식: raw=국토부 원본(skiprows=13), merged=통합xlsx(헤더없음), auto=자동감지",
    )
    parser.add_argument("--sigungu", type=str, default="", help="쉼표 구분 시군구 코드 (미지정시 전국)")
    args = parser.parse_args()

    if args.mode == "excel":
        if not args.file:
            parser.error("--file 이 필요합니다")
        # 쉼표로 복수 파일 지정 지원 (예: 충북2021.xlsx,충북2022.xlsx)
        file_list = [f.strip() for f in args.file.split(",") if f.strip()]
        fmt = getattr(args, "format", "auto")
        all_frames = []
        for fpath in file_list:
            df = collect_from_excel(fpath, fmt=fmt)
            all_frames.append(df)
        df = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
        today = date.today()
        load_to_raw_table(df, today.year, today.month)

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
