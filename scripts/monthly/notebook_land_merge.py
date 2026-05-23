#!/usr/bin/env python3
"""
참고/7.토지 통합 정제.ipynb — 「통합」 단계 스크립트화.

평면 디렉터리(`토지_매매/*.xlsx`)의 국토부 원본 xlsx 이름에서 시도를 추출해
`_토지_매매_<range>.xlsx` 는 같은 시도끼리 concat 하고,

`토지_매매_통합/` 에 `{시도}_토지_매매_통합.xlsx` (헤더·인덱스 없음, 노트북과 동일) 로 저장한다.
노트북은 열을 `:17` 로 잘라 쓰이므로 동일 처리 (실제 원장은 통상 앞쪽 14열이 본 컬럼).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_COL_LIMIT = 17


def sido_from_download_stem(stem: str) -> str | None:
    """예: 서울특별시_토지_매매_20250501_20260430 → 서울특별시"""
    m = re.match(r"^(.+?)_토지_매매", stem.strip())
    if not m:
        return None
    return m.group(1)


def main() -> None:
    ap = argparse.ArgumentParser(description="시도별 토지 매매 원본 통합 (노트북 호환)")
    ap.add_argument(
        "--cycle-id",
        default="202605",
        metavar="YYYYMM",
        help="기본 원본 디렉터리: <repo>/raw/토지/<cycle>/토지_매매",
    )
    ap.add_argument(
        "--source",
        default="",
        help="토지 매매 원본 xlsx 디렉터리 (미지정 시 cycle 기준 기본값)",
    )
    ap.add_argument(
        "--merge-out",
        default="",
        help="통합 결과 폴더 (미지정 시 <repo>/raw/토지/<cycle>/토지_매매_통합)",
    )
    args = ap.parse_args()

    if args.source.strip():
        src = Path(args.source.strip()).expanduser().resolve()
    else:
        src = REPO_ROOT / "raw" / "토지" / args.cycle_id / "토지_매매"
    if args.merge_out.strip():
        merge_dir = Path(args.merge_out.strip()).expanduser().resolve()
    else:
        merge_dir = REPO_ROOT / "raw" / "토지" / args.cycle_id / "토지_매매_통합"

    if not src.is_dir():
        print(f"소스 디렉터리가 없습니다: {src}", file=sys.stderr)
        sys.exit(1)

    merge_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[Path]] = {}
    for p in sorted(src.glob("*.xlsx")):
        name = p.name
        if name.startswith("~$"):
            continue
        if name.endswith("_토지_매매_통합.xlsx") or "_토지_매매_정제" in name:
            continue  # 결과물 재처리 방지
        sido = sido_from_download_stem(p.stem)
        if not sido:
            print(f"[skip] 이름 규칙 없음: {p.name}")
            continue
        grouped.setdefault(sido, []).append(p)

    if not grouped:
        print("그룹할 xlsx 없음.")
        sys.exit(1)

    print(f"통합 출력: {merge_dir}")
    for sido, paths in sorted(grouped.items(), key=lambda kv: kv[0]):
        merged_df = pd.DataFrame()
        for fp in sorted(paths, key=lambda x: x.name.lower()):
            try:
                df = pd.read_excel(fp, skiprows=13, header=None, engine="openpyxl")
                ncol = min(RAW_COL_LIMIT, df.shape[1])
                df = df.iloc[:, :ncol]
                merged_df = pd.concat([merged_df, df], ignore_index=True)
                print(f"  + [{sido}] {fp.name}: {len(df)}행")
            except Exception as e:
                print(f"  ! [{sido}] {fp.name} 오류: {e}", file=sys.stderr)
        outp = merge_dir / f"{sido}_토지_매매_통합.xlsx"
        merged_df.to_excel(outp, index=False, header=False, engine="openpyxl")
        print(f"=> {outp.name} ({len(merged_df)}행)")

    print("통합 완료")


if __name__ == "__main__":
    main()
