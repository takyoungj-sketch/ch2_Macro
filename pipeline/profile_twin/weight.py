from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DEFAULT_WEIGHT_PATH = CONFIG_DIR / "profile_weight.yaml"


@dataclass(frozen=True)
class TwinWeights:
    version: str
    blocks: dict[str, float]
    represent_market_match_bonus: float
    represent_market_mismatch_penalty: float
    population_ratio_low: float
    population_ratio_high: float


def load_twin_weights(path: Path | None = None) -> TwinWeights:
    p = path or DEFAULT_WEIGHT_PATH
    raw: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))
    blocks = {str(k): float(v) for k, v in (raw.get("blocks") or {}).items()}
    rm = raw.get("represent_market") or {}
    cand = raw.get("candidate") or {}
    return TwinWeights(
        version=str(raw.get("version") or "0"),
        blocks=blocks,
        represent_market_match_bonus=float(rm.get("match_bonus") or 0.0),
        represent_market_mismatch_penalty=float(rm.get("mismatch_penalty") or 0.0),
        population_ratio_low=float(cand.get("population_ratio_low") or 0.5),
        population_ratio_high=float(cand.get("population_ratio_high") or 1.5),
    )
