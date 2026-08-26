"""월간 built 창 purge — 빈 keep 거절, 해시 유지 UPSERT."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from purge_built_contract_window import (  # noqa: E402
    _window_pred,
    _ym_bounds,
    validate_keep_hashes,
)


def test_ym_bounds_ok():
    assert _ym_bounds("202507", "202606") == (202507, 202606)


def test_ym_bounds_rejects_inverted():
    with pytest.raises(ValueError):
        _ym_bounds("202606", "202507")


def test_empty_keep_refused():
    with pytest.raises(ValueError, match="keep-hashes empty"):
        validate_keep_hashes(set())


def test_window_pred_aliases_columns():
    raw = _window_pred()
    assert "t." not in raw
    aliased = _window_pred("t")
    assert "t.contract_year" in aliased
    assert "t.contract_month" in aliased
    assert "BETWEEN :lo AND :hi" in aliased
