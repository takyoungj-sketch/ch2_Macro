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


_QUERY_KEY_APP = {"building_key": None, "sale_building_key": "collective"}  # None = 요청 앱의 연결표
_MAX_BODY = 512 * 1024
SPLIT_MESSAGE = "이 단지 키는 서로 다른 단지가 섞여 있어 동별로 나뉘었습니다. 후보 중 하나를 고르세요."


def resolve_key(app: str, key: str, *, cache: KeyMapCache | None = None,
                details: Callable[[str, list[str]], dict[str, dict[str, Any]]] | None = None) -> dict[str, Any]:
    """동기 조회(AI 도구 등). {status: ok|remapped|split, building_key, candidates}."""
    if os.environ.get("CH2_KEY_REMAP_ENABLED", "1") == "0" or not key:
        return {"status": "ok", "building_key": key, "candidates": []}
    details = details or globals()["_default_details"]
    news = (cache or globals()["CACHE"]).get(app).get(key)
    if not news:
        return {"status": "ok", "building_key": key, "candidates": []}
    if len(news) == 1:
        return {"status": "remapped", "building_key": news[0][0], "candidates": []}
    try:
        det = details(app, [n for n, _p, _c in news])
    except Exception:  # noqa: BLE001
        det = {}
    return {"status": "split", "building_key": key,
            "candidates": [{"building_key": n, "split_part": p, "n_tx": c, **det.get(n, {})} for n, p, c in news]}


def split_detail_text(cands: list[dict[str, Any]]) -> str:
    names = []
    for c in cands[:6]:
        where = " ".join(str(x) for x in (c.get("addr3"), c.get("addr4"), c.get("addr5")) if x)
        nm = c.get("display_name") or "단지"
        names.append(f"{nm}({where}, {c.get('n_tx', 0)}건)" if where else f"{nm}({c.get('n_tx', 0)}건)")
    return SPLIT_MESSAGE + (" 후보: " + ", ".join(names) if names else "")


class _Split(Exception):
    def __init__(self, app: str, old: str, news):
        self.app, self.old, self.news = app, old, news


class KeyRemapMiddleware:
    def __init__(self, app, cache: KeyMapCache | None = None,
                 details: Callable[[str, list[str]], dict[str, dict[str, Any]]] = _default_details):
        self.app = app
        self.cache = cache or CACHE
        self.details = details

    async def _map(self, app_name: str) -> KeyMap:
        import anyio

        return await anyio.to_thread.run_sync(self.cache.get, app_name)

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
        remapped: list[tuple[str, str]] = []

        async def one(app_for: str, k: str) -> str:
            kmap = await self._map(app_for)
            news = kmap.get(k) if kmap else None
            if not news:
                return k
            if len(news) > 1:
                raise _Split(app_for, k, news)
            remapped.append((k, news[0][0]))
            return news[0][0]

        try:
            # 1) 경로 /buildings/{key}/
            m = _PATH_RE.match(path)
            if m:
                new = await one(app_name, m.group("key"))
                if new != m.group("key"):
                    new_path = f"{m.group('prefix')}{new}{m.group('rest') or ''}"
                    scope = dict(scope)
                    scope["path"] = new_path
                    scope["raw_path"] = new_path.encode("utf-8")
            # 2) query building_key · sale_building_key(임대 → 매매 키)
            qs = scope.get("query_string") or b""
            if b"building_key=" in qs:
                pairs = parse_qsl(qs.decode("latin-1"), keep_blank_values=True)
                out_pairs, changed = [], False
                for k, v in pairs:
                    if k in _QUERY_KEY_APP:
                        nv = await one(_QUERY_KEY_APP[k] or app_name, v)
                        changed |= nv != v
                        v = nv
                    out_pairs.append((k, v))
                if changed:
                    scope = dict(scope)
                    scope["query_string"] = urlencode(out_pairs).encode("latin-1")
            # 3) 집합 POST JSON body building_keys(코호트)
            if scope.get("method") == "POST" and app_name == "collective":
                scope = dict(scope)
                _body, receive = await self._maybe_rewrite_body(scope, receive, one)
        except _Split as sp:
            await self._send_split(send, sp.app, sp.old, sp.news)
            return
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

    async def _maybe_rewrite_body(self, scope, receive, one):
        ctype = dict(scope.get("headers") or []).get(b"content-type", b"")
        if b"json" not in ctype:
            return None, receive
        chunks, more, size = [], True, 0
        while more:
            msg = await receive()
            if msg["type"] != "http.request":
                break
            chunks.append(msg.get("body", b""))
            size += len(chunks[-1])
            more = msg.get("more_body", False)
            if size > _MAX_BODY:
                break
        raw = b"".join(chunks)
        out = raw
        if size <= _MAX_BODY and b"building_keys" in raw:
            try:
                data = json.loads(raw)
            except ValueError:
                data = None
            if isinstance(data, dict) and isinstance(data.get("building_keys"), list):
                keys = [await one("collective", k) if isinstance(k, str) else k for k in data["building_keys"]]
                if keys != data["building_keys"]:
                    data["building_keys"] = keys
                    out = json.dumps(data, ensure_ascii=False).encode("utf-8")
        sent = False
        tail_more = more and size > _MAX_BODY

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": out, "more_body": tail_more}
            return await receive()

        if out is not raw:
            # content-length 를 새 길이로
            hdrs = [(k, v) for k, v in scope.get("headers") or [] if k != b"content-length"]
            hdrs.append((b"content-length", str(len(out)).encode()))
            scope["headers"] = hdrs
        return out, replay

    async def _send_split(self, send, app_name: str, old: str, news: list[tuple[str, int, int]]) -> None:
        import anyio

        try:
            det = await anyio.to_thread.run_sync(self.details, app_name, [n for n, _p, _c in news])
        except Exception:  # noqa: BLE001
            det = {}
        cands = [{"building_key": n, "split_part": p, "n_tx": c, **det.get(n, {})} for n, p, c in news]
        # detail 은 문자열(기존 화면 오류 표시가 그대로 읽는다), 구조화 정보는 최상위 칸
        body = {"detail": split_detail_text(cands), "key_status": "split", "message": SPLIT_MESSAGE,
                "old_key": old, "candidates": cands}
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        await send({"type": "http.response.start", "status": 409,
                    "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                (b"content-length", str(len(raw)).encode())]})
        await send({"type": "http.response.body", "body": raw})
