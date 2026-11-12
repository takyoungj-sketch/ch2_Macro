"""옛 단지 키 요청 처리 (집합 2단계 — 단지 키 이전, D-084).

키 이전 뒤 옛 키(호남 옛 시도명 키·분할 전 키)로 들어온 요청을 연결표로 풀어 준다.
  - 1:1(호남 표준화 등): 경로·쿼리의 키를 새 키로 바꿔 처리하고 응답 헤더
    `X-CH2-Key-Remapped: <옛키>-><새키>` 를 붙인다.
  - 1:N(분할): 분석하지 않고 409 + `{"detail": {"key_status": "split", "candidates": [...]}}`.
  - 연결표에 없거나 표가 없으면(이전 전) 그대로 통과.
대상: /api/collective/buildings/{key}/…, /api/collective/analysis/hedonic/buildings/{key}/…,
      /api/rent/buildings/{key}/…, 그리고 이 앱들의 query `building_key`.
연결표: 집합 DB `collective_building_key_map`, 임대 DB `rent_building_key_map`(migrate_p2_keys.py 가 만든다).
`CH2_KEY_REMAP_ENABLED=0` 이면 끈다.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode

from sqlalchemy import text

_LOG = logging.getLogger(__name__)

_PATH_RE = re.compile(
    r"^(?P<prefix>/api/(?P<app>collective|rent)(?:/analysis/hedonic)?/buildings/)(?P<key>[0-9a-f]{64})(?P<rest>/.*)?$"
)
_APP_RE = re.compile(r"^/api/(?P<app>collective|rent)(/|$)")
_TTL = 600.0

KeyMap = dict[str, list[tuple[str, int, int]]]  # old -> [(new, split_part, n_tx)]


def _load_from_engine(engine, table: str) -> KeyMap:
    out: KeyMap = {}
    if engine is None:
        return out
    with engine.connect() as c:
        if not c.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{table}"}).scalar():
            return out
        for old, new, part, n in c.execute(text(f"SELECT old_key, new_key, split_part, coalesce(n_tx, 0) FROM {table}")):
            out.setdefault(str(old), []).append((str(new), int(part or 0), int(n or 0)))
    for v in out.values():
        v.sort(key=lambda x: (x[1] or 10**6, -x[2]))
    return out


def _default_loader(app: str) -> KeyMap:
    if app == "rent":
        from app.rent.db import get_rent_engine

        return _load_from_engine(get_rent_engine(), "rent_building_key_map")
    from app.collective.db import get_collective_engine

    return _load_from_engine(get_collective_engine(), "collective_building_key_map")


def _default_details(app: str, keys: list[str]) -> dict[str, dict[str, Any]]:
    """분할 후보 표시용(집합만): 최신 as_of 5년 mart 의 이름·주소·건수."""
    if app != "collective" or not keys:
        return {}
    from app.collective.db import get_collective_engine

    eng = get_collective_engine()
    if eng is None:
        return {}
    with eng.connect() as c:
        rows = c.execute(text("""
            SELECT DISTINCT ON (building_key) building_key, display_name, addr3, addr4, addr5, count
            FROM collective_building_stats WHERE building_key = ANY(:k)
            ORDER BY building_key, as_of_month DESC, window_years DESC"""), {"k": keys}).mappings().all()
    return {r["building_key"]: {"display_name": r["display_name"], "addr3": r["addr3"], "addr4": r["addr4"],
                                "addr5": r["addr5"], "n_tx_window": int(r["count"] or 0)} for r in rows}


class KeyMapCache:
    def __init__(self, loader: Callable[[str], KeyMap] = _default_loader, ttl: float = _TTL):
        self._loader = loader
        self._ttl = ttl
        self._data: dict[str, tuple[float, KeyMap]] = {}
        self._lock = threading.Lock()

    def get(self, app: str) -> KeyMap:
        now = time.monotonic()
        with self._lock:
            hit = self._data.get(app)
            if hit and now - hit[0] < self._ttl:
                return hit[1]
        try:
            m = self._loader(app)
        except Exception:  # noqa: BLE001 — 연결표 조회 실패는 요청을 막지 않는다
            _LOG.exception("key_remap: %s 연결표 로드 실패 — 통과", app)
            m = {}
        with self._lock:
            self._data[app] = (now, m)
        return m

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


CACHE = KeyMapCache()


class KeyRemapMiddleware:
    def __init__(self, app, cache: KeyMapCache | None = None,
                 details: Callable[[str, list[str]], dict[str, dict[str, Any]]] = _default_details):
        self.app = app
        self.cache = cache or CACHE
        self.details = details

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or os.environ.get("CH2_KEY_REMAP_ENABLED", "1") == "0":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        am = _APP_RE.match(path)
        if not am:
            await self.app(scope, receive, send)
            return
        app_name = am.group("app")
        import anyio

        kmap = await anyio.to_thread.run_sync(self.cache.get, app_name)
        if not kmap:
            await self.app(scope, receive, send)
            return
        remapped: list[tuple[str, str]] = []
        m = _PATH_RE.match(path)
        if m and m.group("key") in kmap:
            old = m.group("key")
            news = kmap[old]
            if len(news) > 1:
                await self._send_split(send, app_name, old, news)
                return
            new = news[0][0]
            new_path = f"{m.group('prefix')}{new}{m.group('rest') or ''}"
            scope = dict(scope)
            scope["path"] = new_path
            scope["raw_path"] = new_path.encode("utf-8")
            remapped.append((old, new))
        qs = scope.get("query_string") or b""
        if b"building_key=" in qs:
            pairs = parse_qsl(qs.decode("latin-1"), keep_blank_values=True)
            changed = False
            out_pairs = []
            for k, v in pairs:
                if k == "building_key" and v in kmap:
                    news = kmap[v]
                    if len(news) > 1:
                        await self._send_split(send, app_name, v, news)
                        return
                    remapped.append((v, news[0][0]))
                    v = news[0][0]
                    changed = True
                out_pairs.append((k, v))
            if changed:
                scope = dict(scope)
                scope["query_string"] = urlencode(out_pairs).encode("latin-1")
        if not remapped:
            await self.app(scope, receive, send)
            return
        hdr = ",".join(f"{o}->{n}" for o, n in remapped).encode("latin-1")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((b"x-ch2-key-remapped", hdr))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _send_split(self, send, app_name: str, old: str, news: list[tuple[str, int, int]]) -> None:
        import anyio

        try:
            det = await anyio.to_thread.run_sync(self.details, app_name, [n for n, _p, _c in news])
        except Exception:  # noqa: BLE001
            det = {}
        body = {"detail": {
            "key_status": "split",
            "message": "이 단지 키는 서로 다른 단지가 섞여 있어 동별로 나뉘었습니다. 후보 중 하나를 고르세요.",
            "old_key": old,
            "candidates": [{"building_key": n, "split_part": p, "n_tx": c, **det.get(n, {})} for n, p, c in news],
        }}
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        await send({"type": "http.response.start", "status": 409,
                    "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                (b"content-length", str(len(raw)).encode())]})
        await send({"type": "http.response.body", "body": raw})
