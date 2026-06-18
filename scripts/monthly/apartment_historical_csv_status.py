"""MOLIT 아파트 historical CSV (2010~2020) 존재·완료 여부."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

HISTORICAL_YEARS = tuple(range(2010, 2021))
MANIFEST_NAME = ".download_manifest.json"


def csv_path(raw_dir: Path, region: str, year: int) -> Path:
    return raw_dir / f"{region}_아파트_매매_{year}.csv"


def csv_exists(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def years_present(raw_dir: Path, region: str) -> list[int]:
    out: list[int] = []
    for y in HISTORICAL_YEARS:
        if csv_exists(csv_path(raw_dir, region, y)):
            out.append(y)
    return out


def region_is_complete(raw_dir: Path, region: str) -> bool:
    return len(years_present(raw_dir, region)) == len(HISTORICAL_YEARS)


@dataclass(frozen=True)
class RegionStatus:
    region: str
    sido_code: str
    years_present: tuple[int, ...]
    complete: bool

    @property
    def file_count(self) -> int:
        return len(self.years_present)


def assess_wave(
    raw_dir: Path,
    wave: list[tuple[str, str]],
) -> list[RegionStatus]:
    raw_dir = raw_dir.resolve()
    out: list[RegionStatus] = []
    for sido_code, region in wave:
        ys = tuple(years_present(raw_dir, region))
        out.append(
            RegionStatus(
                region=region,
                sido_code=sido_code,
                years_present=ys,
                complete=len(ys) == len(HISTORICAL_YEARS),
            )
        )
    return out


def ready_sidos(raw_dir: Path, wave: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """11개 연도 CSV가 모두 있는 시도만."""
    return [(s.sido_code, s.region) for s in assess_wave(raw_dir, wave) if s.complete]


def write_manifest(
    raw_dir: Path,
    *,
    regions: list[str],
    stats: dict[str, int],
    stopped_reason: str | None = None,
) -> Path:
    raw_dir = raw_dir.resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "years": list(HISTORICAL_YEARS),
        "stats": stats,
        "stopped_reason": stopped_reason,
        "regions": {
            region: {
                "complete": region_is_complete(raw_dir, region),
                "files": len(years_present(raw_dir, region)),
                "expected": len(HISTORICAL_YEARS),
                "years": years_present(raw_dir, region),
            }
            for region in regions
        },
    }
    path = raw_dir / MANIFEST_NAME
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
