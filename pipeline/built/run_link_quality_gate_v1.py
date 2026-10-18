"""Plan step 9: quality gate for a composite contract-table version, against the previous version.

A version is a contract-shaped SQLite (build_link_contract_shadow_v1). The previous version is either another
contract SQLite (--prev-db) or the frozen enrichment table read through an adapter (--prev-frozen), which is
what exists today. Metrics are kept apart — link success, sample accuracy (unverified until judged),
attribute coverage, temporal fitness, conflict rate — and computed nationally and by sido, asset type and
contract year, each with its denominators and the change from the previous version.

Checks end in pass / warn / fail. Any fail blocks the version; warns need a written waiver; even a clean
pass only makes the version eligible for approval. This script never writes to a product table.
Read-only. Counts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import bindparam, text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from app.built.enrichment_join import canonical_zone_label  # noqa: E402
from built.build_link_contract_shadow_v1 import DIGEST_SQL, OUT as CURRENT_DB, VARIABLES  # noqa: E402
from built.db_utils import get_built_engine  # noqa: E402
from built.measure_link_quality_v1 import SIDOS  # noqa: E402

KNOWN = ("confirmed", "candidates_agree")
STATES = ("confirmed", "candidates_agree", "conflict_missing", "source_missing", "undetermined", "not_linked")
SCOPE_MIN_ELIGIBLE = 1000

# Thresholds (draft; approval of the thresholds themselves is a separate decision).
T = {
    "link_rate_national_drop_fail_pp": 1.0,
    "link_rate_scope_drop_warn_pp": 1.5,
    "link_rate_scope_drop_fail_pp": 3.0,
    "coverage_national_drop_fail_pp": 1.0,
    "coverage_scope_drop_warn_pp": 3.0,
    "conflict_national_rise_warn_pp": 0.2,
    "zone_contract_year_national_drop_warn_pp": 1.0,
    "prev_agreement_building_warn": 0.99,
    "prev_agreement_zone_warn": 0.95,
    "orphan_fail_share": 0.001,
}

LEDGER_SCOPE_SQL = """
SELECT transaction_hash, coalesce(substr(sigungu_code, 1, 2), 'none') AS sido, asset_type, contract_year,
       (is_valid AND gross_area > 0 AND is_partial_ownership IS NOT TRUE
        AND substr(sigungu_code, 1, 2) IN :sidos) AS eligible
FROM built_transactions WHERE contract_year >= 2019
"""
FROZEN_SQL = """
SELECT transaction_hash, structure_raw, max_floor, approve_year, zone_labels
FROM built_transaction_enrichment
"""


# ---------------------------------------------------------------- versions

def load_contract(path: Path) -> dict:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        hdr = pd.read_sql("SELECT target_key, link_state, building_id_state, bldrgst_pk, register_after_contract,"
                          " source_digest FROM ledger_link_header_v1", db)
        val = pd.read_sql("SELECT target_key, variable, value_num, value_text, value_state, use_approved, timing,"
                          " change_risk FROM ledger_link_value_v1", db)
    val["value"] = val["value_text"].where(val["value_text"].notna(), val["value_num"])
    return {"kind": "contract", "path": str(path), "hdr": hdr, "val": val}


def load_frozen(conn, ledger: pd.DataFrame) -> dict:
    """Frozen enrichment as a version: rows present = linked, other eligible = unlinked. No conflict states."""
    fz = pd.read_sql(text(FROZEN_SQL), conn)
    in_ledger = set(ledger["transaction_hash"])
    orphans = int((~fz["transaction_hash"].isin(in_ledger)).sum())
    fz = fz[fz["transaction_hash"].isin(in_ledger)]
    linked = set(fz["transaction_hash"])
    hdr = ledger[["transaction_hash"]].rename(columns={"transaction_hash": "target_key"}).copy()
    hdr["link_state"] = [
        "linked" if h in linked else ("unlinked" if e else "not_applicable")
        for h, e in zip(ledger["transaction_hash"], ledger["eligible"])
    ]
    hdr["building_id_state"] = "not_recorded"
    hdr["bldrgst_pk"] = None
    hdr["register_after_contract"] = None
    hdr["source_digest"] = None
    zone = fz["zone_labels"].map(lambda v: canonical_zone_label(list(v) if v is not None else []))
    parts = []
    for var, series in (("structure", fz["structure_raw"]), ("floors_above", fz["max_floor"]),
                        ("approve_year", fz["approve_year"]), ("zone_latest", zone)):
        has = series.notna() & (series.astype(str).str.strip() != "")
        parts.append(pd.DataFrame({
            "target_key": fz["transaction_hash"].values, "variable": var,
            "value": series.where(has).values,
            "value_state": ["confirmed" if x else "source_missing" for x in has],
            "use_approved": 0, "timing": None, "change_risk": "none",
        }))
    return {"kind": "frozen_enrichment", "path": "built_transaction_enrichment", "hdr": hdr,
            "val": pd.concat(parts, ignore_index=True), "orphans": orphans, "rows": orphans + len(fz)}


# ---------------------------------------------------------------- metrics

def wide(version: dict) -> pd.DataFrame:
    v = version["val"]
    st = v.pivot(index="target_key", columns="variable", values="value_state")
    st.columns = [f"st_{c}" for c in st.columns]
    out = version["hdr"].set_index("target_key").join(st)
    z = v[v["variable"] == "zone_contract_year"].set_index("target_key")
    if len(z):
        out = out.join(z[["timing", "change_risk"]].rename(columns={"timing": "zone_timing", "change_risk": "zone_risk"}))
    return out


def scope_metrics(w: pd.DataFrame) -> dict:
    total = len(w)
    elig = w[w["link_state"] != "not_applicable"]
    lk = w[w["link_state"] == "linked"]
    n_e, n_l = len(elig), len(lk)
    m = {
        "total": total, "eligible": n_e, "linked": n_l, "unlinked": n_e - n_l,
        "not_applicable": total - n_e,
        "link_rate": round(n_l / n_e, 6) if n_e else None,
        "sample_verified": 0, "unverified_linked": n_l,
        "variables": {},
    }
    if "building_id_state" in lk and lk["building_id_state"].ne("not_recorded").any():
        m["building_id_state"] = lk["building_id_state"].value_counts().to_dict()
    for var in VARIABLES:
        col = f"st_{var}"
        if col not in lk:
            continue
        s = lk[col].value_counts()
        conf = int(s.get("confirmed", 0))
        m["variables"][var] = {
            **{k: int(s.get(k, 0)) for k in STATES if k != "not_linked"},
            "coverage_of_eligible": round(conf / n_e, 6) if n_e else None,
            "coverage_of_linked": round(conf / n_l, 6) if n_l else None,
            "conflict_rate_of_linked": round(int(s.get("conflict_missing", 0)) / n_l, 6) if n_l else None,
        }
    if "zone_timing" in lk:
        cy = int((lk["zone_timing"] == "contract_year").sum())
        m["temporal"] = {
            "zone_contract_year": cy,
            "zone_contract_year_rate": round(cy / n_l, 6) if n_l else None,
            "zone_next_base_differs": int((lk["zone_risk"] == "next_base_differs").sum()),
            "register_after_contract": int(pd.to_numeric(lk["register_after_contract"], errors="coerce").fillna(0).sum()),
        }
    return m


def all_scopes(w: pd.DataFrame, ledger: pd.DataFrame) -> dict:
    w = w.join(ledger.set_index("transaction_hash")[["sido", "asset_type", "contract_year"]])
    out = {"national": scope_metrics(w)}
    for key in ("sido", "asset_type", "contract_year"):
        for k, g in w.groupby(key):
            out[f"{key}|{k}"] = scope_metrics(g)
    return out


def pp(cur, prev):
    if cur is None or prev is None:
        return None
    return round((cur - prev) * 100, 3)


def deltas(cur: dict, prev: dict) -> dict:
    out = {}
    for scope, c in cur.items():
        p = prev.get(scope)
        if not p:
            continue
        d = {"link_rate_pp": pp(c["link_rate"], p["link_rate"]), "eligible": c["eligible"] - p["eligible"],
             "linked": c["linked"] - p["linked"], "variables": {}}
        for var, cv in c["variables"].items():
            pv = p["variables"].get(var)
            if pv:
                d["variables"][var] = {
                    "coverage_of_eligible_pp": pp(cv["coverage_of_eligible"], pv["coverage_of_eligible"]),
                    "conflict_rate_pp": pp(cv["conflict_rate_of_linked"], pv["conflict_rate_of_linked"]),
                }
        if "temporal" in c and "temporal" in p:
            d["zone_contract_year_rate_pp"] = pp(c["temporal"]["zone_contract_year_rate"],
                                                 p["temporal"]["zone_contract_year_rate"])
        out[scope] = d
    return out


def agreement(cur: dict, prev: dict) -> dict:
    out = {}
    cv, pv = cur["val"], prev["val"]
    for var in set(cv["variable"]) & set(pv["variable"]):
        a = cv[(cv["variable"] == var) & cv["value_state"].isin(KNOWN)].set_index("target_key")["value"]
        b = pv[(pv["variable"] == var) & pv["value_state"].isin(KNOWN)].set_index("target_key")["value"]
        common = a.index.intersection(b.index)
        if var.startswith("zone"):
            same = sum(canonical_zone_label([str(x)]) == canonical_zone_label([str(y)])
                       for x, y in zip(a[common], b[common]))
        elif var in ("floors_above", "approve_year"):
            same = sum(int(float(x)) == int(float(y)) for x, y in zip(a[common], b[common]))
        else:
            same = sum(str(x).strip() == str(y).strip() for x, y in zip(a[common], b[common]))
        out[var] = {"both_valued": int(len(common)), "same": int(same), "differs": int(len(common) - same),
                    "rate": round(same / len(common), 6) if len(common) else None,
                    "only_current": int(len(a.index.difference(b.index))),
                    "only_previous": int(len(b.index.difference(a.index)))}
    return out


def content_digest(path: Path) -> str:
    h = hashlib.md5()
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        for row in db.execute("SELECT * FROM ledger_link_header_v1 ORDER BY domain, target_key"):
            h.update(repr(row).encode())
        for row in db.execute("SELECT * FROM ledger_link_value_v1 ORDER BY domain, target_key, variable"):
            h.update(repr(row).encode())
    return h.hexdigest()


# ---------------------------------------------------------------- checks

def check(name, status, *, total=None, checked=None, unverified=None, mismatched=None, detail=None):
    return {"check": name, "status": status, "denominator_total": total, "denominator_checked": checked,
            "unverified": unverified, "mismatched": mismatched, "detail": detail}


def run_checks(cur, prev, ledger_digest, scopes_cur, scopes_prev, dl, agree, rebuild_db) -> list[dict]:
    out = []
    hdr = cur["hdr"]
    keys = set(hdr["target_key"])
    led = set(ledger_digest.index)
    dup = int(hdr["target_key"].duplicated().sum())
    miss, extra = len(led - keys), len(keys - led)
    out.append(check("integrity_keys", "fail" if (dup or miss or extra) else "pass", total=len(led),
                     checked=len(hdr), mismatched=dup + miss + extra,
                     detail={"duplicate": dup, "missing_from_version": miss, "not_in_ledger": extra}))
    dg = hdr.set_index("target_key")["source_digest"]
    common = dg.index.intersection(led)
    drift = int((dg[common] != ledger_digest[common]).sum())
    out.append(check("integrity_ledger_digest", "fail" if drift else "pass", total=len(led), checked=len(common),
                     mismatched=drift, detail="ledger rows changed after this version was built"))
    if prev.get("orphans") is not None:
        share = prev["orphans"] / prev["rows"] if prev["rows"] else 0
        st = "fail" if share > T["orphan_fail_share"] else ("warn" if prev["orphans"] else "pass")
        out.append(check("previous_result_orphans", st, total=prev["rows"], checked=prev["rows"],
                         mismatched=prev["orphans"], detail="previous result rows whose transaction is gone"))
    v = cur["val"]
    outside = int(((v["value"].notna()) & ~v["value_state"].isin(KNOWN)).sum())
    agree_on = int(((v["value_state"] == "candidates_agree") & (v["use_approved"] == 1)).sum())
    pk_bad = int((hdr["bldrgst_pk"].notna() & (hdr["building_id_state"] != "confirmed")).sum())
    out.append(check("contract_rules", "fail" if (outside or agree_on or pk_bad) else "pass", total=len(v),
                     checked=len(v), mismatched=outside + agree_on + pk_bad,
                     detail={"value_outside_known_state": outside, "candidates_agree_approved": agree_on,
                             "pk_without_confirmed": pk_bad}))
    # link rate
    nat = dl.get("national", {}).get("link_rate_pp")
    bad, warn = [], []
    for scope, d in dl.items():
        if scope == "national" or d["link_rate_pp"] is None or scopes_cur[scope]["eligible"] < SCOPE_MIN_ELIGIBLE:
            continue
        if d["link_rate_pp"] < -T["link_rate_scope_drop_fail_pp"]:
            bad.append(scope)
        elif d["link_rate_pp"] < -T["link_rate_scope_drop_warn_pp"]:
            warn.append(scope)
    st = "fail" if (nat is not None and nat < -T["link_rate_national_drop_fail_pp"]) or bad else ("warn" if warn else "pass")
    out.append(check("link_rate_change", st, total=scopes_cur["national"]["total"],
                     checked=scopes_cur["national"]["eligible"], mismatched=scopes_cur["national"]["unlinked"],
                     detail={"national_pp": nat, "scopes_fail": bad, "scopes_warn": warn}))
    # coverage and conflict
    cov_fail, cov_warn, conf_warn = [], [], []
    for var, d in dl.get("national", {}).get("variables", {}).items():
        if d["coverage_of_eligible_pp"] is not None and d["coverage_of_eligible_pp"] < -T["coverage_national_drop_fail_pp"]:
            cov_fail.append(var)
        if d["conflict_rate_pp"] is not None and d["conflict_rate_pp"] > T["conflict_national_rise_warn_pp"]:
            conf_warn.append(var)
    for scope, d in dl.items():
        if scope == "national" or scopes_cur[scope]["eligible"] < SCOPE_MIN_ELIGIBLE:
            continue
        for var, x in d["variables"].items():
            if x["coverage_of_eligible_pp"] is not None and x["coverage_of_eligible_pp"] < -T["coverage_scope_drop_warn_pp"]:
                cov_warn.append(f"{scope}:{var}")
    out.append(check("coverage_change", "fail" if cov_fail else ("warn" if cov_warn else "pass"),
                     total=scopes_cur["national"]["eligible"], checked=scopes_cur["national"]["linked"],
                     detail={"national_fail": cov_fail, "scopes_warn": cov_warn}))
    nat_vars = scopes_cur["national"]["variables"]
    out.append(check("conflict_rate", "warn" if conf_warn else "pass", total=scopes_cur["national"]["linked"],
                     checked=scopes_cur["national"]["linked"],
                     mismatched=sum(x.get("conflict_missing", 0) for x in nat_vars.values()),
                     detail={"rise_warn": conf_warn,
                             "by_variable": {k: x.get("conflict_missing", 0) for k, x in nat_vars.items()}}))
    tz = dl.get("national", {}).get("zone_contract_year_rate_pp")
    tc = scopes_cur["national"].get("temporal", {})
    out.append(check("temporal_fitness", "warn" if (tz is not None and tz < -T["zone_contract_year_national_drop_warn_pp"]) else "pass",
                     total=scopes_cur["national"]["linked"], checked=scopes_cur["national"]["linked"],
                     mismatched=scopes_cur["national"]["linked"] - tc.get("zone_contract_year", 0) if tc else None,
                     detail={"zone_contract_year_rate_pp": tz, **tc}))
    aw = []
    for var, a in agree.items():
        limit = T["prev_agreement_zone_warn"] if var.startswith("zone") else T["prev_agreement_building_warn"]
        if a["rate"] is not None and a["rate"] < limit:
            aw.append(var)
    out.append(check("previous_result_agreement", "warn" if aw else "pass",
                     checked=sum(a["both_valued"] for a in agree.values()),
                     mismatched=sum(a["differs"] for a in agree.values()), detail={"below_threshold": aw, **agree}))
    if rebuild_db and Path(rebuild_db).exists():
        a, b = content_digest(Path(cur["path"])), content_digest(Path(rebuild_db))
        out.append(check("rebuild_stability", "pass" if a == b else "fail", checked=len(cur["hdr"]) + len(cur["val"]),
                         mismatched=0 if a == b else None, detail={"same_digest": a == b}))
    else:
        out.append(check("rebuild_stability", "warn", detail="no rebuild given"))
    out.append(check("sample_accuracy", "unverified", total=scopes_cur["national"]["linked"], checked=0,
                     unverified=scopes_cur["national"]["linked"],
                     detail="no independent sample judged; accuracy cannot be claimed and product switch stays closed"))
    return out


def verdict(checks: list[dict]) -> str:
    s = {c["status"] for c in checks}
    if "fail" in s:
        return "blocked"
    if "warn" in s:
        return "needs_waiver"
    return "eligible_for_approval"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--db", type=Path, default=CURRENT_DB)
    ap.add_argument("--prev-db", type=Path)
    ap.add_argument("--prev-frozen", action="store_true")
    ap.add_argument("--rebuild-db", type=Path)
    args = ap.parse_args()
    with get_built_engine().connect() as c:
        ledger = pd.read_sql(
            text(LEDGER_SCOPE_SQL).bindparams(bindparam("sidos", expanding=True)), c, params={"sidos": list(SIDOS)}
        )
        ledger["eligible"] = ledger["eligible"].fillna(False).astype(bool)
        ledger_digest = pd.read_sql(text(DIGEST_SQL), c).set_index("transaction_hash")["digest"]
        cur = load_contract(args.db)
        prev = load_frozen(c, ledger) if args.prev_frozen else load_contract(args.prev_db)
    sc, sp = all_scopes(wide(cur), ledger), all_scopes(wide(prev), ledger)
    dl = deltas(sc, sp)
    agree = agreement(cur, prev)
    checks = run_checks(cur, prev, ledger_digest, sc, sp, dl, agree, args.rebuild_db)
    rep = {
        "step": "9", "current": cur["path"], "previous": prev["path"], "previous_kind": prev["kind"],
        "thresholds": T, "scope_min_eligible": SCOPE_MIN_ELIGIBLE,
        "verdict": verdict(checks),
        "promotion": "never automatic; needs an approval record naming the version, the checks and any waivers",
        "checks": checks, "metrics": sc, "previous_metrics": sp, "deltas": dl,
    }
    args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=int), encoding="utf-8")
    print(json.dumps({"verdict": rep["verdict"], "checks": [(c["check"], c["status"], c["mismatched"]) for c in checks]},
                     ensure_ascii=False, indent=1, default=int))


if __name__ == "__main__":
    main()
