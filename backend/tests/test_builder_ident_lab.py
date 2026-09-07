"""시공사 식별 랩 스냅샷 — 파일 계약만 (OLS 재실행 없음)."""

from __future__ import annotations

import json
from pathlib import Path

from app.collective.regional_regression.builder_ident_lab import FEATURED_BUILDERS, KEEP_LAB_KEYS, OUT

ROOT = Path(__file__).resolve().parents[2]


def test_builder_ident_snapshot_contract():
    path = ROOT / "docs" / "lab" / "builder_ident_run.json"
    assert path == OUT
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in KEEP_LAB_KEYS:
        assert key in data, key
    assert data["decision"] == "D-063"
    assert data["product_change"] is False
    assert data["verdict"]["code"] == "needs_more_verification"
    assert data["method"]["n_eligible"] == 17299
    assert data["fit"]["B_land_fe"]["adj_r2"] > data["fit"]["A_land"]["adj_r2"]
    names = [r["builder"] for r in data["featured"]]
    for name in FEATURED_BUILDERS:
        assert name in names
    next_ids = {n["id"] for n in data["next"]}
    assert next_ids >= {"within-gu", "brand-vs-builder", "public-mix", "holdout", "product-formula"}
    blocked = next(n for n in data["next"] if n["id"] == "product-formula")
    assert blocked["status"] == "blocked"
    within = next(n for n in data["next"] if n["id"] == "within-gu")
    assert within["status"] == "done"
    wg = data["within_gu"]
    assert wg["decision"] == "D-065"
    assert wg["method"]["n_gu_fit"] == 156
    assert wg["method"]["n_stacked"] == 16806
    assert wg["verdict"]["product_formula"] == "do_not_add"
    samsung = next(x for x in wg["featured"] if x["builder"] == "삼성물산")
    assert samsung["within_pct"] > 0
    assert samsung["kept"] is False
    assert data["resume"]["next_id"] == "brand-vs-builder"
