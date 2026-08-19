"""M2 오차 단지 태깅 — 반복 패턴만 다음 변수 후보. M4 금지."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any
import json

from app.collective.new_apt.constants import (
    APE_REVIEW_HOLDOUT,
    APE_REVIEW_MAX,
    APE_REVIEW_NEW_MEDIAN,
    BOOM_YEARS,
    COMMERCIAL_ZONES,
    ERROR_REPEAT_MIN,
    EXPENSIVE_LAND_P50,
    INDUSTRIAL_ZONES,
    LAND_THIN_N,
    LARGE_NEW_HH,
    LOW_PARKING,
    NEW_AGE_MAX,
    OLD_STOCK_AGE,
    SMALL_COMPLEX_HH,
    WATCH_MIN_BUILDERS,
    WATCH_MIN_SIGUNGU,
)

TAG_SPEC: dict[str, dict[str, str]] = {
    "thin_land": {"bucket": "data", "label": "토지 셀 n<15", "action": "data_fix"},
    "commercial_zone": {"bucket": "data", "label": "상업지역 토지 조인", "action": "data_fix"},
    "industrial_zone": {"bucket": "data", "label": "공업지역 토지 조인", "action": "data_fix"},
    "quality_flag": {"bucket": "data", "label": "K-apt 품질 플래그", "action": "data_fix"},
    "thin_tx": {"bucket": "data", "label": "거래 n<15", "action": "warning_only"},
    "small_complex": {"bucket": "structure", "label": "소형 단지(<300세대)", "action": "warning_only"},
    "old_stock": {"bucket": "structure", "label": "노후(연식>15년)", "action": "ignore_old_stock"},
    "low_parking": {"bucket": "structure", "label": "주차 <0.8대", "action": "warning_only"},
    "low_rise": {"bucket": "structure", "label": "5층 이하", "action": "warning_only"},
    "jusang": {"bucket": "extra", "label": "주상복합", "action": "warning_only"},
    "expensive_land_overpred": {
        "bucket": "extra",
        "label": "비싼 땅·낮은 실거래(과대예측)",
        "action": "data_fix",
    },
    "large_new_underpred": {
        "bucket": "extra",
        "label": "신축 대단지 과소예측",
        "action": "later_variable",
    },
    "boom_years": {"bucket": "market", "label": "2020–22년 셀 집중", "action": "warning_only"},
    "systematic": {"bucket": "extra", "label": "여러 해 같은 방향 오차", "action": "warning_only"},
}


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None  # NaN


def tag_cell(cell: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if not cell.get("in_m2") or cell.get("ape") is None:
        return tags
    zone = str(cell.get("zone_compact") or "")
    land_n = _num(cell.get("land_n"))
    hh = _num(cell.get("households"))
    age = _num(cell.get("age"))
    pk = _num(cell.get("parking_per_household"))
    fl = _num(cell.get("max_floor"))
    n_tx = _num(cell.get("n_tx"))
    land = _num(cell.get("land_p50"))
    resid = _num(cell.get("residual"))
    ape = _num(cell.get("ape")) or 0.0

    if land_n is not None and land_n < LAND_THIN_N:
        tags.append("thin_land")
    if zone in COMMERCIAL_ZONES:
        tags.append("commercial_zone")
    if zone in INDUSTRIAL_ZONES:
        tags.append("industrial_zone")
    flags = cell.get("attr_quality_flags")
    if flags and str(flags).strip():
        tags.append("quality_flag")
    if n_tx is not None and n_tx < 15:
        tags.append("thin_tx")
    if hh is not None and hh < SMALL_COMPLEX_HH:
        tags.append("small_complex")
    if age is not None and age > OLD_STOCK_AGE:
        tags.append("old_stock")
    if pk is not None and pk < LOW_PARKING:
        tags.append("low_parking")
    if fl is not None and fl <= 5:
        tags.append("low_rise")
    danji = str(cell.get("danji_class") or "")
    if "주상" in danji:
        tags.append("jusang")
    if resid is not None and resid < 0 and land is not None and land >= EXPENSIVE_LAND_P50 and ape >= 30:
        tags.append("expensive_land_overpred")
    if (
        resid is not None
        and resid > 0
        and ape >= 20
        and hh is not None
        and hh >= LARGE_NEW_HH
        and age is not None
        and age <= NEW_AGE_MAX
    ):
        tags.append("large_new_underpred")
    year = cell.get("calendar_year")
    if year is not None and int(year) in BOOM_YEARS and ape >= 50:
        tags.append("boom_years")
    return tags


def _is_new_building(rows: list[dict[str, Any]]) -> bool:
    ages = [_num(r.get("age")) for r in rows]
    ages_ok = [a for a in ages if a is not None]
    if not ages_ok:
        return False
    return min(ages_ok) <= NEW_AGE_MAX


def _review(b: dict[str, Any]) -> bool:
    if b["in_holdout"] and (b["max_ape"] >= APE_REVIEW_HOLDOUT or b["median_ape"] >= APE_REVIEW_HOLDOUT):
        return True
    if b["is_new"] and b["median_ape"] >= APE_REVIEW_NEW_MEDIAN:
        return True
    return b["max_ape"] >= APE_REVIEW_MAX


def _aggregate_building(key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    apes = sorted(_num(r.get("ape")) or 0.0 for r in rows if r.get("ape") is not None)
    resids = [_num(r.get("residual")) for r in rows if _num(r.get("residual")) is not None]
    mid = apes[len(apes) // 2] if apes else 0.0
    mean_res = sum(resids) / len(resids) if resids else 0.0
    signs = [1 if r > 0 else -1 for r in resids if r != 0]
    systematic = len(rows) >= 3 and len(signs) >= 3 and len(set(signs)) == 1
    tags: set[str] = set()
    for r in rows:
        tags.update(r.get("error_tags") or [])
    if systematic:
        tags.add("systematic")
    first = rows[0]
    ages = [_num(r.get("age")) for r in rows]
    ages_ok = [a for a in ages if a is not None]
    hh = first.get("households")
    is_new = _is_new_building(rows)
    if (
        hh is not None
        and float(hh) >= LARGE_NEW_HH
        and is_new
        and mean_res > 0
        and mid >= 20
    ):
        tags.add("large_new_underpred")
    return {
        "building_key": key,
        "display_name": first.get("display_name"),
        "sigungu_name": first.get("sigungu_name"),
        "sigungu_code": first.get("sigungu_code"),
        "n_years": len(rows),
        "median_ape": round(mid, 1),
        "max_ape": round(max(apes), 1) if apes else 0.0,
        "mean_residual": round(mean_res, 1),
        "direction": "underpred" if mean_res > 0 else "overpred",
        "households": first.get("households"),
        "vintage": first.get("vintage"),
        "age_min": int(min(ages_ok)) if ages_ok else None,
        "zone_compact": first.get("zone_compact"),
        "land_n_min": min((int(r["land_n"]) for r in rows if r.get("land_n") is not None), default=None),
        "land_p50": first.get("land_p50"),
        "danji_class": first.get("danji_class"),
        "builder_group": first.get("builder_group"),
        "brand": first.get("brand"),
        "in_holdout": bool(first.get("in_holdout")),
        "is_new": is_new,
        "tags": sorted(tags),
        "years": sorted({r.get("calendar_year") for r in rows if r.get("calendar_year") is not None}),
    }


def audit_m2_errors(cells: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    by_b: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in cells:
        cell = dict(raw)
        if cell.get("in_m2") and cell.get("ape") is not None:
            cell["error_tags"] = tag_cell(cell)
            by_b[str(cell["building_key"])].append(cell)
        else:
            cell["error_tags"] = []
        tagged.append(cell)

    buildings = [_aggregate_building(k, rows) for k, rows in by_b.items()]
    for b in buildings:
        b["in_review"] = _review(b)
    review = [b for b in buildings if b["in_review"]]
    review.sort(key=lambda b: (-b["max_ape"], -b["median_ape"]))

    patterns: list[dict[str, Any]] = []
    for tag, spec in TAG_SPEC.items():
        hit = [b for b in review if tag in b["tags"]]
        n = len(hit)
        n_hold = sum(1 for b in hit if b["in_holdout"])
        n_new = sum(1 for b in hit if b["is_new"] and not b["in_holdout"])
        n_old = sum(1 for b in hit if not b["is_new"])
        repeat = n >= ERROR_REPEAT_MIN
        relevant = n_hold + n_new
        action = spec["action"]
        if action == "later_variable" and (not repeat or relevant < ERROR_REPEAT_MIN):
            action = "warning_only"
        if action == "data_fix" and not repeat:
            action = "warning_only"
        patterns.append(
            {
                "tag": tag,
                "label": spec["label"],
                "bucket": spec["bucket"],
                "n_buildings": n,
                "n_holdout": n_hold,
                "n_new_train": n_new,
                "n_old": n_old,
                "repeat": repeat,
                "action": action,
                "examples": [
                    {
                        "building_key": b["building_key"],
                        "display_name": b.get("display_name") or b["building_key"][:12],
                        "median_ape": b["median_ape"],
                        "sigungu_name": b.get("sigungu_name"),
                        "in_holdout": b["in_holdout"],
                    }
                    for b in hit[:5]
                ],
            }
        )
    patterns.sort(key=lambda p: (-p["n_buildings"], p["tag"]))

    next_vars = [p for p in patterns if p["action"] == "later_variable"]
    data_fixes = [p for p in patterns if p["action"] == "data_fix" and p["repeat"]]
    watch = summarize_watch(buildings)
    notes = [
        "M2가 대전 신규아파트 기준식이다. M4를 만들지 않는다.",
        "반복(단지≥5)만 다음 변수 후보다. 노후·소형·주상복합은 변수 추가 금지.",
        "신축 대단지 과소예측은 시공사·브랜드 수를 쌓아 두고, 한 구에 몰리면 레이어를 열지 않는다.",
        "시공사와 브랜드는 나중에 각각 M2에 붙여 hold-out으로 경쟁시킨다. 한 식에 동시 투입 금지.",
    ]
    decision = build_decision(next_vars, data_fixes, watch)
    return tagged, {
        "n_m2_buildings": len(buildings),
        "n_review_buildings": len(review),
        "repeat_min": ERROR_REPEAT_MIN,
        "buildings": review[:80],
        "patterns": patterns,
        "next_variable_candidates": [p["tag"] for p in next_vars],
        "data_fix_candidates": [p["tag"] for p in data_fixes],
        "large_new_watch": watch,
        "decision": decision,
        "notes": notes,
    }


def summarize_watch(buildings: list[dict[str, Any]]) -> dict[str, Any]:
    hit = [
        b
        for b in buildings
        if "large_new_underpred" in (b.get("tags") or [])
        and b.get("direction") == "underpred"
        and float(b.get("median_ape") or 0) >= 20
    ]
    apes = [float(b["median_ape"]) for b in hit]
    builders = {str(b.get("builder_group")) for b in hit if b.get("builder_group")}
    brands = {str(b.get("brand")) for b in hit if b.get("brand")}
    gu = {str(b.get("sigungu_code") or b.get("sigungu_name")) for b in hit if b.get("sigungu_code") or b.get("sigungu_name")}
    n_under = sum(1 for b in hit if b.get("direction") == "underpred")
    n = len(hit)
    ready = (
        n >= ERROR_REPEAT_MIN
        and len(gu) >= WATCH_MIN_SIGUNGU
        and len(builders) >= WATCH_MIN_BUILDERS
        and (sum(apes) / n if n else 0) >= 20
    )
    return {
        "pattern": "신축 + 대단지 + 과소예측",
        "n_buildings": n,
        "n_builders": len(builders),
        "n_brands": len(brands),
        "n_sigungu": len(gu),
        "mean_ape": round(float(sum(apes) / n), 1) if n else None,
        "direction_underpred_pct": round(100.0 * n_under / n, 1) if n else None,
        "builders": sorted(builders),
        "brands": sorted(brands),
        "ready_for_builder_layer": ready,
        "gate": {
            "repeat_min": ERROR_REPEAT_MIN,
            "min_sigungu": WATCH_MIN_SIGUNGU,
            "min_builders": WATCH_MIN_BUILDERS,
            "note": "단지·구·시공사가 한쪽에 몰리면 브랜드와 입지를 분리할 수 없다",
        },
        "members": [
            {
                "building_key": b["building_key"],
                "display_name": b.get("display_name"),
                "sigungu_name": b.get("sigungu_name"),
                "median_ape": b.get("median_ape"),
                "households": b.get("households"),
                "builder_group": b.get("builder_group"),
                "brand": b.get("brand"),
                "in_holdout": b.get("in_holdout"),
            }
            for b in sorted(hit, key=lambda x: -float(x.get("median_ape") or 0))
        ],
        "history": [],
    }


def build_decision(
    next_vars: list[dict[str, Any]],
    data_fixes: list[dict[str, Any]],
    watch: dict[str, Any],
) -> dict[str, Any]:
    if watch.get("ready_for_builder_layer"):
        next_step = "누적 문턱은 넘었다. M2에 넣지 말고, M2 vs M2+시공사를 hold-out으로만 비교 검토한다. 브랜드와 동시 투입 금지."
    elif watch.get("n_buildings"):
        next_step = "신축 대단지 과소예측을 누적한다. 시공사 레이어는 아직 열지 않는다."
    else:
        next_step = "데이터 수정 후보를 먼저 보고, M2 시뮬을 유지한다."
    return {
        "baseline_locked": True,
        "baseline": "M2",
        "open_next_variable": False,
        "verdict": "M2 기준식 고정. 다음 변수 없음.",
        "data_fixes": [p["tag"] for p in data_fixes],
        "next_step": next_step,
        "builder_vs_brand": "나중에 M2+시공사 vs M2+브랜드를 hold-out MAPE로 경쟁. 동시 투입 금지.",
    }


def refresh_watch_fields(audit: dict[str, Any]) -> dict[str, Any]:
    """이름·브랜드 조인 뒤 watch/decision을 다시 집계."""
    prev = audit.get("large_new_watch") or {}
    members = list(prev.get("members") or [])
    fake = [
        {
            **m,
            "tags": ["large_new_underpred"],
            "direction": m.get("direction") or "underpred",
        }
        for m in members
    ]
    watch = summarize_watch(fake)
    watch["history"] = prev.get("history") or []
    audit["large_new_watch"] = watch
    audit["decision"] = build_decision(
        [p for p in (audit.get("patterns") or []) if p.get("action") == "later_variable"],
        [p for p in (audit.get("patterns") or []) if p.get("action") == "data_fix" and p.get("repeat")],
        watch,
    )
    return audit


def ledger_path() -> Path:
    return Path(__file__).resolve().parents[4] / "pipeline" / "rent" / "_new_apt_pattern_ledger.json"


def append_watch_ledger(sido_code: str, watch: dict[str, Any]) -> list[dict[str, Any]]:
    """신축 대단지 과소예측 스냅샷을 날짜별로 쌓는다. 같은 날은 덮어쓴다."""
    path = ledger_path()
    doc: dict[str, Any] = {"sido_code": sido_code, "snapshots": []}
    try:
        if path.exists():
            doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        doc = {"sido_code": sido_code, "snapshots": []}
    snap = {
        "as_of": date.today().isoformat(),
        "n_buildings": watch.get("n_buildings"),
        "n_builders": watch.get("n_builders"),
        "n_brands": watch.get("n_brands"),
        "n_sigungu": watch.get("n_sigungu"),
        "mean_ape": watch.get("mean_ape"),
        "direction_underpred_pct": watch.get("direction_underpred_pct"),
        "ready_for_builder_layer": watch.get("ready_for_builder_layer"),
        "building_keys": [m.get("building_key") for m in (watch.get("members") or [])],
    }
    snaps = list(doc.get("snapshots") or [])
    if snaps and snaps[-1].get("as_of") == snap["as_of"]:
        snaps[-1] = snap
    else:
        snaps.append(snap)
    doc["sido_code"] = sido_code
    doc["snapshots"] = snaps[-24:]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        return snaps
    return doc["snapshots"]
