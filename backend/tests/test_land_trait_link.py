from datetime import date

from app.land_trait_link import (
    LINK_STATUS_LABELS,
    NOTICE,
    PRICE_STATUS_LABELS,
    csv_cells,
    item_fields,
)


def test_notice_is_the_list_consent_copy():
    assert len(NOTICE) == 2
    assert "실거래 원장" in NOTICE[0]
    assert "공시지가" in NOTICE[1]


def test_item_fields_keep_a_unique_price_and_label_the_status():
    fields = item_fields(
        {
            "trait_link_status": "exact",
            "trait_price_status": "same_year",
            "official_price_won": 1234500,
            "official_price_year": 2019,
            "trait_asof": date(2019, 1, 1),
            "trait_unverified": True,
        }
    )
    assert fields["trait_link_label"] == "일치"
    assert fields["official_price_won"] == 1234500.0
    assert fields["official_price_year"] == 2019
    assert fields["trait_unverified"] is True


def test_item_fields_leave_a_missing_row_blank():
    fields = item_fields(
        {
            "trait_link_status": None,
            "trait_price_status": None,
            "official_price_won": None,
            "official_price_year": None,
            "trait_asof": None,
            "trait_unverified": None,
        }
    )
    assert fields["trait_link_status"] is None
    assert fields["trait_link_label"] is None
    assert fields["official_price_won"] is None
    assert fields["trait_unverified"] is None


def test_csv_marks_an_uncomputed_row_and_a_price_conflict():
    assert csv_cells({})[0] == "미계산"
    cells = csv_cells(
        {
            "trait_link_status": "label_normalized",
            "trait_link_label": LINK_STATUS_LABELS["label_normalized"],
            "trait_price_status": "price_conflict",
            "official_price_won": None,
            "official_price_year": None,
            "trait_asof": date(2020, 6, 1),
        }
    )
    assert cells[0] == "표기 정규화"
    assert cells[1] == "충돌"
    assert cells[2] == ""
    assert cells[3] == PRICE_STATUS_LABELS["price_conflict"]
    assert cells[4] == "2020-06-01"
