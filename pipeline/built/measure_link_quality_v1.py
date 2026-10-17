"""Plan step 4-C: link success and automatic cross-checks for composite transactions (2019+).

Two configurations, both from the same register caches:
  current  — AL_D003 land area, sido 12 matched on 2026-07 only (what the frozen rows used)
  proposed — land trait slim land area, sido 12 also on 2024-09/2025-07 through the Honam bridge

Automatic cross-checks are reported as agreement rates plus the rate at which a rival
candidate would also agree; they are not link accuracy. Accuracy comes from the blind
sample (`draw_link_sample_v1.py`). Per-row results go to a local file outside the repo;
the report holds counts only. No DB, ledger or enrichment writes.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.classify_frozen_replay_diffs import age_ok, road_ok  # noqa: E402
from built.db_utils import get_built_engine  # noqa: E402
from built.recover_address import CACHE, SNAPSHOTS, TX_SQL, load_land_ledger, to_i  # noqa: E402
from built.register_ledger import connect as ledger_connect  # noqa: E402
from built.replay_enrichment_from_ledger import records, run_matching  # noqa: E402
from built.replay_enrichment_land_supply import SLIM, slim_land  # noqa: E402
from built.replay_honam_bridge import BRIDGED, load_bridge  # noqa: E402

SIDOS = ("11", "12", "26", "27", "28", "30", "31", "36", "41", "43", "44", "47", "48", "50", "51", "52")
VERIFY = Path(r"C:\CH2\parcel_master\verification")
ROWS = VERIFY / "built_link_quality_v1_rows.pkl"
RESIDENTIAL = {"detached": "주거", "commercial": "비주거", "factory": "비주거"}

ALL_TX_SQL = """
SELECT substr(sigungu_code, 1, 2) AS sido, asset_type,
       count(*) AS all_tx,
       count(*) FILTER (WHERE NOT COALESCE(is_valid, false)) AS invalid,
       count(*) FILTER (WHERE COALESCE(is_valid, false) AND NOT (gross_area > 0)) AS no_gross,
       count(*) FILTER (WHERE COALESCE(is_valid, false) AND gross_area > 0
                        AND is_partial_ownership IS TRUE) AS partial
FROM built_transactions WHERE contract_year >= 2019 GROUP BY 1, 2
"""


def land_ok(tx_land, parcel_land) -> bool | None:
    if tx_land is None or parcel_land is None or math.isnan(tx_land) or math.isnan(parcel_land) or tx_land <= 0:
        return None
    return abs(tx_land - parcel_land) <= max(0.5, tx_land * 0.01)


def register_kind(db: sqlite3.Connection, pks: list[str]) -> dict[str, str]:
    """pk → 일반 / 집합 from the title register (code column 1), any version."""
    out: dict[str, set] = defaultdict(set)
    for i in range(0, len(pks), 900):
        chunk = pks[i:i + 900]
        q = f"SELECT pk, raw FROM title_version WHERE pk IN ({','.join('?' * len(chunk))})"
        for pk, raw in db.execute(q, chunk):
            code = raw.split(b"|", 2)[1].strip()
            out[pk].add({b"1": "일반", b"2": "집합"}.get(code, "기타"))
    return {pk: (next(iter(v)) if len(v) == 1 else "변경") for pk, v in out.items()}


def folder_keys(folder: Path, sido: str) -> set[tuple[str, int, int]]:
    keys = set()
    for snap in SNAPSHOTS:
        t = pd.read_csv(folder / f"title_{sido}_{snap}.csv", dtype=str, keep_default_na=False)
        for sg, bd, b, j in zip(t["sigungu_code"], t["bjd_code"], t["bun"], t["ji"]):
            bun = to_i(b)
            if bun is not None:
                keys.add((sg.strip() + bd.strip(), bun, to_i(j) or 0))
    return keys


def measure(sido: str, tx: pd.DataFrame, folder: Path, land: dict) -> pd.DataFrame:
    res, _ = run_matching(tx, folder, sido, land)
    snaps = {h: r["snapshots_matched"] for h, r in records(res).items()}
    res = res.copy()
    res["n_snapshots"] = res["transaction_hash"].map(lambda h: len(snaps.get(h) or []))
    res["slim_land"] = res["parcel"].map(
        lambda p: land.get(tuple(p.split("|")), math.nan) if isinstance(p, str) else math.nan
    )
    return res


def summarize(df: pd.DataFrame, keys: list[str]) -> dict:
    out = {}
    for k, g in df.groupby(keys, dropna=False):
        name = "|".join(str(x) for x in (k if isinstance(k, tuple) else (k,)))
        linked = g[g["tier"].notna()]
        row = {"eligible": len(g), "linked": len(linked), "link_rate": round(len(linked) / len(g), 4) if len(g) else None}
        row["fail"] = {str(f): int(n) for f, n in g.loc[g["tier"].isna(), "fail"].value_counts().items()}
        if len(linked):
            for axis, rival in (("road", "road_share_rival"), ("approve", "approve_share_rival"), ("land_a1", None)):
                col = linked[f"{axis}_ok"].dropna()
                obs = float(col.mean()) if len(col) else None
                d = {"checked": int(len(col)), "agree": int(col.sum()), "agree_rate": round(obs, 4) if obs is not None else None}
                if rival:
                    c = linked[rival].dropna()
                    if len(c):
                        cv = float(c.mean())
                        d["rival_same_rate"] = round(cv, 4)
                        d["rival_rows"] = int(len(c))
                        if obs is not None and cv < 1:
                            d["model_corrected"] = round((obs - cv) / (1 - cv), 4)
                row[axis] = d
            row["tier"] = {str(t): int(n) for t, n in linked["tier"].value_counts().items()}
            row["register"] = {str(t): int(n) for t, n in linked["register"].value_counts().items()}
            row["n_snapshots"] = {str(t): int(n) for t, n in linked["n_snapshots"].value_counts().items()}
            row["n_exact_ge2"] = int((linked["n_exact"] >= 2).sum())
        out[name] = row
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sidos", default=",".join(SIDOS))
    args = ap.parse_args()
    VERIFY.mkdir(parents=True, exist_ok=True)
    eng = get_built_engine()
    new_to_old = load_bridge()
    slim = sqlite3.connect(SLIM.resolve().as_uri() + "?mode=ro", uri=True)
    slim.execute("PRAGMA query_only=ON")
    slim.execute("PRAGMA cache_size=-1000000")
    ledger = ledger_connect()
    with eng.connect() as conn:
        population = pd.read_sql(text(ALL_TX_SQL), conn)
    frames = []
    current_linked = Counter()
    for sido in args.sidos.split(","):
        t0 = time.time()
        with eng.connect() as conn:
            tx = pd.read_sql(text(TX_SQL), conn, params={"sido_like": f"{sido}%", "min_year": 2019})
        al_d003 = load_land_ledger(sido, False)
        cur, _ = run_matching(tx, CACHE, sido, al_d003)
        for a, n in cur.loc[cur["tier"].notna(), "asset_type"].value_counts().items():
            current_linked[f"{sido}|{a}"] += int(n)
        translate = new_to_old if sido == "12" else None
        folder = BRIDGED if sido == "12" else CACHE
        land = slim_land(slim, folder_keys(folder, sido), translate)
        res = measure(sido, tx, folder, land)
        res["sido"] = sido
        res["residential"] = res["asset_type"].map(RESIDENTIAL)
        res["road_ok"] = [road_ok(a, b) for a, b in zip(res["tx_road"], res["reg_road"])]
        res["approve_ok"] = [age_ok(y, a, p) for y, a, p in zip(res["contract_year"], res["tx_age"], res["approve"])]
        res["land_a1_ok"] = [
            land_ok(l, s) if t == "A1" else None for t, l, s in zip(res["tier"], res["land_area"], res["slim_land"])
        ]
        kinds = register_kind(ledger, sorted(set(res["bldrgst_pk"].dropna())))
        res["register"] = [
            (kinds.get(pk, "원장없음") if isinstance(pk, str) else "동률") if isinstance(t, str) else None
            for pk, t in zip(res["bldrgst_pk"], res["tier"])
        ]
        keep = [
            "transaction_hash", "sido", "asset_type", "residential", "contract_year", "contract_month", "tier", "fail",
            "parcel", "bldrgst_pk", "register", "n_range", "n_exact", "n_snapshots", "snapshot_used", "tx_lot",
            "tx_road", "reg_road", "gross_area", "land_area", "slim_land", "tx_age", "approve", "road_ok",
            "approve_ok", "land_a1_ok", "road_share_rival", "road_share_range", "approve_share_rival",
        ]
        frames.append(res[keep])
        print(sido, len(tx), int(res["tier"].notna().sum()), f"{time.time() - t0:.0f}s", flush=True)
    df = pd.concat(frames, ignore_index=True)
    for col in ("road_ok", "approve_ok", "land_a1_ok"):
        df[col] = df[col].astype("boolean")
    df.to_pickle(ROWS)
    report = {
        "run_date": time.strftime("%Y-%m-%d"),
        "scope": "built_transactions contract_year>=2019",
        "config": "proposed: slim land area + Honam bridge (12); current kept as link counts only",
        "note": "agree_rate / model_corrected are automatic cross-checks, not link accuracy",
        "population": population.to_dict(orient="records"),
        "current_linked": dict(current_linked),
        "national": summarize(df.assign(all="전국"), ["all"]),
        "by_residential": summarize(df, ["residential"]),
        "by_asset_type": summarize(df, ["asset_type"]),
        "by_register": summarize(df[df["tier"].notna()], ["register"]),
        "by_residential_register": summarize(df[df["tier"].notna()], ["residential", "register"]),
        "by_sido": summarize(df, ["sido"]),
        "by_sido_residential": summarize(df, ["sido", "residential"]),
        "by_tier": summarize(df[df["tier"].notna()], ["tier"]),
        "by_contract_year": summarize(df, ["contract_year"]),
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=int), encoding="utf-8")
    print(json.dumps(report["national"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
