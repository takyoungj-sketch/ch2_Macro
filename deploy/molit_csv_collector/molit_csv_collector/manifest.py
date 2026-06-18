"""다운로드 진행 manifest (.download_manifest.json)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import PropertyType

MANIFEST_NAME = ".download_manifest.json"


def csv_exists(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def years_present(
    download_dir: Path,
    region: str,
    years: list[int],
    property_type: PropertyType,
) -> list[int]:
    out: list[int] = []
    for year in years:
        path = download_dir / property_type.csv_filename(region, year)
        if csv_exists(path):
            out.append(year)
    return out


def write_manifest(
    download_dir: Path,
    *,
    property_type: PropertyType,
    regions: list[str],
    years: list[int],
    stats: dict[str, int],
    stopped_reason: str | None = None,
) -> Path:
    download_dir = download_dir.resolve()
    download_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "property_type": property_type.key,
        "property_label": property_type.label_ko,
        "deal_type": property_type.deal_type,
        "years": years,
        "stats": stats,
        "stopped_reason": stopped_reason,
        "regions": {
            region: {
                "complete": len(years_present(download_dir, region, years, property_type))
                == len(years),
                "files": len(years_present(download_dir, region, years, property_type)),
                "expected": len(years),
                "years": years_present(download_dir, region, years, property_type),
            }
            for region in regions
        },
    }
    path = download_dir / MANIFEST_NAME
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
