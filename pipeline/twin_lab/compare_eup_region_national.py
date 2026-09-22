#!/usr/bin/env python3
"""읍면동 쌍둥이: 같은 algo 21 점수로 권역 1위와 전국 1위를 비교한다.

제품 카드·마트는 쓰지 않는다. 후보 범위만 다르다.
프로필은 카드와 같은 v2.1-national · as_of 2026-06-01 · window 3 · general.

예:
  cd pipeline
  python -m twin_lab.compare_eup_region_national
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from sqlalchemy import text  # noqa: E402

from build_twin_profile import _load_meta, _load_profiles  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from profile_twin import compute_similarity, load_twin_catalog, load_twin_weights, project_profile  # noqa: E402
from profile_twin.candidate import twin_population_allowed  # noqa: E402
from region_scope import refresh_region_scope_from_db, region_name_of, region_sidoes  # noqa: E402

PROFILE_VERSION = "v2.1-national"
AS_OF = date(2026, 6, 1)
WINDOW_YEARS = 3
TWIN_PROFILE = "general"
OUT_PATH = REPO / "docs" / "lab" / "twin_eup_scope_region_vs_national.json"


def _pop(vector) -> float | None:
    raw = vector.values.get("population")
    try:
        value = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
    if value is None or value <= 0:
        return None
    return value


def _better(score: float, code: str, best: tuple[float, str] | None) -> bool:
    if best is None:
        return True
    if score > best[0]:
        return True
    if score == best[0] and code < best[1]:
        return True
    return False


def _tercile_ids(ranked_codes: list[str]) -> dict[str, str]:
    n = len(ranked_codes)
    out: dict[str, str] = {}
    if n == 0:
        return out
    for i, code in enumerate(ranked_codes):
        slot = min(2, (i * 3) // n)
        out[code] = ("small", "mid", "large")[slot]
    return out


def _pick_anchors(vectors, meta: dict[str, dict], *, per_tercile: int, seed: int) -> list:
    by_region: dict[str, list] = defaultdict(list)
    for vector in vectors:
        am = meta.get(vector.region_code)
        if not am:
            continue
        label = region_name_of(str(am["sido_code"])) or "기타"
        by_region[label].append(vector)

    rng = random.Random(seed)
    chosen: list = []
    for label, group in sorted(by_region.items()):
        buckets: dict[str, list] = defaultdict(list)
        known = [v for v in group if _pop(v) is not None]
        known.sort(key=lambda v: (_pop(v) or 0.0, v.region_code))
        tercile = _tercile_ids([v.region_code for v in known])
        for vector in group:
            if _pop(vector) is None:
                buckets["pop_missing"].append(vector)
            else:
                buckets[tercile[vector.region_code]].append(vector)
        for key in ("small", "mid", "large", "pop_missing"):
            pool = buckets.get(key) or []
            take = pool if len(pool) <= per_tercile else rng.sample(pool, per_tercile)
            chosen.extend(take)
    chosen.sort(key=lambda v: v.region_code)
    return chosen


def _latest_general_batch(conn) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT batch_key
            FROM twin_eupmyeondong_neighbor_mvp
            WHERE algorithm_version = 21
              AND detail_scores->>'profile_version' = :pv
              AND (detail_scores->>'window_years')::int = :wy
              AND detail_scores->>'scope' = 'region'
              AND COALESCE(detail_scores->>'twin_profile', 'general') = 'general'
            GROUP BY batch_key
            ORDER BY MAX(computed_at) DESC
            LIMIT 1
            """
        ),
        {"pv": PROFILE_VERSION, "wy": WINDOW_YEARS},
    ).first()
    return None if row is None else str(row[0])


def _stored_top1(conn, batch_key: str, codes: list[str]) -> dict[str, tuple[str, float]]:
    if not codes:
        return {}
    rows = conn.execute(
        text(
            """
            SELECT anchor_eupmyeondong_code, twin_eupmyeondong_code, similarity_score
            FROM twin_eupmyeondong_neighbor_mvp
            WHERE batch_key = :bk
              AND rank = 1
              AND anchor_eupmyeondong_code = ANY(:codes)
            """
        ),
        {"bk": batch_key, "codes": codes},
    ).fetchall()
    return {str(r[0]): (str(r[1]), float(r[2])) for r in rows}


def _scan_anchor(anchor, vectors, meta, *, catalog, weights) -> dict[str, Any]:
    am = meta[anchor.region_code]
    allowed = region_sidoes(str(am["sido_code"]))
    pop_a = anchor.values.get("population")
    best_nat: tuple[float, str] | None = None
    best_reg: tuple[float, str] | None = None
    n_nat = 0
    n_reg = 0
    for twin in vectors:
        if twin.region_code == anchor.region_code:
            continue
        tm = meta.get(twin.region_code)
        if not tm:
            continue
        if not twin_population_allowed(pop_a, twin.values.get("population"), weights=weights):
            continue
        sim = compute_similarity(anchor, twin, catalog=catalog, weights=weights)
        if sim.similarity <= 0:
            continue
        code = twin.region_code
        n_nat += 1
        if _better(sim.similarity, code, best_nat):
            best_nat = (sim.similarity, code)
        if str(tm["sido_code"]).strip()[:2] in allowed:
            n_reg += 1
            if _better(sim.similarity, code, best_reg):
                best_reg = (sim.similarity, code)

    def pack(best: tuple[float, str] | None) -> dict[str, Any] | None:
        if best is None:
            return None
        score, code = best
        tm = meta[code]
        return {
            "code": code,
            "name": str(tm["region_name"]),
            "sigungu_name": str(tm["sigungu_name"]),
            "sido_name": str(tm["sido_name"]),
            "region": region_name_of(str(tm["sido_code"])) or "기타",
            "score": score,
        }

    nat = pack(best_nat)
    reg = pack(best_reg)
    lift = None
    if nat is not None and reg is not None:
        lift = nat["score"] - reg["score"]
    outside = bool(nat and reg and nat["code"] != reg["code"] and nat["region"] != (region_name_of(str(am["sido_code"])) or "기타"))
    return {
        "anchor_code": anchor.region_code,
        "anchor_name": str(am["region_name"]),
        "sigungu_name": str(am["sigungu_name"]),
        "sido_name": str(am["sido_name"]),
        "region": region_name_of(str(am["sido_code"])) or "기타",
        "population": _pop(anchor),
        "n_national": n_nat,
        "n_region": n_reg,
        "region_top": reg,
        "national_top": nat,
        "lift": lift,
        "national_outside_region": outside,
    }


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _share(flags: list[bool]) -> float | None:
    if not flags:
        return None
    return sum(1 for f in flags if f) / len(flags)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [r for r in rows if r["lift"] is not None]
    lifts = [float(r["lift"]) for r in usable]
    reg_scores = [float(r["region_top"]["score"]) for r in usable]
    nat_scores = [float(r["national_top"]["score"]) for r in usable]

    def pack(group: list[dict[str, Any]]) -> dict[str, Any]:
        g_lifts = [float(r["lift"]) for r in group if r["lift"] is not None]
        g_reg = [float(r["region_top"]["score"]) for r in group if r["region_top"]]
        g_nat = [float(r["national_top"]["score"]) for r in group if r["national_top"]]
        return {
            "n": len(group),
            "median_region_score": _median(g_reg),
            "median_national_score": _median(g_nat),
            "median_lift": _median(g_lifts),
            "share_lift_ge_0_05": _share([x >= 0.05 for x in g_lifts]),
            "share_lift_ge_0_10": _share([x >= 0.10 for x in g_lifts]),
            "share_national_outside": _share([bool(r["national_outside_region"]) for r in group]),
        }

    by_region: dict[str, Any] = {}
    grouped: dict[str, list] = defaultdict(list)
    for row in rows:
        grouped[row["region"]].append(row)
    for label, group in sorted(grouped.items()):
        by_region[label] = pack(group)

    examples = sorted(usable, key=lambda r: (-float(r["lift"]), r["anchor_code"]))
    return {
        "n_scored": len(rows),
        "n_with_both_tops": len(usable),
        "median_region_score": _median(reg_scores),
        "median_national_score": _median(nat_scores),
        "median_lift": _median(lifts),
        "share_lift_ge_0_05": _share([x >= 0.05 for x in lifts]),
        "share_lift_ge_0_10": _share([x >= 0.10 for x in lifts]),
        "share_national_outside": _share([bool(r["national_outside_region"]) for r in usable]),
        "by_region": by_region,
        "largest_lifts": examples[:8],
        "smallest_lifts": list(reversed(examples[-8:])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-tercile", type=int, default=8)
    parser.add_argument("--seed", type=int, default=21)
    parser.add_argument("--max-anchors", type=int, default=0)
    args = parser.parse_args()

    engine = get_collective_engine()
    refresh_region_scope_from_db(engine)
    catalog = load_twin_catalog()
    weights = load_twin_weights(twin_profile=TWIN_PROFILE)

    with engine.connect() as conn:
        profiles = _load_profiles(
            conn,
            profile_version=PROFILE_VERSION,
            as_of=AS_OF,
            window_years=WINDOW_YEARS,
            region_level="eupmyeondong",
            sido_code=None,
        )
        meta = _load_meta(conn, "eupmyeondong")
        batch_key = _latest_general_batch(conn)

    vectors = [
        project_profile(
            p["features"],
            region_level="eupmyeondong",
            region_code=p["region_code"],
            catalog=catalog,
        )
        for p in profiles
        if p["region_code"] in meta
    ]
    anchors = _pick_anchors(vectors, meta, per_tercile=args.per_tercile, seed=args.seed)
    if args.max_anchors > 0:
        anchors = anchors[: args.max_anchors]

    with engine.connect() as conn:
        stored = _stored_top1(conn, batch_key, [a.region_code for a in anchors]) if batch_key else {}

    print(f"profiles={len(vectors)} anchors={len(anchors)} batch={batch_key}", flush=True)
    rows: list[dict[str, Any]] = []
    match_code = 0
    match_checked = 0
    started = time.perf_counter()
    for i, anchor in enumerate(anchors, start=1):
        t0 = time.perf_counter()
        row = _scan_anchor(anchor, vectors, meta, catalog=catalog, weights=weights)
        stored_row = stored.get(anchor.region_code)
        if stored_row and row["region_top"]:
            match_checked += 1
            same_code = stored_row[0] == row["region_top"]["code"]
            same_score = abs(stored_row[1] - round(row["region_top"]["score"], 10)) < 1e-8
            row["stored_region_top_code"] = stored_row[0]
            row["stored_region_top_score"] = stored_row[1]
            row["stored_match"] = same_code and same_score
            if row["stored_match"]:
                match_code += 1
        rows.append(row)
        elapsed = time.perf_counter() - t0
        if i == 1 or i % 10 == 0 or i == len(anchors):
            print(f"{i}/{len(anchors)} {row['sido_name']} {row['anchor_name']} {elapsed:.2f}s", flush=True)

    summary = _summarize(rows)
    payload = {
        "question": "algo 21 점수를 유지하고 읍면동 후보만 전국으로 넓히면 1위 점수가 오르는가",
        "profile_version": PROFILE_VERSION,
        "as_of_month": AS_OF.isoformat(),
        "window_years": WINDOW_YEARS,
        "twin_profile": TWIN_PROFILE,
        "weight_version": weights.version,
        "catalog_version": catalog.version,
        "stored_batch_key": batch_key,
        "seed": args.seed,
        "per_tercile": args.per_tercile,
        "n_profiles": len(vectors),
        "stored_region_top_match": {
            "checked": match_checked,
            "matched": match_code,
        },
        "elapsed_sec": round(time.perf_counter() - started, 1),
        "summary": summary,
        "rows": rows,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH}", flush=True)
    print(
        "median region/national/lift",
        summary["median_region_score"],
        summary["median_national_score"],
        summary["median_lift"],
        flush=True,
    )


if __name__ == "__main__":
    main()
