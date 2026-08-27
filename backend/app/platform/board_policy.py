"""게시판 상태·검색 규칙 (라우터와 테스트가 같이 씀)."""

from __future__ import annotations

PRODUCTS = frozenset({"macro", "fieldnote", "viewer", "general"})
CATEGORIES = frozenset({"question", "bug", "feature"})
STATUSES = frozenset({"open", "checking", "answered", "planned", "done"})
AUTHOR_STATUSES = frozenset({"open", "answered"})
EXCERPT_LEN = 80


def excerpt_text(body: str, max_len: int = EXCERPT_LEN) -> str:
    normalized = " ".join(str(body or "").split())
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[:max_len]}…"


def like_pattern(q: str) -> str:
    cleaned = " ".join(q.split())[:80]
    cleaned = cleaned.replace("%", "").replace("_", "").replace("\\", "")
    return f"%{cleaned}%"


def can_set_status(*, role: str, is_author: bool, new_status: str) -> bool:
    if new_status not in STATUSES:
        return False
    if role == "admin":
        return True
    if is_author and new_status in AUTHOR_STATUSES:
        return True
    return False
