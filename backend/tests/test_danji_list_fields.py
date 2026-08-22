"""기본통계 목록용 시공사 대표 1곳 표기."""

from app.collective.danji_attributes import list_builder_label


def test_list_builder_label_single():
    assert list_builder_label("현대건설", "현대건설(주)", False) == "현대건설"


def test_list_builder_label_joint_takes_first():
    assert list_builder_label("현대건설, 대우건설", "현대건설,대우건설", True) == "현대건설 외"
    assert list_builder_label("한양건설 외", "한양건설, 한양공영, 삼익건설", True) == "한양건설 외"


def test_list_builder_label_missing():
    assert list_builder_label(None, None, False) is None
    assert list_builder_label("", "  ", False) is None
