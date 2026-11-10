"""Monthly supply gates for retries, key identity and warning thresholds."""
from contextlib import nullcontext
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))

import monthly_ledger_supply as supply


def test_same_cycle_reuses_pre_ingest_baseline(monkeypatch, tmp_path):
    conn = Mock()
    db = Mock()
    db.connect.return_value = nullcontext(conn)
    window = Mock(side_effect=[{"same", "gone"}, {"same", "new"}])
    monkeypatch.setattr(supply, "window_keys", window)
    baseline = tmp_path / "before.json.gz"
    args = (db, "land", "2026-09-01", "2026-11-01", baseline)
    supply.capture(*args)
    supply.capture(*args)
    assert supply.read_baseline(baseline, "land", "2026-09-01", "2026-11-01") == {"same", "gone"}
    window.assert_called_once()
    with pytest.raises(ValueError, match="different window"):
        supply.read_baseline(baseline, "land", "2026-08-01", "2026-11-01")


def test_publish_uses_new_and_removed_keys(monkeypatch, tmp_path):
    db = Mock()
    db.connect.return_value = nullcontext(Mock())
    conn = Mock()
    db.begin.return_value = nullcontext(conn)
    monkeypatch.setattr(supply, "read_baseline", lambda *_: {"same", "gone"})
    monkeypatch.setattr(supply, "window_keys", lambda *_: {"same", "new"})
    prepare = Mock(return_value=([], {}))
    reconcile = Mock(return_value=(1, 0))
    monkeypatch.setattr(supply, "prepare", prepare)
    monkeypatch.setattr(supply, "reconcile_orphans", reconcile)
    monkeypatch.setattr(supply, "coverage", lambda *_: [
        {"month": m, "rate": 70, "linked": 7, "eligible": 10, "total": 12}
        for m in ("2026-07", "2026-08", "2026-09", "2026-10")
    ])
    output = tmp_path / "coverage.json"
    supply.publish(db, "land", "2026-09-01", "2026-11-01", "202611", tmp_path / "before", output)
    assert prepare.call_args.args[-1] == {"new"}
    reconcile.assert_called_once_with(conn, "land", {"gone"}, {"new"})
    assert output.is_file()


@pytest.mark.parametrize("latest,expected", [(60, 10.0), (60.01, None), (None, None)])
def test_rate_warning(latest, expected):
    assert supply.rate_warning([{"rate": p} for p in (65, 70, 75, latest)]) == expected
