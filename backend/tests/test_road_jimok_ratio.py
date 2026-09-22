"""도로 지목 상대가격 — DB 없이 짝과 분포만."""
from app.land_lab.road_jimok_ratio import (
    PRIMARY_MIN_N,
    THIRD_TICK,
    build_screen,
    percentile_cont,
    zone_class,
)


def _row(**kw):
    base = {
        "sido_name": "충북",
        "sigungu_name": "청주시",
        "eup_code": "4311100000",
        "eup_name": "가경동",
        "n": 12,
        "p50": 100.0,
        "mean_px": 110.0,
    }
    base.update(kw)
    return base


def _screen(rows):
    return build_screen(
        rows,
        as_of_month="2026-08",
        period_start="2021-09-01",
        period_end="2026-08-31",
    )


def test_zone_class_splits_greenbelt():
    assert zone_class("1주") == "urban"
    assert zone_class("제1종일반주거지역") == "urban"
    assert zone_class("계관") == "nonurban"
    assert zone_class("농림") == "nonurban"
    assert zone_class("개제") == "greenbelt"
    assert zone_class("개발제한구역") == "greenbelt"
    assert zone_class("미분류") is None


def test_percentile_cont_mid():
    assert percentile_cont([1, 2, 3, 4], 0.5) == 2.5
    assert percentile_cont([10], 0.25) == 10


def test_urban_pairs_dae_only():
    rows = [
        _row(zone_type="1주", land_category="도", p50=30, mean_px=40, n=12),
        _row(zone_type="1주", land_category="대", p50=100, mean_px=80, n=20),
        _row(zone_type="1주", land_category="전", p50=10, mean_px=10, n=30),
        _row(zone_type="1주", land_category="답", p50=10, mean_px=10, n=30),
    ]
    screen = _screen(rows)
    cells = screen["cells"]
    assert len(cells) == 1
    assert cells[0]["band"] == "urban_dae"
    assert cells[0]["base_jimok"] == "대"
    assert cells[0]["r_med"] == 0.3
    assert cells[0]["r_mean"] == 0.5
    assert screen["bands"][2]["cuts"]["10"]["n_cells"] == 0
    assert screen["bands"][3]["cuts"]["10"]["n_cells"] == 0


def test_nonurban_keeps_three_ratios():
    rows = []
    for jimok, p50 in (("도", 20), ("대", 100), ("전", 40), ("답", 50)):
        rows.append(
            _row(zone_type="계관", land_category=jimok, p50=p50, mean_px=p50, n=15)
        )
    screen = _screen(rows)
    by = {c["band"]: c["r_med"] for c in screen["cells"]}
    assert by == {
        "nonurban_dae": 0.2,
        "nonurban_jeon": 0.5,
        "nonurban_dap": 0.4,
    }
    assert all(b["cuts"]["10"]["n_cells"] == 0 for b in screen["bands"] if b["id"] == "urban_dae")


def test_greenbelt_is_count_only():
    rows = [
        _row(zone_type="개제", land_category="도", n=40, p50=10, mean_px=10),
        _row(zone_type="개제", land_category="대", n=40, p50=30, mean_px=30),
    ]
    screen = _screen(rows)
    assert screen["cells"] == []
    assert screen["greenbelt"]["n_groups"] == 1
    assert screen["greenbelt"]["n_road_trades"] == 40
    assert all(b["cuts"]["10"]["n_cells"] == 0 for b in screen["bands"])


def test_min_n_is_a_filter_not_a_target():
    rows = [
        _row(eup_code="A", zone_type="2주", land_category="도", n=9, p50=33, mean_px=33),
        _row(eup_code="A", zone_type="2주", land_category="대", n=9, p50=100, mean_px=100),
        _row(eup_code="B", zone_type="2주", land_category="도", n=20, p50=80, mean_px=80),
        _row(eup_code="B", zone_type="2주", land_category="대", n=20, p50=100, mean_px=100),
    ]
    screen = _screen(rows)
    urban = next(b for b in screen["bands"] if b["id"] == "urban_dae")
    assert urban["cuts"]["5"]["n_cells"] == 2
    assert urban["cuts"]["10"]["n_cells"] == 1
    assert urban["cuts"]["20"]["n_cells"] == 1
    assert urban["cuts"]["10"]["n_dropped"] == 1
    assert urban["cuts"]["10"]["n_candidates"] == 2
    assert screen["primary_min_n"] == PRIMARY_MIN_N
    assert len(screen["cells"]) == 1
    assert screen["cells"][0]["eup_code"] == "B"


def test_road_only_is_not_a_ratio():
    rows = [_row(zone_type="농림", land_category="도로", n=15, p50=10, mean_px=10)]
    screen = _screen(rows)
    band = next(b for b in screen["bands"] if b["id"] == "nonurban_dae")
    assert band["cuts"]["10"]["n_cells"] == 0
    assert band["cuts"]["10"]["n_road_only"] == 1
    assert band["cuts"]["10"]["n_candidates"] == 0


def test_public_splits_urban_and_skips_a_pooled_city_rate():
    from app.land_lab.road_jimok_ratio import enrich_public

    cells = []
    for i, r in enumerate((0.4, 0.6, 0.8)):
        cells.append({"band": "urban_dae", "zone": "2주", "r_med": r, "eup_code": f"j{i}"})
    for i, r in enumerate((0.2, 0.3)):
        cells.append({"band": "urban_dae", "zone": "자녹", "r_med": r, "eup_code": f"n{i}"})
    cells.append({"band": "nonurban_dae", "zone": "계관", "r_med": 0.5, "eup_code": "g"})
    payload = {
        "period_start": "2021-09-01",
        "period_end": "2026-08-31",
        "as_of_month": "2026-08",
        "primary_min_n": 10,
        "third_tick": 0.3333,
        "cells": cells,
        "bands": [
            {
                "id": "nonurban_jeon",
                "cuts": {"10": {"n_cells": 4, "r_p25": 0.5, "r_p50": 0.7, "r_p75": 0.9, "n_below_third": 0}},
            },
            {
                "id": "nonurban_dap",
                "cuts": {"10": {"n_cells": 3, "r_p25": 0.6, "r_p50": 0.75, "r_p75": 1.0, "n_below_third": 0}},
            },
        ],
        "regression": {
            "bands": [
                {"id": "urban_dae", "cuts": {"10": {"factor": 0.54, "n_cells": 9}}},
                {"id": "nonurban_dae", "cuts": {"10": {"factor": 0.42, "n_cells": 8}}},
            ]
        },
    }
    pub = enrich_public(payload)["public"]
    by = {row["id"]: row for row in pub["main"]}
    assert by["ju"]["n"] == 3
    assert by["ju"]["p50"] == 0.6
    assert by["nok"]["n"] == 2
    assert by["nok"]["detail"].startswith("자연녹지")
    assert by["gye"]["n"] == 1
    assert by["nonurban_jeon"]["p50"] == 0.7
    assert "urban" not in by
    assert all(row["id"] != "urban_dae" for row in pub["adjusted"])
    assert pub["adjusted"][0]["id"] == "nonurban_dae"
    assert pub["adjusted"][0]["factor"] == 0.42


def test_third_tick_does_not_enter_the_cell():
    rows = [
        _row(zone_type="자녹", land_category="도", n=11, p50=10, mean_px=10),
        _row(zone_type="자녹", land_category="대", n=11, p50=100, mean_px=100),
    ]
    screen = _screen(rows)
    assert screen["third_tick"] == round(THIRD_TICK, 4)
    assert "third" not in screen["cells"][0]
    urban = screen["bands"][0]["cuts"]["10"]
    assert urban["n_below_third"] == 1
