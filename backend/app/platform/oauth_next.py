"""OAuth state/next — 상대 경로만 허용 (오픈 리다이렉트 방지)."""

from __future__ import annotations

DEFAULT_NEXT = "/"
_APP_SCHEMES = ("ch2fieldnote://",)


def safe_oauth_next(value: str | None) -> str:
    """Google state / login next 값을 안전한 복귀 경로로 정규화."""
    v = (value or DEFAULT_NEXT).strip()
    if not v:
        return DEFAULT_NEXT
    if v.startswith("app:"):
        rest = v[4:]
        if rest.startswith(_APP_SCHEMES):
            return v
        return DEFAULT_NEXT
    if v.startswith("//") or "://" in v:
        return DEFAULT_NEXT
    if not v.startswith("/"):
        return DEFAULT_NEXT
    return v
