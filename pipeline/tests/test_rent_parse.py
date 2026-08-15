"""주거 전월세 CSV 파서 — 헤더 매핑·단가 2열·전환율 없음."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(PIPE))

from rent.parse import detect_molit_csv_skiprows, read_rent_csv, refine_rent_dataframe

_FIXTURE = """□ 면책
□ 검색조건
계약일자 : 2024-01-01 ~ 2024-12-31
실거래구분 : 아파트(전월세)
주소구분 : 지번주소
시도 : 서울특별시
시군구 : 전체
읍면동 : 전체
면적 : 전체
금액선택 : 전체
"NO","시군구","번지","본번","부번","단지명","전월세구분","전용면적(㎡)","계약년월","계약일","보증금(만원)","월세금(만원)","층","건축년도","도로명","계약기간","계약구분","갱신요구권 사용","종전계약 보증금(만원)","종전계약 월세(만원)","주택유형"
"1","서울특별시 강남구 압구정동","433","0433","0000","신현대11차","전세","108.36","202412","31","58,500","0","3","1983","압구정로 151","-","-","-","","","아파트"
"2","서울특별시 강남구 청담동","65","0065","0000","진흥아파트","월세","109.31","202412","31","5,000","230","5","1984","학동로 513","202501~202701","신규","-","","","아파트"
"""

_DETACHED = """□ 면책
□ 검색조건
계약일자 : 2021-01-01 ~ 2021-12-31
실거래구분 : 단독다가구(전월세)
주소구분 : 지번주소
시도 : 서울특별시
시군구 : 전체
읍면동 : 전체
면적 : 전체
금액선택 : 전체
"NO","시군구","번지","도로조건","계약면적(㎡)","전월세구분","계약년월","계약일","보증금(만원)","월세금(만원)","건축년도","도로명","계약기간","계약구분","갱신요구권 사용","종전계약 보증금(만원)","종전계약 월세(만원)","주택유형"
"1","서울특별시 강남구 논현동","1**","8m미만","26.88","월세","202112","31","500","65","2009","학동로18길","202201~202212","신규","-","","","단독다가구"
"""


def test_skiprows_and_jeonse_unit_price(tmp_path: Path):
    path = tmp_path / "서울특별시_아파트_전월세_2024.csv"
    path.write_text(_FIXTURE, encoding="utf-8")
    assert detect_molit_csv_skiprows(path) == 10
    raw = read_rent_csv(path)
    df = refine_rent_dataframe(raw, "apartment", source_path="x")
    assert len(df) == 2
    jeonse = df.iloc[0]
    assert jeonse["molit_lease_kind"] == "전세"
    assert jeonse["deposit_manwon"] == 58500
    assert jeonse["monthly_rent_manwon"] == 0
    assert abs(jeonse["deposit_per_m2"] - 58500 / 108.36) < 1e-6
    assert jeonse["monthly_per_m2"] == 0
    wolse = df.iloc[1]
    assert wolse["molit_lease_kind"] == "월세"
    assert abs(wolse["monthly_per_m2"] - 230 / 109.31) < 1e-6
    assert "jeonse_eq" not in df.columns
    assert df["transaction_hash"].nunique() == 2


def test_detached_uses_contract_area(tmp_path: Path):
    path = tmp_path / "서울특별시_단독다가구_전월세_2021.csv"
    path.write_text(_DETACHED, encoding="utf-8")
    raw = read_rent_csv(path)
    df = refine_rent_dataframe(raw, "detached", source_path="x")
    row = df.iloc[0]
    assert pd.isna(row["exclusive_area"])
    assert row["contract_area"] == 26.88
    assert abs(row["monthly_per_m2"] - 65 / 26.88) < 1e-6
    assert pd.isna(row["floor"])
