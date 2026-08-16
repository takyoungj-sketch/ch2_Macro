"""Profile Twin weight profile loader."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from profile_twin.weight import load_twin_weights, resolve_twin_weight_path  # noqa: E402


def test_resolve_built_commercial_weight_path():
    path = resolve_twin_weight_path("built_commercial")
    assert path.name == "profile_weight_built_commercial.yaml"
    w = load_twin_weights(twin_profile="built_commercial")
    assert w.twin_profile == "built_commercial"
    assert w.blocks.get("commercial_profile", 0) > 0
    assert sum(w.blocks.values()) > 0.99


def test_general_weight_profile_default():
    w = load_twin_weights(twin_profile="general")
    assert w.twin_profile == "general"
    assert "apartment_profile" in w.blocks
