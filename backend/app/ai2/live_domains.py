"""비주거 층 지수, 임대 전환율, 지역프로필 쌍둥이. 기존 계산만 읽고 거래 행은 넣지 않는다."""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import text

from app.ai2.live_cases import _bad, _match_labels
from app.ai2.types import Alternative, AnalysisContext, ToolEnvelope
from app.collective.analysis_gates import MIN_COUNT_FLOOR_INDEX
from app.collective.floor_index_regression import MIN_GROUP_FOR_DUMMY

_LOG = logging.getLogger(__name__)

PERIOD = "2021-09~2026-08"
WINDOW_FROM = date(2021, 9, 1)
WINDOW_TO = date(2026, 8, 31)
_SHOP_INDEX_LABELS = ("초고층", "고층")
_FACTORY_INDEX_LABELS = ("3층 이상", "2층")
_SHOP_RULE = "화면 100은 1층입니다."
_FACTORY_RULE = "공장·창고 층은 지하·1·2·3층 이상입니다. 화면 100은 1층입니다."


def fetch_shop_counts(region: str) -> list[tuple[str, str, int]] | None:
    return _fetch_road_counts(region, "collective_shop")


def fetch_factory_counts(region: str) -> list[tuple[str, str, int]] | None:
    return _fetch_road_counts(region, "collective_factory")


def fetch_shop_index(cluster_key: str) -> dict | None:
    return _fetch_road_index(cluster_key, "collective_shop", "shop")


def fetch_factory_index(cluster_key: str) -> dict | None:
    return _fetch_road_index(cluster_key, "collective_factory", "factory")


def _fetch_road_counts(region: str, asset: str) -> list[tuple[str, str, int]] | None:
    from app.collective.db import get_collective_engine

    engine = get_collective_engine()
    if engine is None:
        return None
    sql = text(
        """
        SELECT cluster_key,
               COALESCE(MAX(road_name), cluster_key) AS display_name,
               COUNT(*)::int AS n
        FROM collective_commercial_transactions
        WHERE is_valid = true
          AND unit_price IS NOT NULL
          AND unit_price > 0
          AND asset_type = :asset
          AND (addr3 = :region OR addr4 = :region)
          AND contract_date >= :d0
          AND contract_date <= :d1
        GROUP BY cluster_key
        """
    )
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sql, {"asset": asset, "region": region, "d0": WINDOW_FROM, "d1": WINDOW_TO}
            ).mappings().all()
    except Exception as exc:
        _LOG.warning("AI2 road counts failed: %s", type(exc).__name__)
        return None
    return [
        (str(row["display_name"] or row["cluster_key"]), str(row["cluster_key"]), int(row["n"]))
        for row in rows
    ]


def _fetch_road_index(cluster_key: str, asset: str, floor_mode: str) -> dict | None:
    from app.collective.db import get_collective_engine
    from app.collective.floor_index_regression import compute_residential_floor_index_regression

    engine = get_collective_engine()
    if engine is None:
        return None
    sql = text(
        """
        SELECT unit_price, floor, gross_area, contract_year, contract_month,
               building_year, building_age, building_use
        FROM collective_commercial_transactions
        WHERE cluster_key = :ck
          AND is_valid = true
          AND unit_price IS NOT NULL
          AND unit_price > 0
          AND asset_type = :asset
          AND contract_date >= :d0
          AND contract_date <= :d1
        """
    )
    try:
        import pandas as pd

        with engine.connect() as conn:
            rows = conn.execute(
                sql, {"ck": cluster_key, "asset": asset, "d0": WINDOW_FROM, "d1": WINDOW_TO}
            ).mappings().all()
        frame = pd.DataFrame(rows)
        if not frame.empty:
            frame["exclusive_area"] = frame["gross_area"]
        raw = compute_residential_floor_index_regression(
            frame, asset_type=asset, dimension="floor", floor_mode=floor_mode
        )
    except Exception as exc:
        _LOG.warning("AI2 road floor index failed: %s", type(exc).__name__)
        return None
    cells = [
        {"label": cell.get("label"), "count": cell.get("count"), "index": cell.get("index")}
        for cell in raw.get("cells") or []
    ]
    return {"n": int(raw.get("n_total") or 0), "cells": cells}


def fetch_rent_rate(region: str) -> dict | None:
    from app.rent.db import get_rent_engine

    engine = get_rent_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            names = conn.execute(
                text(
                    """
                    SELECT DISTINCT addr2
                    FROM rent_conversion_rates
                    WHERE asset_type = 'apartment' AND window_years = 5 AND addr2 <> ''
                    """
                )
            ).scalars().all()
            hits = _pick_label([str(name) for name in names], region)
            if len(hits) != 1:
                return {"error": "AMBIGUOUS" if len(hits) > 1 else "NO_MATCH", "matches": hits}
            row = conn.execute(
                text(
                    """
                    SELECT r_selected, n_buildings, gate_passed, as_of_month
                    FROM rent_conversion_rates
                    WHERE asset_type = 'apartment' AND window_years = 5 AND addr2 = :addr2
                    ORDER BY as_of_month DESC
                    LIMIT 1
                    """
                ),
                {"addr2": hits[0]},
            ).mappings().first()
    except Exception as exc:
        _LOG.warning("AI2 rent rate failed: %s", type(exc).__name__)
        return None
    if row is None:
        return {"error": "NO_MATCH"}
    return {
        "region": hits[0],
        "conversion_rate": None if row["r_selected"] is None else float(row["r_selected"]),
        "n_buildings": int(row["n_buildings"] or 0),
        "gate_passed": bool(row["gate_passed"]),
        "window_years": 5,
        "as_of": None if row["as_of_month"] is None else str(row["as_of_month"]),
        "rate_region": hits[0],
    }


def fetch_profile_twin(region: str) -> dict | None:
    from app.collective.db import get_collective_engine
    from app.db import SessionLocal

    land = SessionLocal()
    try:
        sigungu = land.execute(
            text(
                """
                SELECT DISTINCT sigungu_code AS code, btrim(sigungu_name::text) AS name
                FROM region_codes
                WHERE btrim(COALESCE(sigungu_name::text, '')) <> ''
                """
            )
        ).mappings().all()
        eup = land.execute(
            text(
                """
                SELECT DISTINCT eupmyeondong_code AS code, btrim(eupmyeondong_name::text) AS name
                FROM region_codes
                WHERE btrim(COALESCE(eupmyeondong_name::text, '')) <> ''
                """
            )
        ).mappings().all()
    except Exception as exc:
        _LOG.warning("AI2 profile region match failed: %s", type(exc).__name__)
        return None
    finally:
        land.close()
    sigungu_hits = _match_labels([str(row["name"]) for row in sigungu], region)
    eup_hits = _match_labels([str(row["name"]) for row in eup], region)
    exact_sigungu = [name for name in sigungu_hits if "".join(name.split()) == "".join(region.split())]
    exact_eup = [name for name in eup_hits if "".join(name.split()) == "".join(region.split())]
    if len(exact_sigungu) == 1:
        level, code, label = "sigungu", _code_for(sigungu, exact_sigungu[0]), exact_sigungu[0]
    elif len(exact_eup) == 1 and not exact_sigungu:
        level, code, label = "eup", _code_for(eup, exact_eup[0]), exact_eup[0]
    elif len(sigungu_hits) == 1 and not eup_hits:
        level, code, label = "sigungu", _code_for(sigungu, sigungu_hits[0]), sigungu_hits[0]
    elif len(eup_hits) == 1 and not sigungu_hits:
        level, code, label = "eup", _code_for(eup, eup_hits[0]), eup_hits[0]
    elif sigungu_hits or eup_hits:
        return {"error": "AMBIGUOUS", "matches": list(dict.fromkeys([*sigungu_hits, *eup_hits]))}
    else:
        return {"error": "NO_MATCH"}
    engine = get_collective_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            if level == "sigungu":
                row = conn.execute(
                    text(
                        """
                        SELECT twin_sido_name, twin_sigungu_name
                        FROM twin_region_neighbor_mvp
                        WHERE anchor_sigungu_code = :code
                        ORDER BY rank
                        LIMIT 1
                        """
                    ),
                    {"code": code[:5]},
                ).mappings().first()
                twin = None if row is None else f"{row['twin_sido_name']} {row['twin_sigungu_name']}".strip()
            else:
                row = conn.execute(
                    text(
                        """
                        SELECT twin_sido_name, twin_sigungu_name, twin_eupmyeondong_name
                        FROM twin_eupmyeondong_neighbor_mvp
                        WHERE anchor_eupmyeondong_code = :code
                        ORDER BY rank
                        LIMIT 1
                        """
                    ),
                    {"code": code[:8]},
                ).mappings().first()
                twin = None if row is None else (
                    f"{row['twin_sido_name']} {row['twin_sigungu_name']} {row['twin_eupmyeondong_name']}".strip()
                )
    except Exception as exc:
        _LOG.warning("AI2 profile twin failed: %s", type(exc).__name__)
        return None
    if not twin:
        return {"error": "NO_NEIGHBOR", "anchor": label}
    return {"twin_region": twin, "anchor": label}


def run_live_shop(tool_id: str, ctx: AnalysisContext, args: dict) -> ToolEnvelope:
    if ctx.period and ctx.period != PERIOD:
        return ToolEnvelope(
            tool_id=tool_id,
            level="impossible",
            analysis_possible=False,
            reason_code="PERIOD_UNAVAILABLE",
            period=PERIOD,
            facts={"requested_period": ctx.period},
        )
    if tool_id == "sample_status":
        return _shop_sample(ctx)
    if tool_id == "representative_candidates":
        return _shop_representative(ctx)
    if tool_id == "floor_index":
        return _shop_index(ctx, args)
    return _bad(tool_id, "UNSUPPORTED")


def run_live_rent(tool_id: str, ctx: AnalysisContext) -> ToolEnvelope:
    if tool_id != "rent_rate":
        return _bad(tool_id, "UNSUPPORTED")
    found = fetch_rent_rate(ctx.region or "")
    if found is None:
        return _bad(tool_id, "DATABASE_UNAVAILABLE")
    if found.get("error") == "AMBIGUOUS":
        return ToolEnvelope(
            tool_id=tool_id,
            level="impossible",
            analysis_possible=False,
            reason_code="AMBIGUOUS_TARGET",
            facts={"matches": found.get("matches") or []},
        )
    if found.get("error") == "NO_MATCH":
        return _bad(tool_id, "NO_DATA_FOR_REGION")
    if not found.get("gate_passed") or found.get("conversion_rate") is None:
        return ToolEnvelope(
            tool_id=tool_id,
            level="impossible",
            analysis_possible=False,
            reason_code="CONVERSION_GATE",
            valid_n=found.get("n_buildings"),
            period=found.get("as_of"),
            facts={"window_years": found.get("window_years")},
        )
    return ToolEnvelope(
        tool_id=tool_id,
        level="fact",
        analysis_possible=True,
        valid_n=found.get("n_buildings"),
        period=found.get("as_of"),
        facts={
            "conversion_rate": found["conversion_rate"],
            "window_years": found["window_years"],
            "rate_region": found.get("rate_region"),
        },
    )


def run_live_profile(tool_id: str, ctx: AnalysisContext) -> ToolEnvelope:
    if tool_id != "profile_twin_status":
        return _bad(tool_id, "UNSUPPORTED")
    found = fetch_profile_twin(ctx.region or "")
    if found is None:
        return _bad(tool_id, "DATABASE_UNAVAILABLE")
    if found.get("error") == "AMBIGUOUS":
        return ToolEnvelope(
            tool_id=tool_id,
            level="impossible",
            analysis_possible=False,
            reason_code="AMBIGUOUS_TARGET",
            facts={"matches": found.get("matches") or []},
        )
    if found.get("error") in ("NO_MATCH", "NO_NEIGHBOR") or not found.get("twin_region"):
        return _bad(tool_id, "NO_DATA_FOR_REGION")
    return ToolEnvelope(
        tool_id=tool_id,
        level="caution",
        analysis_possible=True,
        reason_code="TWIN_NOT_ADOPTED",
        facts={"twin_adopted": False, "twin_region": found["twin_region"]},
    )


def _is_factory(ctx: AnalysisContext) -> bool:
    return ctx.analysis_type == "factory_floor"


def _road_counts(ctx: AnalysisContext):
    if _is_factory(ctx):
        return fetch_factory_counts(ctx.region or "")
    return fetch_shop_counts(ctx.region or "")


def _road_index(ctx: AnalysisContext, cluster_key: str):
    if _is_factory(ctx):
        return fetch_factory_index(cluster_key)
    return fetch_shop_index(cluster_key)


def _road_labels(ctx: AnalysisContext) -> tuple[str, ...]:
    return _FACTORY_INDEX_LABELS if _is_factory(ctx) else _SHOP_INDEX_LABELS


def _road_rule(ctx: AnalysisContext) -> str:
    return _FACTORY_RULE if _is_factory(ctx) else _SHOP_RULE


def _shop_sample(ctx: AnalysisContext) -> ToolEnvelope:
    rows = _road_counts(ctx)
    if rows is None:
        return _bad("sample_status", "DATABASE_UNAVAILABLE")
    eligible = [row for row in rows if row[2] >= MIN_COUNT_FLOOR_INDEX]
    alts = [Alternative("representative_candidates", "대표 도로 후보", False, {})] if eligible else []
    return ToolEnvelope(
        tool_id="sample_status",
        level="impossible",
        analysis_possible=False,
        reason_code="NO_REGION_LEVEL_INDEX",
        valid_n=sum(row[2] for row in rows),
        required_n=MIN_COUNT_FLOOR_INDEX,
        period=PERIOD,
        alternative_tools=alts,
        facts={"roads": [{"name": name, "n": n} for name, _key, n in rows]},
    )


def _shop_representative(ctx: AnalysisContext) -> ToolEnvelope:
    rows = _road_counts(ctx)
    if rows is None:
        return _bad("representative_candidates", "DATABASE_UNAVAILABLE")
    eligible = [row for row in rows if row[2] >= MIN_COUNT_FLOOR_INDEX]
    if not eligible:
        return ToolEnvelope(
            tool_id="representative_candidates",
            level="impossible",
            analysis_possible=False,
            reason_code="INSUFFICIENT_SAMPLE",
            valid_n=max((row[2] for row in rows), default=0),
            required_n=MIN_COUNT_FLOOR_INDEX,
            period=PERIOD,
        )
    name, key, n = max(eligible, key=lambda row: row[2])
    return ToolEnvelope(
        tool_id="representative_candidates",
        level="fact",
        analysis_possible=True,
        valid_n=n,
        required_n=MIN_COUNT_FLOOR_INDEX,
        period=PERIOD,
        alternative_tools=[Alternative("floor_index", name, True, {"target": name, "cluster_key": key})],
        facts={
            "selected": name,
            "selected_n": n,
            "place": "road",
            "rule": "거래 수가 가장 많고 최소 건수를 넘는 도로",
        },
    )


def _shop_index(ctx: AnalysisContext, args: dict) -> ToolEnvelope:
    rows = _road_counts(ctx)
    if rows is None:
        return _bad("floor_index", "DATABASE_UNAVAILABLE")
    name = str(args.get("target") or ctx.target or "")
    key = str(args.get("cluster_key") or "")
    if not key:
        hits = [row for row in rows if _same(row[0], name)]
        if len(hits) != 1:
            return ToolEnvelope(
                tool_id="floor_index",
                level="impossible",
                analysis_possible=False,
                reason_code="AMBIGUOUS_TARGET" if len(hits) > 1 else "INSUFFICIENT_SAMPLE",
                valid_n=0 if not hits else hits[0][2],
                required_n=MIN_COUNT_FLOOR_INDEX,
                period=PERIOD,
            )
        name, key, _n = hits[0]
    matched = next((row for row in rows if row[1] == key), None)
    valid_n = 0 if matched is None else matched[2]
    if matched is not None:
        name = matched[0]
    if valid_n < MIN_COUNT_FLOOR_INDEX:
        return ToolEnvelope(
            tool_id="floor_index",
            level="impossible",
            analysis_possible=False,
            reason_code="INSUFFICIENT_SAMPLE",
            valid_n=valid_n,
            required_n=MIN_COUNT_FLOOR_INDEX,
            period=PERIOD,
            facts={"target": name},
        )
    fitted = _road_index(ctx, key)
    if fitted is None:
        return _bad("floor_index", "DATABASE_UNAVAILABLE")
    facts: dict = {"target": name, "index_rule": _road_rule(ctx)}
    blank = next(
        (cell for cell in fitted["cells"] if 0 < int(cell.get("count") or 0) < MIN_GROUP_FOR_DUMMY),
        None,
    )
    picked = next(
        (
            cell
            for label in _road_labels(ctx)
            for cell in fitted["cells"]
            if cell.get("label") == label
            and int(cell.get("count") or 0) >= MIN_GROUP_FOR_DUMMY
            and cell.get("index") is not None
        ),
        None,
    )
    if picked is not None:
        facts["local_index"] = picked["index"]
    if "local_index" not in facts and blank is None:
        return ToolEnvelope(
            tool_id="floor_index",
            level="impossible",
            analysis_possible=False,
            reason_code="REGRESSION_FAILED",
            valid_n=valid_n,
            required_n=MIN_COUNT_FLOOR_INDEX,
            period=PERIOD,
            facts={"target": name},
        )
    if blank is not None:
        facts["blank_group"] = blank.get("label")
        facts["blank_group_n"] = int(blank.get("count") or 0)
    return ToolEnvelope(
        tool_id="floor_index",
        level="caution" if blank is not None else "ok",
        analysis_possible=True,
        reason_code="INSUFFICIENT_FLOOR_GROUP" if blank is not None else None,
        valid_n=valid_n,
        required_n=MIN_COUNT_FLOOR_INDEX,
        excluded_n=0 if blank is None else int(blank.get("count") or 0),
        period=PERIOD,
        comparable=False,
        facts=facts,
    )


def _pick_label(labels: list[str], asked: str) -> list[str]:
    hits = _match_labels(labels, asked)
    if hits:
        return hits
    key = "".join(asked.split())
    contained = [name for name in labels if name and "".join(name.split()) in key]
    if not contained:
        return []
    longest = max(len("".join(name.split())) for name in contained)
    return [name for name in contained if len("".join(name.split())) == longest]


def _code_for(rows, name: str) -> str:
    return next(str(row["code"]) for row in rows if str(row["name"]) == name)


def _same(stored: str, asked: str) -> bool:
    left = "".join(stored.split())
    right = "".join(asked.split())
    return bool(right) and (left == right or right in left)
