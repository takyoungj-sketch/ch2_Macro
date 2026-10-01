"""집합 원장의 아파트 층 지수. 건수와 지수만 봉투에 넣고 거래 행은 넣지 않는다."""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import text

from app.collective.analysis_gates import MIN_COUNT_FLOOR_INDEX
from app.collective.db import get_collective_engine
from app.collective.floor_index_regression import MIN_GROUP_FOR_DUMMY, compute_residential_floor_index_regression
from app.ai2.floor_tools import FloorWorld, run_floor_tool
from app.ai2.types import Alternative, AnalysisContext, ToolEnvelope

_LOG = logging.getLogger(__name__)

PERIOD = "2021-09~2026-08"
WINDOW_FROM = date(2021, 9, 1)
WINDOW_TO = date(2026, 8, 31)


def fetch_counts(region: str) -> list[tuple[str, str, int]] | None:
    engine = get_collective_engine()
    if engine is None:
        return None
    sql = text(
        """
        SELECT building_key,
               MAX(display_name) AS display_name,
               COUNT(*)::int AS n
        FROM collective_transactions
        WHERE is_valid = true
          AND unit_price IS NOT NULL
          AND unit_price > 0
          AND asset_type = 'apartment'
          AND (addr3 = :region OR addr4 = :region)
          AND contract_date >= :d0
          AND contract_date <= :d1
        GROUP BY building_key
        """
    )
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sql, {"region": region, "d0": WINDOW_FROM, "d1": WINDOW_TO}
            ).mappings().all()
    except Exception as exc:
        _LOG.warning("AI2 live floor counts failed: %s", type(exc).__name__)
        return None
    return [
        (str(row["display_name"] or row["building_key"]), str(row["building_key"]), int(row["n"]))
        for row in rows
    ]


def fetch_floor_index(building_key: str) -> dict | None:
    engine = get_collective_engine()
    if engine is None:
        return None
    sql = text(
        """
        SELECT unit_price, floor, dong, housing_subtype, exclusive_area,
               contract_year, contract_month, building_age, building_year
        FROM collective_transactions
        WHERE building_key = :bk
          AND is_valid = true
          AND unit_price IS NOT NULL
          AND unit_price > 0
          AND asset_type = 'apartment'
          AND contract_date >= :d0
          AND contract_date <= :d1
        """
    )
    try:
        import pandas as pd

        with engine.connect() as conn:
            rows = conn.execute(
                sql, {"bk": building_key, "d0": WINDOW_FROM, "d1": WINDOW_TO}
            ).mappings().all()
        frame = pd.DataFrame(rows)
    except Exception as exc:
        _LOG.warning("AI2 live floor index failed: %s", type(exc).__name__)
        return None
    try:
        raw = compute_residential_floor_index_regression(
            frame, asset_type="apartment", dimension="floor", floor_mode="relative"
        )
    except Exception as exc:
        _LOG.warning("AI2 live floor regression failed: %s", type(exc).__name__)
        return {"error": "REGRESSION_FAILED"}
    cells = []
    for cell in raw.get("cells") or []:
        cells.append(
            {
                "label": cell.get("label"),
                "count": cell.get("count"),
                "index": cell.get("index"),
            }
        )
    return {"n": int(raw.get("n_total") or 0), "cells": cells}


def run_live_floor(tool_id: str, ctx: AnalysisContext, args: dict) -> ToolEnvelope:
    if tool_id in ("floor_formula", "insight_compare"):
        return run_floor_tool(tool_id, ctx, args, FloorWorld())
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
        return _sample(ctx)
    if tool_id == "representative_candidates":
        return _representative(ctx)
    if tool_id == "floor_index":
        return _index(ctx, args)
    return ToolEnvelope(
        tool_id=tool_id,
        level="impossible",
        analysis_possible=False,
        reason_code="UNSUPPORTED",
        period=PERIOD,
    )


def _sample(ctx: AnalysisContext) -> ToolEnvelope:
    rows = fetch_counts(ctx.region or "")
    if rows is None:
        return _unavailable("sample_status")
    eligible = [row for row in rows if row[2] >= MIN_COUNT_FLOOR_INDEX]
    alts = []
    if eligible:
        alts.append(Alternative("representative_candidates", "대표 단지 후보", False, {}))
    return ToolEnvelope(
        tool_id="sample_status",
        level="impossible",
        analysis_possible=False,
        reason_code="NO_REGION_LEVEL_INDEX",
        valid_n=sum(row[2] for row in rows),
        required_n=MIN_COUNT_FLOOR_INDEX,
        period=PERIOD,
        alternative_tools=alts,
        facts={"complexes": [{"name": name, "n": n} for name, _key, n in rows]},
    )


def _representative(ctx: AnalysisContext) -> ToolEnvelope:
    rows = fetch_counts(ctx.region or "")
    if rows is None:
        return _unavailable("representative_candidates")
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
        alternative_tools=[Alternative("floor_index", name, True, {"target": name, "building_key": key})],
        facts={
            "selected": name,
            "selected_n": n,
            "rule": "거래 수가 가장 많고 최소 건수를 넘는 단지",
        },
    )


def _index(ctx: AnalysisContext, args: dict) -> ToolEnvelope:
    rows = fetch_counts(ctx.region or "")
    if rows is None:
        return _unavailable("floor_index")
    name = str(args.get("target") or ctx.target or "")
    key = str(args.get("building_key") or "")
    if not key:
        hits = [row for row in rows if _same_name(row[0], name)]
        if len(hits) != 1:
            return ToolEnvelope(
                tool_id="floor_index",
                level="impossible",
                analysis_possible=False,
                reason_code="AMBIGUOUS_TARGET" if len(hits) > 1 else "INSUFFICIENT_SAMPLE",
                valid_n=0 if not hits else hits[0][2],
                required_n=MIN_COUNT_FLOOR_INDEX,
                period=PERIOD,
                facts={"matches": [{"name": hit[0], "n": hit[2]} for hit in hits]},
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
    fitted = fetch_floor_index(key)
    if fitted is None:
        return _unavailable("floor_index")
    if fitted.get("error"):
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
    facts: dict = {"target": name}
    blank = next(
        (
            cell
            for cell in fitted["cells"]
            if 0 < int(cell.get("count") or 0) < MIN_GROUP_FOR_DUMMY
        ),
        None,
    )
    top = next((cell for cell in fitted["cells"] if cell.get("label") == "최상층"), None)
    if top is not None and int(top.get("count") or 0) >= MIN_GROUP_FOR_DUMMY and top.get("index") is not None:
        facts["local_index"] = top["index"]
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
    level = "ok"
    reason = None
    excluded = 0
    if blank is not None:
        level = "caution"
        reason = "INSUFFICIENT_FLOOR_GROUP"
        excluded = int(blank.get("count") or 0)
        facts["blank_group"] = blank.get("label")
        facts["blank_group_n"] = excluded
        facts["floor_group_min"] = MIN_GROUP_FOR_DUMMY
    return ToolEnvelope(
        tool_id="floor_index",
        level=level,  # type: ignore[arg-type]
        analysis_possible=True,
        reason_code=reason,
        valid_n=valid_n,
        required_n=MIN_COUNT_FLOOR_INDEX,
        excluded_n=excluded,
        period=PERIOD,
        facts=facts,
    )


def _unavailable(tool_id: str) -> ToolEnvelope:
    return ToolEnvelope(
        tool_id=tool_id,
        level="impossible",
        analysis_possible=False,
        reason_code="DATABASE_UNAVAILABLE",
        period=PERIOD,
    )


def _same_name(stored: str, asked: str) -> bool:
    left = "".join(stored.split())
    right = "".join(asked.split())
    return bool(right) and (left == right or right in left)
