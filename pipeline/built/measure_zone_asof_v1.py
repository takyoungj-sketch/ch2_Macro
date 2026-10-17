"""Plan step 4-D: transaction-time zone vs latest zone for linked composite transactions.

Land trait rows have a base date (price_year, price_month = 01 or 07). For a contract in
(Y, M) the zone at transaction time is classified as:
  observed        — a base in year Y on or before the contract month
  estimated       — no such base, but the nearest bases before (Y-1) and after (later in Y or Y+1)
                    give the same zone
  adjacent_before — only Y-1 (value observed before the contract; zone may have changed since)
  adjacent_after  — only a base after the contract (later in Y or Y+1); post-contract value
  unknown         — no base within a year, or bases before and after disagree, or the base
                    holds two different zones
The base year actually used is kept. A base year is not the date a zone changed.

Input: linked rows from `measure_link_quality_v1` (local). Read-only; counts only in the repo.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from sqlalchemy import bindparam, text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.db_utils import get_built_engine  # noqa: E402
from built.measure_link_quality_v1 import ROWS, VERIFY  # noqa: E402
from built.recover_address import zfamily, zkey  # noqa: E402
from built.replay_enrichment_land_supply import SLIM  # noqa: E402
from built.replay_honam_bridge import load_bridge  # noqa: E402

OUT_ROWS = VERIFY / "built_zone_asof_v1_rows.pkl"
EMPTY_LABELS = {"", '""', "지정되지않음"}
# Older land trait years keep the old province code (LAND_CODE_HISTORY_LAYER V1 prefix swaps).
# Other code changes (e.g. 부천·화성 일반구, 인천 개편, 군위) have no approved bridge and stay unknown.
OLD_SIDO_PREFIX = {"51": "42", "52": "45"}
TX_SQL = """
SELECT t.transaction_hash, t.zone_type, e.zone_labels
FROM built_transactions t LEFT JOIN built_transaction_enrichment e USING (transaction_hash)
WHERE t.transaction_hash IN :hashes
"""


def pnus(parcel: str, bridge: dict[str, str]) -> list[int]:
    bjd, lot = parcel.split("|")
    bun, _, ji = lot.partition("-")
    if not bun.isdigit() or int(bun) > 9999 or int(ji or 0) > 9999:
        return []
    tail = f"1{int(bun):04d}{int(ji or 0):04d}"
    codes = [bridge.get(bjd)] if bjd.startswith("12") else [bjd]
    if bjd[:2] in OLD_SIDO_PREFIX:
        codes.append(OLD_SIDO_PREFIX[bjd[:2]] + bjd[2:])
    return [int(c + tail) for c in codes if c]


def bases(slim: sqlite3.Connection, keys: list[int]) -> dict[tuple[int, int], set[tuple[str, str]]]:
    out: dict[tuple[int, int], set] = defaultdict(set)
    for pnu in keys:
        for y, m, z1, z2 in slim.execute(
            "SELECT price_year, price_month, zone1_code, zone2_code FROM observation WHERE pnu=?", (pnu,)
        ):
            out[(int(y), int(m))].add((z1, z2))
    return out


def classify(b: dict, year: int, month: int) -> dict:
    if not b:
        return {"status": "unknown", "why": "no_parcel"}
    month = month or 12

    def one(key):
        vals = b[key]
        return None if len({v[0] for v in vals}) != 1 else next(iter(vals))

    same = sorted(k for k in b if k[0] == year and k[1] <= month)
    if same:
        v = one(same[-1])
        if v is None:
            return {"status": "unknown", "why": "base_has_two_zones", "obs": [same[-1][0]]}
        return {"status": "observed", "zone": v[0], "zone2": v[1], "obs": [same[-1][0]]}
    before = sorted(k for k in b if k[0] == year - 1)
    after = sorted(k for k in b if (k[0] == year and k[1] > month) or k[0] == year + 1)
    vb = one(before[-1]) if before else None
    va = one(after[0]) if after else None
    if before and after:
        if vb and va and vb[0] == va[0]:
            return {"status": "estimated", "zone": vb[0], "zone2": vb[1], "obs": [before[-1][0], after[0][0]]}
        return {"status": "unknown", "why": "changed_around_contract", "obs": [before[-1][0], after[0][0]]}
    if before and vb:
        return {"status": "adjacent_before", "zone": vb[0], "zone2": vb[1], "obs": [before[-1][0]]}
    if after and va:
        return {"status": "adjacent_after", "zone": va[0], "zone2": va[1], "obs": [after[0][0]]}
    if min(b)[0] > year + 1:
        return {"status": "unknown", "why": "code_newer_than_contract"}
    return {"status": "unknown", "why": "no_base_within_a_year"}


def latest(b: dict) -> tuple[int, str] | None:
    if not b:
        return None
    k = max(b)
    zones = {v[0] for v in b[k]}
    return (k[0], next(iter(zones))) if len(zones) == 1 else (k[0], "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    df = pd.read_pickle(ROWS)
    df = df[df["tier"].notna()].reset_index(drop=True)
    bridge = load_bridge()
    slim = sqlite3.connect(SLIM.resolve().as_uri() + "?mode=ro", uri=True)
    slim.execute("PRAGMA query_only=ON")
    slim.execute("PRAGMA cache_size=-1000000")
    labels = {
        c: ("" if lb in EMPTY_LABELS else lb)
        for c, lb in slim.execute("SELECT code, label FROM code_dictionary WHERE field='zone1' AND is_standard=1")
    }
    labels2 = {
        c: ("" if lb in EMPTY_LABELS else lb)
        for c, lb in slim.execute("SELECT code, label FROM code_dictionary WHERE field='zone2' AND is_standard=1")
    }
    q = text(TX_SQL).bindparams(bindparam("hashes", expanding=True))
    side = []
    with get_built_engine().connect() as conn:
        hashes = df["transaction_hash"].tolist()
        for i in range(0, len(hashes), 20000):
            side.append(pd.read_sql(q, conn, params={"hashes": hashes[i:i + 20000]}))
    side = pd.concat(side).drop_duplicates("transaction_hash").set_index("transaction_hash")

    total = Counter()
    groups: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    rows = []
    for r in df.itertuples(index=False):
        b = bases(slim, pnus(r.parcel, bridge))
        c = classify(b, int(r.contract_year), int(r.contract_month or 0))
        lt = latest(b)
        label = labels.get(c["zone"], "") if c.get("zone") else ""
        latest_label = labels.get(lt[1], "") if lt and lt[1] else ""
        if c["status"] not in ("unknown",) and not label:
            c = {"status": "unknown", "why": "zone_code_empty", "obs": c["obs"]}
        tx_zone = side.at[r.transaction_hash, "zone_type"] if r.transaction_hash in side.index else None
        al = side.at[r.transaction_hash, "zone_labels"] if r.transaction_hash in side.index else None
        al = [x for x in (al or []) if x]
        tags = [f"status:{c['status']}"]
        if c["status"] == "unknown":
            tags.append(f"unknown:{c['why']}")
        if label:
            obs_gap = int(r.contract_year) - c["obs"][0]
            tags.append(f"obs_year_minus_contract:{-obs_gap}")
            if labels2.get(c.get("zone2") or "", ""):
                tags.append("zone2:present")
            if latest_label:
                if zkey(label) == zkey(latest_label):
                    tags.append("vs_latest:same")
                elif zfamily(label) == zfamily(latest_label):
                    tags.append("vs_latest:changed_same_family")
                else:
                    tags.append("vs_latest:changed_family")
            if al:
                tags.append("vs_al_d155_primary:" + ("same" if zkey(label) == zkey(al[0]) else "differs"))
                tags.append("vs_al_d155_any:" + ("in" if zkey(label) in {zkey(x) for x in al} else "out"))
            src = zkey(tx_zone) if isinstance(tx_zone, str) else ""
            if src:
                tags.append("vs_tx_zone:" + ("same" if zkey(label) == src else "differs"))
                if latest_label:
                    tags.append("latest_vs_tx_zone:" + ("same" if zkey(latest_label) == src else "differs"))
        for key in ("all", f"asset:{r.asset_type}", f"sido:{r.sido}", f"year:{r.contract_year}",
                    f"status:{c['status']}"):
            for t in tags:
                groups[key][t.split(":")[0]][t.split(":", 1)[1]] += 1
        total[c["status"]] += 1
        rows.append((r.transaction_hash, c["status"], c.get("why"), c.get("zone"), (c.get("obs") or [None])[0],
                     (c.get("obs") or [None, None])[-1], lt[0] if lt else None, lt[1] if lt else None))
    pd.DataFrame(rows, columns=["transaction_hash", "status", "why", "zone1_code", "obs_year_first",
                                "obs_year_last", "latest_year", "latest_zone1_code"]).to_pickle(OUT_ROWS)
    report = {
        "rows": int(len(df)),
        "note": "base year = land trait 기준연도, not the date a zone changed",
        "groups": {k: {kk: dict(vv) for kk, vv in v.items()} for k, v in groups.items()},
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["groups"]["all"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
