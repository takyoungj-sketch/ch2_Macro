"""플랫폼 OAuth next / 결제 가드."""

from app.platform.oauth_next import DEFAULT_NEXT, safe_oauth_next


def test_safe_oauth_next_relative():
    assert safe_oauth_next("/") == "/"
    assert safe_oauth_next("/board/") == "/board/"
    assert safe_oauth_next("/subscribe/") == "/subscribe/"


def test_safe_oauth_next_rejects_open_redirect():
    assert safe_oauth_next("https://evil.example") == DEFAULT_NEXT
    assert safe_oauth_next("//evil.example") == DEFAULT_NEXT
    assert safe_oauth_next("evil") == DEFAULT_NEXT


def test_safe_oauth_next_fieldnote_scheme():
    assert safe_oauth_next("app:ch2fieldnote://oauth-callback") == "app:ch2fieldnote://oauth-callback"
    assert safe_oauth_next("app:https://evil.example") == DEFAULT_NEXT
