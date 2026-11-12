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


_STAGING_TOKEN = "201001_202605"
_LAND_STAGING = "토지(인천,전남광주)_201001_202605"


def reform_staging_roots(raw: Path | None = None, *, require: bool = False) -> list[Path]:
    """`raw/*(201001_202605)` 또는 한 단계 아래 `raw/<묶음>/*(201001_202605)` staging 루트.

    2026-11 확인: staging 이 `raw/인천, 전남광주/…` 아래로 옮겨져 `raw/` 바로 아래만 보면 0개였다(D-084 C-02).
    require=True 면 0개일 때 FileNotFoundError(조용히 CSV 0개로 진행하지 않게).
    """
    base = raw or RAW
    roots: list[Path] = []
    if base.is_dir():
        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name == _LAND_STAGING:
                continue
            if _STAGING_TOKEN in child.name:
                roots.append(child)
                continue
            for sub in sorted(child.iterdir()):
                if sub.is_dir() and _STAGING_TOKEN in sub.name and sub.name != _LAND_STAGING:
                    roots.append(sub)
    if require and not roots:
        raise FileNotFoundError(f"reform staging 루트 없음: {base}/*{_STAGING_TOKEN}*, {base}/*/*{_STAGING_TOKEN}*")
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
    for root in reform_staging_roots(require=True):
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
