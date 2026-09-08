"""ECOS(한국은행) CSV — G3 랩 1차(연도). 원장 재수집 없음.

파일명에 다운로드 시각이 붙으므로 glob으로 최신 파일을 고른다.
월별 헤더(2010/01)가 오면 frequency=month로 표시만 하고, 1차는 연도 열만 쓴다.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_DATA = _REPO / "data"

_YEAR_COL = re.compile(r"^\d{4}$")
_MONTH_COL = re.compile(r"^(\d{4})[./\-](\d{1,2})$")

# 기본 화면 대표 = CD 91일. 기준금리·국고 3년은 확인용. COFIX는 다른 질문.
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


def _latest(data_dir: Path, pattern: str) -> Path | None:
    hits = sorted(data_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


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


def _find_series(parsed: dict[str, Any], match: str) -> dict[str, Any] | None:
    series: dict[str, dict[str, Any]] = parsed["series"]
    if match in series:
        return series[match]
    key = match.replace(" ", "")
    for name, block in series.items():
        if name.replace(" ", "") == key:
            return block
    # 기준금리 표는 계정명이 조금 다를 수 있음
    if "기준금리" in match:
        for name, block in series.items():
            n = name.replace(" ", "")
            if "기준금리" in n and "한국은행" in n:
                return block
            if n == "기준금리":
                return block
    return None


def _delta_pp(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """금리: 전년 대비 %p. 연도 시계열만."""
    by_y = {int(p["year"]): float(p["v"]) for p in points if "year" in p}
    out: list[dict[str, Any]] = []
    for y in sorted(by_y):
        prev = by_y.get(y - 1)
        if prev is None:
            continue
        out.append({"year": y, "v": round(by_y[y] - prev, 4)})
    return out


def _yoy_pct(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_y = {int(p["year"]): float(p["v"]) for p in points if "year" in p}
    out: list[dict[str, Any]] = []
    for y in sorted(by_y):
        prev = by_y.get(y - 1)
        if prev is None or prev == 0:
            continue
        out.append({"year": y, "v": round((by_y[y] - prev) / abs(prev) * 100.0, 4)})
    return out


def load_macro_ecos(*, data_dir: Path | None = None) -> dict[str, Any]:
    root = data_dir or _repo_data_dir()
    if not root.is_dir():
        raise FileNotFoundError(f"data 폴더 없음: {root}")
    rates_path = _latest(root, "시장금리*.csv")
    m2_path = _latest(root, "M2*.csv")
    policy_path = _latest(root, "*기준금리*.csv")
    if rates_path is None:
        raise FileNotFoundError("data/시장금리*.csv 없음")
    if m2_path is None:
        raise FileNotFoundError("data/M2*.csv 없음")

    rates_parsed = parse_ecos_wide(rates_path)
    m2_parsed = parse_ecos_wide(m2_path)
    policy_parsed = parse_ecos_wide(policy_path) if policy_path is not None else None

    def lookup_rate(match: str) -> tuple[dict[str, Any] | None, str | None]:
        for parsed in (rates_parsed, policy_parsed):
            if parsed is None:
                continue
            hit = _find_series(parsed, match)
            if hit is not None:
                return hit, parsed["frequency"]
        return None, None

    missing: list[str] = []
    rates_out: dict[str, Any] = {}
    for spec in RATE_CATALOG:
        hit, freq = lookup_rate(spec["match"])
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
            "d_pp": _delta_pp(pts) if freq == "year" else [],
        }

    m2_hit = _find_series(m2_parsed, M2_MATCH)
    m2_out: dict[str, Any] | None = None
    if m2_hit is None:
        missing.append("m2")
    else:
        pts = m2_hit["points"]
        m2_out = {
            "id": "m2",
            "label": "M2(평잔, 계절조정)",
            "unit": m2_hit["unit"],
            "values": pts,
            "yoy_pct": _yoy_pct(pts) if m2_parsed["frequency"] == "year" else [],
        }

    years: set[int] = set()
    for block in rates_out.values():
        years.update(int(p["year"]) for p in block["values"] if "year" in p)
    if m2_out:
        years.update(int(p["year"]) for p in m2_out["values"] if "year" in p)

    return {
        "lab": "macro_ecos",
        "note": "ECOS 연도 시계열. 수준 상관은 추세 주의. 인과 아님.",
        "grain": "calendar_year",
        "default_rate": "cd_91",
        "sources": {
            "rates": rates_parsed["file"],
            "policy": policy_parsed["file"] if policy_parsed else None,
            "m2": m2_parsed["file"],
            "rates_frequency": rates_parsed["frequency"],
            "policy_frequency": policy_parsed["frequency"] if policy_parsed else None,
            "m2_frequency": m2_parsed["frequency"],
        },
        "years": sorted(years),
        "rates": rates_out,
        "m2": m2_out,
        "missing": missing,
    }
