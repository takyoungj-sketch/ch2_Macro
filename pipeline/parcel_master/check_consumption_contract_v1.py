"""Plan step 7: read-only counts of the four result tables against the draft consumption contract.

Land, built, collective and rent keep their own tables. This script only reports which
contract fields each table can fill today and how many rows fall into each status.
SELECT only. Counts only, no keys.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from built.db_utils import get_built_engine  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from db_utils import get_engine  # noqa: E402
from rent.db_utils import get_rent_engine  # noqa: E402


def columns(conn, table: str) -> list[str]:
    rows = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t ORDER BY ordinal_position"
        ),
        {"t": table},
    )
    return [r[0] for r in rows]


def exists(conn, table: str) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{table}"}).scalar())


def grouped(conn, sql: str) -> dict:
    return {str(k): int(v) for k, v in conn.execute(text(sql))}


def scalar(conn, sql: str) -> int:
    return int(conn.execute(text(sql)).scalar() or 0)


def land() -> dict:
    with get_engine().connect() as c:
        t = "land_transaction_trait_link"
        if not exists(c, t):
            return {"table": t, "exists": False}
        tx_cols = columns(c, "land_transactions")
        return {
            "table": t,
            "exists": True,
            "columns": columns(c, t),
            "rows": scalar(c, f"SELECT count(1) FROM {t}"),
            "link_status": grouped(c, f"SELECT link_status, count(1) FROM {t} GROUP BY 1 ORDER BY 2 DESC"),
            "price_status": grouped(c, f"SELECT price_status, count(1) FROM {t} GROUP BY 1 ORDER BY 2 DESC"),
            "code_resolution": grouped(c, f"SELECT code_resolution, count(1) FROM {t} GROUP BY 1"),
            "rule_version": grouped(c, f"SELECT rule_version, count(1) FROM {t} GROUP BY 1"),
            "unverified_false": scalar(c, f"SELECT count(1) FROM {t} WHERE NOT unverified"),
            "trait_asof_null": scalar(c, f"SELECT count(1) FROM {t} WHERE trait_asof IS NULL"),
            "tx_share_like_columns": [x for x in tx_cols if any(k in x.lower() for k in ("share", "jibun", "scope"))],
        }


def built() -> dict:
    with get_built_engine().connect() as c:
        t = "built_transaction_enrichment"
        if not exists(c, t):
            return {"table": t, "exists": False}
        tx_cols = columns(c, "built_transactions")
        return {
            "table": t,
            "exists": True,
            "columns": columns(c, t),
            "rows": scalar(c, f"SELECT count(1) FROM {t}"),
            "match_tier": grouped(c, f"SELECT match_tier, count(1) FROM {t} GROUP BY 1"),
            "bldrgst_pk_null": scalar(c, f"SELECT count(1) FROM {t} WHERE bldrgst_pk IS NULL OR bldrgst_pk = ''"),
            "structure_raw_null": scalar(c, f"SELECT count(1) FROM {t} WHERE structure_raw IS NULL OR structure_raw = ''"),
            "max_floor_null": scalar(c, f"SELECT count(1) FROM {t} WHERE max_floor IS NULL"),
            "approve_year_null": scalar(c, f"SELECT count(1) FROM {t} WHERE approve_year IS NULL"),
            "zone_source": grouped(c, f"SELECT coalesce(zone_source, '(null)'), count(1) FROM {t} GROUP BY 1"),
            "zone_multi": scalar(c, f"SELECT count(1) FROM {t} WHERE zone_multi"),
            "land_area_source": grouped(c, f"SELECT coalesce(land_area_source, '(null)'), count(1) FROM {t} GROUP BY 1"),
            "n_snapshots": grouped(c, f"SELECT cardinality(snapshots_matched), count(1) FROM {t} GROUP BY 1 ORDER BY 1"),
            "coverage_scope": grouped(c, f"SELECT coverage_scope, count(1) FROM {t} GROUP BY 1"),
            "matched_cycle": grouped(c, f"SELECT matched_cycle, count(1) FROM {t} GROUP BY 1 ORDER BY 1"),
            "evidence_keys": grouped(
                c, f"SELECT k, count(1) FROM {t}, LATERAL jsonb_object_keys(coalesce(evidence, '{{}}'::jsonb)) k GROUP BY 1"
            ),
            "tx_share_like_columns": [x for x in tx_cols if any(k in x.lower() for k in ("share", "jibun", "scope"))],
        }


def collective() -> dict:
    with get_collective_engine().connect() as c:
        out = {}
        a = "collective_building_attributes"
        if exists(c, a):
            snap = c.execute(text(f"SELECT max(snapshot_ym) FROM {a}")).scalar()
            out[a] = {
                "latest_snapshot": snap,
                "rows_latest": scalar(c, f"SELECT count(1) FROM {a} WHERE snapshot_ym = '{snap}'"),
                "match_tier": grouped(
                    c, f"SELECT asset_type || '|' || match_tier, count(1) FROM {a} WHERE snapshot_ym = '{snap}' GROUP BY 1 ORDER BY 1"
                ),
            }
        p = "collective_building_assessed_land_price"
        if exists(c, p):
            out[p] = {
                "rows": scalar(c, f"SELECT count(1) FROM {p}"),
                "source": grouped(c, f"SELECT source, count(1) FROM {p} GROUP BY 1"),
                "year": grouped(c, f"SELECT assessed_land_price_year, count(1) FROM {p} GROUP BY 1 ORDER BY 1"),
            }
        if exists(c, "collective_building_stats"):
            out["collective_building_stats_keys"] = grouped(
                c, "SELECT asset_type, count(DISTINCT building_key) FROM collective_building_stats GROUP BY 1"
            )
        return out


def rent() -> dict:
    with get_rent_engine().connect() as c:
        t = "rent_sale_building_map"
        if not exists(c, t):
            return {"table": t, "exists": False}
        return {
            "table": t,
            "exists": True,
            "rows": scalar(c, f"SELECT count(1) FROM {t}"),
            "tier": grouped(c, f"SELECT asset_type || '|' || tier, count(1) FROM {t} GROUP BY 1 ORDER BY 1"),
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = {"step": "7", "read_only": True, "land": land(), "built": built(), "collective": collective(), "rent": rent()}
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
