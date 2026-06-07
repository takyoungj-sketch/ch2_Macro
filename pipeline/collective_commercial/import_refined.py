"""collective_commercial ingest — GUKTO 정제 → commercial_clusters + transactions."""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

_ROOT = Path(__file__).resolve().parent.parent / "collective"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from db_utils import get_collective_engine  # noqa: E402

from cluster_keys import (  # noqa: E402
    area_bucket_label,
    confidence_tier,
    derive_building_year,
    make_road_cluster_key,
    make_road_display_label,
)
from gukto_raw_factory import load_collective_factory_raw  # noqa: E402
from gukto_raw_shop import load_collective_shop_raw  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
DDL = REPO / "db" / "019_collective_commercial.sql"
DDL_ROAD_WIDTH = REPO / "db" / "020_collective_commercial_road_width.sql"

UPSERT_CLUSTER = text(
    """
    INSERT INTO commercial_clusters (
        cluster_key, asset_type, display_label, resolution_mode,
        addr1, addr2, addr3, addr4, road_name, zone_type, building_use,
        building_year, area_bucket_label, n_total, cohesion_score, confidence_tier
    ) VALUES (
        :cluster_key, :asset_type, :display_label, :resolution_mode,
        :addr1, :addr2, :addr3, :addr4, :road_name, :zone_type, :building_use,
        :building_year, :area_bucket_label, :n_total, :cohesion_score, :confidence_tier
    )
    ON CONFLICT (cluster_key) DO UPDATE SET
        n_total = EXCLUDED.n_total,
        cohesion_score = EXCLUDED.cohesion_score,
        confidence_tier = EXCLUDED.confidence_tier,
        updated_at = NOW()
    RETURNING id, cluster_key
    """
)

INSERT_TX = text(
    """
    INSERT INTO collective_commercial_transactions (
        transaction_hash, cluster_id, asset_type, cluster_key, resolution_mode,
        addr1, addr2, addr3, addr4, addr5, lot_number, road_name,
        zone_type, building_use, building_year, area_bucket_label,
        contract_year, contract_month, contract_date,
        price, gross_area, land_area, unit_price, floor, road_code, road_width_label, building_age
    ) VALUES (
        :transaction_hash, :cluster_id, :asset_type, :cluster_key, :resolution_mode,
        :addr1, :addr2, :addr3, :addr4, :addr5, :lot_number, :road_name,
        :zone_type, :building_use, :building_year, :area_bucket_label,
        :contract_year, :contract_month, :contract_date,
        :price, :gross_area, :land_area, :unit_price, :floor, :road_code, :road_width_label, :building_age
    )
    """
)


def _null(val):
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, str) and val.strip().lower() in ("", "nan", "none"):
        return None
    return val


def _int_small(val) -> int | None:
    val = _null(val)
    if val is None:
        return None
    try:
        n = int(round(float(val)))
        if -32768 <= n <= 32767:
            return n
    except (TypeError, ValueError):
        pass
    return None


def _str(val, width: int | None = None) -> str | None:
    val = _null(val)
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    return s[:width] if width else s


def apply_ddl(engine) -> None:
    for path in (DDL, DDL_ROAD_WIDTH):
        if not path.is_file():
            continue
        sql = path.read_text(encoding="utf-8")
        with engine.begin() as conn:
            conn.execute(text(sql))
        log.info("DDL applied: %s", path.name)


def enrich_commercial_road(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    derived_by = [
        derive_building_year(cy, age)
        for cy, age in zip(out["contract_year"], out.get("building_age", pd.Series([None] * len(out))))
    ]
    out["building_year"] = [
        _int_small(b) if _int_small(b) is not None else _int_small(d)
        for b, d in zip(out["building_year"], derived_by)
    ]
    out["area_bucket_label"] = [
        area_bucket_label(at, ga) for at, ga in zip(out["asset_type"], out["gross_area"])
    ]
    keys, labels = [], []
    for row in out.itertuples(index=False):
        ck = make_road_cluster_key(
            asset_type=row.asset_type,
            addr1=getattr(row, "addr1", None),
            addr2=getattr(row, "addr2", None),
            addr3=getattr(row, "addr3", None),
            addr4=getattr(row, "addr4", None),
            road_name=getattr(row, "road_name", None),
        )
        keys.append(ck)
        labels.append(
            make_road_display_label(
                road_name=getattr(row, "road_name", None),
                addr3=getattr(row, "addr3", None),
                addr4=getattr(row, "addr4", None),
            )
        )
    out["cluster_key"] = keys
    out["display_label"] = labels
    out["resolution_mode"] = "road"
    return out


enrich_shop = enrich_commercial_road
enrich_factory = enrich_commercial_road


def _cluster_agg(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ck, g in df.groupby("cluster_key", sort=False):
        ga = g["gross_area"].astype(float)
        cv = float(ga.std() / ga.mean()) if len(g) > 1 and ga.mean() > 0 else None
        n = len(g)
        first = g.iloc[0]
        rows.append(
            {
                "cluster_key": ck,
                "asset_type": first["asset_type"],
                "display_label": first["display_label"],
                "addr1": _str(first.get("addr1"), 30),
                "addr2": _str(first.get("addr2"), 30),
                "addr3": _str(first.get("addr3"), 30),
                "addr4": _str(first.get("addr4"), 30),
                "road_name": _str(first.get("road_name"), 120),
                "zone_type": _str(first.get("zone_type"), 40),
                "building_use": _str(first.get("building_use"), 40),
                "building_year": _int_small(first.get("building_year")),
                "area_bucket_label": first["area_bucket_label"],
                "resolution_mode": first.get("resolution_mode", "cluster"),
                "n_total": n,
                "cohesion_score": round(1 - min(cv or 0, 1), 2) if cv is not None else None,
                "confidence_tier": confidence_tier(n, area_cv=cv),
            }
        )
    return pd.DataFrame(rows)


def upsert_clusters(engine, cluster_df: pd.DataFrame) -> dict[str, int]:
    mapping: dict[str, int] = {}
    with engine.begin() as conn:
        for row in cluster_df.itertuples(index=False):
            payload = {
                "cluster_key": row.cluster_key,
                "asset_type": row.asset_type,
                "display_label": row.display_label,
                "addr1": _str(row.addr1, 30),
                "addr2": _str(row.addr2, 30),
                "addr3": _str(row.addr3, 30),
                "addr4": _str(row.addr4, 30),
                "road_name": _str(row.road_name, 120),
                "zone_type": _str(row.zone_type, 40),
                "building_use": _str(row.building_use, 40),
                "building_year": _int_small(row.building_year),
                "area_bucket_label": row.area_bucket_label,
                "resolution_mode": row.resolution_mode,
                "n_total": int(row.n_total),
                "cohesion_score": _null(row.cohesion_score),
                "confidence_tier": row.confidence_tier,
            }
            r = conn.execute(UPSERT_CLUSTER, payload).fetchone()
            mapping[r.cluster_key] = int(r.id)
    return mapping


def insert_transactions(engine, df: pd.DataFrame, id_map: dict[str, int], *, source: str) -> int:
    n = 0
    batch: list[dict] = []
    with engine.begin() as conn:
        for i, row in enumerate(df.itertuples(index=False)):
            d = row._asdict()
            ck = d["cluster_key"]
            th = hashlib.sha256(
                f"{d['asset_type']}|{source}|{i}|{d['price']}|{d['gross_area']}|{d.get('contract_year')}".encode(
                    "utf-8"
                )
            ).hexdigest()
            rec = {
                "transaction_hash": th,
                "cluster_id": id_map[ck],
                "asset_type": d["asset_type"],
                "cluster_key": ck,
                "resolution_mode": d.get("resolution_mode", "cluster"),
                "addr1": _str(d.get("addr1"), 30),
                "addr2": _str(d.get("addr2"), 30),
                "addr3": _str(d.get("addr3"), 30),
                "addr4": _str(d.get("addr4"), 30),
                "addr5": _str(d.get("addr5"), 30),
                "lot_number": _str(d.get("lot_number"), 64),
                "road_name": _str(d.get("road_name"), 120),
                "zone_type": _str(d.get("zone_type"), 40),
                "building_use": _str(d.get("building_use"), 40),
                "building_year": _int_small(d.get("building_year")),
                "area_bucket_label": d["area_bucket_label"],
                "contract_year": _int_small(d.get("contract_year")),
                "contract_month": _int_small(d.get("contract_month")),
                "contract_date": _null(d.get("contract_date")),
                "price": float(d["price"]),
                "gross_area": float(d["gross_area"]),
                "land_area": _null(d.get("land_area")),
                "unit_price": _null(d.get("unit_price")),
                "floor": _null(d.get("floor")),
                "road_code": _null(d.get("road_code")),
                "road_width_label": _str(d.get("road_width_label"), 32),
                "building_age": _null(d.get("building_age")),
            }
            batch.append(rec)
            if len(batch) >= 2000:
                conn.execute(INSERT_TX, batch)
                n += len(batch)
                batch.clear()
        if batch:
            conn.execute(INSERT_TX, batch)
            n += len(batch)
    return n


def purge_asset_type(engine, asset_type: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM collective_commercial_transactions WHERE asset_type = :at"),
            {"at": asset_type},
        )
        conn.execute(
            text("DELETE FROM commercial_clusters WHERE asset_type = :at"),
            {"at": asset_type},
        )
    log.info("purged asset_type=%s", asset_type)


def ingest_asset(engine, loader, *, source: str, enrich_fn, truncate: bool = False, purge: bool = False) -> tuple[int, int]:
    if purge:
        asset_type = "collective_shop" if "shop" in source else "collective_factory"
        purge_asset_type(engine, asset_type)
    df = enrich_fn(loader())
    if df.empty:
        log.warning("no rows for %s", source)
        return 0, 0
    clusters = _cluster_agg(df)
    if truncate:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE collective_commercial_transactions, commercial_clusters RESTART IDENTITY CASCADE"))
    id_map = upsert_clusters(engine, clusters)
    tx_n = insert_transactions(engine, df, id_map, source=source)
    log.info("%s: %d transactions, %d clusters", source, tx_n, len(clusters))
    return tx_n, len(clusters)


def main() -> None:
    p = argparse.ArgumentParser(description="GUKTO 집합상가·집합공장 원본 xlsx 적재 (도로 cluster)")
    p.add_argument("--shop-only", action="store_true")
    p.add_argument("--factory-only", action="store_true")
    p.add_argument("--truncate", action="store_true", help="기존 commercial 테이블 비우고 재적재")
    p.add_argument("--skip-ddl", action="store_true")
    args = p.parse_args()

    engine = get_collective_engine()
    if not args.skip_ddl:
        apply_ddl(engine)
    elif DDL_ROAD_WIDTH.is_file():
        with engine.begin() as conn:
            conn.execute(text(DDL_ROAD_WIDTH.read_text(encoding="utf-8")))
        log.info("migration applied: %s", DDL_ROAD_WIDTH.name)

    do_shop = not args.factory_only
    do_factory = not args.shop_only

    total_tx = 0
    if do_shop:
        n, _ = ingest_asset(
            engine,
            load_collective_shop_raw,
            source="gukto_shop_raw",
            enrich_fn=enrich_commercial_road,
            truncate=args.truncate,
            purge=True,
        )
        total_tx += n
        args.truncate = False
    if do_factory:
        n, _ = ingest_asset(
            engine,
            load_collective_factory_raw,
            source="gukto_factory_raw",
            enrich_fn=enrich_commercial_road,
            truncate=False,
            purge=True,
        )
        total_tx += n

    with engine.connect() as conn:
        shop = conn.execute(
            text("SELECT COUNT(*) FROM collective_commercial_transactions WHERE asset_type='collective_shop'")
        ).scalar()
        fac = conn.execute(
            text("SELECT COUNT(*) FROM collective_commercial_transactions WHERE asset_type='collective_factory'")
        ).scalar()
        cl = conn.execute(text("SELECT COUNT(*) FROM commercial_clusters")).scalar()
    log.info("DONE total_tx=%d shop=%s factory=%s clusters=%s", total_tx, shop, fac, cl)


if __name__ == "__main__":
    main()
