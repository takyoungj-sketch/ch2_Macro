"""상권 공표 조회. 주거 원장과 조인하지 않음."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.rent.sangkwon_agg import (
    ASSET_KINDS,
    MAIN_METRICS,
    METRIC_GROUPS,
    SERIES_METRICS,
    annual_value,
    format_window_label,
    rolling_quarter_window,
)


def import_meta(conn: Connection) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT source_file, latest_year, latest_quarter, n_polygons, n_quarterly, imported_at
            FROM rent_sangkwon_import_meta
            WHERE id = 1
            """
        )
    ).mappings().first()
    return dict(row) if row else None


# 엑셀 지역구분(1) 약칭 ↔ 임대 addr1
_SIDO_SHORT = (
    ("서울특별시", "서울"),
    ("부산광역시", "부산"),
    ("대구광역시", "대구"),
    ("인천광역시", "인천"),
    ("광주광역시", "광주"),
    ("대전광역시", "대전"),
    ("울산광역시", "울산"),
    ("세종특별자치시", "세종"),
    ("경기도", "경기"),
    ("강원특별자치도", "강원"),
    ("강원도", "강원"),
    ("충청북도", "충북"),
    ("충청남도", "충남"),
    ("전북특별자치도", "전북"),
    ("전라북도", "전북"),
    ("전라남도", "전남"),
    ("경상북도", "경북"),
    ("경상남도", "경남"),
    ("제주특별자치도", "제주"),
    ("제주도", "제주"),
)


def excel_sido(addr1: str) -> str:
    a = (addr1 or "").strip()
    for full, short in _SIDO_SHORT:
        if a == full or a == short:
            return short
    return a


def list_polygons(conn: Connection, sido: str | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT sec_seq, sec_nm, sido, buld_nm, geom_geojson
        FROM rent_sangkwon
    """
    params: dict[str, Any] = {}
    if (sido or "").strip():
        sql += " WHERE sido = :sido"
        params["sido"] = excel_sido(sido)
    sql += " ORDER BY sec_nm"
    rows = conn.execute(text(sql), params).mappings()
    return [dict(r) for r in rows]


def fetch_quarterly(
    conn: Connection,
    *,
    sec_nm: str,
    metrics: tuple[str, ...],
    from_year: int,
    include_hidden_bands: bool = False,
) -> list[dict[str, Any]]:
    sql = """
        SELECT sec_nm, sido, asset_kind, metric, floor_band, floor_label,
               year, quarter, value
        FROM rent_sangkwon_quarterly
        WHERE sec_nm = :name
          AND metric IN :metrics
          AND year >= :from_year
    """
    if not include_hidden_bands:
        sql += " AND floor_band = 'all'"
    sql += " ORDER BY year, quarter, asset_kind, metric, floor_label"
    stmt = text(sql).bindparams(bindparam("metrics", expanding=True))
    return list(
        conn.execute(
            stmt,
            {"name": sec_nm, "metrics": list(metrics), "from_year": from_year},
        ).mappings()
    )


def _table_rows(
    grouped: dict[tuple, dict[int, Optional[float]]],
) -> list[dict[str, Any]]:
    out_rows = []
    for group_id, group_label, metrics in METRIC_GROUPS:
        for metric in metrics:
            cells = {k: None for k in ASSET_KINDS}
            for kind in ASSET_KINDS:
                cells[kind] = annual_value(metric, grouped.get((kind, metric), {}))
            out_rows.append(
                {
                    "metric": metric,
                    "group": group_id,
                    "group_label": group_label,
                    "values": cells,
                }
            )
    return out_rows


def annual_table(
    conn: Connection,
    *,
    sec_nm: str,
    year: Optional[int] = None,
) -> dict[str, Any]:
    """기본은 최신 분기 기준 4분기(1년) 롤링. year를 주면 그 해 달력 연간(추세와 동일 식)."""
    meta = import_meta(conn)
    empty = {
        "year": None,
        "sec_nm": sec_nm,
        "sido": "",
        "rows": [],
        "source_file": "",
        "window_label": "",
        "window_mode": "rolling_4q",
        "window_start_year": None,
        "window_start_quarter": None,
        "window_end_year": None,
        "window_end_quarter": None,
    }
    if meta is None:
        return empty

    if year is not None:
        y = int(year)
        rows = fetch_quarterly(
            conn,
            sec_nm=sec_nm,
            metrics=MAIN_METRICS,
            from_year=y,
            include_hidden_bands=False,
        )
        rows = [r for r in rows if int(r["year"]) == y]
        sido = str(rows[0]["sido"]) if rows else ""
        grouped: dict[tuple, dict[int, Optional[float]]] = defaultdict(dict)
        for r in rows:
            key = (r["asset_kind"], r["metric"])
            grouped[key][int(r["quarter"])] = (
                float(r["value"]) if r["value"] is not None else None
            )
        return {
            "year": y,
            "sec_nm": sec_nm,
            "sido": sido,
            "rows": _table_rows(grouped),
            "source_file": meta.get("source_file") or "",
            "latest_year": meta.get("latest_year"),
            "latest_quarter": meta.get("latest_quarter"),
            "window_label": f"{y}년 연간",
            "window_mode": "calendar_year",
            "window_start_year": y,
            "window_start_quarter": 1,
            "window_end_year": y,
            "window_end_quarter": 4,
        }

    ey = meta.get("latest_year")
    eq = meta.get("latest_quarter")
    if ey is None or eq is None:
        return {**empty, "source_file": meta.get("source_file") or ""}
    window = rolling_quarter_window(int(ey), int(eq))
    wanted = set(window)
    rows = fetch_quarterly(
        conn,
        sec_nm=sec_nm,
        metrics=MAIN_METRICS,
        from_year=window[0][0],
        include_hidden_bands=False,
    )
    rows = [r for r in rows if (int(r["year"]), int(r["quarter"])) in wanted]
    sido = str(rows[0]["sido"]) if rows else ""
    raw: dict[tuple, dict[tuple[int, int], Optional[float]]] = defaultdict(dict)
    for r in rows:
        raw[(r["asset_kind"], r["metric"])][(int(r["year"]), int(r["quarter"]))] = (
            float(r["value"]) if r["value"] is not None else None
        )
    grouped = {}
    for key, yq in raw.items():
        grouped[key] = {i + 1: yq.get(window[i]) for i in range(len(window))}
    label = format_window_label(window)
    return {
        "year": int(ey),
        "sec_nm": sec_nm,
        "sido": sido,
        "rows": _table_rows(grouped),
        "source_file": meta.get("source_file") or "",
        "latest_year": int(ey),
        "latest_quarter": int(eq),
        "window_label": label,
        "window_mode": "rolling_4q",
        "window_start_year": window[0][0],
        "window_start_quarter": window[0][1],
        "window_end_year": window[-1][0],
        "window_end_quarter": window[-1][1],
    }


def series_table(
    conn: Connection,
    *,
    sec_nm: str,
    from_year: int = 2019,
) -> dict[str, Any]:
    meta = import_meta(conn)
    rows = fetch_quarterly(
        conn,
        sec_nm=sec_nm,
        metrics=SERIES_METRICS,
        from_year=from_year,
        include_hidden_bands=False,
    )
    sido = str(rows[0]["sido"]) if rows else ""
    by_year: dict[tuple, dict[int, dict[int, Optional[float]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    floors: set[str] = set()
    for r in rows:
        metric = r["metric"]
        fl = r["floor_label"] or ""
        if metric in {"floor_rent", "floor_utility"}:
            floors.add(fl)
        key = (r["asset_kind"], metric, fl)
        by_year[key][int(r["year"])][int(r["quarter"])] = (
            float(r["value"]) if r["value"] is not None else None
        )
    years = sorted({int(r["year"]) for r in rows})
    series = []
    for (kind, metric, fl), year_map in sorted(by_year.items()):
        points = []
        for y in years:
            val = annual_value(metric, year_map.get(y, {}))
            points.append({"year": y, "value": val})
        series.append(
            {
                "asset_kind": kind,
                "metric": metric,
                "floor_label": fl,
                "points": points,
            }
        )
    return {
        "sec_nm": sec_nm,
        "sido": sido,
        "from_year": from_year,
        "years": years,
        "series": series,
        "floor_labels": sorted(floors),
        "source_file": (meta or {}).get("source_file") or "",
        "break_note": "2024.3분기 상권구획 변경으로 일부 상권은 시계열이 단절됩니다.",
    }
