"""로컬 개발에서만 제품 게이트를 생략한다. 사용자·관리자 권한은 부여하지 않는다."""

from urllib.parse import urlsplit

from fastapi import Request

from app.config import settings

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def local_dev_access_enabled(request: Request) -> bool:
    if not getattr(settings, "local_dev_access", False) or (getattr(settings, "api_token", "") or "").strip():
        return False
    if request.client is None or request.client.host not in _LOCAL_HOSTS:
        return False
    if request.url.scheme != "http" or request.url.hostname not in _LOCAL_HOSTS:
        return False
    # 운영 프록시를 거친 요청은 loopback처럼 보여도 허용하지 않는다.
    if any(name in request.headers for name in ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "x-ch2-proxy-token")):
        return False
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != "http" or parsed.hostname not in _LOCAL_HOSTS:
            return False
    return True
