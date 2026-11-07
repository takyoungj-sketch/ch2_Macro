"""Account allowances. External calls run outside DB transactions; only successful
persisted results settle units. Results are separate from the cost ledger.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import (MetaData, Table, Column, String, Integer, Float, Text,
                        DateTime, select, update, and_, UniqueConstraint, CheckConstraint)

POLICY = "launch-2026-11-v1"
LIMITS = {
    "macro": {"macro_question": 200},
    "bundle": {"macro_question": 250, "photo_analysis_image": 500,
               "text_writing": 100, "address_sheet_job": 100},
}
LABELS = {"macro_question": "AI 질문", "photo_analysis_image": "사진 AI 분석",
          "text_writing": "AI 문구 작성", "address_sheet_job": "주소표 보정"}
meta = MetaData()
accounts = Table("ai_allowance_accounts", meta, Column("user_id", Integer, primary_key=True))
balances = Table("ai_allowances", meta,
    Column("user_id", Integer, primary_key=True), Column("feature", String(40), primary_key=True),
    Column("period_start", DateTime(timezone=True), primary_key=True),
    Column("period_end", DateTime(timezone=True), nullable=False),
    Column("limit_units", Integer, nullable=False), Column("used", Integer, nullable=False, default=0),
    Column("reserved", Integer, nullable=False, default=0), Column("policy", String(64), nullable=False),
    CheckConstraint("used >= 0 AND reserved >= 0", name="ai_allowance_nonnegative"))
jobs = Table("ai_allowance_requests", meta,
    Column("id", String(36), primary_key=True), Column("user_id", Integer, nullable=False, index=True),
    Column("key", String(128), nullable=False), Column("fingerprint", String(64), nullable=False),
    Column("feature", String(40), nullable=False), Column("units", Integer, nullable=False),
    Column("period_start", DateTime(timezone=True), nullable=False),
    Column("status", String(24), nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)), Column("error", String(64)),
    UniqueConstraint("user_id", "key", name="ai_request_idempotency"))
results = Table("ai_allowance_results", meta, Column("request_id", String(36), primary_key=True),
                Column("payload", Text, nullable=False))
calls = Table("ai_provider_calls", meta,
    Column("id", String(36), primary_key=True), Column("request_id", String(36), nullable=False, index=True),
    Column("stage", String(32), nullable=False), Column("model", String(128), nullable=False),
    Column("input_tokens", Integer, nullable=False), Column("output_tokens", Integer, nullable=False),
    Column("cached_tokens", Integer, nullable=False), Column("usd", Float),
    Column("status", String(24), nullable=False), Column("created_at", DateTime(timezone=True), nullable=False))
adjustments = Table("ai_allowance_adjustments", meta,
    Column("request_id", String(36), primary_key=True), Column("operator", String(80), nullable=False),
    Column("reason", Text, nullable=False), Column("created_at", DateTime(timezone=True), nullable=False))


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def now_utc():
    return datetime.now(timezone.utc)


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), default=str).encode()).hexdigest()


def month_after(anchor, offset):
    n = anchor.year * 12 + anchor.month - 1 + offset
    y, m = divmod(n, 12)
    return anchor.replace(year=y, month=m + 1,
                          day=min(anchor.day, calendar.monthrange(y, m + 1)[1]))


@dataclass(frozen=True)
class Grant:
    user_id: int
    plan: str
    start: datetime
    end: datetime


def grant_for(db, user, now=None) -> Grant | None:
    """Read paid subscriptions; never infer a bundle from two product booleans.
    Legacy Fieldnote-only/free accounts keep their existing policy.
    """
    from sqlalchemy import text
    now = now or now_utc()
    rows = db.execute(text("""SELECT s.id, s.product, s.plan_id, s.source,
        s.created_at, s.current_period_end FROM subscriptions s
        WHERE s.user_id=:uid AND s.status IN ('active','canceled')
        AND s.product IN ('macro','bundle') AND s.current_period_end > :now
        AND EXISTS (SELECT 1 FROM entitlements e WHERE e.user_id=s.user_id
          AND e.product='macro' AND e.active=TRUE
          AND (e.expires_at IS NULL OR e.expires_at > :now))
        ORDER BY CASE WHEN s.product='bundle' THEN 0 ELSE 1 END, s.current_period_end DESC
        """), {"uid": user.id, "now": now}).mappings().all()
    if not rows:
        return None
    s = rows[0]
    end, created = utc(s["current_period_end"]), utc(s["created_at"])
    if "year" in str(s["plan_id"] or ""):
        offset = max(0, (now.year - created.year) * 12 + now.month - created.month)
        if month_after(created, offset) > now:
            offset -= 1
        start, end = month_after(created, offset), min(end, month_after(created, offset + 1))
    else:
        # Existing web billing uses 31-day periods; don't change billing cadence.
        start = max(created, end - timedelta(days=31))
    # An upgrade must not refresh an already open AI period.
    old = db.execute(select(balances.c.period_start, balances.c.period_end).where(
        balances.c.user_id == user.id, balances.c.period_start <= now,
        balances.c.period_end > now).order_by(balances.c.period_start.desc())).first()
    if old:
        start, end = utc(old[0]), min(end, utc(old[1]))
    return Grant(user.id, str(s["product"]), start, end)


def _upsert(conn, table, values):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = sqlite_insert if conn.dialect.name == "sqlite" else pg_insert
    conn.execute(insert(table).values(**values).on_conflict_do_nothing())


@contextmanager
def locked(engine, user_id):
    with engine.connect() as c:
        if c.dialect.name == "sqlite":
            c.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            c.begin()
        try:
            _upsert(c, accounts, {"user_id": user_id})
            c.execute(select(accounts).where(accounts.c.user_id == user_id).with_for_update()).first()
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise


def _balance_where(grant, feature):
    return and_(balances.c.user_id == grant.user_id, balances.c.feature == feature,
                balances.c.period_start == grant.start)


def snapshot(engine, grant):
    items = []
    with engine.connect() as c:
        for feature, limit in LIMITS[grant.plan].items():
            b = c.execute(select(balances).where(_balance_where(grant, feature))).mappings().first()
            used, reserved = (b["used"], b["reserved"]) if b else (0, 0)
            items.append({"feature": feature, "label": LABELS[feature], "limit": limit,
                          "used": used, "reserved": reserved, "remaining": max(0, limit-used-reserved),
                          "warn": used >= limit * .8, "unit": "장" if feature == "photo_analysis_image" else "회"})
    return {"policy": POLICY, "plan": grant.plan, "period_start": grant.start.isoformat(),
            "period_end": grant.end.isoformat(), "items": items}


@dataclass
class Ticket:
    engine: object
    grant: Grant
    id: str
    feature: str
    units: int
    replay: dict | None = None


def reserve(engine, grant, feature, units, key, digest):
    if feature not in LIMITS[grant.plan]:
        raise HTTPException(403, detail={"code": "feature_not_in_plan", "message": "구독에 포함되지 않은 AI 기능입니다."})
    if not key or len(key) > 128 or not 1 <= units <= 500:
        raise HTTPException(400, detail={"code": "invalid_ai_request", "message": "유효한 작업 ID와 입력이 필요합니다."})
    with locked(engine, grant.user_id) as c:
        existing = c.execute(select(jobs).where(jobs.c.user_id == grant.user_id,
                                              jobs.c.key == key)).mappings().first()
        if existing:
            if existing["fingerprint"] != digest or existing["feature"] != feature:
                raise HTTPException(409, detail={"code": "idempotency_conflict", "message": "다른 입력에는 새 작업 ID가 필요합니다."})
            if existing["status"] == "completed":
                payload = c.execute(select(results.c.payload).where(results.c.request_id == existing["id"])).scalar_one()
                return Ticket(engine, grant, existing["id"], feature, units, json.loads(payload))
            raise HTTPException(409, detail={"code": "request_in_progress" if existing["status"] == "reserved" else "request_finished",
                                             "message": "처리 중이거나 종료된 작업입니다. 실패 후 다시 실행하려면 새 작업을 시작해 주세요."})
        from app.config import settings
        if settings.ai_paid_emergency_stop:
            raise HTTPException(503, detail={"code": "ai_temporarily_unavailable", "message": "AI 서비스 점검 중입니다. 기존 결과는 계속 조회할 수 있습니다."})
        busy = c.execute(select(jobs.c.id).where(jobs.c.user_id == grant.user_id,
                                                 jobs.c.status.in_(["reserved", "unknown"]))).first()
        if busy:
            raise HTTPException(409, detail={"code": "ai_busy", "message": "진행 중인 AI 작업이 끝난 뒤 다시 시도해 주세요."})
        limit = LIMITS[grant.plan][feature]
        _upsert(c, balances, {"user_id": grant.user_id, "feature": feature, "period_start": grant.start,
            "period_end": grant.end, "limit_units": limit, "used": 0, "reserved": 0, "policy": POLICY})
        where = _balance_where(grant, feature)
        b = c.execute(select(balances).where(where)).mappings().one()
        if b["used"] + b["reserved"] + units > limit:
            raise HTTPException(429, detail={"code": "quota_exceeded", "feature": feature,
                "message": "이번 이용 기간의 AI 제공량을 모두 사용했습니다.", "remaining": max(0,limit-b["used"]-b["reserved"]),
                "period_end": grant.end.isoformat()})
        c.execute(update(balances).where(where).values(limit_units=limit, reserved=b["reserved"]+units))
        request_id = str(uuid.uuid4())
        c.execute(jobs.insert().values(id=request_id, user_id=grant.user_id, key=key,
            fingerprint=digest, feature=feature, units=units, period_start=grant.start,
            status="reserved", created_at=now_utc()))
    return Ticket(engine, grant, request_id, feature, units)


def finish(ticket, payload=None, *, error=None):
    """Result persistence and allowance settlement are one atomic transaction."""
    with locked(ticket.engine, ticket.grant.user_id) as c:
        job = c.execute(select(jobs).where(jobs.c.id == ticket.id)).mappings().one()
        if job["status"] != "reserved":
            return
        where = _balance_where(ticket.grant, ticket.feature)
        c.execute(update(balances).where(where).values(
            reserved=balances.c.reserved-ticket.units,
            used=balances.c.used+(ticket.units if payload is not None else 0)))
        if payload is not None:
            c.execute(results.insert().values(request_id=ticket.id,
                payload=json.dumps(payload, ensure_ascii=False, default=str)))
        c.execute(update(jobs).where(jobs.c.id == ticket.id).values(
            status="completed" if payload is not None else "failed", error=error,
            finished_at=now_utc()))


_ticket = ContextVar("ai_allowance_ticket", default=None)
provider_stage = ContextVar("ai_provider_stage", default="generation")


@contextmanager
def tracking(ticket):
    token = _ticket.set(ticket)
    try:
        yield
    finally:
        _ticket.reset(token)


def managed_request():
    return _ticket.get() is not None


def release_abandoned(engine, request_id, operator, reason):
    """Operator must verify the worker is stopped. Never auto-release live jobs."""
    if not operator.strip() or not reason.strip():
        raise ValueError("operator and reason required")
    with engine.connect() as c:
        job = c.execute(select(jobs).where(jobs.c.id == request_id)).mappings().one()
    with locked(engine, job["user_id"]) as c:
        job = c.execute(select(jobs).where(jobs.c.id == request_id)).mappings().one()
        if job["status"] != "reserved" or utc(job["created_at"]) > now_utc()-timedelta(minutes=30):
            raise ValueError("only abandoned reservations older than 30 minutes can be released")
        c.execute(update(balances).where(balances.c.user_id == job["user_id"],
            balances.c.feature == job["feature"], balances.c.period_start == job["period_start"]).values(
                reserved=balances.c.reserved-job["units"]))
        c.execute(update(jobs).where(jobs.c.id == request_id).values(status="failed", error="operator_recovered", finished_at=now_utc()))
        c.execute(adjustments.insert().values(request_id=request_id, operator=operator, reason=reason, created_at=now_utc()))


def record_provider_failure(model, status="unknown"):
    ticket = _ticket.get()
    if ticket:
        with ticket.engine.begin() as c:
            c.execute(calls.insert().values(id=str(uuid.uuid4()), request_id=ticket.id,
                stage=provider_stage.get(), model=model, input_tokens=0, output_tokens=0,
                cached_tokens=0, usd=None, status=status, created_at=now_utc()))


def record_provider(*, model, prompt_tokens, completion_tokens, cached_tokens=0, stage="generation"):
    ticket = _ticket.get()
    if ticket is None:
        return
    from app.ai.usage_log import prices_for
    known = any(k in model.lower() for k in ("gpt-5-mini", "gpt-5.4-mini", "gpt-4o-mini"))
    inp, out = prices_for(model)
    # GPT-4o mini caches cost 50%; GPT-5 mini variants cost 10% of input.
    cached = min(max(0, cached_tokens), prompt_tokens)
    cached_price = inp * (.5 if "gpt-4o-mini" in model.lower() else .1)
    usd = ((prompt_tokens-cached)*inp+cached*cached_price+completion_tokens*out)/1e6 if known else None
    with ticket.engine.begin() as c:
        c.execute(calls.insert().values(id=str(uuid.uuid4()), request_id=ticket.id, stage=stage,
            model=model, input_tokens=prompt_tokens, output_tokens=completion_tokens,
            cached_tokens=cached, usd=usd, status="completed" if known else "cost_unknown", created_at=now_utc()))


def request_user(request):
    """Optional authenticated user without requiring platform DB in legacy/dev mode."""
    from app.platform.db import get_platform_session_factory
    from app.platform.jwt_util import COOKIE_NAME, decode_access_token
    from app.platform.deps import CurrentUser
    from sqlalchemy import text
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else request.cookies.get(COOKIE_NAME, "")
    payload = decode_access_token(token) if token else None
    if not payload or not str(payload.get("sub", "")).isdigit():
        return None
    factory = get_platform_session_factory()
    if factory is None:
        raise HTTPException(503, "AI 이용량 저장소를 사용할 수 없습니다.")
    with factory() as db:
        row = db.execute(text("SELECT id,email,nickname,role FROM users WHERE id=:id"),
                         {"id": int(payload["sub"])}).mappings().first()
        return CurrentUser(**dict(row)) if row else None


def grant_for_user(user):
    from app.platform.db import get_platform_session_factory, get_platform_engine
    factory = get_platform_session_factory()
    if factory is None:
        raise HTTPException(503, "AI 이용량 저장소를 사용할 수 없습니다.")
    with factory() as db:
        return get_platform_engine(), grant_for(db, user)
