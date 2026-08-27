"""Google OAuth + 세션."""

from __future__ import annotations

import json
import logging
import secrets
import urllib.parse
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.platform.db import get_platform_db
from app.platform.deps import CurrentUser, get_optional_user, require_user
from app.platform.entitlements import list_entitlements
from app.platform.jwt_util import COOKIE_NAME, create_access_token
from app.platform.oauth_next import DEFAULT_NEXT, safe_oauth_next

router = APIRouter(prefix="/auth", tags=["platform-auth"])
_log = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_REDACT_TOKEN_KEYS = frozenset({"access_token", "refresh_token", "id_token"})


def _redact_oauth_body(raw: str) -> str:
    """토큰 응답 로그 — access/refresh/id_token 값만 마스킹."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:2000]
    if isinstance(data, dict):
        sanitized = {
            k: ("[REDACTED]" if k in _REDACT_TOKEN_KEYS else v)
            for k, v in data.items()
        }
        return json.dumps(sanitized, ensure_ascii=False)
    return raw[:2000]


def _log_google_authorize_url(url: str, params: dict[str, str]) -> None:
    _log.info(
        "Google OAuth authorize redirect | client_id=%s redirect_uri=%s response_type=%s scope=%s | full_url=%s",
        params.get("client_id"),
        params.get("redirect_uri"),
        params.get("response_type"),
        params.get("scope"),
        url,
    )


def _log_google_http_response(label: str, response: httpx.Response) -> None:
    body = response.text or ""
    logged_body = _redact_oauth_body(body) if label == "token" else body[:2000]
    _log.info(
        "Google OAuth %s endpoint | status=%s body=%s",
        label,
        response.status_code,
        logged_body,
    )


class NicknameUpdate(BaseModel):
    nickname: str = Field(min_length=2, max_length=80)


def _cookie_domain() -> str | None:
    d = (settings.platform_cookie_domain or "").strip()
    return d or None


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.platform_cookie_secure,
        samesite="lax",
        domain=_cookie_domain(),
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def _nickname_from_email(email: str) -> str:
    local = email.split("@")[0][:40] or "user"
    return f"{local}{secrets.randbelow(9000) + 1000}"


@router.get("/google/login")
def google_login(_request: Request, next: str | None = None, state: str | None = None):
    if not settings.google_client_id:
        raise HTTPException(503, "Google OAuth 미설정")
    dest = safe_oauth_next(next or state)
    redirect_uri = settings.google_oauth_redirect_uri
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
        "state": dest,
    }
    url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    _log_google_authorize_url(url, params)
    return Response(status_code=307, headers={"Location": url})


@router.get("/google/callback")
def google_callback(
    code: str,
    state: str = DEFAULT_NEXT,
    db: Session = Depends(get_platform_db),
):
    state = safe_oauth_next(state)
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503, "Google OAuth 미설정")
    redirect_uri = settings.google_oauth_redirect_uri
    with httpx.Client(timeout=30.0) as client:
        token_res = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        _log_google_http_response("token", token_res)
        if token_res.status_code >= 400:
            raise HTTPException(400, "Google 토큰 교환 실패")
        tokens = token_res.json()
        access = tokens.get("access_token")
        if not access:
            raise HTTPException(400, "Google access_token 없음")
        user_res = client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access}"},
        )
        _log_google_http_response("userinfo", user_res)
        if user_res.status_code >= 400:
            raise HTTPException(400, "Google 사용자 정보 조회 실패")
        profile = user_res.json()

    sub = str(profile.get("sub") or "")
    email = str(profile.get("email") or "").strip().lower()
    if not sub or not email:
        raise HTTPException(400, "Google 프로필 불완전")

    row = db.execute(
        text("SELECT id, email, nickname, role FROM users WHERE provider='google' AND provider_sub=:sub"),
        {"sub": sub},
    ).mappings().first()

    if row:
        user_id = int(row["id"])
        nickname = str(row["nickname"])
        role = str(row["role"])
    else:
        nickname = _nickname_from_email(email)
        for _ in range(5):
            try:
                ins = db.execute(
                    text(
                        """
                        INSERT INTO users (email, provider, provider_sub, nickname, role)
                        VALUES (:email, 'google', :sub, :nick, 'member')
                        RETURNING id, nickname, role
                        """
                    ),
                    {"email": email, "sub": sub, "nick": nickname},
                ).mappings().first()
                db.commit()
                user_id = int(ins["id"])
                nickname = str(ins["nickname"])
                role = str(ins["role"])
                break
            except Exception:
                db.rollback()
                nickname = _nickname_from_email(email)
        else:
            raise HTTPException(500, "회원 생성 실패")

    jwt_token = create_access_token(user_id=user_id, email=email, nickname=nickname, role=role)
    if (state or "").startswith("app:"):
        app_redirect = state[4:]
        sep = "&" if "?" in app_redirect else "?"
        target = f"{app_redirect}{sep}token={urllib.parse.quote(jwt_token)}"
        return Response(status_code=307, headers={"Location": target})
    response = Response(status_code=307, headers={"Location": state or "/board/"})
    _set_session_cookie(response, jwt_token)
    return response


@router.get("/me")
def auth_me(user: CurrentUser = Depends(require_user)):
    return {
        "id": user.id,
        "nickname": user.nickname,
        "role": user.role,
    }


@router.get("/entitlements")
def auth_entitlements(
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    ent = list_entitlements(db, user.id)
    return {
        "user_id": user.id,
        "products": ent,
        "fieldnote": ent.get("fieldnote", False),
        "macro": ent.get("macro", False),
    }


@router.patch("/me")
def update_me(
    body: NicknameUpdate,
    user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_platform_db),
):
    nick = body.nickname.strip()
    try:
        db.execute(
            text("UPDATE users SET nickname=:nick, updated_at=now() WHERE id=:id"),
            {"nick": nick, "id": user.id},
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(409, "닉네임이 이미 사용 중입니다.") from exc
    return {"nickname": nick}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/", domain=_cookie_domain())
    return {"ok": True}


@router.get("/status")
def auth_status(user: Annotated[CurrentUser | None, Depends(get_optional_user)]):
    if user is None:
        return {"logged_in": False}
    return {"logged_in": True, "id": user.id, "nickname": user.nickname, "role": user.role}
