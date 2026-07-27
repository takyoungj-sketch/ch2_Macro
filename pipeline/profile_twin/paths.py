from __future__ import annotations

from typing import Any


def get_profile_path(features: dict[str, Any], path: str) -> Any:
    """Dot path into regional_profile.features — e.g. yearly_mix.count_share_by_type."""
    cur: Any = features
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur
