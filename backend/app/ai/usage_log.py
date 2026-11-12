"""Macro AI 사용량 장부 — 토큰·원화. 질문 문장은 저장하지 않는다."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.config import settings

_LOG = logging.getLogger(__name__)
_LOCK = threading.Lock()
_META: ContextVar[dict[str, str]] = ContextVar("ai_usage_meta", default={})

# requested/served 모델 부분일치. (input_usd, output_usd) per 1M tokens
_MODEL_PRICES: dict[str, tuple[float, float]] = {
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-4o-mini": (0.15, 0.60),
}


class AiQuotaExceeded(Exception):
    def __init__(self, message: str, snapshot: dict[str, Any]):
        super().__init__(message)
        self.user_message = message
        self.snapshot = snapshot


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def usage_dir() -> Path:
    override = (getattr(settings, "ai_usage_log_dir", "") or "").strip()
    return Path(override) if override else _repo_root() / "logs" / "ai_usage"


def bind_usage_meta(**kwargs: str) -> Any:
    data = {k: str(v) for k, v in kwargs.items() if v}
    return _META.set(data)


def reset_usage_meta(token: Any) -> None:
    _META.reset(token)


def prices_for(model: str) -> tuple[float, float]:
    m = (model or "").lower()
    for key, pair in _MODEL_PRICES.items():
        if key in m:
            return pair
    return _MODEL_PRICES["gpt-5-mini"]


def estimate_usd(*, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    inn, out = prices_for(model)
    return (max(0, prompt_tokens) / 1_000_000.0) * inn + (
        max(0, completion_tokens) / 1_000_000.0
    ) * out


def _month_key(now: Optional[datetime] = None) -> str:
    dt = now or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m")


def _month_path(month: str) -> Path:
    return usage_dir() / f"{month}.jsonl"


class _JsonlTail:
    """월 JSONL 을 매번 처음부터 읽지 않고 늘어난 부분만 읽어 누계 행을 유지한다."""

    def __init__(self) -> None:
        self.offset = 0
        self.rows: list[dict[str, Any]] = []

    def read(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            self.offset, self.rows = 0, []
            return self.rows
        size = path.stat().st_size
        if size < self.offset:  # 파일 교체·회전
            self.offset, self.rows = 0, []
        if size == self.offset:
            return self.rows
        with path.open("rb") as fh:
            fh.seek(self.offset)
            chunk = fh.read()
        complete = chunk.rfind(b"\n") + 1  # 쓰는 중인 마지막 줄은 다음에 읽는다
        for line in chunk[:complete].decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                self.rows.append(row)
        self.offset += complete
        return self.rows


_TAILS: dict[str, _JsonlTail] = {}


def _cached_rows(path: Path) -> list[dict[str, Any]]:
    with _LOCK:
        tail = _TAILS.setdefault(str(path), _JsonlTail())
        return list(tail.read(path))


def _read_events(month: str) -> list[dict[str, Any]]:
    return _cached_rows(_month_path(month))


def month_snapshot(month: Optional[str] = None) -> dict[str, Any]:
    key = month or _month_key()
    events = _read_events(key)
    calls = len(events)
    usd = sum(float(e.get("usd") or 0) for e in events)
    krw = sum(float(e.get("krw") or 0) for e in events)
    call_limit = int(settings.ai_monthly_call_limit or 0)
    budget = float(settings.ai_monthly_budget_krw or 0)
    call_ratio = (calls / call_limit) if call_limit > 0 else 0.0
    cost_ratio = (krw / budget) if budget > 0 else 0.0
    ratio = max(call_ratio, cost_ratio)
    stopped = (call_limit > 0 and calls >= call_limit) or (budget > 0 and krw >= budget)
    warn = (not stopped) and ratio >= 0.80
    warning = None
    if stopped:
        parts = []
        if call_limit > 0 and calls >= call_limit:
            parts.append(f"월 호출 {calls}/{call_limit}회")
        if budget > 0 and krw >= budget:
            parts.append(f"월 비용 {krw:,.0f}/{budget:,.0f}원")
        warning = "이번 달 AI 한도에 도달했습니다. (" + ", ".join(parts) + ")"
    elif warn:
        warning = (
            f"이번 달 AI 사용량이 80%를 넘었습니다. "
            f"호출 {calls}/{call_limit or '∞'} · 약 {krw:,.0f}/{budget:,.0f}원"
        )
    return {
        "month": key,
        "calls": calls,
        "call_limit": call_limit,
        "usd": round(usd, 6),
        "krw": round(krw, 1),
        "budget_krw": budget,
        "usd_krw": float(settings.ai_usd_krw or 1400),
        "warn": warn,
        "stopped": stopped,
        "warning": warning,
        "requested_model": (settings.openai_model or "").strip(),
        "event_count": calls,
        "recent": events[-50:][::-1],
        "questions": question_stats(key),
        "limit_warnings": limit_warnings(),
    }


def assert_quota_or_raise() -> dict[str, Any]:
    snap = month_snapshot()
    if snap["stopped"]:
        raise AiQuotaExceeded(
            "### 답변\n\n"
            + (snap["warning"] or "이번 달 AI 한도에 도달했습니다.")
            + "\n\n관리자 페이지의 AI 사용량에서 이번 달 장부를 볼 수 있습니다.",
            snap,
        )
    return snap


def record_llm_call(
    *,
    requested_model: str,
    served_model: Optional[str],
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    month = _month_key(now)
    model_for_price = served_model or requested_model
    usd = estimate_usd(
        model=model_for_price,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    krw = usd * float(settings.ai_usd_krw or 1400)
    meta = _META.get() or {}
    event = {
        "ts": now.isoformat(timespec="seconds"),
        "month": month,
        "requested_model": requested_model,
        "served_model": served_model,
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "cached_tokens": int(cached_tokens or 0),
        "usd": round(usd, 8),
        "krw": round(krw, 4),
        "route": meta.get("route") or "",
        "app": meta.get("app") or "",
        "panel": meta.get("panel") or "",
        "scope_label": meta.get("scope_label") or "",
    }
    question = _QUESTION.get()
    if question is not None:
        question.prompt_tokens += event["prompt_tokens"]
        question.completion_tokens += event["completion_tokens"]
        question.usd += event["usd"]
        question.krw += event["krw"]
    path = _month_path(month)
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


# ---------------------------------------------------------------------------
# 질문 단위 장부 (2026-11-09 지시서 §5.6). 질문 문장은 저장하지 않는다.
# ---------------------------------------------------------------------------


@dataclass
class QuestionLog:
    request_id: str
    app: str
    panel: str
    started: float = field(default_factory=time.monotonic)
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    usd: float = 0.0
    krw: float = 0.0
    #: pass | repaired | partial | failed | refusal | none
    validation: str = "none"
    token: Any = None


_QUESTION: ContextVar[Optional[QuestionLog]] = ContextVar("ai_question_log", default=None)


def _question_path(month: str) -> Path:
    return usage_dir() / f"questions-{month}.jsonl"


def begin_question(*, app: str, panel: str, request_id: Optional[str] = None) -> QuestionLog:
    question = QuestionLog(request_id=request_id or uuid.uuid4().hex, app=app or "", panel=panel or "")
    question.token = _QUESTION.set(question)
    return question


def finish_question(question: QuestionLog, response: Any = None) -> Optional[dict[str, Any]]:
    try:
        _QUESTION.reset(question.token)
    except (ValueError, LookupError):
        pass
    now = datetime.now(timezone.utc)
    row = {
        "ts": now.isoformat(timespec="seconds"),
        "request_id": question.request_id,
        "app": question.app,
        "panel": question.panel,
        "llm_calls": question.llm_calls,
        "prompt_tokens": question.prompt_tokens,
        "completion_tokens": question.completion_tokens,
        "usd": round(question.usd, 8),
        "krw": round(question.krw, 4),
        "latency_ms": int((time.monotonic() - question.started) * 1000),
        "validation": question.validation if response is not None else "error",
        "error_code": getattr(response, "error_code", None),
    }
    try:
        path = _question_path(_month_key(now))
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        _LOG.warning("AI question log failed", exc_info=True)
        return None
    return row


def _percentile(values: list[int], q: float) -> Optional[int]:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))]


def question_stats(month: Optional[str] = None) -> dict[str, Any]:
    rows = _cached_rows(_question_path(month or _month_key()))
    answered = [r for r in rows if int(r.get("llm_calls") or 0) > 0]
    n = len(answered)
    latencies = [int(r.get("latency_ms") or 0) for r in answered]
    by_validation: dict[str, int] = {}
    for r in rows:
        key = str(r.get("validation") or "none")
        by_validation[key] = by_validation.get(key, 0) + 1
    return {
        "questions": len(rows),
        "answered_with_llm": n,
        "avg_llm_calls": round(sum(int(r.get("llm_calls") or 0) for r in answered) / n, 2) if n else None,
        "avg_krw": round(sum(float(r.get("krw") or 0) for r in answered) / n, 2) if n else None,
        "latency_p50_ms": _percentile(latencies, 0.5),
        "latency_p90_ms": _percentile(latencies, 0.9),
        "validation": by_validation,
    }


def limit_warnings() -> list[str]:
    """서비스 전체 한도와 개인 한도의 모순을 알린다. 제공 횟수는 바꾸지 않는다."""
    if not getattr(settings, "ai_subscription_quota_enabled", False):
        return []
    from app.ai.allowances import LIMITS

    out: list[str] = []
    call_limit = int(settings.ai_monthly_call_limit or 0)
    personal = max(int(v.get("macro_question", 0)) for v in LIMITS.values())
    if call_limit and call_limit <= personal * 2:
        out.append(
            f"AI_MONTHLY_CALL_LIMIT={call_limit}(LLM 호출 단위)가 개인 월 질문 한도 {personal}회와 비슷하거나 작습니다. "
            "구독자 한두 명만으로 서비스 전체가 멈출 수 있습니다. 전체 한도를 원가(AI_MONTHLY_BUDGET_KRW) 하나로 "
            "일원화하고 호출 한도는 0(해제)으로 두는 안을 검토하세요."
        )
    return out


def log_limit_warnings() -> None:
    for message in limit_warnings():
        _LOG.warning("AI 한도 점검: %s", message)
