"""collective_building_stats mart 조회 + live fallback."""

from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.asset_scope import (
    RESIDENTIAL_ASSET_TYPES,
    apply_asset_type_filter,
    normalize_asset_type as _scope_normalize_asset_type,
)
from app.collective.address import split_building_addresses
from app.collective.analysis_gates import count_recent_transactions, evaluate_analysis_gates
from app.collective.filters import apply_region_filters
from app.collective.schemas import AnalysisFeatures, BuildingStatsRow
from app.stats_utils import compute_stats
from app.v2_stats_windows import (
    default_as_of_month_for_service,
    iter_rolling_year_buckets_old_first,
    period_bounds_for_window,
)

ASSET_TYPE_ORDER = ("apartment", "rowhouse", "officetel", "presale")


def normalize_asset_type(asset_type: Optional[str]) -> Optional[str]:
    """단일 유형만 반환. 복수·all → None (하위 호환)."""
    return _scope_normalize_asset_type(asset_type, allowed=RESIDENTIAL_ASSET_TYPES)


def asset_type_sort_key(asset_type: str | None) -> int:
    if not asset_type:
        return 99
    try:
        return ASSET_TYPE_ORDER.index(asset_type)
    except ValueError:
        return 98


def _stats_row_from_parts(
    r: dict,
    *,
    asset_type: Optional[str],
    gates: AnalysisFeatures,
) -> BuildingStatsRow:
    jibun, road, legacy = split_building_addresses(
        addr3=r.get("addr3"),
        addr4=r.get("addr4"),
        addr5=r.get("addr5"),
        lot_number=r.get("lot_number"),
        road_name=r.get("road_name"),
    )
    return BuildingStatsRow(
        building_key=r["building_key"],
        display_name=r["display_name"] or "",
        address=legacy,
        jibun_address=jibun,
        road_address=road,
        building_year=int(r["building_year"]) if r.get("building_year") is not None else None,
        asset_type=r["asset_type"] or asset_type or "",
        count=int(r["count"] or 0),
        mean=float(r["mean"]) if r.get("mean") is not None else None,
        median=float(r["median"]) if r.get("median") is not None else None,
        ci_lower=float(r["ci_lower"]) if r.get("ci_lower") is not None else None,
        ci_upper=float(r["ci_upper"]) if r.get("ci_upper") is not None else None,
        is_reliable=int(r["count"] or 0) >= 15,
        analysis=gates,
    )


def _stats_row_from_live(
    r: dict,
    st: dict,
    *,
    asset_type: Optional[str],
    gates: AnalysisFeatures,
) -> BuildingStatsRow:
    jibun, road, legacy = split_building_addresses(
        addr3=r.get("addr3"),
        addr4=r.get("addr4"),
        addr5=r.get("addr5"),
        lot_number=r.get("lot_number"),
        road_name=r.get("road_name"),
    )
    return BuildingStatsRow(
        building_key=r["building_key"],
        display_name=r["display_name"] or "",
        address=legacy,
        jibun_address=jibun,
        road_address=road,
        building_year=int(r["building_year"]) if r.get("building_year") is not None else None,
        asset_type=r["asset_type"] or asset_type or "",
        count=st["count"],
        mean=st["mean"],
        median=st["median"],
        ci_lower=st["ci_lower"],
        ci_upper=st["ci_upper"],
        is_reliable=st["is_reliable"],
        analysis=gates,
    )


def _mart_has_addr5(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'collective_building_stats'
              AND column_name = 'addr5'
            LIMIT 1
            """
        )
    ).scalar()
    return bool(row)


def _rolling_bucket_label(period_start: date, period_end: date) -> str:
    return (
        f"{period_start.year % 100:02d}.{period_start.month:02d}"
        f"~{period_end.year % 100:02d}.{period_end.month:02d}"
    )


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text("SELECT to_regclass(:t) IS NOT NULL AS ok"),
        {"t": table},
    ).mappings().first()
    return bool(row and row["ok"])


def latest_mart_snapshot(conn: Connection) -> tuple[date | None, int | None]:
    if not _table_exists(conn, "public.collective_building_stats"):
        return None, None
    row = conn.execute(
        text(
            """
            SELECT as_of_month, window_years
            FROM collective_building_stats
            ORDER BY as_of_month DESC, window_years DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    if not row:
        return None, None
    return row["as_of_month"], int(row["window_years"])


def stats_reference_date(as_of_month: date) -> date:
    if as_of_month.month == 12:
        return date(as_of_month.year + 1, 1, 1)
    return date(as_of_month.year, as_of_month.month + 1, 1)


def stats_as_of_label(as_of_month: date | None) -> str | None:
    if as_of_month is None:
        return None
    return f"{as_of_month.year}년 {as_of_month.month}월 말 기준"


def _mart_region_where(
    conn: Connection,
    *,
    asset_type: Optional[str],
    addr1: Optional[str],
    addr2: Optional[str],
    addr3: Optional[str],
    addr3_list: list[str] | None,
    addr4_list: list[str] | None,
    col_prefix: str = "m",
) -> tuple[str, dict]:
    clauses = ["1=1"]
    params: dict[str, Any] = {}
    apply_region_filters(
        clauses,
        params,
        conn=conn,
        table="collective_building_stats",
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        asset_type=None,
        col_prefix=col_prefix,
        valid_sql=None,
    )
    apply_asset_type_filter(
        clauses,
        params,
        asset_type,
        allowed=RESIDENTIAL_ASSET_TYPES,
        col_prefix=col_prefix,
    )
    return " AND ".join(clauses), params


def _fetch_annual_years(conn: Connection, building_keys: list[str]) -> dict[str, list[int]]:
    if not building_keys or not _table_exists(conn, "public.collective_building_annual_stats"):
        return {}
    rows = conn.execute(
        text(
            """
            SELECT building_key, contract_year, count
            FROM collective_building_annual_stats
            WHERE building_key = ANY(:keys)
            """
        ),
        {"keys": building_keys},
    ).mappings().all()
    out: dict[str, list[int]] = {}
    for r in rows:
        bk = r["building_key"]
        cy = int(r["contract_year"])
        cnt = int(r["count"] or 0)
        out.setdefault(bk, [])
        for _ in range(max(cnt, 1)):
            out[bk].append(cy)
    return out


def list_presale_lifetime_from_mart(
    conn: Connection,
    *,
    addr1: Optional[str],
    addr2: Optional[str],
    addr3: Optional[str],
    addr3_list: list[str] | None,
    addr4_list: list[str] | None,
) -> tuple[list[BuildingStatsRow], dict[str, Any]] | None:
    """분양권 전체기간 mart. 없으면 None → live fallback."""
    if not _table_exists(conn, "public.collective_presale_lifetime_stats"):
        return None

    region_sql, params = _mart_region_where(
        conn,
        asset_type="presale",
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
    )
    # lifetime 테이블은 asset_type 고정 — 필터에서 중복 제외는 apply가 =presale 넣음 OK
    addr5_col = "m.addr5"
    rows = conn.execute(
        text(
            f"""
            SELECT m.building_key, m.display_name, m.asset_type,
                   m.addr3, m.addr4, {addr5_col}, m.lot_number, m.road_name, m.building_year,
                   m.count, m.mean, m.median, m.ci_lower, m.ci_upper,
                   m.period_start, m.period_end, m.snapshot_as_of
            FROM collective_presale_lifetime_stats m
            WHERE {region_sql}
            """
        ),
        params,
    ).mappings().all()
    if not rows:
        return [], {
            "data_source": "mart",
            "presale_stats_mode": "lifetime",
            "stats_as_of_label": "분양권 전체 거래기간",
            "window_years": None,
            "period_start": None,
            "period_end": None,
        }

    years_by_key = _fetch_annual_years(conn, [r["building_key"] for r in rows])
    items: list[BuildingStatsRow] = []
    for r in rows:
        bk = r["building_key"]
        years = years_by_key.get(bk, [])
        cnt_recent = count_recent_transactions(
            years,
            contract_year_from=None,
            contract_year_to=None,
        )
        gates = evaluate_analysis_gates(int(r["count"] or 0), cnt_recent)
        items.append(
            _stats_row_from_parts(
                dict(r),
                asset_type="presale",
                gates=AnalysisFeatures(
                    floor_index=gates.floor_index_eligible,
                    regression=gates.regression_eligible,
                    count_total=gates.count_total,
                    count_recent=gates.count_recent,
                    messages=gates.messages,
                ),
            )
        )

    snap = rows[0].get("snapshot_as_of")
    meta: dict[str, Any] = {
        "data_source": "mart",
        "presale_stats_mode": "lifetime",
        "stats_as_of_label": "분양권 전체 거래기간",
        "window_years": None,
        "period_start": None,
        "period_end": None,
    }
    if snap is not None:
        meta["as_of_month"] = snap.isoformat() if hasattr(snap, "isoformat") else str(snap)
        try:
            d = snap if isinstance(snap, date) else date.fromisoformat(str(snap)[:10])
            meta["stats_reference_date"] = stats_reference_date(d).isoformat()
        except Exception:
            pass
    return items, meta


def list_buildings_from_mart(
    conn: Connection,
    *,
    asset_type: Optional[str],
    addr1: Optional[str],
    addr2: Optional[str],
    addr3: Optional[str],
    addr3_list: list[str] | None,
    addr4_list: list[str] | None,
    window_years: int,
    as_of_month: date | None,
    contract_year_from: Optional[int],
    contract_year_to: Optional[int],
) -> tuple[list[BuildingStatsRow], dict[str, Any]] | None:
    if contract_year_from is not None or contract_year_to is not None:
        return None
    if as_of_month is None or not _table_exists(conn, "public.collective_building_stats"):
        return None

    region_sql, params = _mart_region_where(
        conn,
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
    )
    params["as_of"] = as_of_month
    params["window_years"] = window_years
    addr5_col = "m.addr5" if _mart_has_addr5(conn) else "NULL::varchar AS addr5"

    rows = conn.execute(
        text(
            f"""
            SELECT m.building_key, m.display_name, m.asset_type,
                   m.addr3, m.addr4, {addr5_col}, m.lot_number, m.road_name, m.building_year,
                   m.count, m.mean, m.median, m.ci_lower, m.ci_upper
            FROM collective_building_stats m
            WHERE m.as_of_month = :as_of
              AND m.window_years = :window_years
              AND {region_sql}
            """
        ),
        params,
    ).mappings().all()

    years_by_key = _fetch_annual_years(conn, [r["building_key"] for r in rows])
    items: list[BuildingStatsRow] = []
    for r in rows:
        bk = r["building_key"]
        years = years_by_key.get(bk, [])
        cnt_recent = count_recent_transactions(
            years,
            contract_year_from=contract_year_from,
            contract_year_to=contract_year_to,
        )
        gates = evaluate_analysis_gates(int(r["count"] or 0), cnt_recent)
        items.append(
            _stats_row_from_parts(
                dict(r),
                asset_type=asset_type,
                gates=AnalysisFeatures(
                    floor_index=gates.floor_index_eligible,
                    regression=gates.regression_eligible,
                    count_total=gates.count_total,
                    count_recent=gates.count_recent,
                    messages=gates.messages,
                ),
            )
        )

    meta = {
        "data_source": "mart",
        "as_of_month": as_of_month.isoformat(),
        "stats_reference_date": stats_reference_date(as_of_month).isoformat(),
        "stats_as_of_label": stats_as_of_label(as_of_month),
        "window_years": window_years,
    }
    ps, pe = period_bounds_for_window(as_of_month, window_years)
    meta["period_start"] = ps.isoformat()
    meta["period_end"] = pe.isoformat()
    return items, meta


def building_yearly_from_mart(
    conn: Connection,
    building_key: str,
) -> tuple[str, list[dict], str] | None:
    """(display_name, points, data_source) — mart 없으면 None."""
    if not _table_exists(conn, "public.collective_building_annual_stats"):
        return None
    rows = conn.execute(
        text(
            """
            SELECT display_name, contract_year, count, mean, median
            FROM collective_building_annual_stats
            WHERE building_key = :bk
            ORDER BY contract_year
            """
        ),
        {"bk": building_key},
    ).mappings().all()
    if not rows:
        return None
    display_name = rows[0]["display_name"] or ""
    points = [
        {
            "year": int(r["contract_year"]),
            "count": int(r["count"] or 0),
            "mean": round(float(r["mean"]), 1) if r["mean"] is not None else None,
            "median": round(float(r["median"]), 1) if r.get("median") is not None else None,
        }
        for r in rows
    ]
    return display_name, points, "mart"


def building_yearly_live(
    conn: Connection,
    building_key: str,
) -> tuple[str, list[dict], str] | None:
    rows = conn.execute(
        text(
            """
            SELECT MAX(display_name) AS display_name,
                   contract_year AS year,
                   COUNT(*)::int AS count,
                   AVG(unit_price)::float AS mean,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unit_price)::float AS median
            FROM collective_transactions
            WHERE building_key = :bk
              AND is_valid = true
              AND unit_price IS NOT NULL
              AND unit_price > 0
              AND contract_year IS NOT NULL
            GROUP BY contract_year
            ORDER BY contract_year
            """
        ),
        {"bk": building_key},
    ).mappings().all()
    if not rows:
        return None
    display_name = rows[0]["display_name"] or ""
    points = [
        {
            "year": int(r["year"]),
            "count": int(r["count"] or 0),
            "mean": round(float(r["mean"]), 1) if r["mean"] is not None else None,
            "median": round(float(r["median"]), 1) if r.get("median") is not None else None,
        }
        for r in rows
    ]
    return display_name, points, "live"


def building_yearly_resolved(
    conn: Connection,
    building_key: str,
) -> tuple[str, list[dict], str] | None:
    """장기추세 — annual mart(장기 ingest 포함) + live 연도 보강."""
    mart = building_yearly_from_mart(conn, building_key)
    live = building_yearly_live(conn, building_key)
    if mart is None and live is None:
        return None
    if mart is None:
        return live
    if live is None:
        return mart

    display_name = mart[0] or live[0]
    by_year: dict[int, dict] = {int(p["year"]): p for p in mart[1]}
    for p in live[1]:
        yr = int(p["year"])
        if yr not in by_year:
            by_year[yr] = p
    points = [by_year[y] for y in sorted(by_year)]
    mart_years = {int(p["year"]) for p in mart[1]}
    source: str = "mart" if all(int(p["year"]) in mart_years for p in points) else "live"
    return display_name, points, source


_COMPACT_NAME_RE = re.compile(r"\s+")


def _compact_building_name(name: str | None) -> str:
    return _COMPACT_NAME_RE.sub("", (name or "").strip())


def _related_presale_name_score(
    source_name: str,
    candidate_name: str,
    *,
    same_dong: bool,
) -> float:
    """아파트 등 ↔ 분양권 annual 후보 이름 유사도 (키 병합 아님)."""
    a = _compact_building_name(source_name)
    b = _compact_building_name(candidate_name)
    if not a or not b:
        return 0.0
    base = 0.28 if same_dong else 0.08
    if a in b or b in a:
        return min(1.0, base + 0.7)
    ratio = SequenceMatcher(None, a, b).ratio()
    return min(1.0, base + 0.7 * ratio)


def building_addr_meta(
    conn: Connection,
    building_key: str,
) -> dict[str, Any] | None:
    """거래 원장 우선, 없으면 annual mart (장기 분양권 전용 키 지원)."""
    row = conn.execute(
        text(
            """
            SELECT display_name, asset_type, addr1, addr2, addr3, addr4
            FROM collective_transactions
            WHERE building_key = :bk
            LIMIT 1
            """
        ),
        {"bk": building_key},
    ).mappings().first()
    if row:
        return dict(row)
    if not _table_exists(conn, "public.collective_building_annual_stats"):
        return None
    row = conn.execute(
        text(
            """
            SELECT display_name, asset_type, addr1, addr2, addr3, addr4
            FROM collective_building_annual_stats
            WHERE building_key = :bk
            ORDER BY contract_year DESC
            LIMIT 1
            """
        ),
        {"bk": building_key},
    ).mappings().first()
    return dict(row) if row else None


def list_related_presale_from_annual(
    conn: Connection,
    building_key: str,
    *,
    limit: int = 20,
    min_score: float = 0.45,
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """같은 시군구(·동) annual 분양권 후보. 키 병합 없이 점수순 제안."""
    src = building_addr_meta(conn, building_key)
    if src is None:
        return None
    if not src.get("addr1") or not src.get("addr2"):
        return src, []
    if not _table_exists(conn, "public.collective_building_annual_stats"):
        return src, []

    rows = conn.execute(
        text(
            """
            SELECT building_key,
                   MAX(display_name) AS display_name,
                   MAX(addr1) AS addr1,
                   MAX(addr2) AS addr2,
                   MAX(addr3) AS addr3,
                   MAX(addr4) AS addr4,
                   MIN(contract_year)::int AS year_from,
                   MAX(contract_year)::int AS year_to,
                   SUM(count)::int AS total_count
            FROM collective_building_annual_stats
            WHERE asset_type = 'presale'
              AND addr1 = :a1
              AND addr2 = :a2
              AND building_key <> :bk
            GROUP BY building_key
            """
        ),
        {"a1": src["addr1"], "a2": src["addr2"], "bk": building_key},
    ).mappings().all()

    src_name = str(src.get("display_name") or "")
    src_dong = (src.get("addr3") or "").strip()
    scored: list[dict[str, Any]] = []
    for r in rows:
        same_dong = bool(src_dong) and (r.get("addr3") or "").strip() == src_dong
        score = _related_presale_name_score(
            src_name, str(r.get("display_name") or ""), same_dong=same_dong
        )
        if score < min_score:
            continue
        scored.append(
            {
                "building_key": r["building_key"],
                "display_name": r["display_name"] or "",
                "addr1": r.get("addr1"),
                "addr2": r.get("addr2"),
                "addr3": r.get("addr3"),
                "addr4": r.get("addr4"),
                "year_from": int(r["year_from"]),
                "year_to": int(r["year_to"]),
                "total_count": int(r["total_count"] or 0),
                "score": round(score, 3),
            }
        )
    scored.sort(key=lambda x: (-x["score"], -x["total_count"], x["display_name"]))
    return src, scored[:limit]


def list_buildings_live(
    conn: Connection,
    where: str,
    params: dict,
    *,
    asset_type: Optional[str],
) -> list[BuildingStatsRow]:
    rows = conn.execute(
        text(
            f"""
            SELECT building_key,
                   MAX(display_name) AS display_name,
                   MAX(asset_type) AS asset_type,
                   MAX(addr3) AS addr3,
                   MAX(addr4) AS addr4,
                   MAX(addr5) AS addr5,
                   MAX(lot_number) AS lot_number,
                   MAX(road_name) AS road_name,
                   MAX(building_year) AS building_year,
                   array_agg(unit_price ORDER BY unit_price) AS prices,
                   array_agg(contract_year) AS years
            FROM collective_transactions
            WHERE {where}
            GROUP BY building_key, asset_type
            """
        ),
        params,
    ).mappings().all()

    items: list[BuildingStatsRow] = []
    for r in rows:
        prices = [float(x) for x in (r["prices"] or []) if x is not None]
        years = [int(y) for y in (r["years"] or []) if y is not None]
        st = compute_stats(prices)
        cnt_recent = count_recent_transactions(
            years,
            contract_year_from=params.get("cy_from"),
            contract_year_to=params.get("cy_to"),
        )
        gates = evaluate_analysis_gates(st["count"], cnt_recent)
        items.append(
            _stats_row_from_live(
                dict(r),
                st,
                asset_type=asset_type,
                gates=AnalysisFeatures(
                    floor_index=gates.floor_index_eligible,
                    regression=gates.regression_eligible,
                    count_total=gates.count_total,
                    count_recent=gates.count_recent,
                    messages=gates.messages,
                ),
            )
        )
    return items


def building_rolling_from_mart(
    conn: Connection,
    building_key: str,
    *,
    window_years: int,
    as_of_month: date | None,
) -> tuple[str, list[dict], str] | None:
    if as_of_month is None or not _table_exists(conn, "public.collective_building_rolling_stats"):
        return None
    rows = conn.execute(
        text(
            """
            SELECT display_name, bucket_index, period_start, period_end,
                   count, mean
            FROM collective_building_rolling_stats
            WHERE building_key = :bk
              AND as_of_month = :as_of
              AND window_years = :wy
            ORDER BY bucket_index
            """
        ),
        {"bk": building_key, "as_of": as_of_month, "wy": window_years},
    ).mappings().all()
    if not rows:
        return None
    display_name = rows[0]["display_name"] or ""
    points = [
        {
            "bucket_index": int(r["bucket_index"]),
            "period_start": r["period_start"].isoformat() if r["period_start"] else "",
            "period_end": r["period_end"].isoformat() if r["period_end"] else "",
            "label": _rolling_bucket_label(r["period_start"], r["period_end"]),
            "count": int(r["count"] or 0),
            "mean": round(float(r["mean"]), 1) if r["mean"] is not None else None,
        }
        for r in rows
    ]
    return display_name, points, "mart"


def building_rolling_live(
    conn: Connection,
    building_key: str,
    *,
    window_years: int,
    as_of_month: date | None = None,
) -> tuple[str, list[dict], str] | None:
    """mart 미적재 시 collective_transactions에서 12개월 버킷 live 집계."""
    as_of = as_of_month
    if as_of is None:
        as_of, _ = latest_mart_snapshot(conn)
    if as_of is None:
        as_of = default_as_of_month_for_service()

    _, period_end = period_bounds_for_window(as_of, window_years)
    buckets = iter_rolling_year_buckets_old_first(period_end, window_years)

    meta = conn.execute(
        text(
            """
            SELECT MAX(display_name) AS display_name
            FROM collective_transactions
            WHERE building_key = :bk AND is_valid = true
            """
        ),
        {"bk": building_key},
    ).mappings().first()
    if not meta:
        return None
    display_name = meta["display_name"] or ""

    points: list[dict] = []
    for ps, pe, bidx in buckets:
        row = conn.execute(
            text(
                """
                SELECT array_agg(unit_price ORDER BY unit_price) AS prices
                FROM collective_transactions
                WHERE building_key = :bk
                  AND is_valid = true
                  AND unit_price IS NOT NULL
                  AND unit_price > 0
                  AND contract_date IS NOT NULL
                  AND contract_date >= :ps
                  AND contract_date <= :pe
                """
            ),
            {"bk": building_key, "ps": ps, "pe": pe},
        ).mappings().first()
        prices_raw = (row or {}).get("prices") or []
        prices = [float(x) for x in prices_raw if x is not None]
        if not prices:
            continue
        st = compute_stats(prices)
        if st["count"] <= 0:
            continue
        points.append(
            {
                "bucket_index": bidx,
                "period_start": ps.isoformat(),
                "period_end": pe.isoformat(),
                "label": _rolling_bucket_label(ps, pe),
                "count": st["count"],
                "mean": round(float(st["mean"]), 1) if st["mean"] is not None else None,
            }
        )
    if not points:
        return None
    return display_name, points, "live"
