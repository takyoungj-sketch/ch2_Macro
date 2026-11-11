"""미지원 파라미터 경고·집계 모드 (집합 1단계 C-05, D-084).

요청 query 키·JSON body 키 중 해당 라우트가 받지 않는 것을 **이름만** 집계한다.
요청은 그대로 통과시킨다(거절 모드 없음 — 전환은 별도 승인).

기록 키: (API 경로 템플릿, method, 화면 식별자, 위치(query/body), 파라미터 이름) → 빈도.
기록하지 않는 것: 파라미터 값, 쿼리 문자열, 사용자 ID, IP, 토큰. 경로 변수는 템플릿으로 남는다.

저장: 프로세스 메모리 집계 → 주기(기본 1시간)·종료 시 JSONL 한 줄씩 추가.
경로는 설정 ``API_PARAM_WARN_PATH``(기본 ``logs/api_param_warn.jsonl``, 상대 경로는 저장소 루트 기준).
앱 로그에는 하루 한 번 요약만 남긴다.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlparse

from pydantic import BaseModel

from app.config import settings

_LOG = logging.getLogger(__name__)

SCREEN_HEADER = b"x-ch2-screen"
_SCREEN_RE = re.compile(r"[^A-Za-z0-9/_\-.]")
_MAX_BODY = 512 * 1024


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def warn_log_path() -> Path:
    raw = (getattr(settings, "api_param_warn_path", "") or "").strip() or "logs/api_param_warn.jsonl"
    p = Path(raw)
    return p if p.is_absolute() else _repo_root() / p


def _clean_screen(value: str) -> str:
    return _SCREEN_RE.sub("", value.strip())[:80]


def screen_of(headers: Iterable[tuple[bytes, bytes]]) -> str:
    """X-CH2-Screen 헤더, 없으면 Referer 의 경로만(호스트·쿼리·조각 제거)."""
    referer = ""
    for k, v in headers:
        lk = k.lower()
        if lk == SCREEN_HEADER:
            s = _clean_screen(v.decode("latin-1", "ignore"))
            if s:
                return s
        elif lk == b"referer":
            referer = v.decode("latin-1", "ignore")
    if referer:
        try:
            path = urlparse(referer).path or ""
        except ValueError:
            path = ""
        s = _clean_screen(path)
        if s:
            return "referer:" + s
    return ""


# ---------------- 라우트가 받는 파라미터 ----------------

def _query_names(dependant: Any, seen: set[int] | None = None) -> set[str]:
    seen = seen if seen is not None else set()
    if dependant is None or id(dependant) in seen:
        return set()
    seen.add(id(dependant))
    names = {str(getattr(p, "alias", None) or p.name) for p in getattr(dependant, "query_params", []) or []}
    for sub in getattr(dependant, "dependencies", []) or []:
        names |= _query_names(sub, seen)
    return names


def _reads_raw_request(dependant: Any, seen: set[int] | None = None) -> bool:
    """핸들러·의존성이 Request 를 직접 받으면 query 를 수동으로 읽을 수 있어 query 판정을 하지 않는다."""
    seen = seen if seen is not None else set()
    if dependant is None or id(dependant) in seen:
        return False
    seen.add(id(dependant))
    if getattr(dependant, "request_param_name", None):
        return True
    return any(_reads_raw_request(sub, seen) for sub in getattr(dependant, "dependencies", []) or [])


def _model_of(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for arg in getattr(annotation, "__args__", ()) or ():
        m = _model_of(arg)
        if m is not None:
            return m
    return None


def _model_keys(model: type[BaseModel]) -> set[str]:
    out: set[str] = set()
    for name, f in model.model_fields.items():
        out.add(name)
        if f.alias:
            out.add(f.alias)
        va = getattr(f, "validation_alias", None)
        if isinstance(va, str):
            out.add(va)
    return out


def unknown_body_keys(model: type[BaseModel], data: Any, prefix: str = "", depth: int = 0) -> list[str]:
    """Pydantic(extra=ignore) 가 버리는 키 — 중첩 모델은 점 경로(variables.foo)로."""
    if not isinstance(data, dict) or depth > 4:
        return []
    cfg = getattr(model, "model_config", {}) or {}
    if cfg.get("extra") == "allow":
        return []
    keys = _model_keys(model)
    out: list[str] = []
    for k, v in data.items():
        k = str(k)
        if k not in keys:
            out.append(prefix + k)
            continue
        field = model.model_fields.get(k) or next(
            (f for f in model.model_fields.values() if f.alias == k), None
        )
        sub = _model_of(field.annotation) if field is not None else None
        if sub is not None and isinstance(v, dict):
            out.extend(unknown_body_keys(sub, v, prefix=f"{prefix}{k}.", depth=depth + 1))
    return out


def _route_body_model(route: Any) -> type[BaseModel] | None:
    field = getattr(route, "body_field", None)
    if field is None:
        return None
    dependant = getattr(route, "dependant", None)
    body_params = getattr(dependant, "body_params", []) or []
    if len(body_params) == 1:
        m = _model_of(getattr(body_params[0].field_info, "annotation", None) or getattr(body_params[0], "type_", None))
        if m is not None:
            return m
    return _model_of(getattr(field, "type_", None) or getattr(getattr(field, "field_info", None), "annotation", None))


# ---------------- 집계 ----------------

#: 파라미터 이름은 브라우저가 마음대로 보낼 수 있어 길이·문자·고유 키 수를 묶는다(메모리·로그 폭증 방지).
MAX_PARAM_NAME = 64
MAX_KEYS_PER_WINDOW = 1000
OVERFLOW_PARAM = "_overflow"
_PARAM_RE = re.compile(r"[^A-Za-z0-9_\-.\[\]]")


def clean_param_name(name: str) -> str:
    """영문·숫자·`_-.[]`만 남기고 64자로 자른다."""
    return _PARAM_RE.sub("", str(name or ""))[:MAX_PARAM_NAME]


def _capped(counter: Counter, key: tuple[str, str, str, str, str], route: str) -> tuple[str, str, str, str, str]:
    """창 안 고유 키가 상한에 닿으면 새 키는 (route, '_overflow') 하나로 합친다."""
    if key in counter or len(counter) < MAX_KEYS_PER_WINDOW:
        return key
    return (route, "", "", "", OVERFLOW_PARAM)

class ParamWarnAggregator:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Counter[tuple[str, str, str, str, str]] = Counter()
        self._window_start = time.time()
        self._last_flush = time.time()
        self._day_counts: Counter[tuple[str, str, str, str, str]] = Counter()
        self._day = datetime.now().date()

    def record(self, *, route: str, method: str, screen: str, location: str, params: Iterable[str]) -> None:
        with self._lock:
            for p in params:
                name = clean_param_name(p)
                if not name:
                    continue
                key = (route, method, screen, location, name)
                self._counts[_capped(self._counts, key, route)] += 1
                self._day_counts[_capped(self._day_counts, key, route)] += 1

    def snapshot(self) -> dict[tuple[str, str, str, str, str], int]:
        with self._lock:
            return dict(self._counts)

    def maybe_flush(self) -> None:
        interval = max(60, int(getattr(settings, "api_param_warn_flush_seconds", 3600) or 3600))
        if time.time() - self._last_flush >= interval:
            self.flush()

    def flush(self) -> int:
        with self._lock:
            counts, self._counts = self._counts, Counter()
            start, end = self._window_start, time.time()
            self._window_start = end
            self._last_flush = end
            today = datetime.now().date()
            day_summary = None
            if today != self._day:
                day_summary = (self._day, self._day_counts)
                self._day, self._day_counts = today, Counter()
        if day_summary is not None:
            self._log_day_summary(*day_summary)
        if not counts:
            return 0
        path = warn_log_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            ws = datetime.fromtimestamp(start, timezone.utc).isoformat(timespec="seconds")
            we = datetime.fromtimestamp(end, timezone.utc).isoformat(timespec="seconds")
            with path.open("a", encoding="utf-8") as fh:
                for (route, method, screen, location, param), n in sorted(counts.items()):
                    fh.write(json.dumps({
                        "window_start": ws, "window_end": we, "method": method, "route": route,
                        "screen": screen, "location": location, "param": param, "count": int(n),
                    }, ensure_ascii=False) + "\n")
        except OSError as exc:  # 기록 실패는 요청에 영향 없음
            _LOG.warning("api_param_warn 기록 실패: %s", exc)
        return len(counts)

    @staticmethod
    def _log_day_summary(day, counts: Counter) -> None:
        if not counts:
            return
        total = sum(counts.values())
        top = ", ".join(f"{m} {r} {p}×{n}" for (r, m, _s, _l, p), n in counts.most_common(5))
        _LOG.info("미지원 파라미터 %s: %d건 (%d종) — 상위: %s", day.isoformat(), total, len(counts), top)

    def close(self) -> None:
        self.flush()
        with self._lock:
            day, counts = self._day, self._day_counts
            self._day_counts = Counter()
        self._log_day_summary(day, counts)


AGGREGATOR = ParamWarnAggregator()


class ApiParamWarnMiddleware:
    """순수 ASGI 미들웨어. 라우팅이 끝난 뒤 scope['route'] 로 라우트를 찾아 비교한다."""

    def __init__(self, app, aggregator: ParamWarnAggregator | None = None) -> None:
        self.app = app
        self.agg = aggregator or AGGREGATOR

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not getattr(settings, "api_param_warn_enabled", True):
            await self.app(scope, receive, send)
            return
        chunks: list[bytes] = []
        size = 0
        headers = scope.get("headers") or []
        is_json = any(k.lower() == b"content-type" and b"json" in v.lower() for k, v in headers)

        async def recv():
            nonlocal size
            msg = await receive()
            if is_json and msg.get("type") == "http.request" and size <= _MAX_BODY:
                body = msg.get("body", b"") or b""
                size += len(body)
                if size <= _MAX_BODY:
                    chunks.append(body)
            return msg

        try:
            await self.app(scope, recv, send)
        finally:
            try:
                self._inspect(scope, b"".join(chunks) if is_json and size <= _MAX_BODY else None)
                self.agg.maybe_flush()
            except Exception as exc:  # noqa: BLE001 — 관측 실패가 응답을 바꾸면 안 된다
                _LOG.debug("api_param_warn 검사 실패: %s", exc)

    def _inspect(self, scope, body: bytes | None) -> None:
        route = scope.get("route")
        template = getattr(route, "path_format", None) or getattr(route, "path", None)
        dependant = getattr(route, "dependant", None)
        if not template or dependant is None:
            return
        method = str(scope.get("method") or "").upper()
        screen = screen_of(scope.get("headers") or [])
        qs = scope.get("query_string") or b""
        if qs and not _reads_raw_request(dependant):
            accepted = _query_names(dependant)
            sent = {k for k, _v in parse_qsl(qs.decode("latin-1", "ignore"), keep_blank_values=True)}
            # axios 배열 직렬화(addr3_list[]=…)도 같은 이름으로 본다
            unknown = sorted(k for k in sent if k not in accepted and k.removesuffix("[]") not in accepted)
            if unknown:
                self.agg.record(route=template, method=method, screen=screen, location="query", params=unknown)
        if body:
            model = _route_body_model(route)
            if model is not None:
                try:
                    data = json.loads(body)
                except ValueError:
                    return
                unknown = sorted(set(unknown_body_keys(model, data)))
                if unknown:
                    self.agg.record(route=template, method=method, screen=screen, location="body", params=unknown)
