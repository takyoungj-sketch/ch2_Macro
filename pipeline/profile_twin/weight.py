from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DEFAULT_WEIGHT_PATH = CONFIG_DIR / "profile_weight.yaml"

TWIN_PROFILE_WEIGHT_FILES: dict[str, str] = {
    "general": "profile_weight.yaml",
    "built_commercial": "profile_weight_built_commercial.yaml",
    "built_factory": "profile_weight_built_factory.yaml",
    "built_detached": "profile_weight_built_detached.yaml",
    "built_all": "profile_weight_built_all.yaml",
}


@dataclass(frozen=True)
class TwinWeights:
    version: str
    twin_profile: str
    blocks: dict[str, float]
    represent_market_match_bonus: float
    represent_market_mismatch_penalty: float
    population_ratio_low: float
    population_ratio_high: float


def resolve_twin_weight_path(twin_profile: str = "general") -> Path:
    """twin_profile → YAML 경로. land 등 확장 포인트."""
    key = (twin_profile or "general").strip() or "general"
    filename = TWIN_PROFILE_WEIGHT_FILES.get(key)
    if not filename:
        raise ValueError(f"unknown twin_profile: {key}")
    return CONFIG_DIR / filename


def load_twin_weights(
    path: Path | None = None,
    *,
    twin_profile: str = "general",
) -> TwinWeights:
    p = path or resolve_twin_weight_path(twin_profile)
    raw: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))
    blocks = {str(k): float(v) for k, v in (raw.get("blocks") or {}).items()}
    rm = raw.get("represent_market") or {}
    cand = raw.get("candidate") or {}
    profile_key = twin_profile if twin_profile in TWIN_PROFILE_WEIGHT_FILES else "general"
    return TwinWeights(
        version=str(raw.get("version") or "0"),
        twin_profile=profile_key,
        blocks=blocks,
        represent_market_match_bonus=float(rm.get("match_bonus") or 0.0),
        represent_market_mismatch_penalty=float(rm.get("mismatch_penalty") or 0.0),
        population_ratio_low=float(cand.get("population_ratio_low") or 0.5),
        population_ratio_high=float(cand.get("population_ratio_high") or 1.5),
    )
