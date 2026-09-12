"""통합 게시판 API — PostgreSQL."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.platform.board_policy import (
    CATEGORIES,
    PRODUCTS,
    SECRET_EXCERPT,
    STATUSES,
    can_delete_comment,
    can_delete_post,
    can_edit_comment,
    can_edit_post,
    can_set_status,
    can_view_secret_body,
    excerpt_text,
    like_pattern,
)
from app.platform.db import get_platform_db
from app.platform.deps import CurrentUser, get_optional_user, require_user

router = APIRouter(prefix="/board", tags=["platform-board"])


class PostCreate(BaseModel):
    product: Literal["macro", "fieldnote", "viewer", "general"]
    category: Literal["question", "bug", "feature"]
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=12000)
    author_name: str | None = Field(default=None, max_length=80)
    is_pinned: bool = False
    is_secret: bool = False


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    author_name: str | None = Field(default=None, max_length=80)


class PostPatch(BaseModel):
    status: Literal["open", "checking", "answered", "planned", "done"] | None = None
    is_pinned: bool | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=12000)
    is_secret: bool | None = None


class CommentPatch(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


def _can_see_body(row: dict, user: CurrentUser | None) -> bool:
    return can_view_secret_body(
        is_secret=bool(row.get("is_secret")),
        role=user.role if user else None,
        user_id=user.id if user else None,
        author_id=int(row["user_id"]),
    )


def _post_row_to_api(
    row: dict,
    nickname: str,
    *,
    include_body: bool,
    user: CurrentUser | None,
) -> dict:
    is_secret = bool(row.get("is_secret"))
    can_see = _can_see_body(row, user)
    out = {
        "id": int(row["id"]),
        "product": row["product"],
        "category": row["category"],
        "title": row["title"],
        "author_name": nickname,
        "author_id": int(row["user_id"]),
        "auth_provider": str(row.get("provider") or "google"),
        "status": row["status"],
        "is_pinned": bool(row.get("is_pinned")),
        "is_secret": is_secret,
        "comment_count": int(row["comment_count"]) if row.get("comment_count") is not None else 0,
        "created_at": row["created_at"].isoformat().replace("+00:00", "Z"),
        "updated_at": row["updated_at"].isoformat().replace("+00:00", "Z"),
        "can_delete": bool(user)
        and can_delete_post(role=user.role, user_id=user.id, author_id=int(row["user_id"])),
        "can_edit": bool(user)
        and can_edit_post(role=user.role, user_id=user.id, author_id=int(row["user_id"])),
    }
    if include_body:
        out["body"] = row["body"] if can_see else None
        out["body_hidden"] = not can_see
        out["can_comment"] = can_see
    elif can_see:
        out["excerpt"] = excerpt_text(str(row["body"]))
    else:
        out["excerpt"] = SECRET_EXCERPT
    return out


def _comment_to_api(row: dict, *, user: CurrentUser | None, nickname: str | None = None) -> dict:
    author_id = int(row["user_id"])
    return {
        "id": int(row["id"]),
        "post_id": int(row["post_id"]),
        "body": row["body"],
        "author_name": nickname if nickname is not None else str(row["nickname"]),
        "author_id": author_id,
        "auth_provider": str(row.get("provider") or "google"),
        "created_at": row["created_at"].isoformat().replace("+00:00", "Z"),
        "can_delete": bool(user)
        and can_delete_comment(role=user.role, user_id=user.id, author_id=author_id),
        "can_edit": bool(user)
        and can_edit_comment(role=user.role, user_id=user.id, author_id=author_id),
    }


_LIST_SELECT = """
            SELECT p.*, u.nickname, u.provider,
                   (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count
            FROM posts p
            JOIN users u ON u.id = p.user_id
"""


def _neighbor_item(row) -> dict | None:
    if not row:
        return None
    return {"id": int(row["id"]), "title": str(row["title"])}


def _post_neighbors(db: Session, *, post_id: int, created_at) -> dict:
    newer = db.execute(
        text(
            """
            SELECT id, title FROM posts
            WHERE (created_at, id) > (:ts, :id)
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """
        ),
        {"ts": created_at, "id": post_id},
    ).mappings().first()
    older = db.execute(
        text(
            """
            SELECT id, title FROM posts
            WHERE (created_at, id) < (:ts, :id)
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ),
        {"ts": created_at, "id": post_id},
    ).mappings().first()
    return {"newer": _neighbor_item(newer), "older": _neighbor_item(older)}


@router.get("/meta")
def board_meta():
    kakao_on = bool(
        (settings.kakao_client_id or settings.kakao_rest_api_key or "").strip()
        and (settings.kakao_client_secret or "").strip()
    )
    google_on = bool(settings.google_client_id)
    providers = [p for p, on in (("google", google_on), ("kakao", kakao_on)) if on]
    return {
        "products": sorted(PRODUCTS),
        "categories": sorted(CATEGORIES),
        "statuses": sorted(STATUSES),
        "auth": {
            "enabled": bool(providers),
            "providers": providers,
            "note": (
                "Google 또는 Kakao 로그인으로 글·댓글을 작성할 수 있습니다."
                if providers
                else "소셜 로그인 설정 중입니다."
            ),
        },
    }


@router.get("/posts")
def list_posts(
    db: Session = Depends(get_platform_db),
    user: CurrentUser | None = Depends(get_optional_user),
    product: str | None = None,
    category: str | None = None,
    status: str | None = None,
    q: str | None = None,
    mine: bool = False,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
):
    if mine and user is None:
        raise HTTPException(401, "로그인이 필요합니다.")

    clauses = ["p.is_pinned = FALSE"]
    params: dict = {
        "viewer_id": user.id if user else 0,
        "is_admin": bool(user and user.role == "admin"),
    }
    if product and product in PRODUCTS:
        clauses.append("p.product = :product")
        params["product"] = product
    if category and category in CATEGORIES:
        clauses.append("p.category = :category")
        params["category"] = category
    if status and status in STATUSES:
        clauses.append("p.status = :status")
        params["status"] = status
    if q and q.strip():
        clauses.append(
            """(
                p.title ILIKE :q
                OR (
                    p.body ILIKE :q
                    AND (
                        p.is_secret = FALSE
                        OR p.user_id = :viewer_id
                        OR :is_admin = TRUE
                    )
                )
            )"""
        )
        params["q"] = like_pattern(q)
    if mine and user is not None:
        clauses.append("p.user_id = :uid")
        params["uid"] = user.id
    where = " AND ".join(clauses)
    total = db.execute(
        text(f"SELECT COUNT(*) FROM posts p WHERE {where}"),
        params,
    ).scalar() or 0
    offset = (page - 1) * pageSize
    rows = db.execute(
        text(
            f"""
            {_LIST_SELECT}
            WHERE {where}
            ORDER BY p.created_at DESC
            LIMIT :lim OFFSET :off
            """
        ),
        {**params, "lim": pageSize, "off": offset},
    ).mappings().all()
    items = [
        _post_row_to_api(dict(r), str(r["nickname"]), include_body=False, user=user)
        for r in rows
    ]

    notices: list[dict] = []
    if page == 1 and not mine:
        notice_rows = db.execute(
            text(
                f"""
                {_LIST_SELECT}
                WHERE p.is_pinned = TRUE
                ORDER BY p.created_at DESC
                LIMIT 8
                """
            )
        ).mappings().all()
        notices = [
            _post_row_to_api(dict(r), str(r["nickname"]), include_body=False, user=user)
            for r in notice_rows
        ]

    total_pages = max(1, (int(total) + pageSize - 1) // pageSize)
    return {
        "notices": notices,
        "items": items,
        "total": int(total),
        "page": page,
        "pageSize": pageSize,
        "totalPages": total_pages,
    }


@router.get("/posts/{post_id}")
def get_post(
    post_id: int,
    db: Session = Depends(get_platform_db),
    user: CurrentUser | None = Depends(get_optional_user),
):
    row = db.execute(
        text(
            f"""
            {_LIST_SELECT}
            WHERE p.id = :id
            """
        ),
        {"id": post_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "post_not_found")
    can_see = _can_see_body(dict(row), user)
    comment_items: list[dict] = []
    if can_see:
        comments = db.execute(
            text(
                """
                SELECT c.*, u.nickname, u.provider
                FROM comments c
                JOIN users u ON u.id = c.user_id
                WHERE c.post_id = :pid
                ORDER BY c.created_at ASC
                """
            ),
            {"pid": post_id},
        ).mappings().all()
        comment_items = [_comment_to_api(dict(c), user=user) for c in comments]
    return {
        "post": _post_row_to_api(dict(row), str(row["nickname"]), include_body=True, user=user),
        "comments": comment_items,
        "neighbors": _post_neighbors(db, post_id=post_id, created_at=row["created_at"]),
    }


@router.post("/posts")
def create_post(
    body: PostCreate,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    pinned = bool(body.is_pinned) if user.role == "admin" else False
    row = db.execute(
        text(
            """
            INSERT INTO posts (user_id, product, category, title, body, status, is_pinned, is_secret)
            VALUES (:uid, :product, :category, :title, :body, 'open', :pinned, :secret)
            RETURNING *
            """
        ),
        {
            "uid": user.id,
            "product": body.product,
            "category": body.category,
            "title": body.title.strip(),
            "body": body.body.strip(),
            "pinned": pinned,
            "secret": bool(body.is_secret),
        },
    ).mappings().first()
    db.commit()
    payload = dict(row)
    payload["comment_count"] = 0
    payload["provider"] = user.provider
    return {"post": _post_row_to_api(payload, user.nickname, include_body=True, user=user)}


@router.post("/posts/{post_id}/comments")
def create_comment(
    post_id: int,
    body: CommentCreate,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    post = db.execute(
        text("SELECT id, user_id, is_secret FROM posts WHERE id=:id"),
        {"id": post_id},
    ).mappings().first()
    if not post:
        raise HTTPException(404, "post_not_found")
    if not _can_see_body(dict(post), user):
        raise HTTPException(403, "비밀글에는 댓글을 달 수 없습니다.")
    row = db.execute(
        text(
            """
            INSERT INTO comments (post_id, user_id, body)
            VALUES (:pid, :uid, :body)
            RETURNING *
            """
        ),
        {"pid": post_id, "uid": user.id, "body": body.body.strip()},
    ).mappings().first()
    db.execute(
        text("UPDATE posts SET updated_at=now() WHERE id=:id"),
        {"id": post_id},
    )
    db.commit()
    payload = dict(row)
    payload["provider"] = user.provider
    return {"comment": _comment_to_api(payload, user=user, nickname=user.nickname)}


@router.delete("/posts/{post_id}/comments/{comment_id}")
def delete_comment(
    post_id: int,
    comment_id: int,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    row = db.execute(
        text("SELECT id, post_id, user_id FROM comments WHERE id=:id AND post_id=:pid"),
        {"id": comment_id, "pid": post_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "comment_not_found")
    if not can_delete_comment(role=user.role, user_id=user.id, author_id=int(row["user_id"])):
        raise HTTPException(403, "forbidden")
    db.execute(text("DELETE FROM comments WHERE id=:id"), {"id": comment_id})
    db.execute(
        text("UPDATE posts SET updated_at=now() WHERE id=:id"),
        {"id": post_id},
    )
    db.commit()
    return {"ok": True}


@router.patch("/posts/{post_id}/comments/{comment_id}")
def patch_comment(
    post_id: int,
    comment_id: int,
    body: CommentPatch,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    row = db.execute(
        text(
            """
            SELECT c.id, c.post_id, c.user_id, c.body, c.created_at, u.nickname, u.provider
            FROM comments c
            JOIN users u ON u.id = c.user_id
            WHERE c.id=:id AND c.post_id=:pid
            """
        ),
        {"id": comment_id, "pid": post_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "comment_not_found")
    if not can_edit_comment(role=user.role, user_id=user.id, author_id=int(row["user_id"])):
        raise HTTPException(403, "forbidden")
    post = db.execute(
        text("SELECT user_id, is_secret FROM posts WHERE id=:id"),
        {"id": post_id},
    ).mappings().first()
    if not post:
        raise HTTPException(404, "post_not_found")
    if not _can_see_body(dict(post), user):
        raise HTTPException(403, "forbidden")
    updated = db.execute(
        text(
            """
            UPDATE comments SET body=:body
            WHERE id=:id
            RETURNING id, post_id, user_id, body, created_at
            """
        ),
        {"id": comment_id, "body": body.body.strip()},
    ).mappings().first()
    db.execute(
        text("UPDATE posts SET updated_at=now() WHERE id=:id"),
        {"id": post_id},
    )
    db.commit()
    payload = dict(updated)
    payload["nickname"] = row["nickname"]
    payload["provider"] = row["provider"]
    return {"comment": _comment_to_api(payload, user=user)}


@router.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    row = db.execute(
        text("SELECT user_id FROM posts WHERE id=:id"),
        {"id": post_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "post_not_found")
    if not can_delete_post(role=user.role, user_id=user.id, author_id=int(row["user_id"])):
        raise HTTPException(403, "forbidden")
    db.execute(text("DELETE FROM posts WHERE id=:id"), {"id": post_id})
    db.commit()
    return {"ok": True}


@router.patch("/posts/{post_id}")
def patch_post(
    post_id: int,
    body: PostPatch,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    row = db.execute(
        text("SELECT user_id FROM posts WHERE id=:id"),
        {"id": post_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "post_not_found")
    owner_id = int(row["user_id"])
    is_author = owner_id == user.id
    if user.role != "admin" and not is_author:
        raise HTTPException(403, "forbidden")

    sets: list[str] = ["updated_at=now()"]
    params: dict = {"id": post_id}
    if body.status is not None:
        if not can_set_status(role=user.role, is_author=is_author, new_status=body.status):
            raise HTTPException(403, "status_forbidden")
        sets.append("status=:st")
        params["st"] = body.status
    if body.is_pinned is not None:
        if user.role != "admin":
            raise HTTPException(403, "pin_forbidden")
        sets.append("is_pinned=:pin")
        params["pin"] = body.is_pinned
    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(400, "empty_title")
        sets.append("title=:title")
        params["title"] = title
    if body.body is not None:
        content = body.body.strip()
        if not content:
            raise HTTPException(400, "empty_body")
        sets.append("body=:body")
        params["body"] = content
    if body.is_secret is not None:
        sets.append("is_secret=:secret")
        params["secret"] = bool(body.is_secret)
    if (
        body.status is None
        and body.is_pinned is None
        and body.title is None
        and body.body is None
        and body.is_secret is None
    ):
        raise HTTPException(400, "empty_patch")

    updated = db.execute(
        text(
            f"""
            UPDATE posts SET {", ".join(sets)}
            WHERE id=:id
            RETURNING *
            """
        ),
        params,
    ).mappings().first()
    db.commit()
    payload = dict(updated)
    count = db.execute(
        text("SELECT COUNT(*) FROM comments WHERE post_id=:id"),
        {"id": post_id},
    ).scalar() or 0
    payload["comment_count"] = int(count)
    payload["provider"] = user.provider
    return {"post": _post_row_to_api(payload, user.nickname, include_body=True, user=user)}
