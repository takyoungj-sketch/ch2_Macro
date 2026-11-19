"""Immutable subscription anchors and calendar months in Korean time."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Mapping

KST = timezone(timedelta(hours=9))


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def anchor(sub: Mapping, trial_ends_at: datetime) -> datetime:
    return max(aware(sub["created_at"]), aware(trial_ends_at)).astimezone(KST)


def period_end(start: datetime, k: int) -> datetime:
    if k < 0:
        raise ValueError("period index must be nonnegative")
    start = aware(start).astimezone(KST)
    year, month0 = divmod(start.year * 12 + start.month - 1 + k, 12)
    month = month0 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def next_period_end(start: datetime, old_end: datetime) -> datetime:
    old_end = aware(old_end).astimezone(KST)
    start = aware(start).astimezone(KST)
    k = max(0, (old_end.year - start.year) * 12 + old_end.month - start.month)
    candidate = period_end(start, k)
    return candidate if candidate > old_end else period_end(start, k + 1)


def current_period(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start, end = aware(start).astimezone(KST), aware(end).astimezone(KST)
    if end <= start:
        raise ValueError("period end must follow anchor")
    k = max(0, (end.year - start.year) * 12 + end.month - start.month)
    previous = period_end(start, k)
    if previous >= end:
        previous = period_end(start, max(0, k - 1))
    return previous, end
