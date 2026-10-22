"""범주 결측 공통 규칙."""

import pandas as pd

from app.regression_missing import (
    categorical_dummies,
    drop_unknown_rows,
    pick_reference,
    rare_unknown_warning,
    treatment_label,
)


def test_unknown_is_not_the_reference_when_a_real_level_exists():
    series = pd.Series(["미상"] * 8 + ["철근콘크리트"] * 3)
    frame, levels, ref = categorical_dummies(series, "struct")
    assert ref == "철근콘크리트"
    assert "struct_철근콘크리트" not in frame.columns
    assert "struct_미상" in frame.columns
    assert "미상" in levels


def test_blank_and_null_token_become_unknown():
    series = pd.Series(["", None, "(null)", "벽돌"])
    frame, _levels, ref = categorical_dummies(series, "struct")
    assert ref == "벽돌"
    assert int(frame["struct_미상"].sum()) == 3


def test_drop_removes_only_rows_missing_the_selected_column():
    frame = pd.DataFrame({"structure_group": ["RC", None, "RC"], "price": [1, 2, 3]})
    kept, excluded = drop_unknown_rows(frame, ["structure_group"])
    assert excluded == 1
    assert kept["price"].tolist() == [1, 3]
    untouched, none_excluded = drop_unknown_rows(frame, [])
    assert none_excluded == 0
    assert len(untouched) == 3


def test_reference_tie_uses_name_order():
    assert pick_reference(pd.Series(["나", "가", "나", "가"])) == "가"


def test_explicit_unknown_reference_is_replaced():
    series = pd.Series(["미상", "미상", "세로", "소로"])
    _frame, _levels, ref = categorical_dummies(series, "road", reference="미상")
    assert ref == "세로"


def test_treatment_label():
    assert treatment_label("keep_unknown", 0) == "범주 결측은 미상 범주로 유지. 미상은 기준 범주가 아님"
    assert treatment_label("drop", 12) == "범주 결측 거래 12건 제외"
    assert treatment_label("drop", 12, unit="단지") == "범주 결측 단지 12곳 제외"


def test_rare_unknown_mentions_only_small_levels():
    frame = pd.DataFrame({"structure_group": ["미상", "미상", "RC", "RC", "RC"]})
    assert "구조 2건" in (rare_unknown_warning(frame, [("structure_group", "구조")]) or "")
    many = pd.DataFrame({"structure_group": ["미상"] * 5 + ["RC"] * 5})
    assert rare_unknown_warning(many, [("structure_group", "구조")]) is None
