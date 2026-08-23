"""D-049 지분거래 플래그·필터."""

from __future__ import annotations

from app.built.partial_ownership import apply_partial_ownership_filter, format_partial_n_note


def test_apply_partial_ownership_filter_default_excludes():
    clauses: list[str] = ["is_valid = true"]
    apply_partial_ownership_filter(clauses, include_partial=False)
    assert "is_partial_ownership IS NOT TRUE" in clauses


def test_apply_partial_ownership_filter_include_noop():
    clauses: list[str] = ["is_valid = true"]
    apply_partial_ownership_filter(clauses, include_partial=True)
    assert clauses == ["is_valid = true"]


def test_format_partial_n_note():
    assert format_partial_n_note(include_partial=False, partial_tx_count=89) == "지분 89건 제외"
    assert format_partial_n_note(include_partial=True, partial_tx_count=89) == "지분 89건 포함"
