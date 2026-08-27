from app.collective.transaction_export import public_deal_type, tx_row_dict, transactions_csv_bytes


def test_public_deal_type_keeps_known_values_only():
    assert public_deal_type("presale", "서울특별시 강남구 역삼동") is None
    assert public_deal_type("presale", "중개거래") == "중개거래"
    assert public_deal_type("presale", "직거래") == "직거래"
    assert public_deal_type("presale", " 중개거래 ") == "중개거래"
    assert public_deal_type("presale", "") is None
    assert public_deal_type("apartment", "중개거래") == "중개거래"
    assert public_deal_type("apartment", "경기도 성남시") is None
    assert public_deal_type("apartment", None) is None


def test_tx_row_dict_clears_address_keeps_brokerage():
    addr = tx_row_dict(
        {
            "id": 1,
            "asset_type": "presale",
            "deal_type": "경기도 성남시 분당구",
        }
    )
    assert addr["deal_type"] is None

    kept = tx_row_dict(
        {
            "id": 2,
            "asset_type": "presale",
            "deal_type": "중개거래",
        }
    )
    assert kept["deal_type"] == "중개거래"


def test_presale_csv_deal_type_column_empty_for_address():
    raw = transactions_csv_bytes(
        [{"contract_date": "2024-01-15", "deal_type": "서울시 송파구", "price": 10000}],
        asset_type="presale",
    )
    line = raw.decode("utf-8-sig").strip().split("\n")[-1]
    assert line.endswith(",")
    assert "서울" not in line


def test_presale_csv_keeps_known_deal_type():
    raw = transactions_csv_bytes(
        [{"contract_date": "2024-01-15", "deal_type": "중개거래", "price": 10000}],
        asset_type="presale",
    )
    line = raw.decode("utf-8-sig").strip().split("\n")[-1]
    assert line.endswith("중개거래")
    assert "서울" not in line
