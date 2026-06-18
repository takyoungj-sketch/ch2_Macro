#!/usr/bin/env python3
"""거래 원장 + region_codes → region_sigungu_meta 적재."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from sqlalchemy import text

import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from collective.db_utils import get_collective_engine

try:
    from db_utils import get_built_engine
except ImportError:
    get_built_engine = None  # type: ignore[misc, assignment]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

FLAT_SIDO_TOKEN = "__FLAT_SIDO__"


def _detect_structure(rows: list) -> dict:
    """rows: list of (addr3, addr4, addr5, cnt) from grouped query."""
    total = sum(int(r[3]) for r in rows)
    if total == 0:
        return {
            "structure_type": "FLAT",
            "leaf_level": "addr3",
            "has_ri": False,
        }
    gu_like = sum(int(r[3]) for r in rows if r[0] and str(r[0]).strip().endswith("구"))
    has_a4 = sum(int(r[3]) for r in rows if r[1] and str(r[1]).strip())
    has_a5 = sum(int(r[3]) for r in rows if r[2] and str(r[2]).strip())
    gu_ratio = gu_like / total
    a4_ratio = has_a4 / total
    if gu_ratio >= 0.85 and a4_ratio >= 0.25:
        return {
            "structure_type": "GU",
            "leaf_level": "addr4",
            "has_ri": has_a5 > 0,
        }
    return {
        "structure_type": "FLAT",
        "leaf_level": "addr3",
        "has_ri": has_a5 > 0 or (has_a4 > 0 and not gu_like),
    }


def build_meta(engine, *, domain: str, table: str, asset_type: str | None) -> int:
    asset_clause = "AND asset_type = :asset_type" if asset_type else ""
    params: dict = {}
    if asset_type:
        params["asset_type"] = asset_type

    with engine.begin() as conn:
        if asset_type:
            conn.execute(
                text(
                    "DELETE FROM region_sigungu_meta WHERE asset_domain = :d AND asset_type = :t"
                ),
                {"d": domain, "t": asset_type},
            )
        else:
            conn.execute(
                text(
                    "DELETE FROM region_sigungu_meta WHERE asset_domain = :d AND asset_type IS NULL"
                ),
                {"d": domain},
            )

        groups = conn.execute(
            text(
                f"""
                SELECT addr1, addr2,
                       COUNT(*)::bigint AS tx_count,
                       COUNT(*) FILTER (
                           WHERE beopjungri_code IS NOT NULL
                             AND btrim(beopjungri_code::text) <> ''
                       )::bigint AS mapped_tx_count
                FROM {table}
                WHERE is_valid = true {asset_clause}
                GROUP BY addr1, addr2
                ORDER BY addr1, addr2
                """
            ),
            params,
        ).fetchall()

        n = 0
        for g in groups:
            addr1 = str(g.addr1 or "").strip()
            addr2_raw = str(g.addr2 or "").strip()
            if not addr1:
                continue
            is_flat_sido = not addr2_raw
            addr2_token = FLAT_SIDO_TOKEN if is_flat_sido else addr2_raw

            detail_params = {"a1": addr1}
            if is_flat_sido:
                detail_where = "addr1 = :a1 AND (addr2 IS NULL OR btrim(addr2::text) = '')"
            else:
                detail_where = "addr1 = :a1 AND addr2 = :a2"
                detail_params["a2"] = addr2_raw
            if asset_type:
                detail_where += " AND asset_type = :asset_type"
                detail_params["asset_type"] = asset_type

            detail = conn.execute(
                text(
                    f"""
                    SELECT addr3, addr4, addr5, COUNT(*)::int AS cnt
                    FROM {table}
                    WHERE is_valid = true AND {detail_where}
                    GROUP BY addr3, addr4, addr5
                    """
                ),
                detail_params,
            ).fetchall()

            struct = _detect_structure([(r.addr3, r.addr4, r.addr5, r.cnt) for r in detail])
            if is_flat_sido:
                struct["structure_type"] = "FLAT_SIDO"

            rc = conn.execute(
                text(
                    """
                    SELECT MIN(sido_code) AS sc, MIN(sigungu_code) AS gc,
                           MIN(sido_name) AS sn, MIN(sigungu_name) AS sgn
                    FROM region_codes
                    WHERE sido_name = :a1
                      AND (
                          (:flat AND (sigungu_name = '' OR sigungu_name IS NULL))
                          OR (NOT :flat AND sigungu_name = :a2)
                      )
                    """
                ),
                {"a1": addr1, "a2": addr2_raw, "flat": is_flat_sido},
            ).one()

            conn.execute(
                text(
                    """
                    INSERT INTO region_sigungu_meta (
                        asset_domain, asset_type, sido_code, sido_name,
                        sigungu_code, sigungu_name, addr2_token,
                        structure_type, leaf_level, has_ri,
                        tx_count, mapped_tx_count
                    ) VALUES (
                        :asset_domain, :asset_type, :sido_code, :sido_name,
                        :sigungu_code, :sigungu_name, :addr2_token,
                        :structure_type, :leaf_level, :has_ri,
                        :tx_count, :mapped_tx_count
                    )
                    """
                ),
                {
                    "asset_domain": domain,
                    "asset_type": asset_type,
                    "sido_code": (rc.sc or "00")[:2],
                    "sido_name": addr1,
                    "sigungu_code": rc.gc,
                    "sigungu_name": addr2_raw or addr1,
                    "addr2_token": addr2_token,
                    "structure_type": struct["structure_type"],
                    "leaf_level": struct["leaf_level"],
                    "has_ri": struct["has_ri"],
                    "tx_count": int(g.tx_count),
                    "mapped_tx_count": int(g.mapped_tx_count),
                },
            )
            n += 1
    log.info("%s %s: %d sigungu meta rows", domain, asset_type or "ALL", n)
    return n


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--built", action="store_true")
    p.add_argument("--collective", action="store_true")
    p.add_argument("--all", action="store_true")
    args = p.parse_args()
    if args.all or (not args.built and not args.collective):
        args.built = args.collective = True

    if args.built:
        if get_built_engine is None:
            log.warning("--built skipped: get_built_engine unavailable")
        else:
            eng = get_built_engine()
            with eng.begin() as conn:
                conn.execute(text(Path(REPO / "db" / "022_region_rebuild.sql").read_text(encoding="utf-8")))
            for at in (None, "commercial", "factory", "detached"):
                build_meta(eng, domain="built", table="built_transactions", asset_type=at)

    if args.collective:
        eng = get_collective_engine()
        meta_ddl = REPO / "db" / "022b_region_sigungu_meta.sql"
        with eng.begin() as conn:
            conn.execute(text(meta_ddl.read_text(encoding="utf-8")))
        for at in (None, "apartment", "officetel", "rowhouse", "presale"):
            build_meta(eng, domain="collective", table="collective_transactions", asset_type=at)


if __name__ == "__main__":
    main()
