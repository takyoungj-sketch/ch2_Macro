"""Macro AI 사용량 장부 — 토큰·원화. 질문 문장은 저장하지 않는다."""

from __future__ import annotations

import json
import threading
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.config import settings

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


def _read_events(month: str) -> list[dict[str, Any]]:
    path = _month_path(month)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


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
    path = _month_path(month)
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event
