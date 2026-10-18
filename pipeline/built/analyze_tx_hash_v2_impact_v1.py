"""Plan step 8 side study: what a transaction hash v2 would change. Separate from the incremental update.

The current key (import_refined._tx_hash) is sha256 over asset type, addr1–5, lot, contract year, price,
gross area and building use. Rows that agree on those fields share one key, and the ingest
(ON CONFLICT DO UPDATE) keeps only the last of them. This script re-reads the raw MOLIT CSVs with the
existing refine and record functions (read-only) and, for every group of rows sharing a key, asks which
extra fields would tell them apart:
  + contract month, + contract day, + other source fields (floor, building year, land area, road,
  road width, share, deal type), or nothing (rows identical in every refined field).
It also counts cancelled rows (dropped at refine) whose address/area/use reappear un-cancelled with a
different price — the cancel-and-re-report pattern behind rehashed orphans.
Counts only. No DB writes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from built.import_molit import RAW_BASE, _row_to_record  # noqa: E402
from built.molit_schemas import CANCEL_REGEX, RAW_BASE_DIRS, SCHEMAS  # noqa: E402
from built.refine_built import read_molit_csv, refine_molit_dataframe  # noqa: E402

EXTRA = ("floor", "building_age", "land_area", "road_name", "road_width_label", "partial_ownership_label", "deal_type")
SAME_DEAL = ("asset_type", "addr1", "addr2", "addr3", "addr4", "addr5", "lot_number", "contract_year", "gross_area",
             "building_use")


def refined_with_cancelled(path: Path, asset: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = read_molit_csv(path)
    schema = SCHEMAS[asset]
    if raw.shape[1] > schema.cancel_col:
        c = raw.iloc[:, schema.cancel_col].astype(str).str.strip().str.match(CANCEL_REGEX, na=False)
    else:
        c = pd.Series(False, index=raw.index)
    kept = refine_molit_dataframe(raw, asset)
    cancelled_raw = raw.loc[c].copy()
    if len(cancelled_raw) and raw.shape[1] > schema.cancel_col:
        # refine drops cancelled rows; refine them alone by blanking the cancel column
        cancelled_raw.iloc[:, schema.cancel_col] = ""
        cancelled = refine_molit_dataframe(cancelled_raw, asset)
    else:
        cancelled = pd.DataFrame()
    return kept, cancelled


def key_frame(df: pd.DataFrame) -> pd.DataFrame:
    recs = [_row_to_record(r) for _, r in df.iterrows()]
    out = pd.DataFrame(recs)
    out["_file"] = df["_file"].values
    out["contract_day"] = pd.to_datetime(out["contract_date"], errors="coerce").dt.day
    return out


def classify_groups(df: pd.DataFrame) -> dict:
    g = df.groupby("transaction_hash")
    size = g["transaction_hash"].transform("size")
    dup = df[size > 1].copy()
    out = {"rows": len(df), "keys": int(df["transaction_hash"].nunique()), "rows_lost_to_collision": int(len(df) - df["transaction_hash"].nunique())}
    kinds = Counter()
    rows_kinds = Counter()
    sizes = Counter()
    for _, grp in dup.groupby("transaction_hash"):
        n = len(grp)
        sizes[min(n, 5)] += 1
        if grp["contract_month"].nunique(dropna=False) == n:
            k = "split_by_month"
        elif grp[["contract_month", "contract_day"]].drop_duplicates().shape[0] == n:
            k = "split_by_month_day"
        elif grp[["contract_month", "contract_day", *EXTRA]].astype(str).drop_duplicates().shape[0] == n:
            k = "split_by_month_day_plus_source_fields"
        elif grp[["contract_month", "contract_day", *EXTRA]].astype(str).drop_duplicates().shape[0] > 1:
            k = "partly_split"
        else:
            k = ("identical_in_every_field_same_file" if grp["_file"].nunique() == 1
                 else "identical_in_every_field_across_files")
        kinds[k] += 1
        rows_kinds[k] += n
    out["collision_groups"] = int(sum(kinds.values()))
    out["group_size"] = {("5+" if k == 5 else str(k)): v for k, v in sorted(sizes.items())}
    out["groups_by_what_separates_them"] = dict(kinds)
    out["rows_by_what_separates_them"] = dict(rows_kinds)
    # what v2 (month) and v3 (month+day) would still collapse
    for name, cols in (("v2_month", ["transaction_hash", "contract_month"]),
                       ("v3_month_day", ["transaction_hash", "contract_month", "contract_day"]),
                       ("v3_plus_source_fields", ["transaction_hash", "contract_month", "contract_day", *EXTRA])):
        u = df[cols].astype(str).drop_duplicates().shape[0]
        out[f"rows_still_lost_{name}"] = int(len(df) - u)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    t0 = time.time()
    report = {"source": "raw/raw base MOLIT CSV (2021~2026 files), refine_built + import_molit._row_to_record",
              "note": "counts only; month/day/source fields are not in the current key", "by_asset": {}}
    allk, allc = [], []
    for asset, folder in RAW_BASE_DIRS.items():
        frames, cframes = [], []
        for p in sorted((RAW_BASE / folder).glob("*.csv")):
            k, c = refined_with_cancelled(p, asset)
            if len(k):
                frames.append(k.assign(_file=p.name))
            if len(c):
                cframes.append(c.assign(_file=p.name))
        kept = key_frame(pd.concat(frames, ignore_index=True))
        canc = key_frame(pd.concat(cframes, ignore_index=True)) if cframes else pd.DataFrame()
        r = classify_groups(kept)
        if len(canc):
            sd = kept[list(SAME_DEAL)].apply(lambda r: "|".join(map(str, r)), axis=1)
            cd = canc[list(SAME_DEAL)].apply(lambda r: "|".join(map(str, r)), axis=1)
            kept_price = kept.assign(_k=sd).groupby("_k")["price"].apply(set).to_dict()
            reappear = sum(1 for k, pr in zip(cd, canc["price"]) if k in kept_price)
            other_price = sum(1 for k, pr in zip(cd, canc["price"]) if k in kept_price and pr not in kept_price[k])
            same_key_alive = int(canc["transaction_hash"].isin(set(kept["transaction_hash"])).sum())
            r["cancelled"] = {"rows": len(canc), "same_deal_fields_reappear_uncancelled": int(reappear),
                              "reappear_with_other_price": int(other_price),
                              "same_current_key_alive": same_key_alive}
        report["by_asset"][asset] = r
        allk.append(kept)
        print(asset, json.dumps({k: r[k] for k in ("rows", "keys", "rows_lost_to_collision")}), flush=True)
    report["all"] = classify_groups(pd.concat(allk, ignore_index=True))
    report["seconds"] = round(time.time() - t0, 1)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=int), encoding="utf-8")
    print(json.dumps(report["all"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
