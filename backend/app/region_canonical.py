# -*- coding: utf-8 -*-
"""Backend re-export of pipeline.region_canonical (D-028)."""
from __future__ import annotations

import sys
from pathlib import Path

_PIPE = Path(__file__).resolve().parents[2] / "pipeline"
if str(_PIPE) not in sys.path:
    sys.path.insert(0, str(_PIPE))

from region_canonical import (  # noqa: E402
    RESOLVE_CHANGE_TYPES,
    RESOLVER_VERSION,
    RegionCodeHistorySnapshot,
    build_history_snapshot,
    canonical_prefix_expr,
    canonical_select_expr,
    expand_to_ledger_codes,
    expand_to_ledger_codes_pure,
    is_canonical,
    is_canonical_pure,
    load_history_snapshot,
    lookup_active_admin_codes_by_name,
    lookup_active_beopjungri_by_ri_picks,
    normalize_code,
    normalize_result_codes,
    normalize_result_codes_pure,
    region_codes_join_on_canonical,
    resolve_to_canonical,
    resolve_to_canonical_pure,
)

__all__ = [
    "RESOLVE_CHANGE_TYPES",
    "RESOLVER_VERSION",
    "RegionCodeHistorySnapshot",
    "build_history_snapshot",
    "canonical_prefix_expr",
    "canonical_select_expr",
    "expand_to_ledger_codes",
    "expand_to_ledger_codes_pure",
    "is_canonical",
    "is_canonical_pure",
    "load_history_snapshot",
    "lookup_active_admin_codes_by_name",
    "lookup_active_beopjungri_by_ri_picks",
    "normalize_code",
    "normalize_result_codes",
    "normalize_result_codes_pure",
    "region_codes_join_on_canonical",
    "resolve_to_canonical",
    "resolve_to_canonical_pure",
]
