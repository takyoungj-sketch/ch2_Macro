"""연식=0 잔차 랩 스냅샷 — 파일 계약만 (OLS 재실행 없음)."""

from __future__ import annotations

import json
from pathlib import Path

from app.collective.regional_regression.age0_residual_lab import KEEP_LAB_KEYS, OUT

ROOT = Path(__file__).resolve().parents[2]


def test_age0_residual_snapshot_contract():
    path = ROOT / "docs" / "lab" / "age0_residual_run.json"
    assert path == OUT
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in KEEP_LAB_KEYS:
        assert key in data, key
    assert data["decision"] == "D-064"
    assert data["product_change"] is False
    assert data["verdict"]["code"] == "no_national_premium"
    assert data["national"]["summary_0_3"]["n"] == 744
    assert data["daejeon"]["summary_0_3"]["n"] == 13
    next_ids = {n["id"] for n in data["next"]}
    assert next_ids >= {"seoul-gyeonggi", "within-sigungu", "age-0-1", "national-premium"}
    blocked = next(n for n in data["next"] if n["id"] == "national-premium")
    assert blocked["status"] == "blocked"
    assert data["resume"]["next_id"] == "seoul-gyeonggi"
    seoul = next(s for s in data["sidos"] if "서울" in s["addr1"])
    gyeonggi = next(s for s in data["sidos"] if s["addr1"] == "경기도")
    assert seoul["mean_residual_rate_age0"] > 0
    assert gyeonggi["mean_residual_rate_age0"] < 0
