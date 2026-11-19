"""FieldNote AI 접근과 월 한도.

FN-001은 체험·만료 등급을 만들지 않는다. 익명, 매크로 전용 구독, 그 외 로그인 사용자는 거절한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings

_log = logging.getLogger(__name__)
_KST = ZoneInfo("Asia/Seoul")

PHOTO = "photo_analysis_image"
SHEET = "address_sheet_job"
WRITE = "text_writing"
DAILY = "fieldnote_daily_calls"
_cap_warned_on = None
FEATURES = (
    (PHOTO, "장"),
    (SHEET, "회"),
    (WRITE, "회"),
)

# 앱 extractRejectionCode는 detail.code를 읽는다. 문구에 결제·웹 결제 안내를 넣지 않는다.
_DENY = {
    "login_required": (401, "AI 의견은 CH2 계정 로그인 후 이용할 수 있습니다."),
    "subscription_required": (403, "AI 이용 기간이 아닙니다."),
    "trial_ended": (403, "무료체험이 끝났습니다."),
    "quota_exceeded": (429, "이번 달 AI 사용량을 모두 썼습니다."),
    "rate_limited": (429, "요청이 많습니다. 잠시 후 다시 시도해 주세요."),
    "daily_cap": (503, "오늘 AI 이용이 많아 잠시 후 다시 이용해 주세요."),
    "invalid_request": (400, "요청 형식이 올바르지 않습니다."),
}


@dataclass
class FieldnoteAiAccess:
    tier: str
    period_start: datetime | None
    period_end: datetime | None
    deny_code: str | None


def raise_fieldnote_deny(code: str, message: str | None = None) -> None:
    status, default = _DENY[code]
    raise HTTPException(status_code=status, detail={"code": code, "message": message or default})


def calendar_month(now: datetime) -> tuple[datetime, datetime]:
    local = now.astimezone(_KST)
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def monthly_limit(feature: str, tier: str) -> int:
    if tier in ("none", "expired"):
        return 0
    table = {
        (PHOTO, "paid"): settings.fieldnote_ai_paid_monthly_photo,
        (SHEET, "paid"): settings.fieldnote_ai_paid_monthly_sheet,
        (WRITE, "paid"): settings.fieldnote_ai_paid_monthly_write,
        (PHOTO, "trial"): settings.fieldnote_ai_trial_monthly_photo,
        (SHEET, "trial"): settings.fieldnote_ai_trial_monthly_sheet,
        (WRITE, "trial"): settings.fieldnote_ai_trial_monthly_write,
        (PHOTO, "admin"): settings.fieldnote_ai_admin_monthly_photo,
        (SHEET, "admin"): settings.fieldnote_ai_admin_monthly_sheet,
        (WRITE, "admin"): settings.fieldnote_ai_admin_monthly_write,
    }
    return int(table.get((feature, tier), 0))


def limit_invariant_problems() -> list[str]:
    problems = []
    for feature, _unit in FEATURES:
        paid = monthly_limit(feature, "paid")
        trial = monthly_limit(feature, "trial")
        if paid < 0 or trial < 0 or paid < trial:
            problems.append(feature)
    return problems


def warn_limit_invariant() -> None:
    problems = limit_invariant_problems()
    if problems:
        _log.warning("FieldNote AI 월 한도 불변식이 깨졌습니다. 유료는 체험 이상이어야 합니다: %s", ", ".join(problems))


def resolve_fieldnote_ai_access(db, user, now: datetime | None = None) -> FieldnoteAiAccess:
    """익명은 설정이 0보다 커도 기기 한도로 되돌리지 않는다."""
    now = now or datetime.now(timezone.utc)
    if user is None:
        return FieldnoteAiAccess("none", None, None, "login_required")
    if getattr(user, "role", None) == "admin":
        start, end = calendar_month(now)
        return FieldnoteAiAccess("admin", start, end, None)
    from app.ai.allowances import grant_for
    from app.platform.entitlements import list_entitlements

    grant = grant_for(db, user, now)
    try:
        fieldnote = bool(list_entitlements(db, user.id).get("fieldnote"))
    except Exception:
        _log.exception("fieldnote entitlement check failed user_id=%s", getattr(user, "id", None))
        fieldnote = False
    if grant is not None and fieldnote:
        return FieldnoteAiAccess("paid", grant.start, grant.end, None)
    return FieldnoteAiAccess("none", None, None, "subscription_required")


def kst_day(now: datetime) -> tuple[datetime, datetime]:
    local = now.astimezone(_KST)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def warn_daily_cap(now: datetime | None = None) -> None:
    global _cap_warned_on
    day = kst_day(now or datetime.now(timezone.utc))[0].date()
    if _cap_warned_on == day:
        return
    _cap_warned_on = day
    _log.warning("FieldNote AI 하루 상한에 도달했습니다. day=%s", day.isoformat())


def daily_grant(now: datetime | None = None):
    from app.ai.allowances import Grant

    start, end = kst_day(now or datetime.now(timezone.utc))
    return Grant(0, "fieldnote", start, end)


def reserve_daily_call(engine, parent_id: str, now: datetime | None = None):
    """전역 계정 0은 동시 예약을 허용하고, 호출 수 상한은 행 잠금 안에서 센다."""
    from app.ai import allowances as quota

    grant = daily_grant(now)
    return quota.reserve(
        engine,
        grant,
        DAILY,
        1,
        f"fn-daily:{parent_id}",
        quota.fingerprint({"parent": parent_id}),
        limit=int(settings.fieldnote_ai_daily_cap_calls),
    )


def daily_dollar_exceeds(engine, grant) -> bool:
    """정산액(금액 없는 호출은 최악 단가)과 진행 중 예약에 최악 단가를 더한다."""
    from app.ai.allowances import balances, calls, jobs, locked, utc

    worst = float(settings.fieldnote_ai_worst_call_usd)
    cap = float(settings.fieldnote_ai_daily_cap_usd)
    with locked(engine, 0) as conn:
        reserved = conn.execute(
            select(balances.c.reserved).where(
                balances.c.user_id == 0,
                balances.c.feature == DAILY,
                balances.c.period_start == grant.start,
            )
        ).scalar()
        rows = conn.execute(
            select(calls.c.usd, calls.c.created_at).select_from(
                calls.join(jobs, calls.c.request_id == jobs.c.id)
            ).where(jobs.c.feature.in_((PHOTO, SHEET, WRITE)))
        ).all()
    settled = 0.0
    for usd, created in rows:
        created_at = utc(created)
        if grant.start <= created_at < grant.end:
            settled += worst if usd is None else float(usd)
    return settled + int(reserved or 0) * worst > cap


def fieldnote_usage(engine, user_id: int, access: FieldnoteAiAccess) -> dict:
    """앱은 plan이 bundle일 때만 허용량을 남긴다."""
    from app.ai.allowances import balances

    items = []
    with engine.connect() as conn:
        for feature, unit in FEATURES:
            limit = monthly_limit(feature, access.tier)
            row = conn.execute(
                select(balances).where(
                    balances.c.user_id == user_id,
                    balances.c.feature == feature,
                    balances.c.period_start == access.period_start,
                )
            ).mappings().first()
            used = int(row["used"]) if row else 0
            reserved = int(row["reserved"]) if row else 0
            items.append(
                {
                    "feature": feature,
                    "used": used,
                    "limit": limit,
                    "remaining": max(0, limit - used - reserved),
                    "unit": unit,
                    "warn": bool(limit) and used >= limit * 0.8,
                }
            )
    return {
        "plan": "bundle",
        "mode": "account",
        "period_start": access.period_start.isoformat(),
        "period_end": access.period_end.isoformat(),
        "items": items,
    }


warn_limit_invariant()
