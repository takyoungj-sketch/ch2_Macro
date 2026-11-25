"""지역 코드로 비주거 목록이 원장으로 내려갈 때도 롤링 창을 적용한다."""

from datetime import date
from unittest.mock import MagicMock

from app.collective_commercial import router


def _call(monkeypatch, **overrides):
    captured = {}

    def fake_tx_where(**kwargs):
        captured.update(kwargs)
        return "1=1", {}

    monkeypatch.setattr(router, "_tx_where", fake_tx_where)
    monkeypatch.setattr(router, "list_clusters_from_mart", lambda *args, **kwargs: None)
    monkeypatch.setattr(router, "latest_mart_snapshot", lambda conn: (date(2026, 10, 1), 5))
    monkeypatch.setattr(router, "list_clusters_live", lambda conn, where, params: [])
    db = MagicMock()
    db.connection.return_value = MagicMock()
    kwargs = dict(
        db=db,
        asset_type=None,
        addr1="서울특별시",
        addr2="강남구",
        addr3_list=[],
        addr4_list=[],
        region_codes=["1168010100"],
        region_code_level="beopjungri",
        region_addrs=[],
        contract_year_from=None,
        contract_year_to=None,
        window_years=5,
        sort="count",
        page=1,
        page_size=100,
    )
    kwargs.update(overrides)
    router.list_clusters(**kwargs)
    return captured


def test_region_code_live_list_keeps_rolling_window(monkeypatch):
    captured = _call(monkeypatch)
    assert captured["window_years"] == 5


def test_explicit_year_live_list_does_not_add_rolling_window(monkeypatch):
    captured = _call(monkeypatch, contract_year_from=2024, contract_year_to=2025)
    assert captured["window_years"] is None
