"""관리자 비밀번호 로그인 헬퍼."""

from app.platform.staff_login import (
    clear_failures,
    passwords_match,
    record_failure,
    staff_password_configured,
    too_many_attempts,
)


def test_staff_password_configured():
    assert not staff_password_configured("")
    assert not staff_password_configured("   ")
    assert staff_password_configured("secret")


def test_passwords_match_same_and_different():
    assert passwords_match("abc", "abc")
    assert not passwords_match("abc", "abd")
    assert not passwords_match("abc", "ab")
    assert not passwords_match("", "abc")
    assert not passwords_match("abc", "")


def test_rate_limit_after_five_failures():
    ip = "test-rate-limit-ip"
    clear_failures(ip)
    assert not too_many_attempts(ip)
    for _ in range(5):
        record_failure(ip)
    assert too_many_attempts(ip)
    clear_failures(ip)
    assert not too_many_attempts(ip)
