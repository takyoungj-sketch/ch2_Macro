"""ECOS(한국은행) CSV — G3 랩 (연도·월).

파일명에 다운로드 시각이 붙으므로 glob으로 최신 파일을 고른다.
월 헤더(2010/01, 잠정 `2026/06 p)`)는 frequency=month.
일별 열(2026/08/31)은 건너뛴다.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Literal

_REPO = Path(__file__).resolve().parents[3]
_DATA = _REPO / "data"

_YEAR_COL = re.compile(r"^\d{4}$")
# 2010 · 2025 p)
_YEAR_COL_FLEX = re.compile(r"^(\d{4})(?:\s*p\s*\)?)?$", re.IGNORECASE)
# 2010/01 · 2010-1 · 잠정 2026/06 p)
_MONTH_COL = re.compile(r"^(\d{4})[./\-](\d{1,2})(?:\s*p\s*\)?)?$", re.IGNORECASE)

Grain = Literal["year", "month"]

RATE_CATALOG: tuple[dict[str, str], ...] = (
    {"id": "cd_91", "label": "CD(91일)", "role": "short_market", "match": "CD(91일)"},
    {
        "id": "bok_base",
        "label": "한국은행 기준금리",
        "role": "policy",
        "match": "한국은행 기준금리",
    },
    {"id": "ktb_3y", "label": "국고채(3년)", "role": "medium_market", "match": "국고채(3년)"},
)

M2_MATCH = "M2(평잔,계절조정계열)"


def _repo_data_dir() -> Path:
    return _DATA


def ym_int(month: str) -> int:
    y, m = month.split("-")
    return int(y) * 100 + int(m)


def ym_str(key: int) -> str:
    return f"{key // 100:04d}-{key % 100:02d}"


def add_periods(key: int, lag: int, *, grain: Grain) -> int:
    if grain == "year":
        return key + lag
    y, m = divmod(key, 100)
    m0 = y * 12 + (m - 1) + lag
    y2, m2 = divmod(m0, 12)
    return y2 * 100 + (m2 + 1)


def _candidate_dirs(root: Path) -> list[Path]:
    out = [root]
    if not root.is_dir():
        return out
    for p in sorted(root.iterdir()):
        if p.is_dir() and "한은" in p.name:
            out.append(p)
    return out


def _parse_num(raw: str) -> float | None:
    s = (raw or "").strip().replace(",", "").replace('"', "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _period_kind(col: str) -> str | None:
    c = col.strip()
    if _YEAR_COL.match(c):
        return "year"
    if _MONTH_COL.match(c):
        return "month"
    return None


def parse_ecos_wide(path: Path) -> dict[str, Any]:
    """ECOS 가로형: 통계표,계정항목,단위,변환,기간…"""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError(f"빈 CSV: {path.name}")
    header = [h.strip() for h in rows[0]]
    if len(header) < 5 or header[1] != "계정항목":
        raise ValueError(f"ECOS 가로형이 아님: {path.name}")
    period_idx: list[tuple[int, str, str]] = []
    for i, col in enumerate(header[4:], start=4):
        kind = _period_kind(col)
        if kind == "year":
            period_idx.append((i, "year", col.strip()))
        elif kind == "month":
            m = _MONTH_COL.match(col.strip())
            assert m
            period_idx.append((i, "month", f"{m.group(1)}-{int(m.group(2)):02d}"))
    kinds = {k for _, k, _ in period_idx}
    freq = "month" if "month" in kinds else "year"
    series: dict[str, dict[str, Any]] = {}
    for row in rows[1:]:
        if len(row) < 4:
            continue
        name = (row[1] or "").strip()
        if not name:
            continue
        unit = (row[2] or "").strip()
        points: list[dict[str, Any]] = []
        for i, kind, per in period_idx:
            if kind != freq:
                continue
            v = _parse_num(row[i] if i < len(row) else "")
            if v is None:
                continue
            if kind == "year":
                points.append({"year": int(per), "v": v})
            else:
                points.append({"month": per, "v": v})
        series[name] = {"unit": unit, "points": points}
    return {
        "path": str(path),
        "file": path.name,
        "frequency": freq,
        "series": series,
    }


def parse_ecos_calendar_years(path: Path) -> dict[str, Any]:
    """달력 연 열만 읽는다. 월 열은 무시. `2025 p)`는 year=2025, provisional.

    주식시장 CSV처럼 월·연이 한 장에 있어도 연 시계열을 쓴다.
    같은 해에 확정 열과 잠정 열이 같이 있으면 확정을 남긴다.
    """
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError(f"빈 CSV: {path.name}")
    header = [h.strip() for h in rows[0]]
    if len(header) < 5 or header[1] != "계정항목":
        raise ValueError(f"ECOS 가로형이 아님: {path.name}")
    year_idx: list[tuple[int, int, bool]] = []
    for i, col in enumerate(header[4:], start=4):
        c = col.strip()
        if _MONTH_COL.match(c):
            continue
        m = _YEAR_COL_FLEX.match(c)
        if not m:
            continue
        year_idx.append((i, int(m.group(1)), bool(re.search(r"p\s*\)?", c, re.I))))
    if not year_idx:
        raise ValueError(f"연 열 없음: {path.name}")
    series: dict[str, dict[str, Any]] = {}
    for row in rows[1:]:
        if len(row) < 4:
            continue
        name = (row[1] or "").strip()
        if not name:
            continue
        unit = (row[2] or "").strip()
        by_year: dict[int, dict[str, Any]] = {}
        for i, year, prov in year_idx:
            v = _parse_num(row[i] if i < len(row) else "")
            if v is None:
                continue
            prev = by_year.get(year)
            if prev is not None and (not prev["provisional"]) and prov:
                continue
            by_year[year] = {"year": year, "v": v, "provisional": prov}
        points = [by_year[y] for y in sorted(by_year)]
        series[name] = {"unit": unit, "points": points}
    return {
        "path": str(path),
        "file": path.name,
        "frequency": "year",
        "series": series,
    }


def find_named_series(parsed: dict[str, Any], match: str) -> dict[str, Any] | None:
    return _find_series(parsed, match)


def _find_series(parsed: dict[str, Any], match: str) -> dict[str, Any] | None:
    series: dict[str, dict[str, Any]] = parsed["series"]
    if match in series:
        return series[match]
    key = match.replace(" ", "")
    for name, block in series.items():
        if name.replace(" ", "") == key:
            return block
    if "기준금리" in match:
        for name, block in series.items():
            n = name.replace(" ", "")
            if "기준금리" in n and "한국은행" in n:
                return block
            if n == "기준금리":
                return block
    return None


def _level_map(points: list[dict[str, Any]]) -> tuple[Grain, dict[int, float]]:
    month_pts = [p for p in points if "month" in p]
    if month_pts:
        return "month", {ym_int(str(p["month"])): float(p["v"]) for p in month_pts}
    return "year", {int(p["year"]): float(p["v"]) for p in points if "year" in p}


def _emit(grain: Grain, key: int, v: float) -> dict[str, Any]:
    if grain == "month":
        return {"month": ym_str(key), "v": v}
    return {"year": key, "v": v}


def _delta_pp(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """금리: 전년(동월) 대비 %p."""
    grain, mp = _level_map(points)
    step = 100 if grain == "month" else 1
    out: list[dict[str, Any]] = []
    for k in sorted(mp):
        prev = k - step
        if prev not in mp:
            continue
        out.append(_emit(grain, k, round(mp[k] - mp[prev], 4)))
    return out


def _yoy_pct(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """수준 시계열의 전년(동월) %."""
    grain, mp = _level_map(points)
    step = 100 if grain == "month" else 1
    out: list[dict[str, Any]] = []
    for k in sorted(mp):
        prev = mp.get(k - step)
        if prev is None or prev == 0:
            continue
        out.append(_emit(grain, k, round((mp[k] - prev) / abs(prev) * 100.0, 4)))
    return out


def _latest_for_freq(
    root: Path, pattern: str, want: Grain
) -> tuple[Path, dict[str, Any]] | None:
    hits: list[tuple[float, Path, dict[str, Any]]] = []
    for folder in _candidate_dirs(root):
        for path in folder.glob(pattern):
            try:
                parsed = parse_ecos_wide(path)
            except (OSError, ValueError):
                continue
            if parsed["frequency"] != want:
                continue
            hits.append((path.stat().st_mtime, path, parsed))
    if not hits:
        return None
    hits.sort(key=lambda x: x[0])
    _, path, parsed = hits[-1]
    return path, parsed


def load_macro_ecos(
    *,
    data_dir: Path | None = None,
    frequency: Grain = "year",
) -> dict[str, Any]:
    root = data_dir or _repo_data_dir()
    if not root.is_dir():
        raise FileNotFoundError(f"data 폴더 없음: {root}")
    rates_hit = _latest_for_freq(root, "시장금리*.csv", frequency)
    m2_hit = _latest_for_freq(root, "M2*.csv", frequency)
    policy_hit = _latest_for_freq(root, "*기준금리*.csv", frequency)
    if rates_hit is None:
        raise FileNotFoundError(f"data/ 시장금리*.csv ({frequency}) 없음")
    if m2_hit is None:
        raise FileNotFoundError(f"data/ M2*.csv ({frequency}) 없음")
    rates_path, rates_parsed = rates_hit
    _, m2_parsed = m2_hit
    policy_parsed = policy_hit[1] if policy_hit is not None else None

    def lookup_rate(match: str) -> dict[str, Any] | None:
        for parsed in (rates_parsed, policy_parsed):
            if parsed is None:
                continue
            hit = _find_series(parsed, match)
            if hit is not None:
                return hit
        return None

    missing: list[str] = []
    rates_out: dict[str, Any] = {}
    for spec in RATE_CATALOG:
        hit = lookup_rate(spec["match"])
        if hit is None:
            missing.append(spec["id"])
            continue
        pts = hit["points"]
        rates_out[spec["id"]] = {
            "id": spec["id"],
            "label": spec["label"],
            "role": spec["role"],
            "unit": hit["unit"],
            "values": pts,
            "d_pp": _delta_pp(pts),
        }

    m2_hit_series = _find_series(m2_parsed, M2_MATCH)
    m2_out: dict[str, Any] | None = None
    if m2_hit_series is None:
        missing.append("m2")
    else:
        pts = m2_hit_series["points"]
        m2_out = {
            "id": "m2",
            "label": "M2(평잔, 계절조정)",
            "unit": m2_hit_series["unit"],
            "values": pts,
            "yoy_pct": _yoy_pct(pts),
        }

    periods: set[int] = set()
    grain: Grain = frequency
    for block in rates_out.values():
        g, mp = _level_map(block["values"])
        grain = g
        periods.update(mp)
    if m2_out:
        _, mp = _level_map(m2_out["values"])
        periods.update(mp)

    return {
        "lab": "macro_ecos",
        "note": (
            "ECOS 월 시계열. 전년동월 변화. 인과 아님."
            if frequency == "month"
            else "ECOS 연도 시계열. 수준 상관은 추세 주의. 인과 아님."
        ),
        "grain": "calendar_month" if frequency == "month" else "calendar_year",
        "default_rate": "cd_91",
        "sources": {
            "rates": rates_parsed["file"],
            "policy": policy_parsed["file"] if policy_parsed else None,
            "m2": m2_parsed["file"],
            "rates_frequency": rates_parsed["frequency"],
            "policy_frequency": policy_parsed["frequency"] if policy_parsed else None,
            "m2_frequency": m2_parsed["frequency"],
            "rates_dir": str(rates_path.parent.name),
        },
        "years": sorted({k // 100 if frequency == "month" else k for k in periods}),
        "periods": [ym_str(k) if frequency == "month" else str(k) for k in sorted(periods)],
        "rates": rates_out,
        "m2": m2_out,
        "missing": missing,
    }
