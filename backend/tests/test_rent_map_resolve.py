from app.rent.map_resolve import (
    emd_codes_for_leaf_names,
    majority_emd_codes,
    resolve_rent_map_codes,
)


class _FakeResult:
    def __init__(self, scalar=0, rows=()):
        self._scalar = scalar
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def scalar(self):
        return self._scalar


class _FakeConn:
    def __init__(self):
        self.sql = ""
        self.params = {}

    def execute(self, sql, params=None):
        self.sql = str(sql)
        self.params = params or {}
        return _FakeResult()


def test_resolve_dong_uses_beopjungri_prefix():
    conn = _FakeConn()
    resolve_rent_map_codes(conn, addr1="서울특별시", addr2="강남구", leaf_list=["역삼동"])
    assert "beopjungri_code" in conn.sql
    assert "LEFT(" in conn.sql
    assert "addr3 IN" in conn.sql
    assert conn.params["leaves"] == ["역삼동"]


def test_resolve_sigungu_uses_sigungu_code():
    conn = _FakeConn()
    resolve_rent_map_codes(conn, addr1="서울특별시", addr2="강남구")
    assert "sigungu_code" in conn.sql
    assert "LEFT(btrim(beopjungri" not in conn.sql
    assert conn.params.get("a2") == "강남구"


def test_resolve_flat_sido_skips_addr2_eq():
    conn = _FakeConn()
    resolve_rent_map_codes(conn, addr1="세종특별자치시", addr2="__FLAT_SIDO__")
    assert "addr2 = :a2" not in conn.sql
    assert "a2" not in conn.params
    assert conn.params["a1"] == "세종특별자치시"


def test_resolve_city_gu_uses_sigungu():
    conn = _FakeConn()
    resolve_rent_map_codes(conn, addr1="충청북도", addr2="청주시", gu_list=["흥덕구"])
    assert "sigungu_code" in conn.sql
    assert "addr3 IN" in conn.sql
    assert conn.params["gus"] == ["흥덕구"]


def test_resolve_city_dong_uses_addr4():
    conn = _FakeConn()
    resolve_rent_map_codes(
        conn,
        addr1="충청북도",
        addr2="청주시",
        gu_list=["흥덕구"],
        leaf_list=["가경동"],
    )
    assert "LEFT(" in conn.sql
    assert "addr4 IN" in conn.sql
    assert conn.params["leaves"] == ["가경동"]
    assert conn.params["gus"] == ["흥덕구"]


def test_majority_drops_stray_emd():
    assert majority_emd_codes([("43113114", 309), ("43113310", 1)]) == ["43113114"]


def test_emd_name_filter_keeps_bokdae_only():
    class _NamedConn:
        def execute(self, sql, params=None):
            return [("43113114",)]

    assert emd_codes_for_leaf_names(
        _NamedConn(),  # type: ignore[arg-type]
        ["43113114", "43113310"],
        ["복대동"],
        [("43113114", 309), ("43113310", 1)],
    ) == ["43113114"]
