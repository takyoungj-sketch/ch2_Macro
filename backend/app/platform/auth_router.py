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
    logged_body = _redact_oauth_body(body) if "token" in label else body[:2000]
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


def _nickname_from_seed(seed: str) -> str:
    local = "".join(ch for ch in (seed or "user") if ch.isalnum() or ch in "._-")[:40] or "user"
    return f"{local}{secrets.randbelow(9000) + 1000}"


def _nickname_from_email(email: str) -> str:
    local = email.split("@")[0][:40] or "user"
    return _nickname_from_seed(local)


def _oauth_providers() -> dict[str, bool]:
    kakao_id = (settings.kakao_client_id or settings.kakao_rest_api_key or "").strip()
    return {
        "google": bool(settings.google_client_id),
        "kakao": bool(kakao_id and (settings.kakao_client_secret or "").strip()),
    }


def _kakao_client_id() -> str:
    return (settings.kakao_client_id or settings.kakao_rest_api_key or "").strip()


def _finish_web_or_app_login(*, user_id: int, email: str, nickname: str, role: str, state: str) -> Response:
    jwt_token = create_access_token(user_id=user_id, email=email, nickname=nickname, role=role)
    if (state or "").startswith("app:"):
        app_redirect = state[4:]
        sep = "&" if "?" in app_redirect else "?"
        target = f"{app_redirect}{sep}token={urllib.parse.quote(jwt_token)}"
        return Response(status_code=307, headers={"Location": target})
    response = Response(status_code=307, headers={"Location": state or DEFAULT_NEXT})
    _set_session_cookie(response, jwt_token)
    return response


def _get_or_create_oauth_user(
    db: Session,
    *,
    provider: str,
    sub: str,
    email: str,
    nickname_seed: str,
) -> tuple[int, str, str]:
    row = db.execute(
        text("SELECT id, nickname, role FROM users WHERE provider=:p AND provider_sub=:sub"),
        {"p": provider, "sub": sub},
    ).mappings().first()
    if row:
        return int(row["id"]), str(row["nickname"]), str(row["role"])
    nickname = _nickname_from_seed(nickname_seed)
    for _ in range(5):
        try:
            ins = db.execute(
                text(
                    """
                    INSERT INTO users (email, provider, provider_sub, nickname, role)
                    VALUES (:email, :p, :sub, :nick, 'member')
                    RETURNING id, nickname, role
                    """
                ),
                {"email": email, "p": provider, "sub": sub, "nick": nickname},
            ).mappings().first()
            db.commit()
            return int(ins["id"]), str(ins["nickname"]), str(ins["role"])
        except Exception:
            db.rollback()
            nickname = _nickname_from_seed(nickname_seed)
    raise HTTPException(500, "회원 생성 실패")


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

    user_id, nickname, role = _get_or_create_oauth_user(
        db, provider="google", sub=sub, email=email, nickname_seed=email.split("@")[0]
    )
    return _finish_web_or_app_login(
        user_id=user_id, email=email, nickname=nickname, role=role, state=state
    )


KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"


@router.get("/kakao/login")
def kakao_login(_request: Request, next: str | None = None, state: str | None = None):
    client_id = _kakao_client_id()
    if not client_id or not (settings.kakao_client_secret or "").strip():
        raise HTTPException(503, "카카오 로그인을 준비 중입니다.")
    dest = safe_oauth_next(next or state)
    params = {
        "client_id": client_id,
        "redirect_uri": settings.kakao_oauth_redirect_uri,
        "response_type": "code",
        "state": dest,
    }
    url = f"{KAKAO_AUTH_URL}?{urllib.parse.urlencode(params)}"
    _log.info(
        "Kakao OAuth authorize redirect | client_id_suffix=%s redirect_uri=%s",
        client_id[-6:] if len(client_id) >= 6 else "short",
        settings.kakao_oauth_redirect_uri,
    )
    return Response(status_code=307, headers={"Location": url})


@router.get("/kakao/callback")
def kakao_callback(
    code: str | None = None,
    state: str = DEFAULT_NEXT,
    error: str | None = None,
    db: Session = Depends(get_platform_db),
):
    if error or not code:
        raise HTTPException(400, "카카오 로그인이 취소되었거나 실패했습니다.")
    state = safe_oauth_next(state)
    client_id = _kakao_client_id()
    secret = (settings.kakao_client_secret or "").strip()
    if not client_id or not secret:
        raise HTTPException(503, "카카오 로그인을 준비 중입니다.")
    with httpx.Client(timeout=30.0) as client:
        token_res = client.post(
            KAKAO_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": secret,
                "redirect_uri": settings.kakao_oauth_redirect_uri,
                "code": code,
            },
        )
        _log_google_http_response("kakao-token", token_res)
        if token_res.status_code >= 400:
            raise HTTPException(400, "카카오 토큰 교환 실패")
        tokens = token_res.json()
        access = tokens.get("access_token")
        if not access:
            raise HTTPException(400, "카카오 access_token 없음")
        user_res = client.get(
            KAKAO_USERINFO_URL,
            headers={"Authorization": f"Bearer {access}"},
        )
        _log_google_http_response("kakao-userinfo", user_res)
        if user_res.status_code >= 400:
            raise HTTPException(400, "카카오 사용자 정보 조회 실패")
        profile = user_res.json()

    sub = str(profile.get("id") or "")
    account = profile.get("kakao_account") or {}
    props = profile.get("properties") or {}
    kakao_email = str(account.get("email") or "").strip().lower()
    nick_profile = (account.get("profile") or {}).get("nickname") or props.get("nickname") or ""
    if not sub:
        raise HTTPException(400, "카카오 프로필 불완전")
    email = kakao_email or f"kakao-{sub}@noreply.ch2data.com"
    seed = str(nick_profile or f"kakao{sub}")
    user_id, nickname, role = _get_or_create_oauth_user(
        db, provider="kakao", sub=sub, email=email, nickname_seed=seed
    )
    return _finish_web_or_app_login(
        user_id=user_id, email=email, nickname=nickname, role=role, state=state
    )


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
    providers = _oauth_providers()
    if user is None:
        return {"logged_in": False, "providers": providers}
    return {
        "logged_in": True,
        "id": user.id,
        "nickname": user.nickname,
        "role": user.role,
        "providers": providers,
    }
