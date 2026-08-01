"""통합 게시판 API — PostgreSQL."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.platform.db import get_platform_db
from app.platform.deps import CurrentUser, require_user

router = APIRouter(prefix="/board", tags=["platform-board"])

PRODUCTS = frozenset({"macro", "fieldnote", "viewer", "general"})
CATEGORIES = frozenset({"question", "bug", "feature"})
STATUSES = frozenset({"open", "resolved"})


class PostCreate(BaseModel):
    product: Literal["macro", "fieldnote", "viewer", "general"]
    category: Literal["question", "bug", "feature"]
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=12000)
    author_name: str | None = Field(default=None, max_length=80)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    author_name: str | None = Field(default=None, max_length=80)


class StatusUpdate(BaseModel):
    status: Literal["open", "resolved"]


def _post_row_to_api(row: dict, nickname: str) -> dict:
    return {
        "id": int(row["id"]),
        "product": row["product"],
        "category": row["category"],
        "title": row["title"],
        "body": row["body"],
        "author_name": nickname,
        "author_id": int(row["user_id"]),
        "auth_provider": "google",
        "status": row["status"],
        "created_at": row["created_at"].isoformat().replace("+00:00", "Z"),
        "updated_at": row["updated_at"].isoformat().replace("+00:00", "Z"),
    }


@router.get("/meta")
def board_meta():
    oauth_ready = bool(settings.google_client_id)
    return {
        "products": sorted(PRODUCTS),
        "categories": sorted(CATEGORIES),
        "statuses": sorted(STATUSES),
        "auth": {
            "enabled": oauth_ready,
            "providers": ["google", "kakao"],
            "note": (
                "Google 로그인으로 글·댓글을 작성할 수 있습니다."
                if oauth_ready
                else "소셜 로그인 설정 중입니다."
            ),
        },
    }


@router.get("/posts")
def list_posts(
    db: Session = Depends(get_platform_db),
    product: str | None = None,
    category: str | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
):
    clauses = ["1=1"]
    params: dict = {}
    if product and product in PRODUCTS:
        clauses.append("p.product = :product")
        params["product"] = product
    if category and category in CATEGORIES:
        clauses.append("p.category = :category")
        params["category"] = category
    where = " AND ".join(clauses)
    total = db.execute(
        text(f"SELECT COUNT(*) FROM posts p WHERE {where}"),
        params,
    ).scalar() or 0
    offset = (page - 1) * pageSize
    rows = db.execute(
        text(
            f"""
            SELECT p.*, u.nickname
            FROM posts p
            JOIN users u ON u.id = p.user_id
            WHERE {where}
            ORDER BY p.created_at DESC
            LIMIT :lim OFFSET :off
            """
        ),
        {**params, "lim": pageSize, "off": offset},
    ).mappings().all()
    items = [_post_row_to_api(dict(r), str(r["nickname"])) for r in rows]
    total_pages = max(1, (int(total) + pageSize - 1) // pageSize)
    return {
        "items": items,
        "total": int(total),
        "page": page,
        "pageSize": pageSize,
        "totalPages": total_pages,
    }


@router.get("/posts/{post_id}")
def get_post(post_id: int, db: Session = Depends(get_platform_db)):
    row = db.execute(
        text(
            """
            SELECT p.*, u.nickname
            FROM posts p
            JOIN users u ON u.id = p.user_id
            WHERE p.id = :id
            """
        ),
        {"id": post_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "post_not_found")
    comments = db.execute(
        text(
            """
            SELECT c.*, u.nickname
            FROM comments c
            JOIN users u ON u.id = c.user_id
            WHERE c.post_id = :pid
            ORDER BY c.created_at ASC
            """
        ),
        {"pid": post_id},
    ).mappings().all()
    comment_items = [
        {
            "id": int(c["id"]),
            "post_id": int(c["post_id"]),
            "body": c["body"],
            "author_name": str(c["nickname"]),
            "author_id": int(c["user_id"]),
            "auth_provider": "google",
            "created_at": c["created_at"].isoformat().replace("+00:00", "Z"),
        }
        for c in comments
    ]
    return {
        "post": _post_row_to_api(dict(row), str(row["nickname"])),
        "comments": comment_items,
    }


@router.post("/posts")
def create_post(
    body: PostCreate,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    row = db.execute(
        text(
            """
            INSERT INTO posts (user_id, product, category, title, body, status)
            VALUES (:uid, :product, :category, :title, :body, 'open')
            RETURNING *
            """
        ),
        {
            "uid": user.id,
            "product": body.product,
            "category": body.category,
            "title": body.title.strip(),
            "body": body.body.strip(),
        },
    ).mappings().first()
    db.commit()
    return {"post": _post_row_to_api(dict(row), user.nickname)}


@router.post("/posts/{post_id}/comments")
def create_comment(
    post_id: int,
    body: CommentCreate,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    post = db.execute(text("SELECT id FROM posts WHERE id=:id"), {"id": post_id}).first()
    if not post:
        raise HTTPException(404, "post_not_found")
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
    return {
        "comment": {
            "id": int(row["id"]),
            "post_id": post_id,
            "body": row["body"],
            "author_name": user.nickname,
            "author_id": user.id,
            "auth_provider": "google",
            "created_at": row["created_at"].isoformat().replace("+00:00", "Z"),
        }
    }


@router.patch("/posts/{post_id}")
def patch_post(
    post_id: int,
    body: StatusUpdate,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    row = db.execute(
        text("SELECT user_id FROM posts WHERE id=:id"),
        {"id": post_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "post_not_found")
    if user.role != "admin" and int(row["user_id"]) != user.id:
        raise HTTPException(403, "forbidden")
    updated = db.execute(
        text(
            """
            UPDATE posts SET status=:st, updated_at=now()
            WHERE id=:id
            RETURNING *
            """
        ),
        {"st": body.status, "id": post_id},
    ).mappings().first()
    db.commit()
    return {"post": _post_row_to_api(dict(updated), user.nickname)}
