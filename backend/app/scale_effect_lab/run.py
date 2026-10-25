"""읍면동 규모효과 7모형 비교를 돌려 docs/lab/scale_effect_lab.json 에 남긴다.

제품 회귀 식은 읽기만 한다. 원장은 고치지 않는다.
선정은 거래 수와 규모 분포만 쓴다. 단가로 고르지 않는다.

backend 에서:
  python -m app.scale_effect_lab.run
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.scale_effect_lab.fit import fit_cell, summarize

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lab" / "scale_effect_lab.json"
METRO = ("서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시")
METRO_CODES = {"11", "26", "27", "28", "29", "30", "31"}
MAX_ROWS = 3500


def _cols(conn: Connection, table: str) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :t
            """
        ),
        {"t": table},
    ).fetchall()
    return {str(r[0]) for r in rows}


def _window(conn: Connection, table: str, cols: set[str]) -> tuple[int, int]:
    col = "contract_year" if "contract_year" in cols else None
    if col is None:
        raise RuntimeError(f"{table} contract_year 없음")
    valid = "AND is_valid = TRUE" if "is_valid" in cols else ""
    year = conn.execute(text(f"SELECT MAX({col})::int FROM {table} WHERE {col} IS NOT NULL {valid}")).scalar()
    if year is None:
        raise RuntimeError(f"{table} 연도 없음")
    return int(year) - 4, int(year)


def _emd_expr(cols: set[str]) -> str:
    parts = []
    for col in ("addr4", "addr3", "eupmyeondong_name"):
        if col in cols:
            parts.append(f"NULLIF(btrim({col}::text), '')")
    if not parts:
        return "NULL::text"
    return "COALESCE(" + ", ".join(parts) + ")"


def _prefix_bounds(code: str) -> tuple[str, str]:
    n = int(str(code).strip())
    return f"{n:08d}00", f"{n + 1:08d}00"


def _collapse(series: pd.Series, k: int = 4) -> np.ndarray:
    s = series.fillna("").astype(str).str.strip()
    s = s.replace({"": "기타", "None": "기타", "nan": "기타"})
    top = s.value_counts().head(k).index.tolist()
    s = s.where(s.isin(top), "기타")
    cats = [c for c in top if c != "기타"]
    if (s == "기타").any() and "기타" not in cats:
        cats = cats[:-1] if len(cats) >= k else cats
    dummies = pd.get_dummies(s, dtype=float)
    keep = [c for c in dummies.columns if c != "기타"][:k]
    if not keep:
        return np.zeros((len(s), 0))
    return dummies[keep].to_numpy(dtype=float)


_RES_ZONE = {"1전", "2전", "1주", "2주", "3주", "준주"}
_COM_ZONE = {"근상", "유상", "일상", "중상"}
_IND_ZONE = {"전공", "일공", "준공"}
_NONURBAN_ZONE = {"자녹", "생녹", "보녹", "계관", "보관", "생관", "농림", "자보", "개제"}


def _zone_group(series: pd.Series) -> pd.Series:
    raw = series.fillna("").astype(str).str.strip()

    def one(v: str) -> str:
        if v in _RES_ZONE or "주거" in v:
            return "주거"
        if v in _COM_ZONE or "상업" in v:
            return "상업"
        if v in _IND_ZONE or "공업" in v:
            return "공업"
        if v in _NONURBAN_ZONE or any(tok in v for tok in ("녹지", "관리", "농림", "보전")):
            return "비도시"
        return "기타"

    return raw.map(one)


def _sample_clause(n: int, cols: set[str]) -> str:
    if n <= MAX_ROWS:
        return ""
    key = None
    for cand in ("transaction_hash", "id", "beopjungri_code"):
        if cand in cols:
            key = cand
            break
    if key is None:
        return ""
    pct = max(1, min(99, int(MAX_ROWS / max(n, 1) * 100) + 1))
    return f"AND mod(abs(hashtext({key}::text)), 100) < {pct}"


def _pick(rows: list[dict[str, Any]], pred, used: set[str]) -> dict[str, Any] | None:
    pool = [r for r in rows if pred(r) and str(r["code"]) not in used]
    if not pool:
        return None
    pool.sort(key=lambda r: (-(float(r.get("spread") or 0)), -int(r["n"])))
    chosen = pool[0]
    used.add(str(chosen["code"]))
    return chosen


def _screen_frame(conn: Connection, sql: str, params: dict) -> list[dict[str, Any]]:
    recs = conn.execute(text(sql), params).mappings().all()
    out = []
    for r in recs:
        d = dict(r)
        n = int(d["n"] or 0)
        p50 = float(d["p50"] or 0)
        p90 = float(d["p90"] or 0)
        d["n"] = n
        d["p50"] = p50
        d["p90"] = p90
        d["spread"] = (p90 / p50) if p50 > 0 else 0.0
        d["code"] = str(d["code"]).strip()
        out.append(d)
    return out


def _load_rows(conn: Connection, sql: str, params: dict) -> pd.DataFrame:
    recs = conn.execute(text(sql), params).mappings().all()
    return pd.DataFrame(recs)


def _finish_cell(spec: dict[str, Any], df: pd.DataFrame, *, y: str, size: str, cont: list[str], dummies: np.ndarray) -> dict[str, Any]:
    if df.empty or y not in df or size not in df:
        spec["fit"] = {"status": "행 없음"}
        return spec
    work = df.copy()
    work[y] = pd.to_numeric(work[y], errors="coerce")
    work[size] = pd.to_numeric(work[size], errors="coerce")
    blocks = []
    n_cont = 0
    for col in cont:
        if col not in work:
            continue
        val = pd.to_numeric(work[col], errors="coerce")
        med = float(val.median()) if val.notna().any() else 0.0
        blocks.append((val.fillna(med) - med).to_numpy(dtype=float))
        n_cont += 1
    if dummies.size:
        blocks.append(dummies)
    controls = np.column_stack(blocks) if blocks else None
    size_v = work[size].to_numpy(dtype=float)
    p10 = float(np.nanpercentile(size_v[np.isfinite(size_v) & (size_v > 0)], 10))
    p90 = float(np.nanpercentile(size_v[np.isfinite(size_v) & (size_v > 0)], 90))
    spec["fit"] = fit_cell(
        y=work[y].to_numpy(dtype=float),
        size=size_v,
        controls=controls,
        n_cont=n_cont,
        p10=p10,
        p90=p90,
    )
    spec["n_used"] = int(spec["fit"].get("n") or 0)
    return spec


def _base_spec(role: str, label: str, row: dict[str, Any] | None, *, thin: bool, controls: str, slice_name: str) -> dict[str, Any]:
    if row is None:
        return {"role": role, "role_label": label, "status": "후보 없음", "thin": thin, "controls": controls, "slice": slice_name}
    name = " ".join(str(row.get(k) or "").strip() for k in ("sido", "sigungu", "emd") if str(row.get(k) or "").strip())
    return {
        "role": role,
        "role_label": label,
        "status": "ok",
        "thin": thin,
        "name": name,
        "code": str(row["code"]),
        "slice": slice_name,
        "n": int(row["n"]),
        "spread": round(float(row["spread"]), 2),
        "controls": controls,
    }


def run_land(engine: Engine) -> dict[str, Any]:
    full_c = "연도·도로·용도"
    thin_c = "연도만"
    with engine.connect() as conn:
        cols = _cols(conn, "land_transactions")
        y0, y1 = _window(conn, "land_transactions", cols)
        sql = """
            SELECT left(btrim(beopjungri_code::text), 8) AS code,
                   max(sido_code) AS sido_code,
                   max(sigungu_code) AS sigungu_code,
                   btrim(land_category::text) AS cat,
                   COUNT(*)::int AS n,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY area_sqm) AS p50,
                   percentile_cont(0.9) WITHIN GROUP (ORDER BY area_sqm) AS p90,
                   COUNT(*) FILTER (WHERE btrim(zone_type::text) IN ('1전','2전','1주','2주','3주','준주') OR zone_type LIKE '%주거%')::int AS n_res,
                   COUNT(*) FILTER (WHERE btrim(zone_type::text) IN ('근상','유상','일상','중상') OR zone_type LIKE '%상업%')::int AS n_com,
                   COUNT(*) FILTER (WHERE btrim(zone_type::text) IN ('전공','일공','준공') OR zone_type LIKE '%공업%')::int AS n_ind
            FROM land_transactions
            WHERE is_valid = TRUE
              AND COALESCE(is_cancelled, FALSE) = FALSE
              AND COALESCE(is_partial_ownership, FALSE) = FALSE
              AND contract_year BETWEEN :y0 AND :y1
              AND area_sqm > 0 AND area_sqm < 10000000
              AND unit_price_per_sqm > 0
              AND btrim(land_category::text) IN ('대', '전', '답')
              AND beopjungri_code IS NOT NULL
            GROUP BY 1, btrim(land_category::text)
            HAVING COUNT(*) >= 30
        """
        rows = _screen_frame(conn, sql, {"y0": y0, "y1": y1})
        sigungu_names = {
            str(r["code"]).strip(): (str(r["sido"] or "").strip(), str(r["sigungu"] or "").strip())
            for r in conn.execute(
                text(
                    """
                    SELECT btrim(sigungu_code::text) AS code,
                           max(btrim(sido_name::text)) AS sido,
                           max(btrim(sigungu_name::text)) AS sigungu
                    FROM region_codes
                    GROUP BY 1
                    """
                )
            ).mappings()
        }
        emd_names = {
            str(r["code"]).strip(): str(r["emd"] or "").strip()
            for r in conn.execute(
                text(
                    """
                    SELECT left(btrim(beopjungri_code::text), 8) AS code,
                           max(btrim(eupmyeondong_name::text)) AS emd
                    FROM region_codes
                    GROUP BY 1
                    """
                )
            ).mappings()
        }
        for r in rows:
            n = max(int(r["n"]), 1)
            sido, sigungu = sigungu_names.get(str(r.get("sigungu_code") or "").strip(), ("", ""))
            r["sido"] = sido
            r["sigungu"] = sigungu
            r["emd"] = emd_names.get(str(r["code"]), "")
            r["res"] = int(r.get("n_res") or 0) / n
            r["com"] = int(r.get("n_com") or 0) / n
            r["ind"] = int(r.get("n_ind") or 0) / n
            r["metro"] = str(r.get("sido_code") or "").strip() in METRO_CODES
            r["gun"] = sigungu.endswith("군")
            r["city"] = sigungu.endswith("시")
        used: set[str] = set()
        picks = [
            ("urban_res", "도시 주거", False, "대", full_c, lambda r: r["cat"] == "대" and r["metro"] and r["res"] >= 0.55 and r["n"] >= 100 and r["spread"] >= 1.8),
            ("urban_com", "도시 상업", False, "대", full_c, lambda r: r["cat"] == "대" and r["metro"] and r["com"] >= 0.35 and r["n"] >= 80 and r["spread"] >= 1.6),
            ("fringe", "외곽 개발", False, "대", full_c, lambda r: r["cat"] == "대" and (not r["metro"]) and r["city"] and r["p90"] >= 800 and r["n"] >= 80 and r["spread"] >= 1.8),
            ("rural", "농촌", False, "전·답", full_c, lambda r: r["cat"] in ("전", "답") and r["gun"] and r["n"] >= 80 and r["spread"] >= 2),
            ("mixed", "용도 혼재", False, "대", full_c, lambda r: r["cat"] == "대" and 0.2 <= r["res"] <= 0.55 and (r["com"] + r["ind"]) >= 0.15 and r["n"] >= 80),
            ("thin", "얇은 표본", True, "대", thin_c, lambda r: r["cat"] == "대" and 30 <= r["n"] <= 70 and r["spread"] >= 1.6),
        ]
        cells = []
        for role, label, thin, slice_name, controls, pred in picks:
            row = _pick(rows, pred, used)
            spec = _base_spec(role, label, row, thin=thin, controls=controls, slice_name=slice_name if row is None else f"{row['cat']}")
            if row is None:
                cells.append(spec)
                continue
            lo, hi = _prefix_bounds(row["code"])
            sample = _sample_clause(int(row["n"]), cols)
            df = _load_rows(
                conn,
                f"""
                SELECT area_sqm::float8 AS size, unit_price_per_sqm::float8 AS y,
                       contract_year::float8 AS year, road_condition, zone_type
                FROM land_transactions
                WHERE is_valid = TRUE
                  AND COALESCE(is_cancelled, FALSE) = FALSE
                  AND COALESCE(is_partial_ownership, FALSE) = FALSE
                  AND contract_year BETWEEN :y0 AND :y1
                  AND area_sqm > 0 AND unit_price_per_sqm > 0
                  AND btrim(land_category::text) = :cat
                  AND beopjungri_code >= :lo AND beopjungri_code < :hi
                  {sample}
                """,
                {"y0": y0, "y1": y1, "cat": row["cat"], "lo": lo, "hi": hi},
            )
            cont = ["year"]
            dummies = np.zeros((len(df), 0))
            if not thin and not df.empty:
                road = _collapse(df["road_condition"])
                zone = _collapse(_zone_group(df["zone_type"]), k=4)
                dummies = np.column_stack([a for a in (road, zone) if a.size]) if road.size or zone.size else dummies
            cells.append(_finish_cell(spec, df, y="y", size="size", cont=cont, dummies=dummies))
    return _domain("land", "토지", "계약면적", "㎡당 단가", y0, y1, cells, "대·전·답은 한 식에 섞지 않았다. 용도 혼재는 대지 안 용도 비율이다.")


def run_built(engine: Engine) -> dict[str, Any]:
    with engine.connect() as conn:
        cols = _cols(conn, "built_transactions")
        y0, y1 = _window(conn, "built_transactions", cols)
        code_col = "eupmyeondong_code" if "eupmyeondong_code" in cols else "beopjungri_code"
        emd = _emd_expr(cols)
        sql = f"""
            SELECT left(btrim({code_col}::text), 8) AS code,
                   max(addr1) AS sido, max(addr2) AS sigungu, max({emd}) AS emd,
                   btrim(asset_type::text) AS cat,
                   COUNT(*)::int AS n,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY gross_area) AS p50,
                   percentile_cont(0.9) WITHIN GROUP (ORDER BY gross_area) AS p90,
                   COUNT(*) FILTER (WHERE btrim(zone_type::text) IN ('1전','2전','1주','2주','3주','준주') OR zone_type LIKE '%주거%')::int AS n_res,
                   COUNT(*) FILTER (WHERE btrim(zone_type::text) IN ('근상','유상','일상','중상') OR zone_type LIKE '%상업%')::int AS n_com,
                   COUNT(*) FILTER (WHERE btrim(zone_type::text) IN ('전공','일공','준공') OR zone_type LIKE '%공업%')::int AS n_ind
            FROM built_transactions
            WHERE is_valid = TRUE
              AND contract_year BETWEEN :y0 AND :y1
              AND gross_area > 0 AND price > 0
              AND asset_type IN ('commercial', 'factory', 'detached')
              AND {code_col} IS NOT NULL
            GROUP BY 1, btrim(asset_type::text)
            HAVING COUNT(*) >= 30
        """
        rows = _screen_frame(conn, sql, {"y0": y0, "y1": y1})
        for r in rows:
            n = max(int(r["n"]), 1)
            r["res"] = int(r.get("n_res") or 0) / n
            r["com"] = int(r.get("n_com") or 0) / n
            r["ind"] = int(r.get("n_ind") or 0) / n
            r["metro"] = str(r.get("sido") or "") in METRO
            r["gun"] = str(r.get("sigungu") or "").endswith("군")
            r["city"] = str(r.get("sigungu") or "").endswith("시")
        used: set[str] = set()
        picks = [
            ("urban_res", "도시 주거", False, lambda r: r["cat"] == "detached" and r["metro"] and r["n"] >= 80 and r["spread"] >= 1.6),
            ("urban_com", "도시 상업", False, lambda r: r["cat"] == "commercial" and r["metro"] and r["n"] >= 80 and r["spread"] >= 1.5),
            ("fringe", "외곽 개발", False, lambda r: r["cat"] == "factory" and (not r["metro"]) and r["city"] and r["n"] >= 40 and r["spread"] >= 1.5),
            ("rural", "농촌", False, lambda r: r["cat"] == "detached" and r["gun"] and r["n"] >= 40 and r["spread"] >= 1.5),
            ("mixed", "용도 혼재", False, lambda r: r["cat"] == "commercial" and 0.15 <= r["res"] <= 0.6 and r["com"] >= 0.15 and r["n"] >= 60),
            ("thin", "얇은 표본", True, lambda r: r["cat"] == "commercial" and 30 <= r["n"] <= 70 and r["spread"] >= 1.4),
        ]
        cells = []
        for role, label, thin, pred in picks:
            row = _pick(rows, pred, used)
            spec = _base_spec(role, label, row, thin=thin, controls="연식만" if thin else "연식·도로·용도", slice_name="" if row is None else str(row["cat"]))
            if row is None:
                cells.append(spec)
                continue
            sample = _sample_clause(int(row["n"]), cols)
            where_code = f"left(btrim({code_col}::text), 8) = :code"
            df = _load_rows(
                conn,
                f"""
                SELECT gross_area::float8 AS size, (price / gross_area)::float8 AS y,
                       building_age::float8 AS age, road_width_label, zone_type
                FROM built_transactions
                WHERE is_valid = TRUE
                  AND contract_year BETWEEN :y0 AND :y1
                  AND gross_area > 0 AND price > 0
                  AND btrim(asset_type::text) = :cat
                  AND {where_code}
                  {sample}
                """,
                {"y0": y0, "y1": y1, "cat": row["cat"], "code": row["code"]},
            )
            dummies = np.zeros((len(df), 0))
            if not thin and not df.empty:
                road = _collapse(df["road_width_label"]) if "road_width_label" in df else np.zeros((len(df), 0))
                zone = _collapse(_zone_group(df["zone_type"]), k=4) if "zone_type" in df else np.zeros((len(df), 0))
                parts = [a for a in (road, zone) if getattr(a, "size", 0)]
                dummies = np.column_stack(parts) if parts else dummies
            cells.append(_finish_cell(spec, df, y="y", size="size", cont=["age"], dummies=dummies))
    return _domain("built", "복합", "연면적", "연면적당 단가", y0, y1, cells, "단독·상업·공장만. 단가 = 거래금액 / 연면적.")


def _collective(engine: Engine, *, commercial: bool) -> dict[str, Any]:
    table = "collective_commercial_transactions" if commercial else "collective_transactions"
    size_col = "gross_area" if commercial else "exclusive_area"
    label = "비주거" if commercial else "집합주거"
    domain = "commercial" if commercial else "residential"
    size_label = "연면적" if commercial else "전용면적"
    with engine.connect() as conn:
        cols = _cols(conn, table)
        if size_col not in cols:
            return _domain(domain, label, size_label, "㎡당 단가", 0, 0, [], f"{size_col} 열이 없다.")
        y0, y1 = _window(conn, table, cols)
        code_col = "eupmyeondong_code" if "eupmyeondong_code" in cols else "beopjungri_code"
        emd = _emd_expr(cols)
        asset_filter = (
            "asset_type IN ('collective_shop', 'collective_factory')"
            if commercial
            else "asset_type IN ('apartment', 'officetel', 'rowhouse')"
        )
        sql = f"""
            SELECT left(btrim({code_col}::text), 8) AS code,
                   max(addr1) AS sido, max(addr2) AS sigungu, max({emd}) AS emd,
                   btrim(asset_type::text) AS cat,
                   COUNT(*)::int AS n,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY {size_col}) AS p50,
                   percentile_cont(0.9) WITHIN GROUP (ORDER BY {size_col}) AS p90
            FROM {table}
            WHERE is_valid = TRUE
              AND contract_year BETWEEN :y0 AND :y1
              AND {size_col} > 0 AND unit_price > 0
              AND {asset_filter}
              AND {code_col} IS NOT NULL
            GROUP BY 1, btrim(asset_type::text)
            HAVING COUNT(*) >= 25
        """
        rows = _screen_frame(conn, sql, {"y0": y0, "y1": y1})
        by_code: dict[str, set[str]] = {}
        for r in rows:
            r["metro"] = str(r.get("sido") or "") in METRO
            r["gun"] = str(r.get("sigungu") or "").endswith("군")
            r["city"] = str(r.get("sigungu") or "").endswith("시")
            by_code.setdefault(str(r["code"]), set()).add(str(r["cat"]))
        for r in rows:
            r["n_types"] = len(by_code.get(str(r["code"]), ()))
        used: set[str] = set()
        if commercial:
            picks = [
                ("urban_com", "도시 상업", False, lambda r: r["cat"] == "collective_shop" and r["metro"] and r["n"] >= 80 and r["spread"] >= 1.4),
                ("fringe", "외곽 개발", False, lambda r: r["cat"] == "collective_factory" and r["city"] and r["n"] >= 40 and r["spread"] >= 1.4),
                ("urban_res", "도시 소형", False, lambda r: r["cat"] == "collective_shop" and r["metro"] and r["n"] >= 60 and r["p90"] <= 400),
                ("rural", "농촌", False, lambda r: r["cat"] == "collective_shop" and r["gun"] and r["n"] >= 30),
                ("mixed", "유형 혼재", False, lambda r: r["n_types"] >= 2 and r["n"] >= 40),
                ("thin", "얇은 표본", True, lambda r: r["cat"] == "collective_shop" and 25 <= r["n"] <= 60),
            ]
        else:
            picks = [
                ("urban_res", "도시 주거", False, lambda r: r["cat"] == "apartment" and r["metro"] and r["n"] >= 120 and r["spread"] >= 1.3),
                ("urban_com", "오피스텔", False, lambda r: r["cat"] == "officetel" and r["metro"] and r["n"] >= 60 and r["spread"] >= 1.3),
                ("fringe", "외곽 개발", False, lambda r: r["cat"] == "apartment" and (not r["metro"]) and r["city"] and r["n"] >= 80 and r["spread"] >= 1.3),
                ("rural", "농촌", False, lambda r: r["cat"] == "apartment" and r["gun"] and r["n"] >= 30),
                ("mixed", "유형 혼재", False, lambda r: r["n_types"] >= 2 and r["cat"] == "apartment" and r["n"] >= 40),
                ("thin", "얇은 표본", True, lambda r: r["cat"] == "apartment" and 25 <= r["n"] <= 70 and r["spread"] >= 1.2),
            ]
        cells = []
        for role, label_r, thin, pred in picks:
            row = _pick(rows, pred, used)
            spec = _base_spec(role, label_r, row, thin=thin, controls="연도만" if thin else "연도·층", slice_name="" if row is None else str(row["cat"]))
            if row is None:
                cells.append(spec)
                continue
            sample = _sample_clause(int(row["n"]), cols)
            floor = "floor::float8 AS floor" if "floor" in cols else "NULL::float8 AS floor"
            asset_clause = "" if role == "mixed" and commercial else "AND btrim(asset_type::text) = :cat"
            params = {"y0": y0, "y1": y1, "code": row["code"]}
            if asset_clause:
                params["cat"] = row["cat"]
            df = _load_rows(
                conn,
                f"""
                SELECT {size_col}::float8 AS size, unit_price::float8 AS y,
                       contract_year::float8 AS year, {floor}
                FROM {table}
                WHERE is_valid = TRUE
                  AND contract_year BETWEEN :y0 AND :y1
                  AND {size_col} > 0 AND unit_price > 0
                  AND left(btrim({code_col}::text), 8) = :code
                  {asset_clause}
                  {sample}
                """,
                params,
            )
            dummies = np.zeros((len(df), 0))
            cells.append(_finish_cell(spec, df, y="y", size="size", cont=[] if thin else ["year", "floor"], dummies=dummies))
    note = "상가·공장. 도시 소형은 연면적 꼬리가 짧은 상가다." if commercial else "아파트·오피스텔·연립. 오피스텔 칸이 도시 상업의 자리이다."
    return _domain(domain, label, size_label, "㎡당 단가", y0, y1, cells, note)


def _domain(domain: str, label: str, size_label: str, y_label: str, y0: int, y1: int, cells: list[dict], note: str) -> dict[str, Any]:
    questions = summarize(cells)
    return {
        "id": domain,
        "label": label,
        "size_label": size_label,
        "y_label": y_label,
        "year_from": y0,
        "year_to": y1,
        "note": note,
        "questions": questions,
        "cells": cells,
    }


def main() -> None:
    from app.built.db import get_built_engine
    from app.collective.db import get_collective_engine
    from app.db import engine as land_engine

    domains = []
    built_engine = get_built_engine()
    collective_engine = get_collective_engine()
    only = {a.strip() for a in sys.argv[1:] if a.strip()}
    if (not only or "built" in only or "residential" in only or "commercial" in only) and (
        built_engine is None or collective_engine is None
    ):
        raise RuntimeError("built 또는 collective DB 연결이 없다")
    runners = (
        ("land", lambda: run_land(land_engine)),
        ("built", lambda: run_built(built_engine)),
        ("residential", lambda: _collective(collective_engine, commercial=False)),
        ("commercial", lambda: _collective(collective_engine, commercial=True)),
    )
    for name, fn in runners:
        if only and name not in only:
            continue
        try:
            print(f"run {name}", flush=True)
            domains.append(fn())
            print(f"done {name}", flush=True)
        except Exception as exc:
            domains.append(
                {
                    "id": name,
                    "label": name,
                    "note": f"실행 실패: {type(exc).__name__}: {exc}",
                    "questions": {"explain": "실행되지 않았다.", "predict": "실행되지 않았다.", "recommend": "실행되지 않았다."},
                    "cells": [],
                }
            )
            print(f"fail {name}: {type(exc).__name__}: {exc}", flush=True)
    payload = {
        "title": "규모효과 모형 비교",
        "term": "규모효과(면적에 따른 단가 변화)",
        "generated": date.today().isoformat(),
        "window": "최근 계약연도 포함 5년",
        "models": ["선형 OLS", "log-log OLS", "2차 OLS", "Ridge", "Lasso", "2차+Ridge", "2차+Lasso"],
        "score": "5겹 검증. 예측은 ㎡당 단가로 되돌린 MAPE. 정규화 강도는 학습 겹 안에서만 고른다.",
        "hold": "결측 행은 모형보다 먼저 한 번만 뺀다. 제품 선택창과 회귀 식은 바꾸지 않았다.",
        "domains": domains,
    }
    if only and OUT.exists():
        prev = json.loads(OUT.read_text(encoding="utf-8"))
        by_id = {d.get("id"): d for d in prev.get("domains") or [] if d.get("id")}
        for d in domains:
            by_id[d.get("id")] = d
        order = ["land", "built", "residential", "commercial"]
        payload["domains"] = [by_id[k] for k in order if k in by_id]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
