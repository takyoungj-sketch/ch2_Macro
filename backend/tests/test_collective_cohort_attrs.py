"""코호트 통합회귀: 단지 속성 변수와 단지 FE는 같이 쓰지 않는다."""

from __future__ import annotations

import pandas as pd

from app.collective.regression.building_attrs import apply_building_attr_quality
from app.collective.regression.engine import _build_design_matrix
from app.collective.schemas import CollectiveRegressionRequest, CollectiveRegressionSpec


def _req(**kwargs) -> CollectiveRegressionRequest:
    spec = dict(
        exclusive_area=False,
        building_age=False,
        floor=False,
        dong=False,
        households=False,
        parking=False,
        assessed_land_price=False,
        structure=False,
        asset_type_dummy=False,
    )
    spec.update(kwargs)
    return CollectiveRegressionRequest(
        asset_type="apartment",
        variables=CollectiveRegressionSpec(**spec),
    )


def _two_buildings(*, hh_a: float | None, hh_b: float | None, n: int = 6, extra: dict | None = None) -> pd.DataFrame:
    rows = []
    extra = extra or {}
    for bk, name, hh, price in (("aaa", "A단지", hh_a, 10000.0), ("bbb", "B단지", hh_b, 12000.0)):
        for i in range(n):
            row = {
                "building_key": bk,
                "display_name": name,
                "price": price + i,
                "floor": 5,
                "households": hh,
            }
            row.update(extra)
            rows.append(row)
    return pd.DataFrame(rows)


def test_households_replaces_building_fe():
    work = _two_buildings(hh_a=100, hh_b=400)
    _, X, labels, meta, warnings = _build_design_matrix(
        work,
        _req(households=True),
        cohort_mode=True,
        building_display_names={"aaa": "A단지", "bbb": "B단지"},
    )
    assert "households" in X.columns
    assert not any(c.startswith("bld_") for c in X.columns)
    assert meta.used_building_attrs
    assert meta.building_fe_map == {}
    assert labels["households"] == "세대수"
    assert any("단지 FE 생략" in w for w in warnings)
    assert not any("단지 FE 기준" in w for w in warnings)


def test_households_skipped_when_no_between_building_variation():
    work = _two_buildings(hh_a=200, hh_b=200)
    _, X, _, meta, warnings = _build_design_matrix(
        work,
        _req(households=True),
        cohort_mode=True,
        building_display_names={"aaa": "A단지", "bbb": "B단지"},
    )
    assert "households" not in X.columns
    assert any(c.startswith("bld_") for c in X.columns)
    assert not meta.used_building_attrs
    assert any("단지 간 차이가 없어 생략" in w for w in warnings)
    assert any("단지 FE 기준" in w for w in warnings)


def test_kapt_same_pnu_nulls_households_and_parking():
    df = pd.DataFrame(
        [
            {
                "building_key": "ot",
                "match_rule": "kapt_same_pnu",
                "households": 299,
                "parking_per_household": 1.1,
                "attr_quality_flags": None,
            },
            {
                "building_key": "apt",
                "match_rule": "name_exact",
                "households": 400,
                "parking_per_household": 1.2,
                "attr_quality_flags": None,
            },
        ]
    )
    out = apply_building_attr_quality(df)
    assert pd.isna(out.loc[0, "households"])
    assert pd.isna(out.loc[0, "parking_per_household"])
    assert out.loc[1, "households"] == 400
    assert out.loc[1, "parking_per_household"] == 1.2


def test_structure_dummies_skip_fe():
    rows = []
    for bk, name, st, price in (("aaa", "A단지", "철근콘크리트", 10000.0), ("bbb", "B단지", "철골조", 12000.0)):
        for i in range(6):
            rows.append(
                {
                    "building_key": bk,
                    "display_name": name,
                    "price": price + i,
                    "floor": 5,
                    "structure_group": st,
                }
            )
    work = pd.DataFrame(rows)
    _, X, labels, meta, warnings = _build_design_matrix(
        work,
        _req(structure=True),
        cohort_mode=True,
        building_display_names={"aaa": "A단지", "bbb": "B단지"},
    )
    assert not any(c.startswith("bld_") for c in X.columns)
    assert any(c.startswith("struct_") for c in X.columns)
    assert meta.structure_reference is not None
    assert any("구조" in v for v in labels.values())
    assert any("단지 FE 생략" in w for w in warnings)


def test_type_dummy_warns_when_floors_do_not_overlap():
    rows = []
    for i in range(6):
        rows.append(
            {
                "building_key": "ot",
                "display_name": "블루지움",
                "price": 8000.0 + i,
                "floor": 5 + i,
                "asset_type": "officetel",
            }
        )
        rows.append(
            {
                "building_key": "apt",
                "display_name": "블루지움",
                "price": 11000.0 + i,
                "floor": 19 + i,
                "asset_type": "apartment",
            }
        )
    work = pd.DataFrame(rows)
    _, x, _, _, warnings = _build_design_matrix(
        work,
        _req(asset_type_dummy=True),
        cohort_mode=True,
        building_display_names={"ot": "블루지움", "apt": "블루지움"},
    )
    assert any(c.startswith("atype_") for c in x.columns)
    assert any("유형이 층으로 갈립니다" in w for w in warnings)
    assert any("순수 유형 효과" in w for w in warnings)


def test_type_dummy_no_floor_warning_when_floors_overlap():
    rows = []
    for i in range(6):
        rows.append(
            {
                "building_key": "ot",
                "price": 8000.0 + i,
                "floor": 10,
                "asset_type": "officetel",
            }
        )
        rows.append(
            {
                "building_key": "apt",
                "price": 11000.0 + i,
                "floor": 10,
                "asset_type": "apartment",
            }
        )
    work = pd.DataFrame(rows)
    _, _, _, _, warnings = _build_design_matrix(
        work,
        _req(asset_type_dummy=True),
        cohort_mode=True,
        building_display_names={"ot": "OT", "apt": "APT"},
    )
    assert not any("유형이 층으로 갈립니다" in w for w in warnings)
