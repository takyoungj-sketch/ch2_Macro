"""기본통계 목록용 시공사 대표 1곳 표기 · 개별공시지가 필드."""

from app.collective.danji_attributes import list_builder_label
from app.collective.schemas import BuildingStatsRow


def test_list_builder_label_single():
    assert list_builder_label("현대건설", "현대건설(주)", False) == "현대건설"


def test_list_builder_label_joint_takes_first():
    assert list_builder_label("현대건설, 대우건설", "현대건설,대우건설", True) == "현대건설 외"
    assert list_builder_label("한양건설 외", "한양건설, 한양공영, 삼익건설", True) == "한양건설 외"


def test_list_builder_label_missing():
    assert list_builder_label(None, None, False) is None
    assert list_builder_label("", "  ", False) is None


def test_building_stats_row_land_price_fields():
    row = BuildingStatsRow(
        building_key="k" * 64,
        display_name="우주마루",
        asset_type="officetel",
        count=3,
        assessed_land_price=2_150_000,
        assessed_land_price_year=2026,
    )
    dumped = row.model_dump()
    assert dumped["assessed_land_price"] == 2_150_000
    assert dumped["assessed_land_price_year"] == 2026
    assert dumped["type_siblings"] == []
    assert dumped["scale_scope"] is None
