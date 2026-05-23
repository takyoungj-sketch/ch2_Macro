#!/usr/bin/env python3
"""
참고/7.토지 통합 정제.ipynb — 「정제」 단계 스크립트화.

통합 출력(`*_토지_매매_통합.xlsx`, 헤더 없음)을 읽어 노트북과 동일한 열 순서·매핑·필터로
`토지_매매_정제/*.xlsx` 를 만든다. (pandas to_excel, 인덱스 없음과 동일하게 index=False 유지.)
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

# 참고 노트북 원본 매핑
ZONE_ABBREV = {
    "제1종전용주거지역": "1전",
    "제2종전용주거지역": "2전",
    "제1종일반주거지역": "1주",
    "제2종일반주거지역": "2주",
    "제3종일반주거지역": "3주",
    "준주거지역": "준주",
    "근린상업지역": "근상",
    "유통상업지역": "유상",
    "일반상업지역": "일상",
    "중심상업지역": "중상",
    "전용공업지역": "전공",
    "일반공업지역": "일공",
    "준공업지역": "준공",
    "자연녹지지역": "자녹",
    "생산녹지지역": "생녹",
    "보전녹지지역": "보녹",
    "계획관리지역": "계관",
    "보전관리지역": "보관",
    "생산관리지역": "생관",
    "개발제한구역": "개제",
    "농림지역": "농림",
    "자연환경보전지역": "자보",
}

JIROK_ABBREV = {
    "과수원": "과",
    "창고용지": "창",
    "임야": "임",
    "공장용지": "장",
    "도로": "도",
    "잡종지": "잡",
    "구거": "구",
    "유지": "유",
    "학교용지": "학",
    "묘지": "묘",
    "철도용지": "철",
    "목장용지": "목",
    "제방": "제",
    "공원": "공",
    "양어장": "양",
    "하천": "천",
    "주차장": "차",
    "종교용지": "종",
    "수도용지": "수",
    "유원지": "원",
    "체육용지": "체",
    "주유소용지": "주",
}

ROAD_ABBREV = {
    "8m미만": "8미",
    "12m미만": "12미",
    "25m미만": "25미",
    "25m이상": "25이",
}


def refine_merged_land_df(df: pd.DataFrame) -> pd.DataFrame:
    """통합 무헤더 DataFrame 에 컬럼명을 부여한 뒤 노트북과 동일한 정제 적용."""

    COLS = [
        "순번",
        "시군구",
        "번지",
        "지목",
        "용도지역",
        "도로조건",
        "계약연월",
        "계약일",
        "계약면적",
        "거래금액(만원)",
        "지분구분",
        "해제사유발생일",
        "거래유형",
        "중개사소재지",
    ]
    n_take = min(len(COLS), df.shape[1])
    df = df.iloc[:, :n_take].copy()
    df.columns = COLS[:n_take]

    # 부족한 열 추가 (예외 처리)
    for c in COLS:
        if c not in df.columns:
            df[c] = ""

    df["거래금액(만원)"] = (
        df["거래금액(만원)"].astype(str).str.replace(",", "", regex=False).replace("nan", "")
    )
    df["거래금액(만원)"] = pd.to_numeric(df["거래금액(만원)"], errors="coerce")
    df["계약면적"] = pd.to_numeric(df["계약면적"], errors="coerce")

    # 해제 거래 제거 (노트북과 동일: '-' 문자열)
    rel = df["해제사유발생일"].astype(str).str.strip()
    rel = rel.replace({"nan": "-", "<NA>": "-", "None": "-"})
    df["해제사유발생일"] = rel.where(rel != "", "-")
    df = df[df["해제사유발생일"] == "-"].copy()

    df = df.drop(columns=["중개사소재지"])

    split_cols = df["시군구"].astype(str).str.split(" ", n=4, expand=True).reindex(columns=range(5))
    split_cols.columns = ["주소1", "주소2", "주소3", "주소4", "주소5"]
    df = pd.concat([df, split_cols], axis=1)

    cy = df["계약연월"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df["연도"] = cy.str[:4]
    df["월"] = cy.str[4:]
    df["월"] = df["월"].str.zfill(2)

    df["면적구분"] = "정상"
    df.loc[df["계약면적"] < 30, "면적구분"] = "광소"
    df.loc[df["계약면적"] >= 3000, "면적구분"] = "광대"

    df["단가"] = (df["거래금액(만원)"] / df["계약면적"]).round(1)

    df = df.drop(columns=["계약연월", "해제사유발생일", "계약일"])

    df = df[
        [
            "순번",
            "시군구",
            "주소1",
            "주소2",
            "주소3",
            "주소4",
            "주소5",
            "번지",
            "지목",
            "용도지역",
            "도로조건",
            "연도",
            "월",
            "면적구분",
            "계약면적",
            "거래금액(만원)",
            "단가",
            "지분구분",
            "거래유형",
        ]
    ]

    df["용도지역"] = df["용도지역"].map(ZONE_ABBREV).fillna("기타")
    df["지목"] = df["지목"].map(JIROK_ABBREV).fillna(df["지목"])

    df["도로조건"] = df["도로조건"].map(ROAD_ABBREV).fillna("-")

    return df


def main() -> None:
    ap = argparse.ArgumentParser(description="토지 매매 통합 → 정제 (노트북 호환)")
    ap.add_argument("--cycle-id", default="202605", metavar="YYYYMM")
    ap.add_argument(
        "--merged-dir",
        default="",
        help="통합 xlsx 디렉터리 (미지정: raw/토지/<cycle>/토지_매매_통합)",
    )
    ap.add_argument(
        "--output-dir",
        default="",
        help="정제 출력 (미지정: raw/토지/<cycle>/토지_매매_정제)",
    )
    args = ap.parse_args()

    if args.merged_dir.strip():
        indir = Path(args.merged_dir.strip()).expanduser().resolve()
    else:
        indir = REPO_ROOT / "raw" / "토지" / args.cycle_id / "토지_매매_통합"
    if args.output_dir.strip():
        outdir = Path(args.output_dir.strip()).expanduser().resolve()
    else:
        outdir = REPO_ROOT / "raw" / "토지" / args.cycle_id / "토지_매매_정제"

    if not indir.is_dir():
        print(f"통합 디렉터리가 없습니다: {indir}", file=sys.stderr)
        sys.exit(1)

    outdir.mkdir(parents=True, exist_ok=True)
    excel_files = [
        f
        for f in glob.glob(str(indir / "*.xlsx"))
        if not os.path.basename(f).startswith("~$")
    ]

    for file_path in sorted(excel_files):
        basename = os.path.basename(file_path)
        print(f"처리중: {basename}")

        df = pd.read_excel(file_path, engine="openpyxl", header=None)
        # 숫자 열 타입 재구성 위해 refine 에서 coercion
        df = refine_merged_land_df(df)

        new_name = basename.replace("통합", "정제")
        save_path = outdir / new_name
        df.to_excel(save_path, index=False, engine="openpyxl")
        print(f"완료: {new_name}")

    print("전체 정제 완료")


if __name__ == "__main__":
    main()
