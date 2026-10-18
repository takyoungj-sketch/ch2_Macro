"""Plan step 8: incremental-update tests R0–R9 on a test region, in a separate test environment.

Every version lives under C:\\CH2\\parcel_master\\versions_test\\built (outside the repo). The ledger,
transaction DB, enrichment DB and product DB are read only; a fingerprint of the product-side tables is
taken before and after to show they did not change. Test approvals are written by this harness and say
so; they are not user approvals and allow shadow_only publication inside the test registry only.

  R0  engine full build vs the step 7 test table (same rules; differences listed by column)
  R1  same inputs twice → identical
  R2  register edition added (2024-09+2025-07 → +2026-07): incremental vs full rebuild
  R3  land releases added (slim asof bits ≤ 28 → all): incremental vs full rebuild
  R4  transactions added / removed / corrected (same-parcel pairs): incremental vs full, orphans
  R5  two changes applied in both orders → identical to each other and to the full rebuild
  R6  injected failures (build, splice, gate, publish, restore) → active version and product unchanged
  R7  publish then restore the previous version → logical content identical to the original
  R8  a degraded candidate is blocked by the gate and cannot be published, even with an approval file
  R9  quarter replay: previous quarter (2 editions, land ≤ bit 28, contracts ≤ 2026-03, removals pending)
      → current quarter in one incremental step, compared with a full rebuild transaction by transaction
Counts only in the report.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.build_link_contract_shadow_v1 import OUT as STEP7, VARIABLES  # noqa: E402
from built.db_utils import get_built_engine  # noqa: E402
from built.incremental_update_v1 import compare_logical, incremental, read_table, untouched_check  # noqa: E402
from built.ledger_version_registry_v1 import Refused, Registry, sha256  # noqa: E402
from built.link_engine_v1 import ENGINE_RULE, Defn, compute, counts, ledger_universe, write_version  # noqa: E402
from built.run_link_quality_gate_v1 import gate  # noqa: E402

ROOT = Path(r"C:\CH2\parcel_master\versions_test\built")
REGION = ("12", "43", "50")
TWO = ("2024-09", "2025-07")
ALL = ("2024-09", "2025-07", "2026-07")
B = Defn(ALL, None, "2026Q3")
SEED = 20261018

PRODUCT_SQL = {
    "built_transaction_enrichment": "SELECT count(*), md5(string_agg(md5(e::text), '' ORDER BY transaction_hash))"
                                    " FROM built_transaction_enrichment e",
    "built_transactions_2019": "SELECT count(*), md5(string_agg(md5(t::text), '' ORDER BY transaction_hash))"
                               " FROM built_transactions t WHERE contract_year >= 2019",
}


def product_fingerprint() -> dict:
    with get_built_engine().connect() as c:
        return {k: list(c.execute(text(q)).fetchone()) for k, q in PRODUCT_SQL.items()}


REUSE = False


def full(universe: pd.DataFrame, defn: Defn, name: str, workers: int) -> dict:
    p = ROOT / f"{name}.sqlite"
    side = ROOT / f"{name}_build.json"
    if REUSE and p.exists() and side.exists():
        rec = json.loads(side.read_text(encoding="utf-8"))
        if rec.get("defn") == json.loads(json.dumps(defn.to_dict())) and rec.get("keys") == len(universe) and rec.get("sha256") == sha256(p):
            return {**rec["stats"], "reused": True}
    t0 = time.time()
    h, v, d, st = compute(universe, defn, workers=workers)
    write_version(p, h, v, d, {"version_id": name, "parent": "", "defn": defn.to_dict(), "rule_version": ENGINE_RULE,
                               "built_by": "full"})
    stats = {"path": str(p), "seconds": round(time.time() - t0, 1), "bytes": p.stat().st_size,
             "link_state": counts(h), "value_rows": len(v), "matched": st["matched_rows"]}
    side.write_text(json.dumps({"defn": defn.to_dict(), "keys": len(universe), "sha256": sha256(p), "stats": stats}),
                    encoding="utf-8")
    return stats


def cmp(a: Path, b: Path, **kw) -> dict:
    r = compare_logical(a, b, **kw)
    r.pop("_bad_keys")
    return r


def inc(prev: str, new: Defn, ledger: pd.DataFrame, name: str, workers: int, **kw) -> dict:
    r = incremental(ROOT / f"{prev}.sqlite", ROOT / f"{name}.sqlite", new, ledger, name, workers=workers, **kw)
    r["untouched"] = untouched_check(ROOT / f"{prev}.sqlite", ROOT / f"{name}.sqlite", r.pop("_touched"))
    return r


def samples(u: pd.DataFrame) -> dict:
    """1% new, 1% removed (disjoint), plus 100 correction pairs on the same parcel (one removed, one new)."""
    f = ROOT / "samples.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    deps = read_table(ROOT / "B_full.sqlite", "ledger_link_deps_v1")
    rng = random.Random(SEED)
    lk = deps[deps["parcel"].notna()].sort_values("target_key")
    pairs = []
    for _, g in lk.groupby("parcel", sort=True):
        if len(g) >= 2:
            pairs.append(tuple(g["target_key"].iloc[:2]))
    rng.shuffle(pairs)
    pairs = pairs[:100]
    used = {k for p in pairs for k in p}
    keys = sorted(set(u["transaction_hash"]) - used)
    rng.shuffle(keys)
    n = len(keys) // 100
    s = {"new": keys[:n] + [p[1] for p in pairs], "removed": keys[n:2 * n] + [p[0] for p in pairs],
         "pairs": [list(p) for p in pairs]}
    f.write_text(json.dumps(s), encoding="utf-8")
    return s


def approval(version_id: str, db: Path, gate_path: Path, waive: bool = True) -> Path:
    g = json.loads(gate_path.read_text(encoding="utf-8"))
    rec = {
        "domain": "built", "version": version_id, "version_db_sha256": sha256(db),
        "gate_report_sha256": sha256(gate_path), "verdict": g["verdict"],
        "waivers": [{"check": c["check"], "reason": "test harness waiver (not a user approval)"}
                    for c in g["checks"] if c["status"] == "warn"] if waive else [],
        "sample_accuracy": "unverified", "scope_of_approval": "shadow_only",
        "approved_by": "test-harness (not a user approval)", "approved_on": time.strftime("%Y-%m-%d"),
    }
    p = db.with_name(db.stem + "_approval.json")
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def run_gate(name: str, prev: str, rebuild: str | None = None) -> dict:
    t0 = time.time()
    rep = gate(ROOT / f"{name}.sqlite", ROOT / f"{prev}.sqlite", rebuild_db=ROOT / f"{rebuild}.sqlite" if rebuild else None,
               scope_sidos=REGION)
    p = ROOT / f"{name}_gate.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=int), encoding="utf-8")
    return {"verdict": rep["verdict"], "seconds": round(time.time() - t0, 1),
            "checks": {c["check"]: c["status"] for c in rep["checks"]}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="R0,R1,R2,R3,R4,R5,R9,R6,R7,R8")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reuse", action="store_true", help="reuse full builds whose definition, key count and sha256 match")
    args = ap.parse_args()
    global REUSE
    REUSE = args.reuse
    ROOT.mkdir(parents=True, exist_ok=True)
    res_file = ROOT / "results.json"
    res = json.loads(res_file.read_text(encoding="utf-8")) if res_file.exists() else {}

    def save():
        res_file.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=int), encoding="utf-8")

    W = args.workers
    u = ledger_universe(sidos=REGION)
    res["region"] = {"sidos": list(REGION), "keys": len(u)}
    if "product_before" not in res:
        res["product_before"] = product_fingerprint()
    only = args.only.split(",")
    if "R0" in only or not (ROOT / "B_full.sqlite").exists():
        b = full(u, B, "B_full", W)
        r0 = cmp(ROOT / "B_full.sqlite", STEP7, variables=VARIABLES, with_deps=False,
                 header_exclude=("computed_cycle", "rule_version"), keys=set(u["transaction_hash"]))
        res["R0"] = {"full": b, "vs_step7": r0}
        save()
    if "R1" in only:
        b2 = full(u, B, "B_full_again", W)
        res["R1"] = {"full": b2, "compare": cmp(ROOT / "B_full.sqlite", ROOT / "B_full_again.sqlite"),
                     "same_file_sha256": sha256(ROOT / "B_full.sqlite") == sha256(ROOT / "B_full_again.sqlite")}
        save()
    if "R2" in only:
        a = full(u, Defn(TWO, None, "2026Q2"), "A_reg", W)
        i = inc("A_reg", B, u, "R2_inc", W)
        res["R2"] = {"previous_full": a, "incremental": i, "vs_full": cmp(ROOT / "R2_inc.sqlite", ROOT / "B_full.sqlite")}
        save()
    if "R3" in only:
        a = full(u, Defn(ALL, 28, "2026Q2"), "A_land", W)
        i = inc("A_land", B, u, "R3_inc", W)
        res["R3"] = {"previous_full": a, "incremental": i, "vs_full": cmp(ROOT / "R3_inc.sqlite", ROOT / "B_full.sqlite")}
        save()
    s = samples(u)
    u_tx_a = u[~u["transaction_hash"].isin(set(s["new"]))]
    u_tx_b = u[~u["transaction_hash"].isin(set(s["removed"]))]
    if "R4" in only:
        a = full(u_tx_a, B, "A_tx", W)
        bt = full(u_tx_b, B, "B_tx_full", W)
        i = inc("A_tx", B, u_tx_b, "R4_inc", W)
        orphans = read_table(ROOT / "R4_inc.sqlite", "ledger_link_orphan_v1")
        pair_old = {p[0] for p in s["pairs"]}
        res["R4"] = {
            "previous_full": a, "full": bt, "incremental": i,
            "vs_full": cmp(ROOT / "R4_inc.sqlite", ROOT / "B_tx_full.sqlite"),
            "orphans": {"expected": len(s["removed"]), "found": len(orphans),
                        "missing": len(set(s["removed"]) - set(orphans["target_key"])),
                        "classification": orphans["classification"].value_counts().to_dict(),
                        "pairs": len(pair_old),
                        "pairs_rehashed_candidate": int(orphans[orphans["target_key"].isin(pair_old)]
                                                        ["classification"].eq("rehashed_candidate").sum()),
                        "orphan_rows_keep_header_and_values": int((orphans["header_json"].str.len() > 2).sum())},
            "removed_keys_left_in_current_table": int(read_table(ROOT / "R4_inc.sqlite", "ledger_link_header_v1")
                                                      ["target_key"].isin(set(s["removed"])).sum()),
        }
        save()
    if "R5" in only:
        a = full(u, Defn(TWO, 28, "2026Q2"), "A_both", W)
        p1a = inc("A_both", Defn(ALL, 28, "2026Q3"), u, "R5_reg_first_1", W)
        p1 = inc("R5_reg_first_1", B, u, "R5_reg_first", W)
        p2a = inc("A_both", Defn(TWO, None, "2026Q3"), u, "R5_land_first_1", W)
        p2 = inc("R5_land_first_1", B, u, "R5_land_first", W)
        res["R5"] = {"previous_full": a, "register_then_land": [p1a, p1], "land_then_register": [p2a, p2],
                     "orders_compared": cmp(ROOT / "R5_reg_first.sqlite", ROOT / "R5_land_first.sqlite"),
                     "register_first_vs_full": cmp(ROOT / "R5_reg_first.sqlite", ROOT / "B_full.sqlite"),
                     "land_first_vs_full": cmp(ROOT / "R5_land_first.sqlite", ROOT / "B_full.sqlite")}
        save()
    if "R9" in only:
        ym = u["contract_year"] * 100 + u["contract_month"].fillna(12)
        u_q = u[ym <= 202603]
        a = full(u_q, Defn(TWO, 28, "2026Q2"), "A_quarter", W)
        if not (ROOT / "B_tx_full.sqlite").exists():
            full(u_tx_b, B, "B_tx_full", W)
        i = inc("A_quarter", B, u_tx_b, "R9_inc", W)
        bt_bytes = (ROOT / "B_tx_full.sqlite").stat().st_size
        res["R9"] = {"previous_full": a, "incremental": i,
                     "vs_full": cmp(ROOT / "R9_inc.sqlite", ROOT / "B_tx_full.sqlite"),
                     "full_rebuild_bytes": bt_bytes,
                     "full_rebuild_seconds": res.get("R4", {}).get("full", {}).get("seconds")}
        save()
    if any(x in only for x in ("R6", "R7", "R8")):
        reg_root = ROOT / "registry"
        if reg_root.exists():
            shutil.rmtree(reg_root)
        reg = Registry(reg_root)
        out: dict = {}
        # initial active = previous quarter
        g0 = run_gate("A_reg", "A_reg")
        reg.register("A_reg", ROOT / "A_reg.sqlite", ROOT / "A_reg_gate.json")
        reg.publish("A_reg", approval("A_reg", ROOT / "A_reg.sqlite", ROOT / "A_reg_gate.json"), 0)
        base = reg.status()
        out["initial"] = {"gate": g0, "status": base}
        fp0 = product_fingerprint()
        fails = {}
        for point in ("splice_before_copy", "splice_mid"):
            try:
                inc("A_reg", B, u, f"R6_fail_{point}", W, fail_at=point)
                fails[point] = "no failure raised"
            except RuntimeError as e:
                fails[point] = {"raised": str(e), "status_unchanged": reg.status() == base,
                                "candidate_file_left": (ROOT / f"R6_fail_{point}.sqlite").exists(),
                                "partial_file_left": (ROOT / f"R6_fail_{point}.partial").exists()}
                (ROOT / f"R6_fail_{point}.partial").unlink(missing_ok=True)
        # good candidate
        i = inc("A_reg", B, u, "C_new", W)
        g1 = run_gate("C_new", "A_reg", rebuild="B_full")
        reg.register("C_new", ROOT / "C_new.sqlite", ROOT / "C_new_gate.json")
        ap_ok = approval("C_new", ROOT / "C_new.sqlite", ROOT / "C_new_gate.json")
        if any(s == "warn" for s in g1["checks"].values()):
            bad_ap, label = approval("C_new", ROOT / "C_new.sqlite", ROOT / "C_new_gate.json", waive=False), \
                "publish_without_waivers"
        else:
            rec = json.loads(ap_ok.read_text(encoding="utf-8"))
            rec["gate_report_sha256"] = "0" * 64
            bad_ap = ROOT / "C_new_approval_tampered.json"
            bad_ap.write_text(json.dumps(rec), encoding="utf-8")
            label = "publish_with_mismatched_gate_hash"
        try:
            reg.publish("C_new", bad_ap, base["revision"])
            fails[label] = "published (unexpected)"
        except Refused as e:
            fails[label] = {"refused": str(e)[:120], "status_unchanged": reg.status() == base}
        if reg.status() != base:
            raise RuntimeError(f"{label} changed the registry; stopping the registry tests")
        try:
            reg.publish("C_new", ap_ok, base["revision"], fail_at="publish_before_commit")
        except RuntimeError as e:
            fails["publish_before_commit"] = {"raised": str(e), "status_unchanged": reg.status() == base}
        try:
            reg.publish("C_new", ap_ok, base["revision"] + 5)
        except Refused as e:
            fails["publish_stale_revision"] = {"refused": str(e)[:120], "status_unchanged": reg.status() == base}
        out["R6"] = {"injected": fails, "candidate": {"incremental_seconds": i["seconds"], "gate": g1}}
        # R7 publish then restore, then revoke
        st1 = reg.publish("C_new", ap_ok, base["revision"])
        try:
            reg.restore("A_reg", st1["revision"], fail_at="restore_before_commit")
        except RuntimeError as e:
            out["R6"]["injected"]["restore_before_commit"] = {"raised": str(e), "status_unchanged": reg.status() == st1}
        st2 = reg.restore("A_reg", st1["revision"], reason="R7 rollback test")
        restored_same = cmp(Path(read_active(reg)), ROOT / "A_reg.sqlite")
        st3 = reg.restore("C_new", st2["revision"], reason="R7 forward again")
        st4 = reg.revoke("C_new", "R7 approval withdrawn test")
        out["R7"] = {"published": st1, "restored": st2, "restored_vs_original": restored_same["identical"],
                     "restored_sha256_matches": st2["active_db_sha256"] == sha256(ROOT / "A_reg.sqlite"),
                     "forward_again": st3, "after_revoke": st4,
                     "revoked_cannot_publish": _try(lambda: reg.publish("C_new", ap_ok, st4["revision"]))}
        # R8 degraded candidate
        bad = full(u, Defn(("2024-09",), None, "2026Q3"), "C_bad", W)
        g2 = run_gate("C_bad", "A_reg")
        reg.register("C_bad", ROOT / "C_bad.sqlite", ROOT / "C_bad_gate.json")
        st5 = reg.status()
        out["R8"] = {"candidate": bad, "gate": g2,
                     "publish_attempt": _try(lambda: reg.publish("C_bad", approval("C_bad", ROOT / "C_bad.sqlite",
                                                                                ROOT / "C_bad_gate.json"), st5["revision"])),
                     "status_unchanged": reg.status() == st5}
        out["events"] = reg.events()
        out["product_unchanged_during_registry_tests"] = product_fingerprint() == fp0
        res["registry"] = out
        save()
    res["product_after"] = product_fingerprint()
    res["product_unchanged"] = res["product_after"] == res["product_before"]
    res["storage_bytes"] = {p.name: p.stat().st_size for p in sorted(ROOT.glob("*.sqlite"))}
    save()
    args.out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=int), encoding="utf-8")
    print(json.dumps({k: (v.get("vs_full", {}).get("identical") if isinstance(v, dict) else None)
                      for k, v in res.items() if k.startswith("R")}, ensure_ascii=False))


def read_active(reg: Registry) -> str:
    import sqlite3
    with sqlite3.connect(reg.path) as db:
        return db.execute("SELECT v.path FROM pointer p JOIN version v ON v.version_id = p.active").fetchone()[0]


def _try(fn) -> dict:
    try:
        fn()
        return {"refused": False}
    except Refused as e:
        return {"refused": True, "reason": str(e)[:160]}


if __name__ == "__main__":
    main()
