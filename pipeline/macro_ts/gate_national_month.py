"""전국 월 마트 숫자 게이트. 원장 단절이 다시 들어가면 실패."""

from __future__ import annotations

from typing import Any


def _year_count(series: dict[int, dict[str, float]], year: int) -> float:
    return sum(cell["count"] for ym, cell in series.items() if ym // 100 == year)


def _year_month_avg(series: dict[int, dict[str, float]], year: int) -> float | None:
    vals = [cell["count"] for ym, cell in series.items() if ym // 100 == year]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _missing_months(series: dict[int, dict[str, float]]) -> list[int]:
    if len(series) < 2:
        return []
    keys = sorted(series)
    missing: list[int] = []
    y, m = keys[0] // 100, keys[0] % 100
    end = keys[-1]
    while y * 100 + m < end:
        m += 1
        if m > 12:
            m = 1
            y += 1
        k = y * 100 + m
        if k not in series:
            missing.append(k)
    return missing


def evaluate_gate(by_type: dict[str, dict[int, dict[str, float]]]) -> dict[str, Any]:
    failures: list[str] = []
    notes: list[str] = []
    for name, series in sorted(by_type.items()):
        miss = _missing_months(series)
        if miss:
            failures.append(f"{name} 빈 달 {len(miss)}개 예:{miss[:6]}")
        if series:
            notes.append(f"{name} {min(series)}–{max(series)} n_months={len(series)}")

    apt = by_type.get("아파트") or {}
    c2018 = _year_count(apt, 2018)
    c2019 = _year_count(apt, 2019)
    if c2018 <= 0 or c2019 <= 0:
        failures.append(f"아파트 2018/2019 건수 없음 {c2018:.0f}/{c2019:.0f}")
    else:
        ratio = c2019 / c2018
        notes.append(f"아파트 연건수 2018={c2018:.0f} 2019={c2019:.0f} ratio={ratio:.2f}")
        if c2018 < 200_000:
            failures.append(f"아파트 2018 연 건수 {c2018:.0f} — raw가 안 붙음(원장 공백 규모)")
        if ratio >= 5:
            failures.append(f"아파트 2019/2018={ratio:.1f} — 원장 단절 패턴")

    for name, series in by_type.items():
        a = _year_month_avg(series, 2020)
        b = _year_month_avg(series, 2021)
        if a is None or b is None or a <= 0:
            continue
        r = b / a
        notes.append(f"{name} 월평균 2021/2020={r:.2f}")
        if r >= 10 or r <= 0.1:
            failures.append(f"{name} 2021/2020 월평균 {r:.1f} — 이음 단절")

    return {"ok": not failures, "failures": failures, "notes": notes}
