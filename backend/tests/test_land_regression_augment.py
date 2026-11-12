"""토지 회귀 표본 확장. 가격으로 지역을 고르지 않고, 검증은 기준 칸만 쓴다."""

from datetime import date

import pandas as pd

from app.land_lab.regression_augment import (
    CellCount,
    _modal_other_key,
    add_counts,
    apply_assessed_rows,
    assign_folds,
    evaluate_cv,
    experiment_b_quota,
    pick_twin,
    prepare_frame,
    select_round1,
)


def _cell(code: str, name: str, zone: str, jimok: str, n: int, sido: str = "11") -> CellCount:
    return CellCount(code, name, sido, "서울", "구", zone, jimok, n)


def test_type_a_keeps_only_modal_residential_lot():
    modal = _cell("11110001", "사직동", "2주", "대", 40)
    other = _cell("11110001", "사직동", "자녹", "전", 10)
    rural = _cell("11110002", "오창읍", "계관", "전", 40)
    chosen, _counts = select_round1([modal, other, rural])
    assert chosen["A"] == modal
    assert chosen["C"] is None


def test_m1_skips_when_target_is_the_modal_cell():
    frame = pd.DataFrame(
        {
            "eup_code": ["E"] * 30 + ["E"] * 10,
            "zone": ["2주"] * 30 + ["자녹"] * 10,
            "jimok": ["대"] * 30 + ["전"] * 10,
        }
    )
    anchor = _cell("E", "사직동", "2주", "대", 30)
    assert _modal_other_key(frame, anchor) is None


def test_folds_cover_only_the_target_rows():
    frame = pd.DataFrame(
        {
            "is_target": [True] * 30 + [False] * 10,
            "contract_year": [2021 + (i % 5) for i in range(40)],
        }
    )
    first = assign_folds(frame)
    second = assign_folds(frame)
    assert first.tolist() == second.tolist()
    assert set(first.iloc[:30].unique()) == {0, 1, 2, 3, 4}
    assert (first.iloc[30:] == -1).all()


def test_twin_uses_composition_not_a_price_field():
    anchor = _cell("A", "가경동", "2주", "대", 40, "43")
    close = [
        anchor,
        _cell("A", "가경동", "자녹", "임", 10, "43"),
        _cell("B", "복대동", "2주", "대", 20, "43"),
        _cell("B", "복대동", "자녹", "임", 8, "43"),
        _cell("C", "성화동", "농림", "답", 30, "43"),
        _cell("C", "성화동", "2주", "대", 15, "43"),
    ]
    twin = pick_twin(close, anchor)
    assert twin is not None
    assert twin[0].eup_code == "B"


def test_cv_scores_the_target_cell_only():
    rows = []
    for i in range(40):
        area = 100 + i
        rows.append(
            {
                "id": i,
                "eup_code": "E",
                "zone": "계관",
                "jimok": "전",
                "area_sqm": area,
                "unit_price_per_sqm": 20 * (area ** 0.5),
                "contract_year": 2021 + (i % 5),
                "contract_date": date(2021 + (i % 5), 6, 1),
                "road_condition": "8미만",
                "deal_type": "중개거래",
            }
        )
    for i in range(20):
        area = 200 + i
        rows.append(
            {
                "id": 100 + i,
                "eup_code": "E",
                "zone": "계관",
                "jimok": "답",
                "area_sqm": area,
                "unit_price_per_sqm": 8 * (area ** 0.5),
                "contract_year": 2022,
                "contract_date": date(2022, 6, 1),
                "road_condition": "8미만",
                "deal_type": "중개거래",
            }
        )
    raw = pd.DataFrame(rows)
    anchor = _cell("E", "오창읍", "계관", "전", 40)
    frame = prepare_frame(raw, anchor, None, _modal_other_key(raw, anchor))
    assert add_counts(frame, anchor)["M2"] == 20
    assert experiment_b_quota(add_counts(frame, anchor)) == 20
    scored = evaluate_cv(frame, anchor)
    assert scored["M0"]["status"] == "estimated"
    assert scored["M2"]["status"] == "estimated"
    assert scored["M0"]["n_test_mean"] < 15


def test_assessed_price_drops_shares_and_enters_the_formula():
    rows = []
    for i in range(40):
        price = 400 + i * 15
        rows.append(
            {
                "id": i,
                "eup_code": "E",
                "zone": "2주",
                "jimok": "대",
                "area_sqm": 80 + (i % 7) * 20,
                "unit_price_per_sqm": 2.5 * price,
                "official_price_won": None if i == 1 else price,
                "is_partial_ownership": i == 0,
                "contract_year": 2021 + (i % 4),
                "contract_date": date(2021 + (i % 4), 6, 1),
                "road_condition": "8미만",
                "deal_type": "중개거래",
            }
        )
    kept, cover = apply_assessed_rows(pd.DataFrame(rows))
    assert cover["n_partial"] == 1
    assert set(kept["id"]) == set(range(2, 40))
    anchor = _cell("E", "합정동", "2주", "대", 38)
    frame = prepare_frame(kept, anchor, None, None)
    scored = evaluate_cv(frame, anchor, use_assessed=True)
    assert scored["M0"]["status"] == "estimated"
    assert scored["M0"]["log_assessed_sign"] == 1.0
