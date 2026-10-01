"""토스 심사용 이메일·비밀번호 로그인 헬퍼."""

from app.platform.review_login import (
    clear_failures,
    record_failure,
    review_credentials_match,
    review_login_configured,
    too_many_attempts,
)


def test_review_login_configured():
    assert not review_login_configured("", "secret")
    assert not review_login_configured("a@b.com", "")
    assert review_login_configured("a@b.com", "secret")


def test_review_credentials_match():
    assert review_credentials_match("review@ch2data.com", "pw", "review@ch2data.com", "pw")
    assert review_credentials_match("review@ch2data.com", "pw", "REVIEW@ch2data.com", "pw")
    assert not review_credentials_match("review@ch2data.com", "pw", "other@ch2data.com", "pw")
    assert not review_credentials_match("review@ch2data.com", "pw", "review@ch2data.com", "bad")


def test_review_rate_limit_after_five_failures():
    ip = "test-review-rate-limit-ip"
    clear_failures(ip)
    assert not too_many_attempts(ip)
    for _ in range(5):
        record_failure(ip)
    assert too_many_attempts(ip)
    clear_failures(ip)
    assert not too_many_attempts(ip)
