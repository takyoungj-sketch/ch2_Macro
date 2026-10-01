"""토지 쌍둥이와 복합 예측. 기존 엔진 결과만 봉투에 넣고 거래 행은 넣지 않는다."""

from __future__ import annotations

import logging
import re

from sqlalchemy import text

from app.ai2.case_tools import BUILT_PREDICT_MIN_N
from app.ai2.types import AnalysisContext, ToolEnvelope

_LOG = logging.getLogger(__name__)

_REQUIRED = (
    ("gross_area", "연면적"),
    ("land_area", "대지면적"),
    ("building_age", "연식"),
)
_REFERENCE_FIELDS = (
    ("zone_type", "zone_type"),
    ("building_use", "building_use"),
    ("structure_group", "structure_group"),
    ("road_width_label", "road_width"),
)


def fetch_land_twin(region: str) -> dict | None:
    from app.db import SessionLocal
    from app.land_lab.land_twin import list_sigungu, run_sigungu

    db = SessionLocal()
    try:
        listing = list_sigungu(db)
        labels = [str(row["label"]) for row in listing.get("regions") or []]
        hits = _match_labels(labels, region)
        if len(hits) != 1:
            return {"error": "AMBIGUOUS" if len(hits) > 1 else "NO_MATCH", "matches": hits}
        code = next(
            str(row["region_code"])
            for row in listing["regions"]
            if str(row["label"]) == hits[0]
        )
        result = run_sigungu(db, code)
    except Exception as exc:
        _LOG.warning("AI2 live twin failed: %s", type(exc).__name__)
        return None
    finally:
        db.close()
    rows = result.get("rows") or []
    top = next((row for row in rows if row.get("structure_rank") == 1), None)
    start = result.get("period_start")
    end = result.get("period_end")
    period = None if start is None or end is None else f"{start}~{end}"
    anchor_n = (result.get("anchor") or {}).get("n_tx")
    return {
        "twin_region": None if top is None else top.get("label"),
        "anchor_n": None if anchor_n is None else int(anchor_n),
        "period": period,
    }


def fetch_built_predict(ctx: AnalysisContext) -> dict | None:
    from app.built.db import get_built_engine
    from app.built.regression.engine import predict_regression
    from app.built.schemas import RegressionPredictRequest

    engine = get_built_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            scope = _built_scope(conn, ctx.region or "")
            if scope is None or scope.get("error"):
                return scope
            request = RegressionPredictRequest(
                asset_type="all",
                admin_level=scope["admin_level"],
                addr1=scope["addr1"],
                addr2=scope["addr2"],
                addr3=scope.get("addr3"),
                addr4_list=scope.get("addr4_list") or [],
                gross_area=ctx.gross_area,
                land_area=ctx.land_area,
                building_age=ctx.building_age,
                road_width_label=ctx.road_width_label,
                response_scale="linear",
                time_adjust=False,
                enrich=False,
                include_partial=False,
            )
            fitted = predict_regression(conn, request)
    except ValueError as exc:
        text_error = str(exc)
        found = re.search(r"scope n=(\d+)", text_error)
        if "예측 불가" in text_error and found:
            return {"error": "INSUFFICIENT_SAMPLE", "n": int(found.group(1))}
        if "값이 필요" in text_error:
            return {"error": "MISSING_INPUTS"}
        _LOG.warning("AI2 live built predict rejected: %s", type(exc).__name__)
        return {"error": "ENGINE_REJECTED"}
    except Exception as exc:
        _LOG.warning("AI2 live built predict failed: %s", type(exc).__name__)
        return None
    return {
        "n": int(fitted.n),
        "y_hat": fitted.y_hat,
        "pi_lower": fitted.pi_lower,
        "pi_upper": fitted.pi_upper,
        "y_hat_suppressed": bool(fitted.y_hat_suppressed),
        "price_base_year": fitted.price_base_year,
        "reference_inputs": _reference_inputs(ctx),
    }


def run_live_twin(tool_id: str, ctx: AnalysisContext) -> ToolEnvelope:
    if tool_id != "twin_status":
        return _bad(tool_id, "UNSUPPORTED")
    found = fetch_land_twin(ctx.region or "")
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
    if found.get("error") == "NO_MATCH" or not found.get("twin_region"):
        return _bad(tool_id, "NO_DATA_FOR_REGION")
    return ToolEnvelope(
        tool_id=tool_id,
        level="caution",
        analysis_possible=True,
        reason_code="TWIN_NOT_ADOPTED",
        valid_n=found.get("anchor_n"),
        period=found.get("period"),
        facts={
            "twin_adopted": False,
            "twin_region": found["twin_region"],
        },
    )


def run_live_built(tool_id: str, ctx: AnalysisContext) -> ToolEnvelope:
    if tool_id != "built_predict":
        return _bad(tool_id, "UNSUPPORTED")
    if ctx.measure == "unit_price":
        return _bad(tool_id, "MEASURE_UNSUPPORTED")
    missing = [label for name, label in _REQUIRED if getattr(ctx, name) is None]
    if missing:
        return ToolEnvelope(
            tool_id=tool_id,
            level="impossible",
            analysis_possible=False,
            reason_code="MISSING_INPUTS",
            required_n=BUILT_PREDICT_MIN_N,
            facts={"missing": missing},
        )
    fitted = fetch_built_predict(ctx)
    if fitted is None:
        return _bad(tool_id, "DATABASE_UNAVAILABLE")
    if fitted.get("error") == "INSUFFICIENT_SAMPLE":
        return ToolEnvelope(
            tool_id=tool_id,
            level="impossible",
            analysis_possible=False,
            reason_code="INSUFFICIENT_SAMPLE",
            valid_n=fitted.get("n"),
            required_n=BUILT_PREDICT_MIN_N,
        )
    if fitted.get("error") == "AMBIGUOUS":
        return ToolEnvelope(
            tool_id=tool_id,
            level="impossible",
            analysis_possible=False,
            reason_code="AMBIGUOUS_TARGET",
            facts={"matches": fitted.get("matches") or []},
        )
    if fitted.get("error") in ("NO_MATCH", "NO_DATA_FOR_REGION"):
        return _bad(tool_id, "NO_DATA_FOR_REGION")
    if fitted.get("error"):
        return _bad(tool_id, str(fitted["error"]))
    suppressed = bool(fitted.get("y_hat_suppressed"))
    return ToolEnvelope(
        tool_id=tool_id,
        level="caution" if suppressed else "ok",
        analysis_possible=True,
        reason_code="EXTRAPOLATION" if suppressed else None,
        valid_n=fitted.get("n"),
        required_n=BUILT_PREDICT_MIN_N,
        facts={
            "y_hat": fitted.get("y_hat"),
            "pi_lower": fitted.get("pi_lower"),
            "pi_upper": fitted.get("pi_upper"),
            "y_hat_suppressed": suppressed,
            "reference_inputs": fitted.get("reference_inputs") or [],
            "price_base_year": fitted.get("price_base_year"),
            "price_basis": "total",
        },
    )


def _built_scope(conn, region: str) -> dict | None:
    rows = conn.execute(
        text(
            """
            SELECT addr1, addr2, addr3, addr4
            FROM built_transactions
            WHERE is_valid = true
              AND (addr2 = :region OR addr3 = :region OR addr4 = :region)
            GROUP BY addr1, addr2, addr3, addr4
            """
        ),
        {"region": region},
    ).mappings().all()
    paths = [dict(row) for row in rows]
    for level, column in (("eupmyeondong", "addr4"), ("gu", "addr3"), ("sigungu", "addr2")):
        matched = [path for path in paths if path.get(column) == region]
        if not matched:
            continue
        parents = {(path.get("addr1"), path.get("addr2"), path.get("addr3")) for path in matched}
        if level != "eupmyeondong":
            parents = {(path.get("addr1"), path.get("addr2")) for path in matched}
        if len(parents) != 1:
            shown = sorted(
                {
                    " ".join(
                        str(path.get(key) or "")
                        for key in ("addr1", "addr2", "addr3", "addr4")
                    ).strip()
                    for path in matched
                }
            )
            return {"error": "AMBIGUOUS", "matches": shown}
        first = matched[0]
        scope = {
            "admin_level": level,
            "addr1": first.get("addr1"),
            "addr2": first.get("addr2"),
            "addr3": first.get("addr3") if level != "sigungu" else None,
            "addr4_list": [region] if level == "eupmyeondong" else [],
        }
        return scope
    return {"error": "NO_MATCH"}


def _reference_inputs(ctx: AnalysisContext) -> list[str]:
    names = []
    for field_name, label in _REFERENCE_FIELDS:
        if getattr(ctx, field_name, None) in (None, ""):
            names.append(label)
    return names


def _match_labels(labels: list[str], asked: str) -> list[str]:
    key = "".join(asked.split())
    exact = [label for label in labels if "".join(label.split()) == key]
    if exact:
        return exact
    return [label for label in labels if key and key in "".join(label.split())]


def _bad(tool_id: str, reason: str) -> ToolEnvelope:
    return ToolEnvelope(
        tool_id=tool_id,
        level="impossible",
        analysis_possible=False,
        reason_code=reason,
        required_n=BUILT_PREDICT_MIN_N if tool_id == "built_predict" else None,
    )
