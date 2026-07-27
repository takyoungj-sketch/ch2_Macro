from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DEFAULT_CATALOG_PATH = CONFIG_DIR / "profile_feature_catalog.yaml"


@dataclass(frozen=True)
class TwinFeatureSpec:
    key: str
    profile_path: str
    block: str
    dtype: str
    label_ko: str = ""
    unit: str | None = None
    mask_from: str | None = None
    mask_min_count_from: str | None = None
    mask_min_count: int | None = None
    optional: bool = False


@dataclass(frozen=True)
class TwinCatalog:
    version: str
    features: tuple[TwinFeatureSpec, ...]

    def by_key(self) -> dict[str, TwinFeatureSpec]:
        return {f.key: f for f in self.features}

    def by_block(self) -> dict[str, list[TwinFeatureSpec]]:
        out: dict[str, list[TwinFeatureSpec]] = {}
        for f in self.features:
            out.setdefault(f.block, []).append(f)
        return out


def load_twin_catalog(path: Path | None = None) -> TwinCatalog:
    p = path or DEFAULT_CATALOG_PATH
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    tv = raw.get("twin_vector") or {}
    specs: list[TwinFeatureSpec] = []
    for key, spec in (tv.get("features") or {}).items():
        if not isinstance(spec, dict):
            continue
        specs.append(
            TwinFeatureSpec(
                key=str(key),
                profile_path=str(spec.get("profile_path") or key),
                block=str(spec.get("block") or "misc"),
                dtype=str(spec.get("dtype") or "numeric"),
                label_ko=str(spec.get("label_ko") or ""),
                unit=spec.get("unit"),
                mask_from=spec.get("mask_from"),
                mask_min_count_from=spec.get("mask_min_count_from"),
                mask_min_count=int(spec["mask_min_count"]) if spec.get("mask_min_count") is not None else None,
                optional=bool(spec.get("mask") == "optional"),
            )
        )
    return TwinCatalog(version=str(tv.get("version") or "0"), features=tuple(specs))
