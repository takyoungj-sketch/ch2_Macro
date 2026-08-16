"""Lab-only Twin Engine V2 runner (D-044).

Reads V1 `regional_profile`. Does not write marts or swap the product Twin card.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.map.neighbors import canonicalize_code_for_level, fetch_neighbor_codes
from app.region_canonical import resolve_to_canonical

_PIPE = Path(__file__).resolve().parents[2] / "pipeline"
if str(_PIPE) not in sys.path:
    sys.path.insert(0, str(_PIPE))

from profile_twin.v2 import (  # noqa: E402
    V2Score,
    V2Snapshot,
    compute_similarity_v2,
    expand_nhop,
    extract_snapshot,
    in_region_scope,
    load_v2_weights,
    pass_population_log_gate,
)
from region_scope import candidate_scope_sidoes, region_name_of  # noqa: E402

_VALID_LEVELS = frozenset({"sigungu", "eupmyeondong", "beopjungri"})
_NEIGHBOR_LEVEL = {
    "eupmyeondong": "eupmyeondong",
    "beopjungri": "beopjungri",
}


def _canonical_code(land_db: Session | None, *, region_level: str, region_code: str) -> str:
    code = (region_code or "").strip()
    lv = region_level.strip().lower()
    if land_db is None:
        if lv == "eupmyeondong":
            return code[:8]
        if lv == "sigungu":
            return code[:5]
        return code
    probe = code[:8] if lv == "eupmyeondong" and len(code) >= 8 else code
    resolved = resolve_to_canonical(land_db, [probe])
    out = resolved[0] if resolved else probe
    if lv == "eupmyeondong":
        return out[:8]
    if lv == "sigungu":
        return out[:5]
    return out


_PROFILE_VERSION_FALLBACKS = ("v2.1-national", "v2.0-national")


def _code_aliases(region_level: str, code: str) -> list[str]:
    c = (code or "").strip()
    out: list[str] = []
    for item in (c, c[:8] if region_level == "eupmyeondong" else "", f"{c[:8]}00" if region_level == "eupmyeondong" and len(c) >= 8 else ""):
        s = item.strip()
        if s and s not in out:
            out.append(s)
    return out


def _resolve_anchor_row(
    db: Session,
    *,
    profile_version: str,
    region_level: str,
    window_years: int,
    region_code: str,
) -> tuple[str, date, str, dict[str, Any]]:
    """앵커가 실제로 있는 version×as_of. 전국 MAX 월을 쓰지 않는다.

    v2.1 7월은 일부만 있어서 가경동처럼 6월만 있는 지역이 빠진다.
    """
    versions: list[str] = []
    for v in (profile_version, *_PROFILE_VERSION_FALLBACKS):
        if v and v not in versions:
            versions.append(v)
    codes = _code_aliases(region_level, region_code)
    if not codes:
        raise LookupError("지역코드 없음")
    for pv in versions:
        stmt = text(
            """
            SELECT region_code, as_of_month, features
            FROM regional_profile
            WHERE profile_version = :pv
              AND region_level = :level
              AND window_years = :wy
              AND region_code IN :codes
            ORDER BY as_of_month DESC
            LIMIT 1
            """
        ).bindparams(bindparam("codes", expanding=True))
        row = db.execute(
            stmt,
            {"pv": pv, "level": region_level, "wy": window_years, "codes": codes},
        ).mappings().first()
        if row and row.get("as_of_month"):
            feats = row.get("features") or {}
            if not isinstance(feats, dict):
                feats = dict(feats)
            return (
                pv,
                row["as_of_month"],
                str(row["region_code"]).strip(),
                feats,
            )
    raise LookupError(f"앵커 프로필 없음: {region_level}/{region_code}")


def _load_profiles(
    db: Session,
    *,
    profile_version: str,
    region_level: str,
    window_years: int,
    as_of: date,
    sidoes: frozenset[str] | None = None,
    codes: list[str] | None = None,
    sigungu_prefixes: list[str] | None = None,
) -> list[dict[str, Any]]:
    where = [
        "profile_version = :pv",
        "region_level = :level",
        "window_years = :wy",
        "as_of_month = :as_of",
    ]
    params: dict[str, Any] = {
        "pv": profile_version,
        "level": region_level,
        "wy": window_years,
        "as_of": as_of,
    }
    if codes and sigungu_prefixes:
        where.append("(region_code IN :codes OR left(region_code, 5) IN :prefixes)")
        params["codes"] = codes
        params["prefixes"] = sigungu_prefixes
    elif codes:
        where.append("region_code IN :codes")
        params["codes"] = codes
    elif sigungu_prefixes:
        where.append("left(region_code, 5) IN :prefixes")
        params["prefixes"] = sigungu_prefixes
    elif sidoes:
        where.append("left(region_code, 2) IN :sidoes")
        params["sidoes"] = sorted(sidoes)

    sql = f"""
        SELECT region_code, features
        FROM regional_profile
        WHERE {" AND ".join(where)}
    """
    stmt = text(sql)
    if "codes" in params:
        stmt = stmt.bindparams(bindparam("codes", expanding=True))
    if "prefixes" in params:
        stmt = stmt.bindparams(bindparam("prefixes", expanding=True))
    if "sidoes" in params:
        stmt = stmt.bindparams(bindparam("sidoes", expanding=True))
    return [dict(r) for r in db.execute(stmt, params).mappings().all()]


def _nhop_from_db(
    land_db: Session | None,
    *,
    region_level: str,
    seeds: list[str],
    n_hop: int,
) -> tuple[set[str], bool]:
    nb_level = _NEIGHBOR_LEVEL.get(region_level)
    if land_db is None or not nb_level or n_hop <= 0 or not seeds:
        return set(seeds), False
    adj: dict[str, list[str]] = {}
    frontier = {canonicalize_code_for_level(nb_level, s) for s in seeds}
    seen = set(frontier)
    current = set(frontier)
    used_graph = False
    for _ in range(n_hop):
        if not current:
            break
        fetched = fetch_neighbor_codes(land_db, level=nb_level, codes=current)
        if any(fetched.values()):
            used_graph = True
        nxt: set[str] = set()
        for node, nbs in fetched.items():
            adj.setdefault(node, [])
            for nb in nbs:
                c = canonicalize_code_for_level(nb_level, nb)
                adj[node].append(c)
                if c not in seen:
                    seen.add(c)
                    nxt.add(c)
        current = nxt
    if not used_graph:
        return set(seeds), False
    return expand_nhop(adj, seeds, n_hop) | set(seeds), True


def _sigungu_pool_from_eup_hops(
    land_db: Session | None,
    *,
    anchor_sigungu: str,
    n_hop: int,
) -> tuple[set[str], bool]:
    """시군구 풀: 앵커 시군 읍면동의 n-hop이 닿는 시군 접두어."""
    if land_db is None or n_hop <= 0:
        return {anchor_sigungu}, False
    try:
        rows = land_db.execute(
            text(
                """
                SELECT DISTINCT left(btrim(eupmyeondong_code::text), 8) AS eup
                FROM region_codes
                WHERE COALESCE(is_active, TRUE)
                  AND btrim(sigungu_code::text) = :sg
                  AND eupmyeondong_code IS NOT NULL
                """
            ),
            {"sg": anchor_sigungu},
        ).mappings().all()
    except Exception:
        return {anchor_sigungu}, False
    seeds = [str(r["eup"]).strip()[:8] for r in rows if r.get("eup")]
    hop_eups, used = _nhop_from_db(
        land_db, region_level="eupmyeondong", seeds=seeds or [anchor_sigungu], n_hop=n_hop
    )
    sigs = {c[:5] for c in hop_eups if len(c) >= 5}
    sigs.add(anchor_sigungu)
    return sigs, used


def _lookup_names(
    land_db: Session | None,
    *,
    region_level: str,
    codes: list[str],
) -> dict[str, dict[str, str]]:
    if land_db is None or not codes:
        return {}
    uniq = []
    seen: set[str] = set()
    for c in codes:
        s = str(c).strip()
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    if not uniq:
        return {}
    if region_level == "beopjungri":
        col, name_col = "btrim(beopjungri_code::text)", "beopjungri_name"
    elif region_level == "eupmyeondong":
        col, name_col = "left(btrim(eupmyeondong_code::text), 8)", "eupmyeondong_name"
    else:
        col, name_col = "btrim(sigungu_code::text)", "sigungu_name"
    try:
        stmt = text(
            f"""
            SELECT {col} AS code,
                   MAX({name_col}) AS region_name,
                   MAX(sigungu_name) AS sigungu_name,
                   MAX(sido_name) AS sido_name
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND {col} IN :codes
            GROUP BY 1
            """
        ).bindparams(bindparam("codes", expanding=True))
        rows = land_db.execute(stmt, {"codes": uniq}).mappings().all()
    except Exception:
        return {}
    return {
        str(r["code"]).strip(): {
            "region_name": str(r.get("region_name") or ""),
            "sigungu_name": str(r.get("sigungu_name") or ""),
            "sido_name": str(r.get("sido_name") or ""),
        }
        for r in rows
    }


def _v1_scores(
    db: Session,
    land_db: Session | None,
    *,
    region_level: str,
    anchor: str,
    twins: list[str],
) -> dict[str, float]:
    if not twins:
        return {}
    source = land_db if region_level == "beopjungri" and land_db is not None else db
    try:
        if region_level == "eupmyeondong":
            stmt = text(
                """
                SELECT twin_eupmyeondong_code AS code, similarity_score
                FROM twin_eupmyeondong_neighbor_mvp
                WHERE anchor_eupmyeondong_code = :anchor
                  AND twin_eupmyeondong_code IN :twins
                """
            ).bindparams(bindparam("twins", expanding=True))
        elif region_level == "sigungu":
            stmt = text(
                """
                SELECT twin_sigungu_code AS code, similarity_score
                FROM twin_region_neighbor_mvp
                WHERE anchor_sigungu_code = :anchor
                  AND twin_sigungu_code IN :twins
                """
            ).bindparams(bindparam("twins", expanding=True))
        else:
            stmt = text(
                """
                SELECT twin_region_code AS code, similarity_score
                FROM twin_neighbor_v8
                WHERE anchor_region_code = :anchor
                  AND twin_region_code IN :twins
                """
            ).bindparams(bindparam("twins", expanding=True))
        rows = source.execute(stmt, {"anchor": anchor, "twins": twins}).mappings().all()
    except Exception:
        return {}
    out: dict[str, float] = {}
    for r in rows:
        try:
            out[str(r["code"]).strip()] = float(r["similarity_score"])
        except (TypeError, ValueError, KeyError):
            continue
    return out


def _score_payload(score: V2Score) -> dict[str, Any]:
    return {
        "twin_score": score.twin_score,
        "confidence": score.confidence,
        "structure_score": score.structure_score,
        "market_score": score.market_score,
        "used_blocks": score.used_blocks,
        "dropped_blocks": score.dropped_blocks,
        "detail": {
            t.key: {
                "score": t.score,
                "used": t.used,
                "design_weight": t.design_weight,
                "note": t.note,
            }
            for t in score.terms
        },
    }


def rank_twins_v2(
    db: Session,
    land_db: Session | None,
    *,
    region_level: str,
    region_code: str,
    role: str = "compare",
    top_k: int = 8,
    n_hop: int | None = None,
    profile_version: str = "v2.1-national",
    window_years: int = 3,
    include_v1: bool = True,
) -> dict[str, Any]:
    lv = (region_level or "").strip().lower()
    if lv not in _VALID_LEVELS:
        raise ValueError("region_level은 sigungu / eupmyeondong / beopjungri 만")
    role_key = (role or "compare").strip().lower()
    if role_key not in ("compare", "pool"):
        raise ValueError("role은 compare 또는 pool")

    weights = load_v2_weights()
    rw = weights.role(role_key)
    hop = int(n_hop) if n_hop is not None else int(rw.n_hop or 2)

    asked_code = _canonical_code(land_db, region_level=lv, region_code=region_code)
    profile_version, as_of, anchor_code, anchor_feats = _resolve_anchor_row(
        db,
        profile_version=profile_version,
        region_level=lv,
        window_years=window_years,
        region_code=asked_code,
    )

    allowed = candidate_scope_sidoes(anchor_code[:2], "region")
    scope_label = region_name_of(anchor_code[:2]) or ""

    universe_fallback: str | None = None
    graph_used = False
    load_kwargs: dict[str, Any] = {}
    if role_key == "compare":
        universe_kind = "region"
        load_kwargs["sidoes"] = allowed
    elif lv == "sigungu":
        universe_kind = "sigungu_adjacent_nhop"
        hop_sigs, graph_used = _sigungu_pool_from_eup_hops(
            land_db, anchor_sigungu=anchor_code[:5], n_hop=hop
        )
        if not graph_used:
            universe_fallback = "same_sido_no_graph"
            load_kwargs["sidoes"] = frozenset({anchor_code[:2]})
        else:
            load_kwargs["sigungu_prefixes"] = sorted(hop_sigs)
    else:
        universe_kind = "sigungu_adjacent_nhop"
        hop_set, graph_used = _nhop_from_db(
            land_db, region_level=lv, seeds=[anchor_code], n_hop=hop
        )
        if not graph_used:
            universe_fallback = "same_sigungu_no_graph"
            hop_set = set()
        neighbor_sigs = {c[:5] for c in hop_set if len(c) >= 5}
        neighbor_sigs.add(anchor_code[:5])
        load_kwargs["codes"] = sorted(hop_set | {anchor_code})
        load_kwargs["sigungu_prefixes"] = sorted(neighbor_sigs)

    rows = _load_profiles(
        db,
        profile_version=profile_version,
        region_level=lv,
        window_years=window_years,
        as_of=as_of,
        **load_kwargs,
    )
    snaps: dict[str, V2Snapshot] = {}
    for row in rows:
        code = str(row.get("region_code") or "").strip()
        feats = row.get("features") or {}
        if not isinstance(feats, dict):
            feats = dict(feats)
        snaps[code] = extract_snapshot(
            feats, region_code=code, apt_min_count=weights.apt_min_count
        )

    if anchor_code not in snaps:
        snaps[anchor_code] = extract_snapshot(
            anchor_feats, region_code=anchor_code, apt_min_count=weights.apt_min_count
        )
    anchor = snaps[anchor_code]

    if role_key == "compare":
        universe_codes = {
            c
            for c, s in snaps.items()
            if c != anchor_code and in_region_scope(s.sido_code, allowed)
        }
    else:
        universe_codes = {
            c
            for c, s in snaps.items()
            if c != anchor_code and in_region_scope(s.sido_code, allowed)
        }

    gated_out = 0
    scored: list[tuple[str, V2Score]] = []
    for code in universe_codes:
        snap = snaps.get(code)
        if snap is None:
            continue
        if not pass_population_log_gate(
            anchor.population, snap.population, max_ratio=weights.population_max_ratio
        ):
            gated_out += 1
            continue
        scored.append(
            (
                code,
                compute_similarity_v2(anchor, snap, role=role_key, weights=weights),
            )
        )
    scored.sort(key=lambda x: (-x[1].twin_score, -x[1].confidence, x[0]))
    top = scored[: max(1, min(int(top_k), 30))]

    name_codes = [anchor_code] + [c for c, _ in top]
    names = _lookup_names(land_db, region_level=lv, codes=name_codes)
    v1 = {}
    if include_v1:
        v1 = _v1_scores(
            db,
            land_db,
            region_level=lv,
            anchor=anchor_code,
            twins=[c for c, _ in top],
        )

    def _name_row(code: str) -> dict[str, str]:
        return names.get(code) or {
            "region_name": "",
            "sigungu_name": "",
            "sido_name": "",
        }

    neighbors = []
    for rank, (code, score) in enumerate(top, start=1):
        nm = _name_row(code)
        payload = _score_payload(score)
        payload.update(
            {
                "rank": rank,
                "region_code": code,
                "region_name": nm["region_name"],
                "sigungu_name": nm["sigungu_name"],
                "sido_name": nm["sido_name"],
                "v1_similarity": v1.get(code),
            }
        )
        neighbors.append(payload)

    an = _name_row(anchor_code)
    return {
        "engine": "v2",
        "weight_version": weights.version,
        "role": role_key,
        "region_level": lv,
        "profile_version": profile_version,
        "window_years": window_years,
        "as_of_month": as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of),
        "anchor": {
            "region_code": anchor_code,
            "region_name": an["region_name"],
            "sigungu_name": an["sigungu_name"],
            "sido_name": an["sido_name"],
            "population": anchor.population,
        },
        "weights": {
            "structure": rw.structure_weight,
            "market": rw.market_weight,
        },
        "universe": {
            "kind": universe_kind,
            "size": len(universe_codes),
            "after_population_gate": len(scored),
            "gated_out_population": gated_out,
            "n_hop": hop if role_key == "pool" else None,
            "graph_used": bool(role_key == "pool" and graph_used),
            "fallback": universe_fallback,
            "scope_label": scope_label,
        },
        "neighbors": neighbors,
    }
