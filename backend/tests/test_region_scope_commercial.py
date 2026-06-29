"""beopjungri_code 컬럼 없을 때 region scope fallback."""

from unittest.mock import MagicMock

from app.region_scope import expand_beopjungri_codes


def test_expand_beopjungri_skips_when_column_missing():
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {"ok": False}
    assert (
        expand_beopjungri_codes(
            conn,
            table="collective_commercial_transactions",
            addr1="광주광역시",
            addr2="남구",
            asset_type="collective_shop",
        )
        == []
    )
