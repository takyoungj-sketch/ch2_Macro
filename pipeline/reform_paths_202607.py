"""2026-07 행정개편 raw 경로·파일 탐색 (인천·전남광주 staging)."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "raw"

AFFECTED_SIDO = ("12", "28", "29", "46")
REFORM_SIDO_PREFIXES = ("인천광역시", "전남광주통합특별시")

BUILT_TYPE_DIRS: dict[str, str] = {
    "commercial": "상업업무_201001_202605",
    "factory": "공장창고_201001_202605",
    "detached": "단독다가구_201001_202605",
}

COLLECTIVE_RESIDENTIAL_DIRS: dict[str, str] = {
    "apartment": "아파트_201001_202605",
    "rowhouse": "연립다세대_201001_202605",
    "officetel": "오피스텔_201001_202605",
    "presale": "분양입주권_201001_202605",
}

COLLECTIVE_COMMERCIAL_DIRS: dict[str, str] = {
    "collective_shop": "상업업무_201001_202605",
    "collective_factory": "공장창고_201001_202605",
}


def reform_staging_roots() -> list[Path]:
    """`raw/*(201001_202605)` staging 루트 (인천·전남광주 각 1개)."""
    roots: list[Path] = []
    if not RAW.is_dir():
        return roots
    for child in sorted(RAW.iterdir()):
        if child.is_dir() and "201001_202605" in child.name and child.name != "토지(인천,전남광주)_201001_202605":
            roots.append(child)
    return roots


def year_from_csv_name(name: str) -> int | None:
    m = re.search(r"_(\d{4})(?:\.csv|_\d{8}_\d{8}\.csv)$", name, re.I)
    if m:
        return int(m.group(1))
    m2 = re.search(r"_(\d{4})\d{4}_\d{8}\.csv$", name, re.I)
    return int(m2.group(1)) if m2 else None


def list_reform_csvs(
    type_dir_name: str,
    *,
    sido_prefixes: tuple[str, ...] = REFORM_SIDO_PREFIXES,
    year_from: int = 2010,
    year_to: int = 2026,
    extra_name_filter: str | None = None,
) -> list[Path]:
    """staging 루트들 아래 유형 폴더에서 reform 시도 CSV 목록."""
    paths: list[Path] = []
    seen: set[str] = set()
    for root in reform_staging_roots():
        folder = root / type_dir_name
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.csv")):
            if extra_name_filter and extra_name_filter not in path.name:
                continue
            if sido_prefixes and not any(path.name.startswith(p) for p in sido_prefixes):
                continue
            year = year_from_csv_name(path.name)
            if year is None or year < year_from or year > year_to:
                continue
            key = path.name.lower()
            if key in seen:
                continue
            seen.add(key)
            paths.append(path)
    return paths
