"""시군구 메타 목록 · 칩 이름 우선(COUNT 없음)."""

from __future__ import annotations

from types import SimpleNamespace

from app.collective.meta_cache import clear_meta_cache
from app.region_catalog import list_addr2_from_meta, list_gu_names


def test_list_addr2_from_meta_skips_unknown_table():
    class Conn:
        def execute(self, *args, **kwargs):
            raise AssertionError("commercial has no sigungu meta domain")

    assert (
        list_addr2_from_meta(
            Conn(),
            table="collective_commercial_transactions",
            addr1="서울특별시",
            asset_type=None,
        )
        is None
    )


def test_list_addr2_from_meta_hit():
    class Conn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            if "to_regclass" in sql:
                return SimpleNamespace(scalar=lambda: True)
            assert "region_sigungu_meta" in sql
            return SimpleNamespace(
                fetchall=lambda: [
                    SimpleNamespace(addr2_token="청주시"),
                    SimpleNamespace(addr2_token="충주시"),
                ]
            )

    assert list_addr2_from_meta(
        Conn(),
        table="built_transactions",
        addr1="충청북도",
        asset_type=None,
    ) == ["청주시", "충주시"]


def test_list_addr2_from_meta_missing_table_falls_back():
    class Conn:
        def execute(self, stmt, params=None):
            return SimpleNamespace(scalar=lambda: False)

    assert (
        list_addr2_from_meta(
            Conn(),
            table="collective_transactions",
            addr1="충청북도",
            asset_type="apartment",
        )
        is None
    )


def test_list_gu_names_zero_count_and_ttl():
    clear_meta_cache()
    n = {"q": 0}

    class Conn:
        def execute(self, stmt, params=None):
            n["q"] += 1
            sql = str(stmt).upper()
            assert "COUNT(" not in sql
            return SimpleNamespace(
                mappings=lambda: SimpleNamespace(all=lambda: [{"name": "흥덕구"}])
            )

    kwargs = dict(
        table="built_transactions",
        addr1="충청북도",
        addr2="청주시",
        asset_type=None,
    )
    first = list_gu_names(Conn(), **kwargs)
    second = list_gu_names(Conn(), **kwargs)
    assert first == second
    assert first[0]["name"] == "흥덕구"
    assert first[0]["count"] == 0
    assert first[0]["disabled"] is False
    assert n["q"] == 1
