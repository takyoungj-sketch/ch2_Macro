"""게시판 상태·검색·비밀글·삭제 규칙."""

from datetime import datetime, timezone

from app.platform.board_policy import (
    SECRET_EXCERPT,
    can_delete_comment,
    can_delete_post,
    can_set_status,
    can_view_secret_body,
    excerpt_text,
    like_pattern,
)
from app.platform.board_router import _post_row_to_api
from app.platform.deps import CurrentUser


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


def test_can_view_secret_body():
    assert can_view_secret_body(is_secret=False, role=None, user_id=None, author_id=1)
    assert not can_view_secret_body(is_secret=True, role=None, user_id=None, author_id=1)
    assert not can_view_secret_body(is_secret=True, role="member", user_id=9, author_id=1)
    assert can_view_secret_body(is_secret=True, role="member", user_id=1, author_id=1)
    assert can_view_secret_body(is_secret=True, role="admin", user_id=9, author_id=1)


def test_can_delete_post_and_comment():
    assert can_delete_post(role="admin", user_id=9, author_id=1)
    assert can_delete_post(role="member", user_id=1, author_id=1)
    assert not can_delete_post(role="member", user_id=9, author_id=1)
    assert can_delete_comment(role="admin", user_id=9, author_id=1)
    assert can_delete_comment(role="member", user_id=1, author_id=1)
    assert not can_delete_comment(role="member", user_id=9, author_id=1)


def test_can_edit_matches_delete():
    from app.platform.board_policy import can_edit_comment, can_edit_post

    assert can_edit_post(role="admin", user_id=9, author_id=1)
    assert can_edit_post(role="member", user_id=1, author_id=1)
    assert not can_edit_post(role="member", user_id=9, author_id=1)
    assert can_edit_comment(role="member", user_id=1, author_id=1)
    assert not can_edit_comment(role="member", user_id=9, author_id=1)


def _secret_row():
    now = datetime.now(timezone.utc)
    return {
        "id": 1,
        "product": "viewer",
        "category": "bug",
        "title": "오류 제보",
        "body": "secret-body-xyz",
        "user_id": 3,
        "status": "open",
        "is_pinned": False,
        "is_secret": True,
        "comment_count": 2,
        "created_at": now,
        "updated_at": now,
        "provider": "google",
    }


def test_secret_list_hides_excerpt_from_strangers():
    out = _post_row_to_api(_secret_row(), "nick", include_body=False, user=None)
    assert out["excerpt"] == SECRET_EXCERPT
    assert "secret-body" not in str(out)
    assert out["is_secret"] is True
    assert out["can_delete"] is False


def test_secret_detail_hides_body_from_strangers():
    out = _post_row_to_api(_secret_row(), "nick", include_body=True, user=None)
    assert out["body"] is None
    assert out["body_hidden"] is True
    assert out["can_comment"] is False


def test_secret_detail_author_and_admin_see_body():
    author = CurrentUser(id=3, email="a@b.c", nickname="nick", role="member")
    admin = CurrentUser(id=9, email="c@d.e", nickname="admin", role="admin")
    as_author = _post_row_to_api(_secret_row(), "nick", include_body=True, user=author)
    as_admin = _post_row_to_api(_secret_row(), "nick", include_body=True, user=admin)
    assert as_author["body"] == "secret-body-xyz"
    assert as_author["can_delete"] is True
    assert as_author["can_edit"] is True
    assert as_admin["body"] == "secret-body-xyz"
    assert as_admin["can_delete"] is True
    assert as_admin["can_edit"] is True
