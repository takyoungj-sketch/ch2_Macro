# -*- coding: utf-8 -*-
"""Audit all historical CSV: filename region vs metadata '시도 :' inside file."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "raw" / "토지_2010_2020"

# filename prefix -> acceptable metadata sido strings
REGION_ALIASES: dict[str, tuple[str, ...]] = {
    "서울특별시": ("서울특별시", "서울"),
    "부산광역시": ("부산광역시", "부산"),
    "대구광역시": ("대구광역시", "대구"),
    "인천광역시": ("인천광역시", "인천"),
    "광주광역시": ("광주광역시", "광주"),
    "대전광역시": ("대전광역시", "대전"),
    "울산광역시": ("울산광역시", "울산"),
    "세종특별자치시": ("세종특별자치시", "세종"),
    "경기도": ("경기도", "경기"),
    "강원특별자치도": ("강원특별자치도", "강원도", "강원"),
    "충청북도": ("충청북도", "충북"),
    "충청남도": ("충청남도", "충남"),
    "전북특별자치도": ("전북특별자치도", "전라북도", "전북"),
    "전라남도": ("전라남도", "전남"),
    "경상북도": ("경상북도", "경북"),
    "경상남도": ("경상남도", "경남"),
    "제주특별자치도": ("제주특별자치도", "제주"),
}


def decode_csv_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("cp949", "utf-8-sig", "utf-8", "euc-kr"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp949", errors="replace")


def parse_expected_region(filename: str) -> str | None:
    m = re.match(r"^(.+?)_토지_매매_\d{4}\.csv$", filename)
    return m.group(1) if m else None


def parse_metadata_sido(text: str) -> str | None:
    for ln in text.splitlines():
        if "시도 :" in ln:
            # "시도 : 전북특별자치도" or quoted CSV cell
            m = re.search(r"시도\s*:\s*([^\"]+)", ln)
            if m:
                return m.group(1).strip().strip('"')
    return None


def matches(expected: str, actual: str | None) -> bool:
    if not actual:
        return False
    aliases = REGION_ALIASES.get(expected, (expected,))
    return any(a in actual or actual.startswith(a) for a in aliases)


def main() -> None:
    files = sorted(RAW.glob("*_토지_매매_*.csv"))
    bad: list[tuple[str, str, str | None]] = []
    missing_meta: list[str] = []
    by_region: dict[str, list[str]] = defaultdict(list)

    for p in files:
        expected = parse_expected_region(p.name)
        if not expected:
            continue
        text = decode_csv_text(p)
        actual = parse_metadata_sido(text)
        if not actual:
            missing_meta.append(p.name)
            continue
        if not matches(expected, actual):
            bad.append((p.name, expected, actual))
            by_region[expected].append(f"{p.name} → 실제={actual}")

    print(f"총 CSV: {len(files)}")
    print(f"메타 없음: {len(missing_meta)}")
    print(f"불일치: {len(bad)}")
    print()

    if bad:
        print("=== 파일명 vs 내용 불일치 ===")
        for name, exp, act in bad:
            print(f"  {name}")
            print(f"    기대={exp}  실제={act}")
        print()
        print("=== 시도별 불일치 건수 ===")
        for region in sorted(by_region, key=lambda r: -len(by_region[r])):
            print(f"  {region}: {len(by_region[region])}건")
            for line in by_region[region][:3]:
                print(f"    - {line}")
            if len(by_region[region]) > 3:
                print(f"    ... 외 {len(by_region[region]) - 3}건")
    else:
        print("모든 CSV 파일명·내용 일치")


if __name__ == "__main__":
    main()
