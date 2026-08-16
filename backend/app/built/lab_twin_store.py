"""Twin Experiment Lab — 파일 기반 mart 로더."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_DEFAULT_DIRS = [
    _REPO / "logs" / "twin_lab",
    _REPO / "pipeline" / "fixtures",
]


def lab_enabled() -> bool:
    return (os.getenv("TWIN_LAB_ENABLED") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _mart_dirs() -> list[Path]:
    extra = (os.getenv("TWIN_LAB_MART_DIR") or "").strip()
    dirs: list[Path] = []
    if extra:
        dirs.append(Path(extra))
    dirs.extend(_DEFAULT_DIRS)
    return dirs


def list_experiments() -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for d in _mart_dirs():
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            name = path.name
            if name.startswith("twin_built_lift"):
                continue
            if name == "twin_built_lift_bench.json":
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict) or "experiment_id" not in data:
                # demo fixture 파일명
                if name == "twin_lab_pilot_demo.json" and "regions" in data:
                    pass
                else:
                    continue
            exp_id = str(data.get("experiment_id") or path.stem)
            if exp_id in seen:
                continue
            seen[exp_id] = {
                "experiment_id": exp_id,
                "asset_type": data.get("asset_type"),
                "period_years": data.get("period_years"),
                "anchor_basin": data.get("anchor_basin"),
                "versions": data.get("versions") or [],
                "n_regions": len(data.get("regions") or []),
                "generated_at": data.get("generated_at"),
                "source": data.get("source"),
                "path": str(path),
            }
    items = list(seen.values())
    # 실측(non-demo) 최신순 → demo
    items.sort(
        key=lambda x: (
            1 if "demo" in str(x["experiment_id"]) else 0,
            str(x.get("generated_at") or ""),
            x["experiment_id"],
        ),
        reverse=False,
    )
    non_demo = sorted(
        [x for x in items if "demo" not in str(x["experiment_id"])],
        key=lambda x: str(x.get("generated_at") or ""),
        reverse=True,
    )
    demos = [x for x in items if "demo" in str(x["experiment_id"])]
    return non_demo + demos


def load_experiment(experiment_id: str) -> dict[str, Any] | None:
    want = experiment_id.strip()
    for d in _mart_dirs():
        if not d.is_dir():
            continue
        candidates = [
            d / f"{want}.json",
            d / "twin_lab_pilot_demo.json" if want in {"pilot-commercial-demo", "demo"} else None,
        ]
        for path in candidates:
            if path is None or not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(data.get("experiment_id")) == want or (
                want in {"demo", "pilot-commercial-demo"}
                and path.name == "twin_lab_pilot_demo.json"
            ):
                data.setdefault("experiment_id", want if want != "demo" else "pilot-commercial-demo")
                return data
        # stem scan
        for path in d.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(data.get("experiment_id")) == want:
                return data
    return None
