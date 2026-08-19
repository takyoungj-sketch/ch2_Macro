"""헤도닉 mart 조회·/run 재추정."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.hedonic.constants import DEFAULT_ASSET_TYPE
from app.collective.hedonic.schemas import (
    AttributeEffectsResponse,
    AttributeEffectsRunRequest,
    BuildingQualityResponse,
    HedonicCoeff,
    MacroEffectsResponse,
    QualityIndexAnalysisResponse,
    QualityIndexRow,
    SigunguBaseLevelRow,
)
from app.collective.hedonic.stage2 import run_attribute_effects, run_block_l_macro
from app.v2_stats_windows import default_as_of_month_for_service


def _latest_as_of(conn: Connection, table: str) -> date | None:
    row = conn.execute(
        text(f"SELECT MAX(as_of_month) AS m FROM {table} WHERE asset_type = :at"),
        {"at": DEFAULT_ASSET_TYPE},
    ).mappings().first()
    if not row or row["m"] is None:
        return None
    return row["m"]


def _resolve_as_of(conn: Connection, as_of: date | None) -> date:
    if as_of is not None:
        return as_of
    latest = _latest_as_of(conn, "collective_building_quality_index")
    if latest is not None:
        return latest
    return default_as_of_month_for_service()


def fetch_quality_index_analysis(
    conn: Connection,
    *,
    as_of_month: date | None,
    window_years: int,
    sigungu_code: str | None = None,
    limit: int = 500,
) -> QualityIndexAnalysisResponse:
    as_of = _resolve_as_of(conn, as_of_month)
    params: dict[str, Any] = {
        "as_of": as_of,
        "wy": window_years,
        "at": DEFAULT_ASSET_TYPE,
        "lim": limit,
    }
    sg_clause = ""
    if sigungu_code:
        sg_clause = "AND q.sigungu_code = :sg"
        params["sg"] = sigungu_code

    rows = conn.execute(
        text(
            f"""
            SELECT q.building_key, q.sigungu_code, q.quality_index, q.quality_se, q.n_tx,
                   t.display_name
            FROM collective_building_quality_index q
            LEFT JOIN (
                SELECT building_key, MAX(display_name) AS display_name
                FROM collective_transactions
                GROUP BY building_key
            ) t ON t.building_key = q.building_key
            WHERE q.as_of_month = :as_of AND q.window_years = :wy AND q.asset_type = :at
            {sg_clause}
            ORDER BY q.quality_index DESC
            LIMIT :lim
            """
        ),
        params,
    ).mappings().all()

    base_rows = conn.execute(
        text(
            """
            SELECT sigungu_code, base_ln_price, ref_area, ref_floor_group, ref_year,
                   area_beta, r_squared, n_buildings, n_tx
            FROM collective_sigungu_base_level
            WHERE as_of_month = :as_of AND window_years = :wy AND asset_type = :at
            ORDER BY sigungu_code
            """
        ),
        {"as_of": as_of, "wy": window_years, "at": DEFAULT_ASSET_TYPE},
    ).mappings().all()

    buildings: list[QualityIndexRow] = []
    indices = [float(r["quality_index"]) for r in rows]
    for r in rows:
        qi = float(r["quality_index"])
        pct = None
        if indices:
            pct = sum(1 for x in indices if x <= qi) / len(indices) * 100.0
        buildings.append(
            QualityIndexRow(
                building_key=str(r["building_key"]),
                display_name=r.get("display_name"),
                sigungu_code=str(r["sigungu_code"]),
                quality_index=qi,
                quality_se=float(r["quality_se"]) if r.get("quality_se") is not None else None,
                n_tx=int(r["n_tx"]),
                percentile_in_sigungu=round(pct, 1) if pct is not None else None,
            )
        )

    warnings: list[str] = []
    if not rows:
        warnings.append("mart에 품질지수 없음 — pipeline/build_collective_quality_index.py 실행 필요")

    dist = {}
    if indices:
        s = pd.Series(indices)
        dist = {
            "mean": round(float(s.mean()), 6),
            "std": round(float(s.std()), 6),
            "p25": round(float(s.quantile(0.25)), 6),
            "p50": round(float(s.quantile(0.5)), 6),
            "p75": round(float(s.quantile(0.75)), 6),
        }

    return QualityIndexAnalysisResponse(
        as_of_month=as_of,
        window_years=window_years,
        asset_type=DEFAULT_ASSET_TYPE,
        n_buildings=len(rows),
        n_sigungu=len(base_rows),
        buildings=buildings,
        sigungu_base=[SigunguBaseLevelRow(**dict(r)) for r in base_rows],
        distribution=dist,
        warnings=warnings,
    )


def fetch_building_quality(
    conn: Connection,
    building_key: str,
    *,
    as_of_month: date | None,
    window_years: int,
) -> BuildingQualityResponse:
    as_of = _resolve_as_of(conn, as_of_month)
    row = conn.execute(
        text(
            """
            SELECT q.*, b.base_ln_price, t.display_name
            FROM collective_building_quality_index q
            LEFT JOIN collective_sigungu_base_level b
              ON b.as_of_month = q.as_of_month
             AND b.window_years = q.window_years
             AND b.asset_type = q.asset_type
             AND b.sigungu_code = q.sigungu_code
            LEFT JOIN (
                SELECT building_key, MAX(display_name) AS display_name
                FROM collective_transactions WHERE building_key = :bk GROUP BY building_key
            ) t ON t.building_key = q.building_key
            WHERE q.building_key = :bk AND q.as_of_month = :as_of
              AND q.window_years = :wy AND q.asset_type = :at
            """
        ),
        {"bk": building_key, "as_of": as_of, "wy": window_years, "at": DEFAULT_ASSET_TYPE},
    ).mappings().first()

    warnings: list[str] = []
    if not row:
        return BuildingQualityResponse(
            building_key=building_key,
            as_of_month=as_of,
            window_years=window_years,
            warnings=["품질지수 없음 — 표본·시군구 게이트 미달 또는 mart 미빌드"],
        )

    sg_rows = conn.execute(
        text(
            """
            SELECT quality_index FROM collective_building_quality_index
            WHERE as_of_month = :as_of AND window_years = :wy AND asset_type = :at
              AND sigungu_code = :sg
            """
        ),
        {
            "as_of": as_of,
            "wy": window_years,
            "at": DEFAULT_ASSET_TYPE,
            "sg": row["sigungu_code"],
        },
    ).scalars().all()
    qi = float(row["quality_index"])
    pct = None
    if sg_rows:
        pct = sum(1 for x in sg_rows if float(x) <= qi) / len(sg_rows) * 100.0

    decomp = [
        {"label": "시군구 기준 log(㎡당가)", "value": float(row["base_ln_price"]) if row.get("base_ln_price") else None},
        {"label": "단지 품질지수(센터링 FE)", "value": qi},
    ]

    return BuildingQualityResponse(
        building_key=building_key,
        display_name=row.get("display_name"),
        as_of_month=as_of,
        window_years=window_years,
        quality_index=qi,
        quality_se=float(row["quality_se"]) if row.get("quality_se") is not None else None,
        n_tx=int(row["n_tx"]),
        sigungu_code=str(row["sigungu_code"]),
        percentile_in_sigungu=round(pct, 1) if pct is not None else None,
        sigungu_base_ln_price=float(row["base_ln_price"]) if row.get("base_ln_price") else None,
        decomposition=decomp,
        warnings=warnings,
    )


def _load_stage2_frame(conn: Connection, as_of: date, window_years: int) -> pd.DataFrame:
    snap = conn.execute(text("SELECT MAX(snapshot_ym) FROM collective_building_attributes")).scalar()
    sql = text(
        """
        SELECT q.building_key, q.sigungu_code, q.quality_index, q.quality_se,
               LEFT(q.sigungu_code, 2) AS sido_code,
               a.match_tier, a.brand, a.builder_group, a.structure_group,
               a.households, a.max_floor, a.parking_per_household,
               a.approved_year, a.building_year, a.danji_class, a.supply_type,
               a.danji_code, a.attr_quality_flags, a.n_tx,
               e.eup_population, e.rent_jeonse_p50, e.land_p50_zone
        FROM collective_building_quality_index q
        JOIN collective_building_attributes a
          ON a.building_key = q.building_key
         AND a.asset_type = q.asset_type
         AND a.snapshot_ym = :snap
        LEFT JOIN collective_building_location_enrichment e
          ON e.building_key = q.building_key
         AND e.as_of_month = q.as_of_month
         AND e.window_years = q.window_years
         AND e.asset_type = q.asset_type
        WHERE q.as_of_month = :as_of AND q.window_years = :wy AND q.asset_type = :at
        """
    )
    return pd.read_sql(
        sql,
        conn,
        params={"as_of": as_of, "wy": window_years, "at": DEFAULT_ASSET_TYPE, "snap": snap},
    )


def _result_to_response(
    result,
    *,
    as_of: date,
    window_years: int,
) -> AttributeEffectsResponse:
    coefs: list[HedonicCoeff] = []
    for c in result.coefficients:
        se = c.get("se")
        t_val = (c["coef"] / se) if se and se != 0 else None
        pct = c.get("pct_effect")
        effect_plain = f"{pct:+.2f}%" if pct is not None else None
        coefs.append(
            HedonicCoeff(
                **c,
                t=round(t_val, 4) if t_val is not None else None,
                effect_plain=effect_plain,
            )
        )
    return AttributeEffectsResponse(
        as_of_month=as_of,
        window_years=window_years,
        asset_type=DEFAULT_ASSET_TYPE,
        spec=result.spec,
        scope_level=result.scope_level,
        scope_code=result.scope_code,
        include_location=result.include_location,
        weighting=result.weighting,
        equation=result.equation,
        coefficients=coefs,
        warnings=result.warnings,
        model_candidates=result.model_candidates,
        sample_breakdown=result.sample_breakdown,
        reference_categories=result.reference_categories,
        controls_note=result.controls_note,
        n_buildings=result.n_buildings,
        adj_r_squared=result.adj_r_squared,
    )


def fetch_attribute_effects_mart(
    conn: Connection,
    *,
    as_of_month: date | None,
    window_years: int,
    spec: str,
    scope_level: str = "national",
    scope_code: str | None = None,
    include_location: bool = False,
) -> AttributeEffectsResponse:
    as_of = _resolve_as_of(conn, as_of_month)
    model = conn.execute(
        text(
            """
            SELECT * FROM collective_attribute_effects_model
            WHERE as_of_month = :as_of AND window_years = :wy AND asset_type = :at
              AND spec = :spec AND scope_level = :sl
              AND (scope_code IS NOT DISTINCT FROM :sc)
              AND include_location = :loc
            ORDER BY created_at DESC LIMIT 1
            """
        ),
        {
            "as_of": as_of,
            "wy": window_years,
            "at": DEFAULT_ASSET_TYPE,
            "spec": spec,
            "sl": scope_level,
            "sc": scope_code,
            "loc": include_location,
        },
    ).mappings().first()

    coef_rows = conn.execute(
        text(
            """
            SELECT term, term_label, term_kind, coef, pct_effect, se, p_value,
                   ci_low, ci_high, boot_ci_low, boot_ci_high, n_buildings, vif
            FROM collective_attribute_effects
            WHERE as_of_month = :as_of AND window_years = :wy AND asset_type = :at
              AND spec = :spec AND scope_level = :sl
              AND (scope_code IS NOT DISTINCT FROM :sc)
            ORDER BY term
            """
        ),
        {
            "as_of": as_of,
            "wy": window_years,
            "at": DEFAULT_ASSET_TYPE,
            "spec": spec,
            "sl": scope_level,
            "sc": scope_code,
        },
    ).mappings().all()

    warnings: list[str] = []
    if not coef_rows:
        warnings.append("mart 계수 없음 — build_collective_attribute_effects.py 실행 또는 /run 사용")

    coefs = []
    for r in coef_rows:
        se = r.get("se")
        t_val = (float(r["coef"]) / float(se)) if se and float(se) != 0 else None
        pct = r.get("pct_effect")
        coefs.append(
            HedonicCoeff(
                term=r["term"],
                term_label=r["term_label"],
                term_kind=r["term_kind"],
                coef=float(r["coef"]),
                pct_effect=float(pct) if pct is not None else None,
                se=float(se) if se is not None else None,
                t=round(t_val, 4) if t_val is not None else None,
                p_value=float(r["p_value"]) if r.get("p_value") is not None else None,
                ci_low=float(r["ci_low"]) if r.get("ci_low") is not None else None,
                ci_high=float(r["ci_high"]) if r.get("ci_high") is not None else None,
                boot_ci_low=float(r["boot_ci_low"]) if r.get("boot_ci_low") is not None else None,
                boot_ci_high=float(r["boot_ci_high"]) if r.get("boot_ci_high") is not None else None,
                n_buildings=int(r["n_buildings"]) if r.get("n_buildings") is not None else None,
                vif=float(r["vif"]) if r.get("vif") is not None else None,
                effect_plain=f"{float(pct):+.2f}%" if pct is not None else None,
            )
        )

    ref = {}
    sample = {}
    eq = ""
    adj = None
    n_bld = 0
    if model:
        ref = model.get("reference_categories") or {}
        if isinstance(ref, str):
            ref = json.loads(ref)
        sample = model.get("sample_breakdown") or {}
        if isinstance(sample, str):
            sample = json.loads(sample)
        eq = model.get("equation") or ""
        adj = float(model["adj_r_squared"]) if model.get("adj_r_squared") is not None else None
        n_bld = int(model["n_buildings"]) if model.get("n_buildings") is not None else 0

    return AttributeEffectsResponse(
        as_of_month=as_of,
        window_years=window_years,
        asset_type=DEFAULT_ASSET_TYPE,
        spec=spec,
        scope_level=scope_level,
        scope_code=scope_code,
        include_location=include_location,
        equation=eq,
        coefficients=coefs,
        warnings=warnings,
        sample_breakdown=sample,
        reference_categories=ref,
        n_buildings=n_bld,
        adj_r_squared=adj,
    )


def run_attribute_effects_live(
    conn: Connection,
    body: AttributeEffectsRunRequest,
) -> AttributeEffectsResponse:
    as_of = _resolve_as_of(conn, body.as_of_month)
    df = _load_stage2_frame(conn, as_of, body.window_years)
    include_terms = set(body.include_terms)
    if body.include_location:
        include_terms |= {"eup_population", "rent_jeonse_p50", "land_p50_zone"}
    if body.spec == "A":
        include_terms.discard("builder")
    elif body.spec == "B":
        include_terms.discard("brand")

    result = run_attribute_effects(
        df,
        spec=body.spec,
        scope_level=body.scope_level,
        scope_code=body.scope_code,
        include_terms=include_terms,
        include_location=body.include_location,
        match_tiers=set(body.match_tiers),
        supply_types=set(body.supply_types),
        min_buildings_per_term=body.min_buildings_per_term,
        weighting=body.weighting,
        bootstrap_reps=100,
    )
    return _result_to_response(result, as_of=as_of, window_years=body.window_years)


def fetch_macro_effects_mart(
    conn: Connection,
    *,
    as_of_month: date | None,
    window_years: int,
) -> MacroEffectsResponse:
    as_of = _resolve_as_of(conn, as_of_month)
    resp = fetch_attribute_effects_mart(
        conn,
        as_of_month=as_of,
        window_years=window_years,
        spec="L",
        scope_level="national",
    )
    return MacroEffectsResponse(
        as_of_month=as_of,
        window_years=window_years,
        asset_type=DEFAULT_ASSET_TYPE,
        equation=resp.equation,
        coefficients=resp.coefficients,
        warnings=resp.warnings,
        sample_breakdown=resp.sample_breakdown,
        reference_categories=resp.reference_categories,
        n_sigungu=resp.n_buildings,
        adj_r_squared=resp.adj_r_squared,
        controls_note="블록 L — 품질지수 식과 분리된 시군구 매크로 회귀",
    )
