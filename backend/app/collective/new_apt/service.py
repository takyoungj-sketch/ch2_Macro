"""신규아파트 실험 — 마트 로드 + 이름 조인."""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import ProgrammingError

from app.collective.new_apt.constants import DAEJEON_SIGUNGU, SIDO_CHUNGBUK, SIDO_DAEJEON, SIDO_NAMES
from app.collective.new_apt.error_audit import append_watch_ledger, refresh_watch_fields
from app.collective.new_apt.experiment import run_experiment
from app.collective.new_apt.regional import run_region_compare

MART_SQL = """
SELECT *
FROM new_apartment_complex_year
WHERE sido_code = :sido
"""

NAME_SQL = """
SELECT building_key,
       MAX(display_name) AS display_name,
       MAX(addr2) AS addr2,
       MAX(addr3) AS addr3
FROM collective_transactions
WHERE sido_code = :sido
  AND asset_type = 'apartment'
GROUP BY building_key
"""

BRAND_SQL = """
SELECT building_key,
       MAX(brand) AS brand,
       MAX(builder_group) AS builder_group
FROM collective_building_attributes
WHERE asset_type = 'apartment'
GROUP BY building_key
"""

GU_SQL = """
SELECT DISTINCT btrim(sigungu_code::text) AS code,
       MAX(btrim(sigungu_name::text)) AS name
FROM region_codes
WHERE btrim(sigungu_code::text) LIKE :prefix
GROUP BY 1
"""


def _gu_names(conn: Connection, sido: str) -> dict[str, str]:
    names = dict(DAEJEON_SIGUNGU)
    try:
        rows = conn.execute(text(GU_SQL), {"prefix": f"{sido}%"}).mappings().all()
    except Exception:  # noqa: BLE001
        return names
    for r in rows:
        code = str(r["code"] or "").strip()
        name = str(r["name"] or "").strip()
        if code and name:
            names[code] = name
    return names


def load_experiment(conn: Connection, *, sido_code: str = SIDO_DAEJEON) -> dict[str, Any]:
    try:
        df = pd.read_sql(text(MART_SQL), conn, params={"sido": sido_code})
    except ProgrammingError as exc:
        raise RuntimeError("new_apartment_complex_year 마트가 없습니다") from exc
    if df.empty:
        raise RuntimeError("마트가 비어 있습니다 — build_new_apartment_dataset.py 먼저")

    bundle = run_experiment(df)
    names = pd.read_sql(text(NAME_SQL), conn, params={"sido": sido_code})
    name_map = (
        names.drop_duplicates("building_key").set_index("building_key")["display_name"].astype(str).to_dict()
        if not names.empty
        else {}
    )
    gu_map = _gu_names(conn, sido_code)
    for cell in bundle["cells"]:
        cell["display_name"] = name_map.get(cell["building_key"]) or cell["building_key"][:12]
        code = cell.get("sigungu_code")
        cell["sigungu_name"] = gu_map.get(code, code) if code else None
    audit = bundle.get("error_audit") or {}
    for b in audit.get("buildings") or []:
        b["display_name"] = name_map.get(b["building_key"]) or b.get("display_name")
        code = b.get("sigungu_code")
        if code:
            b["sigungu_name"] = gu_map.get(code, b.get("sigungu_name") or code)
    bmap = {b["building_key"]: b for b in audit.get("buildings") or []}
    for p in audit.get("patterns") or []:
        for ex in p.get("examples") or []:
            src = bmap.get(ex.get("building_key") or "")
            if src:
                ex["display_name"] = src.get("display_name")
                ex["sigungu_name"] = src.get("sigungu_name")
    for row in bundle["validation"]["leave_one_gu"]:
        row["label"] = gu_map.get(row["group"], row.get("label") or row["group"])
    brand_map: dict[str, str] = {}
    builder_map: dict[str, str] = {}
    try:
        brand_df = pd.read_sql(text(BRAND_SQL), conn)
        if not brand_df.empty:
            brand_map = (
                brand_df.dropna(subset=["brand"])
                .drop_duplicates("building_key")
                .set_index("building_key")["brand"]
                .astype(str)
                .to_dict()
            )
            builder_map = (
                brand_df.dropna(subset=["builder_group"])
                .drop_duplicates("building_key")
                .set_index("building_key")["builder_group"]
                .astype(str)
                .to_dict()
            )
    except Exception:  # noqa: BLE001
        brand_map, builder_map = {}, {}
    for cell in bundle["cells"]:
        key = cell["building_key"]
        cell["brand"] = brand_map.get(key) or cell.get("brand")
        cell["builder_group"] = cell.get("builder_group") or builder_map.get(key)
    audit = bundle.get("error_audit") or {}
    for b in audit.get("buildings") or []:
        key = b["building_key"]
        b["brand"] = brand_map.get(key) or b.get("brand")
        b["builder_group"] = b.get("builder_group") or builder_map.get(key)
    bmap = {b["building_key"]: b for b in audit.get("buildings") or []}
    cell_meta = {}
    for c in bundle["cells"]:
        cell_meta.setdefault(c["building_key"], c)
    for m in (audit.get("large_new_watch") or {}).get("members") or []:
        key = m.get("building_key") or ""
        src = bmap.get(key) or cell_meta.get(key) or {}
        m["display_name"] = name_map.get(key) or src.get("display_name") or m.get("display_name")
        m["sigungu_name"] = src.get("sigungu_name") or m.get("sigungu_name")
        m["sigungu_code"] = src.get("sigungu_code") or m.get("sigungu_code")
        m["builder_group"] = src.get("builder_group") or builder_map.get(key) or m.get("builder_group")
        m["brand"] = src.get("brand") or brand_map.get(key) or m.get("brand")
    refresh_watch_fields(audit)
    watch = audit.get("large_new_watch") or {}
    hist = append_watch_ledger(sido_code, watch)
    if audit.get("large_new_watch") is not None:
        audit["large_new_watch"]["history"] = hist
    bundle["error_audit"] = audit
    bundle["sido_code"] = sido_code
    bundle["sido_name"] = SIDO_NAMES.get(sido_code, sido_code)
    return bundle


def load_mart(conn: Connection, sido_code: str) -> pd.DataFrame:
    try:
        df = pd.read_sql(text(MART_SQL), conn, params={"sido": sido_code})
    except ProgrammingError as exc:
        raise RuntimeError("new_apartment_complex_year 마트가 없습니다") from exc
    return df


def load_region_compare(conn: Connection) -> dict[str, Any]:
    dj = load_mart(conn, SIDO_DAEJEON)
    cb = load_mart(conn, SIDO_CHUNGBUK)
    if dj.empty:
        raise RuntimeError("대전 마트가 비어 있습니다 — build_new_apartment_dataset.py --sido-code 30")
    if cb.empty:
        raise RuntimeError("충북 마트가 비어 있습니다 — build_new_apartment_dataset.py --sido-code 43 --replace")
    return run_region_compare(dj, cb)
