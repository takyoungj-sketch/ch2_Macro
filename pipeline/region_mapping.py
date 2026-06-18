"""
복합·집합 ingest 공용 — addr 정규화(D-015) + beopjungri_code 매핑(토지 clean.py 수준).

docs/REGION_ARCHITECTURE_ROADMAP.md §D-015
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from clean import build_region_lookup, map_beopjungri_codes

log = logging.getLogger(__name__)

CODE_WIDTH = {
    "sido_code": 2,
    "sigungu_code": 5,
    "eupmyeondong_code": 8,
    "beopjungri_code": 10,
}


def _s(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("", "nan", "none") else s


def normalize_addr_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    D-015: 구 없는 시에서 리가 addr4에 있으면 addr5로 승격.
    addr3이 '구'로 끝나지 않고 addr4만 있고 addr5가 비면 addr4=리.
    """
    out = df.copy()
    for c in ("addr1", "addr2", "addr3", "addr4", "addr5"):
        if c not in out.columns:
            out[c] = ""
        out[c] = out[c].apply(_s)

    mask = (
        out["addr4"].ne("")
        & out["addr5"].eq("")
        & ~out["addr3"].str.endswith("구", na=False)
    )
    if mask.any():
        out.loc[mask, "addr5"] = out.loc[mask, "addr4"]
        out.loc[mask, "addr4"] = ""

    return out


def build_sigungu_name_row(row: pd.Series) -> str:
    """addr1~5 → land clean.py sigungu_name 전체 주소 문자열."""
    parts = [_s(row.get(c)) for c in ("addr1", "addr2", "addr3", "addr4", "addr5")]
    parts = [p for p in parts if p]
    return " ".join(parts)


def _load_code_enrichment(engine: Engine) -> dict[str, tuple[str, str, str, str]]:
    """beopjungri_code → (sido, sigungu, eup, beop names + codes)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT beopjungri_code, sido_code, sigungu_code, eupmyeondong_code,
                       sido_name, sigungu_name, eupmyeondong_name, beopjungri_name
                FROM region_codes
                WHERE COALESCE(is_active, true)
                """
            )
        ).fetchall()
    out: dict[str, tuple[str, str, str, str]] = {}
    for r in rows:
        code = str(r.beopjungri_code).strip()
        out[code] = (
            str(r.sido_code).strip(),
            str(r.sigungu_code).strip(),
            str(r.eupmyeondong_code).strip(),
            code,
        )
    return out


def attach_beopjungri_codes(
    df: pd.DataFrame,
    engine: Engine,
    *,
    region_maps: dict | None = None,
) -> pd.DataFrame:
    """
    addr1~5 정규화 후 map_beopjungri_codes 적용.
    반환: sido/sigungu/eup/beopjungri_code, needs_review, mapping_notes
    """
    if df.empty:
        for c in ("sido_code", "sigungu_code", "eupmyeondong_code", "beopjungri_code"):
            if c not in df.columns:
                df[c] = pd.Series(dtype=object)
        df["needs_review"] = pd.Series(dtype=bool)
        df["mapping_notes"] = pd.Series(dtype=object)
        return df

    work = normalize_addr_fields(df)
    maps = region_maps or build_region_lookup(engine)

    map_in = pd.DataFrame(index=work.index)
    map_in["sigungu_name"] = work.apply(build_sigungu_name_row, axis=1)
    map_in["eupmyeondong_name"] = ""
    map_in["sido_code"] = ""
    map_in["sigungu_code"] = ""

    mapped = map_beopjungri_codes(map_in, maps)
    enrich = _load_code_enrichment(engine)

    out = work.copy()
    out["beopjungri_code"] = mapped["beopjungri_code"].values
    out["needs_review"] = mapped["needs_review"].values
    out["mapping_notes"] = mapped["mapping_notes"].values

    sido_c: list[str | None] = []
    sg_c: list[str | None] = []
    eup_c: list[str | None] = []
    for code in out["beopjungri_code"]:
        c = _s(code)
        if c and c in enrich:
            sc, gc, ec, _ = enrich[c]
            sido_c.append(sc or None)
            sg_c.append(gc or None)
            eup_c.append(ec or None)
        else:
            sido_c.append(None)
            sg_c.append(None)
            eup_c.append(None)

    out["sido_code"] = sido_c
    out["sigungu_code"] = sg_c
    out["eupmyeondong_code"] = eup_c

    total = len(out)
    mapped_n = int(out["beopjungri_code"].astype(str).str.strip().ne("").sum())
    review_n = int(out["needs_review"].sum())
    log.info(
        "beopjungri attach: mapped=%d/%d (%.1f%%), needs_review=%d",
        mapped_n,
        total,
        100.0 * mapped_n / total if total else 0,
        review_n,
    )
    return out


def clean_code_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col, width in CODE_WIDTH.items():
        if col not in out.columns:
            continue
        out[col] = out[col].apply(
            lambda v, w=width: (
                None
                if v is None or (isinstance(v, float) and pd.isna(v)) or _s(v) == ""
                else _s(v)[:w]
            )
        )
    return out


def log_mapping_coverage(engine: Engine, table: str, *, asset_type: str | None = None) -> None:
    clauses = ["TRUE"]
    params: dict = {}
    if asset_type:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    where = " AND ".join(clauses)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"""
                SELECT COUNT(*)::int AS total,
                       COUNT(*) FILTER (
                           WHERE beopjungri_code IS NOT NULL
                             AND btrim(beopjungri_code::text) <> ''
                       )::int AS mapped,
                       COUNT(*) FILTER (WHERE COALESCE(needs_review, false))::int AS review
                FROM {table}
                WHERE {where}
                """
            ),
            params,
        ).one()
    log.info(
        "%s%s coverage: total=%s mapped=%s (%.1f%%) needs_review=%s",
        table,
        f" asset_type={asset_type}" if asset_type else "",
        row.total,
        row.mapped,
        100.0 * row.mapped / row.total if row.total else 0,
        row.review,
    )
