"""recover_from_parcel 지번 키 파싱."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from built.recover_from_parcel import UNIVERSE_COUNT_SQL, _parcel_key


def test_parcel_key_plain_and_hyphen():
    assert _parcel_key("4313012500|123") == ("4313012500", 123, 0)
    assert _parcel_key("4313012500|123-4") == ("4313012500", 123, 4)
    assert _parcel_key("nope") is None


def test_universe_count_includes_partials():
    sql = UNIVERSE_COUNT_SQL.lower()
    assert "contract_year >= :min_year" in sql
    assert "is_partial_ownership" not in sql
    assert "gross_area > 0" in sql
