"""Status-quo scope for the composite switch: engine V2 national version vs the product enrichment table.

Per transaction:
  same          both linked, same parcel (bjd|lot)
  same_bridge   sido 12: parcels differ only by the honam bridge (old ↔ new 법정동 code)
  changed       both linked, different parcel
  dropped       enrichment has a row, the engine does not link it (switching would remove the value)
  new           engine links it, the enrichment has no row
Then a blind sample of the not-status-quo links (new + changed) in the 4-C worksheet format, excluding the
transactions of the 219 sample. Read only (product DB under SET TRANSACTION READ ONLY, version SQLite mode=ro).
Per-row files and the answer key stay outside the repo; the report has counts only.
"""

from __future__ import annotations

import argparse
import json
import random
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
from built.draw_link_sample_v1 import ASSET, OUT as SAMPLE_DIR, WORKSHEET_COLS, hint_fields, tx_details  # noqa: E402
from built.link_engine_v1 import ledger_universe  # noqa: E402
from built.replay_honam_bridge import load_bridge  # noqa: E402

VERSION = Path(r"C:\CH2\parcel_master\versions_test\built\N_full_ENGINE_V2.sqlite")
VERIFY = Path(r"C:\CH2\parcel_master\verification")
SEED = 20261019


def same_via_bridge(a: str, b: str, bridge: dict) -> bool:
    ba, la = a.split("|", 1)
    bb, lb = b.split("|", 1)
    return la == lb and (bridge.get(ba) == bb or bridge.get(bb) == ba)


def allocate(sizes: dict, n: int) -> dict:
    """Proportional allocation, at least 1 per non-empty stratum (largest remainder)."""
    total = sum(sizes.values())
    alloc = {s: max(1, int(n * c / total)) for s, c in sizes.items()}
    while sum(alloc.values()) < n:
        s = max(alloc, key=lambda s: n * sizes[s] / total - alloc[s])
        alloc[s] += 1
    while sum(alloc.values()) > n:
        s = max((s for s in alloc if alloc[s] > 1), key=lambda s: alloc[s] - n * sizes[s] / total)
        alloc[s] -= 1
    return alloc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n-new", type=int, default=24)
    ap.add_argument("--n-changed", type=int, default=6)
    args = ap.parse_args()
    bridge = load_bridge()
    u = ledger_universe().set_index("transaction_hash")
    v = sqlite3.connect(VERSION.resolve().as_uri() + "?mode=ro", uri=True)
    eng = {k: (st, p, t) for k, st, p, t in v.execute(
        "SELECT h.target_key, h.link_state, d.parcel, d.tier FROM ledger_link_header_v1 h"
        " LEFT JOIN ledger_link_deps_v1 d ON d.target_key = h.target_key")}
    v.close()
    with get_built_engine().connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        enr = {r[0]: (r[1], r[2]) for r in c.execute(text(
            "SELECT transaction_hash, recovered_lot, match_tier FROM built_transaction_enrichment"))}

    cls: dict[str, str] = {}
    for k in set(eng) | set(enr):
        st, p, _ = eng.get(k, (None, None, None))
        linked = st == "linked" and p
        if k in enr and linked:
            e = enr[k][0]
            if e == p:
                cls[k] = "same"
            elif same_via_bridge(e, p, bridge):
                cls[k] = "same_bridge"
            else:
                cls[k] = "changed_same_bjd" if e.split("|")[0] == p.split("|")[0] else "changed_other_bjd"
        elif k in enr:
            cls[k] = "dropped_" + ("not_in_ledger" if k not in u.index else st or "absent")
        elif linked:
            cls[k] = "new"

    groups: dict = defaultdict(Counter)
    rows = []
    for k, c_ in cls.items():
        a = u.loc[k, "asset_type"] if k in u.index else "not_in_ledger"
        s = u.loc[k, "sido"] if k in u.index else "none"
        st, p, tier = eng.get(k, (None, None, None))
        for g in ("all", f"asset:{a}", f"sido:{s}", f"engine_tier:{tier}"):
            groups[g][c_] += 1
        if c_ not in ("same", "same_bridge"):
            rows.append((k, c_, a, s, tier, p, enr.get(k, (None, None))[0], enr.get(k, (None, None))[1]))
    VERIFY.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["transaction_hash", "class", "asset_type", "sido", "engine_tier", "engine_parcel",
                                "enrichment_lot", "enrichment_tier"]).to_csv(
        VERIFY / "built_engine_vs_enrichment_v1_rows.csv", index=False, encoding="utf-8-sig")

    # blind sample: new and changed links get fixed totals, each split by asset (proportional, at least 1)
    used = set(pd.read_csv(SAMPLE_DIR / "key.csv", usecols=["transaction_hash"], dtype=str)["transaction_hash"])
    pool = [r for r in rows if (r[1] == "new" or r[1].startswith("changed")) and r[0] not in used]
    strata: dict = defaultdict(list)
    for r in pool:
        strata[("new" if r[1] == "new" else "changed", r[2])].append(r)
    total = sum(len(x) for x in strata.values())
    alloc = {}
    for grp, n in (("new", args.n_new), ("changed", args.n_changed)):
        alloc.update(allocate({s: len(x) for s, x in strata.items() if s[0] == grp}, n))
    rng = random.Random(SEED)
    picked = []
    for s in sorted(strata):
        g = sorted(strata[s])
        rng.shuffle(g)
        for r in g[:alloc[s]]:
            picked.append((s, r, len(g) / alloc[s]))
    rng.shuffle(picked)
    details = tx_details([r[0] for _, r, _ in picked])
    sheet, key = [], []
    for i, (s, r, w) in enumerate(picked, start=1):
        d = details.loc[r[0]]
        addr, hint = hint_fields(d)
        name = f"{s[0]}|{ASSET.get(s[1], s[1])}"
        sheet.append({"번호": f"N{i}", "확인차수": "새연결", "묶음": name, "KAIS검색힌트": hint, "주소": addr,
                      "마스킹지번": d.lot_number, "도로명": d.road_name, "연면적": d.gross_area, "대지": d.land_area,
                      "계약일": d.contract_date, "가격_만원": d.price, "건물용도": d.building_use,
                      "KAIS_실제지번": "", "확인불가": "", "메모": ""})
        key.append({"번호": f"N{i}", "transaction_hash": r[0], "stratum": name, "weight": w, "class": r[1],
                    "sido": r[3], "asset_type": r[2], "tier": r[4], "recovered_lot": r[5].split("|", 1)[1],
                    "enrichment_lot": (r[6] or "|").split("|", 1)[1]})
    pd.DataFrame(sheet, columns=WORKSHEET_COLS).to_csv(SAMPLE_DIR / "new_links_worksheet.csv", index=False,
                                                       encoding="utf-8-sig")
    pd.DataFrame(key).to_csv(SAMPLE_DIR / "new_links_key.csv", index=False, encoding="utf-8-sig")

    out = {g: dict(sorted(c.items())) for g, c in sorted(groups.items())}
    rep = {"plan_step": "4-C follow-up — status-quo scope for the composite switch (read only)",
           "engine_version": "N_full_ENGINE_V2 (test folder)", "enrichment_rows": len(enr),
           "classes": out,
           "sample": {"seed": SEED, "pool_new_and_changed_excluding_219": total,
                      "strata": {f"{a}|{b}": {"population": len(strata[(a, b)]), "sample": alloc[(a, b)]}
                                 for a, b in sorted(strata)},
                      "worksheet": "outside repo (verification/built_link_sample_v1/new_links_worksheet.csv)"},
           "rows_file": "outside repo (verification)"}
    args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"enrichment_rows": len(enr), "all": out["all"], "sample": rep["sample"]["strata"],
                      **{g: out[g] for g in out if g.startswith("asset:")}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
