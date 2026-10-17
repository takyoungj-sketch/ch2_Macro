"""Zone labels for frozen composite enrichment rows: AL_D155 (latest) vs land trait slim at contract year.

For 상가/공장 the transaction itself carries a zone label, which serves as an independent check
for both supplies. Read-only on the DB and the slim. Writes counts only.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.db_utils import get_built_engine  # noqa: E402
from built.recover_address import zfamily, zkey  # noqa: E402

SLIM = Path(r"C:\CH2\parcel_master\land_trait_slim_v1.sqlite")
SQL = """
SELECT e.recovered_lot, e.zone_labels, t.contract_year, t.asset_type, t.zone_type
FROM built_transaction_enrichment e
JOIN built_transactions t ON t.transaction_hash = e.transaction_hash
WHERE t.contract_year >= 2019
"""


def slim_zone(slim: sqlite3.Connection, pnu: int, year: int, labels: dict[str, str]) -> tuple[str, str]:
    rows = slim.execute(
        "SELECT price_year, asof_mask, zone1_code, zone2_code FROM observation WHERE pnu=?", (pnu,)
    ).fetchall()
    for y, how in ((year, "same_year"), (year - 1, "previous_year")):
        cand = [r for r in rows if r[0] == str(y)]
        if cand:
            r = max(cand, key=lambda r: r[1].bit_length())
            return labels.get(r[2], ""), how
    return "", "no_year" if rows else "no_parcel"


def pnu_of(lot: str) -> int | None:
    try:
        bjd10, tail = lot.split("|", 1)
        bun, _, ji = tail.partition("-")
        value = int(f"{bjd10}1{int(bun):04d}{int(ji or 0):04d}")
    except ValueError:
        return None
    return value if len(bjd10) == 10 and value < 2**63 else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    with get_built_engine().connect() as conn:
        df = pd.read_sql(text(SQL), conn)
    slim = sqlite3.connect(SLIM.resolve().as_uri() + "?mode=ro", uri=True)
    slim.execute("PRAGMA query_only=ON")
    labels = dict(slim.execute("SELECT code, label FROM code_dictionary WHERE field='zone1' AND is_standard=1"))
    total = Counter()
    by_type: dict[str, Counter] = defaultdict(Counter)
    by_sido: dict[str, Counter] = defaultdict(Counter)
    for lot, zl, year, asset, tx_zone in df.itertuples(index=False):
        c = by_type[asset]
        s = by_sido[str(lot)[:2]]
        pnu = pnu_of(str(lot))
        slim_label, how = slim_zone(slim, pnu, int(year), labels) if pnu else ("", "bad_lot")
        al = [x for x in (zl or []) if x]
        sk = zkey(slim_label)
        for bucket in (total, c, s):
            bucket["rows"] += 1
            bucket[f"slim_{how}"] += 1
            if not sk:
                bucket["slim_empty"] += 1
            if not al:
                bucket["al_d155_empty"] += 1
                if sk:
                    bucket["slim_fills_empty"] += 1
            if sk and al:
                bucket["both"] += 1
                if sk == zkey(al[0]):
                    bucket["slim_eq_al_primary"] += 1
                if sk in {zkey(x) for x in al}:
                    bucket["slim_in_al_labels"] += 1
                if zfamily(sk) == zfamily(al[0]):
                    bucket["same_family_primary"] += 1
            src = zkey(tx_zone) if isinstance(tx_zone, str) else ""
            if src:
                bucket["tx_has_zone"] += 1
                if sk:
                    bucket["tx_vs_slim_n"] += 1
                    bucket["tx_eq_slim"] += int(sk == src)
                if al:
                    bucket["tx_vs_al_n"] += 1
                    bucket["tx_eq_al_primary"] += int(zkey(al[0]) == src)
    report = {
        "rows": len(df),
        "total": dict(total),
        "by_asset_type": {k: dict(v) for k, v in by_type.items()},
        "by_sido": {k: dict(v) for k, v in sorted(by_sido.items())},
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["total"], ensure_ascii=False), flush=True)
    for k, v in report["by_asset_type"].items():
        print(k, json.dumps(v, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
