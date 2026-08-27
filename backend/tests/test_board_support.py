"""게시판 상태·검색 헬퍼."""

from app.platform.board_policy import can_set_status, excerpt_text, like_pattern


def test_excerpt_text_truncates():
    assert excerpt_text("a" * 90).endswith("…")
    assert len(excerpt_text("short")) == 5


def test_like_pattern_strips_wildcards():
    assert like_pattern("  100%_off  ") == "%100off%"


def test_can_set_status_roles():
    assert can_set_status(role="admin", is_author=False, new_status="planned")
    assert can_set_status(role="member", is_author=True, new_status="answered")
    assert can_set_status(role="member", is_author=True, new_status="open")
    assert not can_set_status(role="member", is_author=True, new_status="planned")
    assert not can_set_status(role="member", is_author=False, new_status="answered")
