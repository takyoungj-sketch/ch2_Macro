"""twin_lab.mart 변환 단위 테스트."""

from __future__ import annotations

import json
from pathlib import Path

from twin_lab.mart import bench_report_to_lab_mart

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "twin_lab_pilot_demo.json"


def test_demo_mart_shape():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["experiment_id"] == "pilot-commercial-demo"
    assert "v0" in data["kpis"]
    assert "v2" in data["kpis"]
    assert len(data["regions"]) >= 8
    row = data["regions"][0]
    assert "versions" in row and "v0" in row["versions"]


def test_bench_report_to_lab_mart():
    report = {
        "generated_at": "2026-08-11T00:00:00+00:00",
        "defaults": {
            "asset_type": "commercial",
            "profile_version": "v2.1-national",
            "window_years": 3,
            "contract_year_from": 2019,
            "contract_year_to": 2025,
            "twin_scope_eup": "region",
        },
        "profiles": {
            "general": {
                "cases": [
                    {
                        "case_id": "a",
                        "label": "A동",
                        "admin_level": "eupmyeondong",
                        "region_codes": ["43113113"],
                        "sample_group": "dev",
                        "twins": [{"region_code": "x", "label": "X", "similarity": 0.8}],
                        "twin_meta": {"twin_profile": "general"},
                        "stage1": {
                            "selection_n": 40,
                            "fit_n": 40,
                            "cv_mape": 20.0,
                            "primary_blocks": ["gross_area"],
                            "response_scale": "log",
                        },
                        "stage2": {"ran": True, "twin_gate_pass_rate": 1.0},
                        "lift": {
                            "best_pool_cv_mape": 18.0,
                            "best_pool_n": 80,
                            "best_pool_blocks": ["gross_area", "land_area"],
                            "best_pool_id": "twin_pool_n3",
                        },
                    }
                ]
            },
            "built_commercial": {
                "cases": [
                    {
                        "case_id": "a",
                        "label": "A동",
                        "admin_level": "eupmyeondong",
                        "region_codes": ["43113113"],
                        "twins": [{"region_code": "y", "label": "Y", "similarity": 0.85}],
                        "twin_meta": {"twin_profile": "built_commercial"},
                        "stage1": {
                            "selection_n": 40,
                            "fit_n": 40,
                            "cv_mape": 20.0,
                            "primary_blocks": ["gross_area"],
                            "response_scale": "log",
                        },
                        "stage2": {"ran": True, "twin_gate_pass_rate": 0.8},
                        "lift": {
                            "best_pool_cv_mape": 16.0,
                            "best_pool_n": 75,
                            "best_pool_blocks": ["gross_area"],
                            "best_pool_id": "twin_pool_n3",
                        },
                    }
                ]
            },
        },
    }
    mart = bench_report_to_lab_mart(report, experiment_id="unit-test")
    assert mart["experiment_id"] == "unit-test"
    assert mart["versions"] == ["v0", "v1", "v2"]
    r0 = mart["regions"][0]
    assert r0["versions"]["v0"]["cv_mape"] == 20.0
    assert r0["versions"]["v1"]["cv_mape"] == 18.0
    assert r0["versions"]["v2"]["lift_rel"] == 0.2
    assert r0["winner"] == "v2"
    assert r0["sample_group"] == "dev"
    assert mart["kpis"]["v2"]["median_lift_rel"] == 0.2
    assert "dev" in mart["kpis_by_sample_group"]
    assert mart["kpis_by_sample_group"]["dev"]["v2"]["median_lift_rel"] == 0.2
    assert "twin_pool_n1" in mart["pool_ablation_v2"]
