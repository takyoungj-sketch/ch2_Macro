"""연립·다세대 층 효용 랩 — 칸·게이트·건물 FE."""
from __future__ import annotations

import math

import numpy as np

from app.collective.regression.engine import relative_floor_group
from app.rowhouse_lab.floor_elevator import (
    elevator_from_counts,
    exp1_gate,
    floor_bin,
    floor_bin_detail,
    floor_bucket,
    ident_window_45,
)
from app.rowhouse_lab.floor_elevator_fit import (
    dirs_agree,
    fit_floor_fe,
    pack_fit,
    run_phase1,
    signs_disagree,
)
from app.rowhouse_lab.floor_elevator_screen import build_screen_sql, fetch_phase1_tx_sql
from app.ledger_region_sql import beopjungri_eq_or_in


def test_floor_bin_is_absolute_not_relative():
    assert floor_bin(1, 5) == "1"
    assert floor_bin(2, 5) == "mid"
    assert floor_bin(4, 5) == "mid"
    assert floor_bin(5, 5) == "top"
    assert floor_bin(0, 5) is None
    assert relative_floor_group(2, 5) == "floor_rel_mid"
    assert floor_bin(2, 4) == "mid"
    assert floor_bin(4, 4) == "top"


def test_floor_bin_detail_splits_mid():
    assert floor_bin_detail(2, 5) == "2"
    assert floor_bin_detail(3, 5) == "3"
    assert floor_bin_detail(4, 5) == "4"
    assert floor_bin_detail(5, 5) == "top"


def test_exp1_gate_needs_spread_not_just_n():
    assert exp1_gate(n=59, n_1=10, n_mid=20, max_floor=5)
    assert not exp1_gate(n=59, n_1=59, n_mid=0, max_floor=5)
    assert not exp1_gate(n=8, n_1=3, n_mid=3, max_floor=5)
    assert not exp1_gate(n=20, n_1=5, n_mid=5, max_floor=3)


def test_ident_window_only_4_or_5():
    assert ident_window_45(4)
    assert ident_window_45(5)
    assert not ident_window_45(6)
    assert not ident_window_45(3)


def test_elevator_from_counts():
    assert elevator_from_counts(None, None) is None
    assert elevator_from_counts(0, 0) is False
    assert elevator_from_counts(1, 0) is True
    assert elevator_from_counts(0, 2) is True


def test_screen_sql_no_any():
    sql = build_screen_sql()
    assert "ANY" not in sql.upper()
    pred, extra = beopjungri_eq_or_in(["11110"], column="sigungu_code")
    assert "ANY" not in pred.upper()
    assert extra
    tx_sql = fetch_phase1_tx_sql()
    assert "ANY" not in tx_sql.upper()
    assert "IN :building_keys" in tx_sql


def test_fit_floor_fe_recovers_top_premium():
    rows = []
    rng = np.random.default_rng(0)
    for b in range(4):
        for i in range(8):
            fl = [1, 2, 3, 4, 5][i % 5]
            area = 50.0 + (i % 3)
            ln_p = 4.0 + 0.15 * (1 if fl == 5 else 0) + 0.4 * math.log(area) + 0.02 * rng.normal()
            rows.append(
                {
                    "building_key": f"b{b}",
                    "floor": fl,
                    "exclusive_area": area,
                    "unit_price": math.exp(ln_p),
                    "contract_year": 2024,
                    "contract_month": 3,
                }
            )
    out = fit_floor_fe(rows)
    assert out["ok"]
    assert out["gamma_top"] is not None
    assert out["gamma_top"] > 0.05
    assert out["p_top"] is not None and out["p_top"] < 0.1


def test_pack_fit_and_dirs_agree():
    packed = pack_fit(
        {
            "ok": True,
            "n": 100,
            "n_buildings": 10,
            "gamma_mid": math.log(1.1),
            "gamma_top": math.log(0.9),
            "se_mid": 0.01,
            "se_top": 0.01,
            "p_mid": 0.001,
            "p_top": 0.001,
            "beta_area": 0.4,
            "r2": 0.2,
            "reason": "",
        }
    )
    assert packed["dir_mid"] == "plus"
    assert packed["dir_top"] == "minus"
    assert packed["pct_mid"] is not None and abs(packed["pct_mid"] - 0.1) < 0.01
    assert dirs_agree(["plus", "ns", "plus"]) == "plus"
    assert dirs_agree(["plus", "minus"]) == "split"
    assert dirs_agree(["ns", "na"]) == "ns"
    assert signs_disagree("plus", 0.3)
    assert not signs_disagree("plus", 0.7)
    assert floor_bucket(4) == "4"
    assert floor_bucket(6) == "6plus"


def _synth_cell(key: str, n: int, region: str, mx: float = 5) -> dict:
    return {
        "building_key": key,
        "eligible": True,
        "n": n,
        "region_type": region,
        "max_floor_tx": mx,
        "housing_subtype": "다세대주택",
    }


def test_run_phase1_n_sensitivity_does_not_use_gamma():
    rng = np.random.default_rng(1)
    tx = []
    cells = []
    for b in range(6):
        key = f"b{b}"
        n = 12 if b < 4 else 55
        cells.append(_synth_cell(key, n, "metro_gu" if b % 2 == 0 else "gun", 5))
        for i in range(n):
            fl = [1, 2, 3, 4, 5][i % 5]
            area = 48.0 + (i % 4)
            ln_p = 4.2 - 0.12 * (1 if 1 < fl < 5 else 0) + 0.3 * math.log(area) + 0.01 * rng.normal()
            tx.append(
                {
                    "building_key": key,
                    "floor": fl,
                    "exclusive_area": area,
                    "unit_price": math.exp(ln_p),
                    "contract_year": 2023 + (i % 2),
                    "contract_month": 4,
                }
            )
    out = run_phase1(tx, cells)
    assert out["pooled"]["ok"]
    assert out["by_n"]["10"]["n_buildings"] == 6
    assert out["by_n"]["50"]["n_buildings"] == 2
    assert "n_sig_mid" in out
    assert out["type_agree_mid"] in {"plus", "minus", "ns", "split"}
    assert "n_pos_mid" in out["building_delta"]


def test_aggregate_elevator_mixed_is_unknown():
    from app.rowhouse_lab.floor_elevator_attach import aggregate_pnu_elevator
    from app.rowhouse_lab.floor_elevator import TITLE_RIDE_ELVT_COL, TITLE_EMGEN_ELVT_COL

    assert TITLE_RIDE_ELVT_COL == 45
    assert TITLE_EMGEN_ELVT_COL == 46
    yes = {
        "main_purpose": "공동주택",
        "purpose_detail": "다세대주택",
        "elevator": True,
        "ride": 1,
        "emgen": 0,
        "floors_above": 4,
    }
    no = {**yes, "elevator": False, "ride": 0}
    mixed = aggregate_pnu_elevator([yes, no])
    assert mixed["elevator"] is None
    assert mixed["mixed"] is True
    all_no = aggregate_pnu_elevator([no, {**no, "floors_above": 5}])
    assert all_no["elevator"] is False
    all_yes = aggregate_pnu_elevator([yes])
    assert all_yes["elevator"] is True


def test_fit_theta_recovers_extra_top_slope():
    rng = np.random.default_rng(2)
    rows = []
    for b in range(8):
        elev = b >= 4
        for i in range(10):
            fl = [1, 2, 3, 4, 5][i % 5]
            area = 50.0 + (i % 3)
            extra = 0.18 if (elev and fl == 5) else 0.0
            ln_p = 4.0 + 0.04 * (1 if fl == 5 else 0) + extra + 0.3 * math.log(area) + 0.01 * rng.normal()
            rows.append(
                {
                    "building_key": f"b{b}",
                    "floor": fl,
                    "exclusive_area": area,
                    "unit_price": math.exp(ln_p),
                    "contract_year": 2024,
                    "contract_month": 6,
                    "elevator": elev,
                }
            )
    out = pack_fit(fit_floor_fe(rows, interact_elev=True))
    assert out["ok"]
    assert out["n_elev_yes"] == 4
    assert out["n_elev_no"] == 4
    assert out["theta_top"] is not None and out["theta_top"] > 0.08
    assert out["dir_theta_top"] == "plus"


def test_phase2a_balance_gate():
    from app.rowhouse_lab.floor_elevator_fit import run_phase2a_balance
    from app.rowhouse_lab.floor_elevator import REGION_TYPES

    cells = []
    elev = {}
    types = REGION_TYPES[:3]
    n = 0
    for rt in types:
        for i in range(12):
            ky = f"y{n}"
            kn = f"n{n}"
            n += 1
            base = {
                "eligible": True,
                "ident_45": True,
                "median_year": 2010,
                "max_floor_tx": 4,
                "region_type": rt,
            }
            cells.append({**base, "building_key": ky})
            cells.append({**base, "building_key": kn})
            elev[ky] = True
            elev[kn] = False
    bal = run_phase2a_balance(cells, elev)
    assert bal["n_yes"] == 36
    assert bal["n_no"] == 36
    assert bal["n_cells_both"] >= 3
    assert bal["level_ok"]


def test_cap_band_is_seoul_gyeonggi_incheon():
    from app.rowhouse_lab.floor_elevator import cap_band, age_coarse

    assert cap_band("서울특별시") == "capital"
    assert cap_band("경기도") == "capital"
    assert cap_band("인천광역시") == "capital"
    assert cap_band("부산광역시") == "noncapital"
    assert cap_band("충청북도") == "noncapital"
    assert age_coarse(2012) == "new"
    assert age_coarse(1990) == "old"


def test_purpose_band_from_title_not_filename():
    from app.rowhouse_lab.floor_elevator_attach import purpose_band_from_dongs

    assert purpose_band_from_dongs([{"purpose_detail": "다세대주택", "main_purpose": "공동주택"}]) == "다세대"
    assert purpose_band_from_dongs([{"purpose_detail": "연립주택", "main_purpose": "공동주택"}]) == "연립"
    assert purpose_band_from_dongs(
        [
            {"purpose_detail": "다세대주택", "main_purpose": "공동주택"},
            {"purpose_detail": "연립주택", "main_purpose": "공동주택"},
        ]
    ) == "both"


def test_lab_sketch_one_is_100():
    from app.rowhouse_lab.floor_elevator_fit import lab_sketch

    sk = lab_sketch(
        {
            "gamma_mid": 0.0,
            "gamma_top": math.log(0.975),
            "theta_mid": 0.0,
            "theta_top": math.log(1.135 / 0.975),
        }
    )
    assert sk["no"]["1"] == 100.0
    assert sk["yes"]["1"] == 100.0
    assert sk["no"]["top"] is not None and abs(sk["no"]["top"] - 97.5) < 0.2
    assert sk["yes"]["top"] is not None and abs(sk["yes"]["top"] - 113.5) < 0.3


def test_run_phase3_keeps_same_eligible_set():
    from app.rowhouse_lab.floor_elevator_fit import lab_sketch, run_phase3

    rng = np.random.default_rng(3)
    tx = []
    cells = []
    elev = {}
    purpose = {}
    for b in range(8):
        key = f"b{b}"
        elev[key] = b % 2 == 0
        purpose[key] = "연립" if b < 4 else "다세대"
        sido = "서울특별시" if b < 4 else "부산광역시"
        year = 1990 if b % 4 < 2 else 2012
        mx = 4 if b < 4 else 5
        cells.append(
            {
                **_synth_cell(key, 12, "metro_gu", mx),
                "sido_name": sido,
                "median_year": year,
            }
        )
        floors = [1, 2, 3, 4] if mx == 4 else [1, 2, 3, 4, 5]
        for i in range(12):
            fl = floors[i % len(floors)]
            area = 50.0 + (i % 3)
            extra = 0.16 if (elev[key] and fl == mx) else 0.0
            ln_p = 4.0 + extra + 0.3 * math.log(area) + 0.01 * rng.normal()
            if b == 7:
                ln_p += 2.0
            tx.append(
                {
                    "building_key": key,
                    "floor": fl,
                    "exclusive_area": area,
                    "unit_price": math.exp(ln_p),
                    "contract_year": 2024,
                    "contract_month": 5,
                    "elevator": elev[key],
                }
            )
    out = run_phase3(tx, cells, elev, purpose)
    assert out["reselected"] is False
    assert out["n_eligible"] == 8
    assert out["n_known"] == 8
    assert out["by_n"]["10"]["n_buildings"] == 8
    assert out["by_cap"]["capital"]["n_buildings"] == 4
    assert out["by_cap"]["noncapital"]["n_buildings"] == 4
    assert out["by_age"]["old"]["n_buildings"] == 4
    assert out["by_age"]["new"]["n_buildings"] == 4
    assert out["by_purpose"]["연립"]["n_buildings"] == 4
    assert out["agree_theta_top"] == "plus"
    assert "6plus" not in (out.get("agree_slices_top") or [])
    sk = lab_sketch(out["pooled"])
    assert sk["yes"]["1"] == 100.0
    assert out["sketch"]["yes"]["1"] == 100.0

