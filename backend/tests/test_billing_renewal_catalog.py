"""FN-006: the cron entry point runs one renewal pass and does not price old plans."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def test_renewal_entrypoint_calls_due_processing_without_real_io(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location(
        "fn006_billing_renewal", Path(__file__).resolve().parents[1] / "scripts/platform_billing_renewal.py"
    )
    renewal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renewal)
    closed = []
    db = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(renewal, "get_platform_session_factory", lambda: lambda: db)
    calls = []

    def renew(session):
        assert session is db
        calls.append(session)
        return 4

    monkeypatch.setattr(renewal, "renew_due_subscriptions", renew)
    assert renewal.main() == 0
    assert calls == [db]
    assert closed == [True]
    assert "OK: renewed 4" in capsys.readouterr().out
