"""FN-002 C-1: the cron entry point retains existing monthly renewal prices."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def test_renewal_entrypoint_passes_all_monthly_prices_without_real_io(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location(
        "fn002_billing_renewal", Path(__file__).resolve().parents[1] / "scripts/platform_billing_renewal.py"
    )
    renewal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renewal)
    closed = []
    db = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(renewal, "get_platform_session_factory", lambda: lambda: db)
    calls = []

    def renew(session, *, plan_prices, plan_names):
        assert session is db
        calls.append((plan_prices, plan_names))
        return 4

    monkeypatch.setattr(renewal, "renew_due_subscriptions", renew)
    assert renewal.main() == 0
    assert calls == [({
        "ch2_monthly": 10000, "fieldnote_monthly": 10000,
        "macro_monthly": 10000, "bundle_monthly": 15000,
    }, {
        "ch2_monthly": "CH2 bundle month", "fieldnote_monthly": "CH2 fieldnote month",
        "macro_monthly": "CH2 macro month", "bundle_monthly": "CH2 bundle month",
    })]
    assert closed == [True]
    assert "OK: renewed 4" in capsys.readouterr().out
