"""다운로드 진행 manifest (.download_manifest.json)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import DownloadPeriod, PropertyType

MANIFEST_NAME = ".download_manifest.json"


def csv_exists(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def periods_present(
    download_dir: Path,
    region: str,
    periods: list[DownloadPeriod],
    property_type: PropertyType,
) -> list[str]:
    out: list[str] = []
    for period in periods:
        path = download_dir / property_type.csv_filename(region, period.key)
        if csv_exists(path):
            out.append(period.key)
    return out


def write_manifest(
    download_dir: Path,
    *,
    property_type: PropertyType,
    regions: list[str],
    periods: list[DownloadPeriod],
    stats: dict[str, int],
    stopped_reason: str | None = None,
) -> Path:
    download_dir = download_dir.resolve()
    download_dir.mkdir(parents=True, exist_ok=True)
    period_keys = [p.key for p in periods]
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "property_type": property_type.key,
        "property_label": property_type.label_ko,
        "deal_type": property_type.deal_type,
        "periods": [
            {"key": p.key, "from_date": p.from_date, "to_date": p.to_date} for p in periods
        ],
        "stats": stats,
        "stopped_reason": stopped_reason,
        "regions": {
            region: {
                "complete": len(periods_present(download_dir, region, periods, property_type))
                == len(periods),
                "files": len(periods_present(download_dir, region, periods, property_type)),
                "expected": len(periods),
                "periods": periods_present(download_dir, region, periods, property_type),
            }
            for region in regions
        },
    }
    path = download_dir / MANIFEST_NAME
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
