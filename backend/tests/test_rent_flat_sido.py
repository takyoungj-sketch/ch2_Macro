from datetime import date

from app.flat_sido_region import FLAT_SIDO_ADDR2_TOKEN
from app.rent.conversion_query import _fetch_rate_rows


class _FakeResult:
    def mappings(self):
        return self

    def all(self):
        return []


class _FakeConn:
    def __init__(self):
        self.sql = ""
        self.params = {}

    def execute(self, sql, params=None):
        self.sql = str(sql)
        self.params = params or {}
        return _FakeResult()


def test_conversion_rate_flat_sido_matches_empty_addr2(monkeypatch):
    from app.rent import conversion_query as cq

    monkeypatch.setattr(cq, "_has_addr3", lambda _conn: True)
    conn = _FakeConn()
    _fetch_rate_rows(
        conn,
        as_of=date(2026, 7, 1),
        window_years=5,
        addr1="세종특별자치시",
        addr2=FLAT_SIDO_ADDR2_TOKEN,
        assets=["apartment"],
        addr3="",
    )
    assert "addr2 = :a2" not in conn.sql
    assert "addr2 = ''" in conn.sql or "addr2 IS NULL" in conn.sql
    assert "a2" not in conn.params
