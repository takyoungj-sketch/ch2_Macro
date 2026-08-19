"""신규아파트 회귀 — 단위 테스트."""

from app.collective.new_apt.dataset import pick_specific_uqa, zone_compact
from app.collective.new_apt.experiment import land_join_summary, leave_one_group_out, run_experiment
from app.collective.new_apt.models import holdout_buildings, land_dispersion
import numpy as np
import pandas as pd


def test_zone_compact_maps_ald155_label():
    assert zone_compact("제2종일반주거지역") == "2주"
    assert zone_compact("제3종일반주거지역") == "3주"
    assert zone_compact("도시지역") is None


def test_pick_specific_uqa_drops_urban_only():
    g = pd.DataFrame(
        {"uqa_code": ["UQA001"], "uqa_label": ["도시지역"]}
    )
    out = pick_specific_uqa(g)
    assert out["zone_resolution"] == "coarse_only"


def test_pick_specific_uqa_tie_is_mixed():
    g = pd.DataFrame(
        {
            "uqa_code": ["UQA122", "UQA123"],
            "uqa_label": ["제2종일반주거지역", "제3종일반주거지역"],
        }
    )
    out = pick_specific_uqa(g)
    assert out["zone_resolution"] == "priority_tie"
    assert "제3종" in str(out["uqa_label"])
    g = pd.DataFrame(
        {
            "uqa_code": ["UQA122", "UQA122", "UQA123"],
            "uqa_label": ["제2종일반주거지역", "제2종일반주거지역", "제3종일반주거지역"],
        }
    )
    out = pick_specific_uqa(g)
    assert out["zone_resolution"] == "majority"
    assert out["uqa_code"] == "UQA122"


def test_holdout_from_new_buildings():
    df = pd.DataFrame(
        {
            "building_key": ["a"] * 3 + ["b"] * 3 + ["c"] * 3 + ["old"] * 3,
            "age": [1, 1, 1, 2, 2, 2, 4, 4, 4, 20, 20, 20],
        }
    )
    keys = holdout_buildings(df, seed=0)
    assert keys
    assert "old" not in keys
    assert keys <= {"a", "b", "c"}


def test_land_dispersion_within_eup_smaller_than_city():
    rows = []
    for eup, base in (("30110101", 400), ("30170101", 1200)):
        for i in range(5):
            rows.append(
                {
                    "land_p50": base + i * 5,
                    "beopjungri_code": eup + "00",
                    "sigungu_code": eup[:5],
                }
            )
    out = land_dispersion(pd.DataFrame(rows))
    assert out["land_cv_daejeon"] > out["land_cv_mean_within_eup"]


def _toy_m2_frame(n_gu: int = 2, n_per: int = 40) -> pd.DataFrame:
    rows = []
    for g in range(n_gu):
        gu = f"301{g}0"
        for i in range(n_per):
            land = 400 + g * 500 + i
            hh = 300 + i * 10
            rows.append(
                {
                    "sido_code": "30",
                    "sigungu_code": gu,
                    "building_key": f"{gu}-{i}",
                    "calendar_year": 2020 + (i % 6),
                    "y_median_unit_price": 400 + 0.2 * land + 0.05 * hh,
                    "n_tx": 20,
                    "age": i % 8,
                    "vintage": "2000-2009",
                    "households": hh,
                    "max_floor": 15 + (i % 10),
                    "parking_per_household": 1.0 + (i % 5) * 0.1,
                    "land_p50": land,
                    "land_n": 40,
                    "match_tier": "A",
                    "beopjungri_code": f"{gu}10100",
                    "zone_resolution": "exact",
                    "builder_group": None,
                    "structure_group": "RC",
                }
            )
    return pd.DataFrame(rows)


def test_land_join_summary_counts_missing():
    df = pd.DataFrame(
        {
            "building_key": ["a", "b"],
            "land_p50": [400.0, np.nan],
            "land_n": [20, np.nan],
            "zone_resolution": ["exact", "missing"],
        }
    )
    out = land_join_summary(df)
    assert out["n_cells"] == 2
    assert out["n_land"] == 1
    assert out["n_missing_land"] == 1


def test_leave_one_gu_out_returns_groups():
    df = _toy_m2_frame()
    rows = leave_one_group_out(df, group_col="sigungu_code", min_hold=10, min_train=30)
    assert len(rows) == 2
    assert any(r.get("mape") is not None or r.get("skipped") for r in rows)


def test_run_experiment_marks_m2_baseline():
    df = _toy_m2_frame(n_gu=2, n_per=50)
    out = run_experiment(df)
    assert out["baseline"] == "M2"
    assert out["m2"].get("product") == "M2"
    assert out["cells"]
    assert out["land_join"]["n_cells"] > 0
    assert any(r.get("is_baseline") for r in out["comparison"]["table"])
    assert "error_audit" in out
    assert out["error_audit"]["repeat_min"] == 5


def test_tag_cell_commercial_and_thin_land():
    from app.collective.new_apt.error_audit import tag_cell

    tags = tag_cell(
        {
            "in_m2": True,
            "ape": 60,
            "zone_compact": "일상",
            "land_n": 3,
            "households": 200,
            "age": 20,
            "parking_per_household": 0.5,
            "max_floor": 15,
            "n_tx": 12,
            "land_p50": 700,
            "residual": -200,
            "y": 230,
            "yhat": 430,
        }
    )
    assert "commercial_zone" in tags
    assert "thin_land" in tags
    assert "old_stock" in tags
    assert "expensive_land_overpred" in tags


def test_audit_repeat_and_no_m4_candidate_from_old_only():
    from app.collective.new_apt.error_audit import audit_m2_errors

    cells = []
    for i in range(6):
        cells.append(
            {
                "building_key": f"old{i}",
                "in_m2": True,
                "in_holdout": False,
                "ape": 70,
                "residual": -200,
                "y": 200,
                "yhat": 400,
                "zone_compact": "3주",
                "land_n": 40,
                "households": 400,
                "age": 25,
                "parking_per_household": 1.0,
                "max_floor": 15,
                "n_tx": 20,
                "land_p50": 300,
                "calendar_year": 2022,
                "sigungu_code": "30170",
            }
        )
    _, audit = audit_m2_errors(cells)
    old = next(p for p in audit["patterns"] if p["tag"] == "old_stock")
    assert old["repeat"] is True
    assert old["action"] == "ignore_old_stock"
    assert audit["next_variable_candidates"] == []


def test_watch_gate_blocks_single_gu():
    from app.collective.new_apt.error_audit import summarize_watch

    buildings = [
        {
            "building_key": f"b{i}",
            "tags": ["large_new_underpred"],
            "direction": "underpred",
            "median_ape": 25.0,
            "builder_group": f"builder{i % 3}",
            "brand": "A",
            "sigungu_code": "30200",
            "sigungu_name": "유성구",
        }
        for i in range(6)
    ]
    watch = summarize_watch(buildings)
    assert watch["n_buildings"] == 6
    assert watch["n_sigungu"] == 1
    assert watch["ready_for_builder_layer"] is False


def test_ledger_overwrites_same_day(tmp_path, monkeypatch):
    from app.collective.new_apt import error_audit as ea

    monkeypatch.setattr(ea, "ledger_path", lambda: tmp_path / "led.json")
    payload = {
        "n_buildings": 4,
        "n_builders": 2,
        "n_brands": 1,
        "n_sigungu": 1,
        "mean_ape": 30.0,
        "direction_underpred_pct": 100.0,
        "ready_for_builder_layer": False,
        "members": [{"building_key": "a"}],
    }
    first = ea.append_watch_ledger("30", payload)
    second = ea.append_watch_ledger("30", {**payload, "n_buildings": 4, "mean_ape": 31.0})
    assert len(first) == 1
    assert len(second) == 1
    assert second[0]["mean_ape"] == 31.0


def _toy_chungbuk_frame(n_gu: int = 2, n_per: int = 50) -> pd.DataFrame:
    df = _toy_m2_frame(n_gu=n_gu, n_per=n_per)
    df = df.copy()
    df["sido_code"] = "43"
    df["sigungu_code"] = df["sigungu_code"].str.replace("301", "431", regex=False)
    df["building_key"] = "cb-" + df["building_key"].astype(str)
    df["beopjungri_code"] = df["sigungu_code"] + "10100"
    df["y_median_unit_price"] = df["y_median_unit_price"] * 0.72
    return df


def test_transfer_verdict_does_not_adopt_on_better_average():
    from app.collective.new_apt.regional import transfer_verdict

    better = transfer_verdict(13.2, 11.0)
    assert better["improves_daejeon"] is True
    assert better["adopt_pooled"] is False
    worse = transfer_verdict(13.2, 16.0)
    assert worse["code"] == "worsens"
    assert worse["adopt_pooled"] is False
    similar = transfer_verdict(13.2, 13.4)
    assert similar["code"] == "similar"
    assert similar["adopt_pooled"] is False


def test_region_compare_freezes_daejeon_holdout():
    from app.collective.new_apt.models import holdout_buildings, prepare_track_a
    from app.collective.new_apt.regional import run_region_compare

    dj = _toy_m2_frame(n_gu=2, n_per=50)
    cb = _toy_chungbuk_frame(n_gu=2, n_per=50)
    out = run_region_compare(dj, cb)
    assert out["adopt_pooled"] is False
    assert out["baseline_status"] == "daejeon_provisional"
    ids = {m["id"] for m in out["models"]}
    assert ids == {"A", "B", "C_naive", "C_sido", "C_gu"}
    a = next(m for m in out["models"] if m["id"] == "A")
    c = next(m for m in out["models"] if m["id"] == "C_sido")
    assert a["hold_scope"] == "대전 hold-out"
    assert c["hold_scope"] == "동일 대전 hold-out"
    assert a["n_holdout"] == c["n_holdout"]
    assert a["n_hold_buildings"] == c["n_hold_buildings"]
    expected = holdout_buildings(prepare_track_a(dj))
    assert out["transfer"]["n_hold_buildings"] == len(expected)
    assert any(str(n).startswith("sido_") for n in [row["name"] for row in c.get("coefficients") or []])
    assert c["focus"]["ln_land_p50"]["coef"] is not None
    assert out["transfer"]["verdict"]["adopt_pooled"] is False
    misleading = out["transfer"]["misleading_overall"]
    assert "채택 기준 아님" in misleading["label"]


def test_pick_ald155_prefers_toi():
    from pathlib import Path

    from app.collective.new_apt.dataset import pick_ald155_dirs

    out = pick_ald155_dirs(Path("e:/ch2/ch2_Macro/raw"), "43")
    assert all("43" in p.name for p in out)
    if out:
        assert any("토이계" in str(p) for p in out)

