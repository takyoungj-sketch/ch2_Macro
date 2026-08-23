#!/usr/bin/env python3
"""기존 built_transactions 에 지분 플래그 백필 (D-049). 해시는 바꾸지 않는다."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from built.db_utils import get_built_engine  # noqa: E402
from built.import_molit import (  # noqa: E402
    _row_to_record,
    ensure_schema,
    list_csv_files,
)
from built.molit_schemas import BuiltAssetType  # noqa: E402
from built.refine_built import read_molit_csv, refine_molit_dataframe  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

UPDATE_SQL = text(
    """
    UPDATE built_transactions
    SET is_partial_ownership = :is_partial_ownership,
        partial_ownership_label = :partial_ownership_label
    WHERE transaction_hash = :transaction_hash
    """
)


KEY_UPDATE_SQL = text(
    """
    UPDATE built_transactions
    SET is_partial_ownership = TRUE,
        partial_ownership_label = COALESCE(:partial_ownership_label, '지분')
    WHERE asset_type = :asset_type
      AND lot_number IS NOT DISTINCT FROM :lot_number
      AND contract_date IS NOT DISTINCT FROM :contract_date
      AND price = :price
      AND round(gross_area::numeric, 2) = round((:gross_area)::numeric, 2)
    """
)


def _collect_share_records(asset_type: BuiltAssetType) -> tuple[list[dict], list[dict]]:
    hashes: list[dict] = []
    keys: list[dict] = []
    for path in list_csv_files(asset_type):
        raw = read_molit_csv(path)
        if raw.shape[1] <= 16:
            continue
        share_mask = raw.iloc[:, 16].astype(str).str.contains("지분", na=False)
        types = raw.iloc[:, 2].astype(str).str.strip()
        keep = share_mask & (types == "일반")
        if not keep.any():
            continue
        df = refine_molit_dataframe(raw.loc[keep].copy(), asset_type)
        if df.empty:
            continue
        share = df.loc[df["is_partial_ownership"].astype(bool)]
        for _, row in share.iterrows():
            rec = _row_to_record(row)
            hashes.append(
                {
                    "transaction_hash": rec["transaction_hash"],
                    "is_partial_ownership": True,
                    "partial_ownership_label": rec.get("partial_ownership_label"),
                }
            )
            keys.append(
                {
                    "asset_type": rec["asset_type"],
                    "lot_number": rec.get("lot_number"),
                    "contract_date": rec.get("contract_date"),
                    "price": rec.get("price"),
                    "gross_area": rec.get("gross_area"),
                    "partial_ownership_label": rec.get("partial_ownership_label") or "지분",
                }
            )
        log.info("%s %s share_rows=%s", asset_type, path.name, len(share))
    return hashes, keys


def main() -> None:
    engine = get_built_engine()
    ensure_schema(engine)
    key_rows: list[dict] = []
    for asset in ("commercial", "factory"):
        _hashes, keys = _collect_share_records(asset)
        key_rows.extend(keys)
    keys_df = pd.DataFrame(key_rows)
    log.info("share key rows %s", len(keys_df))
    keys_df.to_sql("tmp_built_share_keys", con=engine, index=False, if_exists="replace")
    log.info("tmp table written")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE built_transactions
                SET is_partial_ownership = FALSE,
                    partial_ownership_label = NULL
                """
            )
        )
        result = conn.execute(
            text(
                """
                UPDATE built_transactions t
                SET is_partial_ownership = TRUE,
                    partial_ownership_label = COALESCE(s.partial_ownership_label, '지분')
                FROM tmp_built_share_keys s
                WHERE t.asset_type = s.asset_type
                  AND t.lot_number IS NOT DISTINCT FROM s.lot_number
                  AND t.contract_date IS NOT DISTINCT FROM s.contract_date::date
                  AND t.price = s.price
                  AND round(t.gross_area::numeric, 2) = round(s.gross_area::numeric, 2)
                """
            )
        )
        log.info("join updated %s", result.rowcount)
        conn.execute(text("DROP TABLE IF EXISTS tmp_built_share_keys"))
        stats = conn.execute(
            text(
                """
                SELECT asset_type,
                       COUNT(*) FILTER (WHERE is_valid) AS n,
                       COUNT(*) FILTER (WHERE is_valid AND is_partial_ownership) AS share_n
                FROM built_transactions
                GROUP BY asset_type
                ORDER BY 1
                """
            )
        ).mappings().all()
    log.info("backfill complete")
    for row in stats:
        n = int(row["n"] or 0)
        s = int(row["share_n"] or 0)
        pct = (100.0 * s / n) if n else 0.0
        log.info("ledger %s n=%s share=%s (%.1f%%)", row["asset_type"], n, s, pct)


if __name__ == "__main__":
    main()
