"""토스 심사용 이메일·비밀번호 로그인 — 값은 env에만 두고 git에 넣지 않는다."""

from __future__ import annotations

from app.platform.staff_login import (
    clear_failures,
    passwords_match,
    record_failure,
    too_many_attempts,
)


def review_login_configured(email: str, password: str) -> bool:
    return bool((email or "").strip() and (password or "").strip())


def review_credentials_match(expected_email: str, expected_password: str, submitted_email: str, submitted_password: str) -> bool:
    exp_mail = (expected_email or "").strip().lower()
    sub_mail = (submitted_email or "").strip().lower()
    if not exp_mail or sub_mail != exp_mail:
        return False
    return passwords_match(expected_password, submitted_password)


__all__ = [
    "clear_failures",
    "record_failure",
    "too_many_attempts",
    "review_login_configured",
    "review_credentials_match",
]
