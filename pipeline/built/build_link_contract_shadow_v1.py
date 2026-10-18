"""Plan step 7: composite transactions in the consumption-contract shape, as a local SQLite test table.

Every 2019+ composite transaction gets one header row: linked, unlinked (with the fail reason) or
not_applicable (partial ownership, no region code, invalid). Linked and unlinked rows get one value
row per variable. Values are written only when confirmed or candidates-agree; everything else is a
state with no value. Ledger values are not copied — each header holds an md5 digest of the ledger
row, recomputed after the build to show the ledger did not change.

Inputs (read-only): built_transactions, built_transaction_enrichment, 4-C rows, 4-D zone rows,
4-E pk/attr shadow, land trait slim code dictionary.
Output: C:\\CH2\\parcel_master\\verification\\built_link_contract_shadow_v1.sqlite (outside the repo)
and a counts-only JSON report.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from app.built.enrichment_join import canonical_zone_label  # noqa: E402
from built.db_utils import get_built_engine  # noqa: E402
from built.measure_link_quality_v1 import ROWS, VERIFY  # noqa: E402
from built.measure_zone_asof_v1 import EMPTY_LABELS, OUT_ROWS as ZONE_ROWS  # noqa: E402
from built.replay_enrichment_land_supply import SLIM  # noqa: E402
from built.resolve_tied_bldrgst_pk_v1 import SHADOW  # noqa: E402

OUT = VERIFY / "built_link_contract_shadow_v1.sqlite"
RULE_VERSION = "BUILT_A1A2_TIME_FALLBACK+LEDGER_SUPPLY_PROPOSED+CONTRACT_V1"
CYCLE = "202610"
VARIABLES = ("structure", "main_use", "floors_above", "approve_year", "zone_contract_year", "zone_latest", "land_area")
BRIDGED_SNAPSHOTS = {"2024-09", "2025-07"}

DIGEST_SQL = """
SELECT transaction_hash,
       md5(concat_ws('|', transaction_hash, asset_type,
           coalesce(beopjungri_code, '~'), coalesce(sigungu_code, '~'), coalesce(lot_number, '~'),
           coalesce(road_name, '~'), coalesce(contract_year::text, '~'), coalesce(contract_month::text, '~'),
           coalesce(contract_date::text, '~'), coalesce(zone_type, '~'), coalesce(building_use, '~'),
           price::text, coalesce(gross_area::text, '~'), coalesce(land_area::text, '~'),
           coalesce(building_age::text, '~'), is_valid::text, coalesce(is_partial_ownership::text, '~'))) AS digest,
       asset_type, contract_year, contract_month, gross_area, land_area, price,
       is_valid, is_partial_ownership, sigungu_code, beopjungri_code
FROM built_transactions
WHERE contract_year >= 2019
"""

FROZEN_SQL = """
SELECT transaction_hash, match_tier, structure_raw, max_floor, approve_year, zone_labels
FROM built_transaction_enrichment
"""

SQLITE_DDL = """
CREATE TABLE ledger_link_header_v1 (
    domain TEXT NOT NULL, target_kind TEXT NOT NULL, target_key TEXT NOT NULL,
    link_state TEXT NOT NULL CHECK (link_state IN ('linked','unlinked','not_applicable')),
    link_reason TEXT,
    link_level TEXT NOT NULL CHECK (link_level IN ('building','parcel','complex','none')),
    parcel_resolved INTEGER NOT NULL,
    building_id_state TEXT NOT NULL CHECK (building_id_state IN
        ('confirmed','candidates_agree','candidates_conflict','aggregated','weak_match','not_applicable')),
    bldrgst_pk TEXT, candidate_count INTEGER, hold_flags TEXT NOT NULL DEFAULT '',
    code_resolution TEXT CHECK (code_resolution IS NULL OR code_resolution IN
        ('held','reissued_1to1','current_code','bridge_12','prefix_v1')),
    register_snapshot TEXT, register_after_contract INTEGER, trait_asof TEXT,
    rule_version TEXT NOT NULL, unverified INTEGER NOT NULL DEFAULT 1,
    verification_basis TEXT NOT NULL CHECK (verification_basis IN ('none','auto_crosscheck','sample')),
    computed_cycle TEXT NOT NULL, source_digest TEXT,
    PRIMARY KEY (domain, target_key),
    CHECK (bldrgst_pk IS NULL OR building_id_state = 'confirmed'),
    CHECK ((link_state = 'linked') = (link_level <> 'none')),
    CHECK (unverified = 1 OR verification_basis = 'sample')
);
CREATE TABLE ledger_link_value_v1 (
    domain TEXT NOT NULL, target_key TEXT NOT NULL, variable TEXT NOT NULL,
    value_num REAL, value_text TEXT,
    value_state TEXT NOT NULL CHECK (value_state IN
        ('confirmed','candidates_agree','conflict_missing','source_missing','undetermined','not_linked')),
    value_level TEXT NOT NULL CHECK (value_level IN ('building','parcel','complex_aggregate')),
    source TEXT, basis_date TEXT,
    timing TEXT CHECK (timing IS NULL OR timing IN ('contract_year','contract_year_estimated','previous_year',
        'adjacent_before','adjacent_after','pre_contract_register','post_contract_register','latest')),
    change_risk TEXT NOT NULL DEFAULT 'none' CHECK (change_risk IN ('none','next_base_differs','undetermined')),
    use_approved INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (domain, target_key, variable),
    FOREIGN KEY (domain, target_key) REFERENCES ledger_link_header_v1 (domain, target_key),
    CHECK ((value_state IN ('confirmed','candidates_agree')) = (value_num IS NOT NULL OR value_text IS NOT NULL)),
    CHECK (use_approved = 0 OR value_state IN ('confirmed','candidates_agree')),
    CHECK (value_state <> 'candidates_agree' OR use_approved = 0),
    CHECK (value_level <> 'complex_aggregate' OR value_state <> 'candidates_agree')
);
"""

ZONE_TIMING = {
    "observed": "contract_year",
    "estimated": "contract_year_estimated",
    "adjacent_before": "adjacent_before",
    "adjacent_after": "adjacent_after",
}
ZONE_UNKNOWN_STATE = {
    "base_has_two_zones": "conflict_missing",
    "changed_around_contract": "conflict_missing",
    "code_newer_than_contract": "undetermined",
}
STABILITY_RISK = {"next_base_differs": "next_base_differs", "no_next_base": "undetermined"}


def nn(x):
    return None if x is None or (isinstance(x, float) and x != x) or x is pd.NA else x


def zone_labels() -> dict[str, str]:
    with sqlite3.connect(f"file:{SLIM}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        out = {}
        for code, label in db.execute(
            "SELECT code, label FROM code_dictionary WHERE field = 'zone1' AND is_standard = 1 ORDER BY code"
        ):
            if label not in EMPTY_LABELS and code not in out:
                out[code] = label
        return out


def ledger_snapshot(conn) -> pd.DataFrame:
    return pd.read_sql(text(DIGEST_SQL), conn)


def not_applicable_reason(r) -> str:
    if not r.is_valid:
        return "invalid"
    if not (r.gross_area and r.gross_area > 0):
        return "no_gross_area"
    if r.is_partial_ownership == True:  # noqa: E712
        return "partial_ownership"
    if not r.sigungu_code or not r.beopjungri_code:
        return "no_region_code"
    return "not_in_matching_input"


def building_value(var, value, flag, ident, after, snap, numeric):
    """One building variable from the attr shadow. ident: confirmed / candidates_agree / candidates_conflict."""
    timing = "post_contract_register" if after else "pre_contract_register"
    v = nn(value)
    if ident == "confirmed":
        state = "confirmed" if v is not None else "source_missing"
    elif v is not None:
        state = "candidates_agree"
    elif flag:
        state = "conflict_missing"
    else:
        state = "source_missing"
    if state not in ("confirmed", "candidates_agree"):
        v = None
    num = float(v) if (v is not None and numeric) else None
    txt = None if (v is None or numeric) else str(v)
    return (var, num, txt, state, "building", "building_ledger", snap, timing, "none", int(state == "confirmed"))


def zone_values(z, labels) -> list[tuple]:
    out = []
    if z is None:
        out.append(("zone_contract_year", None, None, "source_missing", "parcel", "land_trait_slim", None, None, "none", 0))
        out.append(("zone_latest", None, None, "source_missing", "parcel", "land_trait_slim", None, "latest", "none", 0))
        return out
    status = z["status"]
    label = labels.get(str(nn(z["zone1_code"]) or ""))
    risk = STABILITY_RISK.get(nn(z["stability"]), "none")
    if status in ZONE_TIMING and label:
        timing = ZONE_TIMING[status]
        base = nn(z["base_date"]) or nn(z["base_date_after"])
        out.append(("zone_contract_year", None, label, "confirmed", "parcel", "land_trait_slim", base, timing,
                    risk, int(timing == "contract_year")))
    else:
        state = ZONE_UNKNOWN_STATE.get(nn(z["why"]), "source_missing")
        out.append(("zone_contract_year", None, None, state, "parcel", "land_trait_slim", None, None, "none", 0))
    latest = labels.get(str(nn(z["latest_zone1_code"]) or ""))
    if latest:
        out.append(("zone_latest", None, latest, "confirmed", "parcel", "land_trait_slim", None, "latest", "none", 1))
    else:
        out.append(("zone_latest", None, None, "source_missing", "parcel", "land_trait_slim", None, "latest", "none", 0))
    return out


def build(snap: pd.DataFrame, rows: pd.DataFrame, zone: pd.DataFrame, pk: pd.DataFrame, attr: pd.DataFrame,
          labels: dict) -> tuple[list, list]:
    rows = rows.set_index("transaction_hash").to_dict("index")
    zone = zone.set_index("transaction_hash").to_dict("index")
    pk = pk.set_index("transaction_hash").to_dict("index")
    attr = attr.set_index("transaction_hash").to_dict("index")
    headers, values = [], []
    for r in snap.itertuples(index=False):
        h = r.transaction_hash
        if h not in rows:
            headers.append(("built", "transaction", h, "not_applicable", not_applicable_reason(r), "none", 0,
                            "not_applicable", None, None, "", None, None, None, None, RULE_VERSION, 1, "none",
                            CYCLE, r.digest))
            continue
        m = rows[h]
        linked = nn(m["tier"]) is not None
        if not linked:
            headers.append(("built", "transaction", h, "unlinked", nn(m["fail"]), "none", 0, "not_applicable",
                            None, None, "", None, None, None, None, RULE_VERSION, 1, "none", CYCLE, r.digest))
            for var in VARIABLES:
                level = "parcel" if var in ("zone_contract_year", "zone_latest", "land_area") else "building"
                values.append((h, var, None, None, "not_linked", level, None, None, None, "none", 0))
            continue
        a = attr[h]
        p = pk[h]
        ident = a["identification"]
        snap_used = nn(m["snapshot_used"])
        cy, cm = int(m["contract_year"]), int(m["contract_month"])
        after = bool(snap_used) and (int(snap_used[:4]) * 12 + int(snap_used[5:7])) > cy * 12 + cm
        flags = []
        if m["register"] == "집합":
            flags.append("collective_register")
        elif m["register"] == "변경":
            flags.append("register_kind_changed")
        approve = nn(a["approve"])
        if ident == "confirmed" and approve and str(approve).isdigit() and int(approve) > cy:
            flags.append("approve_after_contract")
        code_res = "bridge_12" if m["sido"] == "12" and snap_used in BRIDGED_SNAPSHOTS else "held"
        headers.append(("built", "transaction", h, "linked", m["tier"],
                        "building" if ident == "confirmed" else "parcel", 1, ident,
                        nn(p["bldrgst_pk"]) if ident == "confirmed" else None,
                        None if ident == "confirmed" else int(nn(p["n_candidates"]) or 0),
                        ",".join(flags), code_res, snap_used, int(after), None, RULE_VERSION, 1,
                        "auto_crosscheck", CYCLE, r.digest))
        for var, col, numeric in (("structure", "struct", False), ("main_use", "use", False),
                                  ("floors_above", "floors", True), ("approve_year", "approve", True)):
            values.append((h, *building_value(var, a[col], int(nn(a[f"{col}_conflict"]) or 0), ident, after,
                                              snap_used, numeric)))
        z = zone.get(h)
        for v in zone_values(z, labels):
            values.append((h, *v))
        land = nn(m["slim_land"])
        if land is not None:
            values.append((h, "land_area", float(land), None, "confirmed", "parcel", "land_trait_slim", None,
                           "latest", "none", 0))
        else:
            values.append((h, "land_area", None, None, "source_missing", "parcel", "land_trait_slim", None,
                           "latest", "none", 0))
    return headers, values


def write(headers: list, values: list, path: Path = OUT) -> None:
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SQLITE_DDL)
    db.executemany("INSERT INTO ledger_link_header_v1 VALUES (" + ",".join("?" * 20) + ")", headers)
    db.executemany(
        "INSERT INTO ledger_link_value_v1 VALUES ('built'," + ",".join("?" * 11) + ")", values
    )
    db.commit()
    db.close()


def same_num(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) < 1e-6


def verify(before: pd.DataFrame, after: pd.DataFrame, rows: pd.DataFrame, frozen: pd.DataFrame,
           path: Path = OUT) -> dict:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    hdr = pd.read_sql("SELECT target_key, link_state, link_reason, building_id_state, source_digest, link_level,"
                      " hold_flags, register_after_contract FROM ledger_link_header_v1", db)
    val = pd.read_sql("SELECT target_key, variable, value_num, value_text, value_state, use_approved, timing,"
                      " change_risk FROM ledger_link_value_v1", db)
    db.close()
    rep: dict = {}
    # keys
    keys_db = set(before["transaction_hash"])
    keys_hdr = set(hdr["target_key"])
    rep["keys"] = {
        "ledger_2019_plus": len(keys_db),
        "ledger_duplicate_hash": int(before["transaction_hash"].duplicated().sum()),
        "header_rows": len(hdr),
        "header_duplicate_key": int(hdr["target_key"].duplicated().sum()),
        "missing_from_header": len(keys_db - keys_hdr),
        "extra_in_header": len(keys_hdr - keys_db),
        "matching_input_rows": len(rows),
        "matching_input_not_in_header": len(set(rows["transaction_hash"]) - keys_hdr),
    }
    # ledger unchanged
    b = before.set_index("transaction_hash")["digest"]
    a = after.set_index("transaction_hash")["digest"]
    hd = hdr.set_index("target_key")["source_digest"]
    rep["ledger_unchanged"] = {
        "digest_before_vs_after_differs": int((b != a.reindex(b.index)).sum()),
        "rows_after": len(after),
        "header_digest_vs_ledger_differs": int((hd != a.reindex(hd.index)).sum()),
    }
    # matching input values vs ledger (the 4-C rows were built from this ledger)
    led = before.set_index("transaction_hash")
    mi = rows.set_index("transaction_hash").join(led[["asset_type", "contract_year", "contract_month", "gross_area",
                                                      "land_area"]], rsuffix="_db")
    rep["matching_input_vs_ledger"] = {
        "asset_type_differs": int((mi["asset_type"] != mi["asset_type_db"]).sum()),
        "contract_year_differs": int((mi["contract_year"] != mi["contract_year_db"]).sum()),
        "contract_month_differs": int((mi["contract_month"] != mi["contract_month_db"]).sum()),
        "gross_area_differs": int(sum(not same_num(nn(x), nn(y)) for x, y in zip(mi["gross_area"], mi["gross_area_db"]))),
        "land_area_differs": int(sum(not same_num(nn(x), nn(y)) for x, y in zip(mi["land_area"], mi["land_area_db"]))),
    }
    # header states
    rep["link_state"] = hdr["link_state"].value_counts().to_dict()
    rep["not_applicable_reason"] = hdr.loc[hdr["link_state"] == "not_applicable", "link_reason"].value_counts().to_dict()
    rep["unlinked_reason"] = hdr.loc[hdr["link_state"] == "unlinked", "link_reason"].value_counts().to_dict()
    lk = hdr[hdr["link_state"] == "linked"]
    rep["building_id_state_linked"] = lk["building_id_state"].value_counts().to_dict()
    rep["link_level_linked"] = lk["link_level"].value_counts().to_dict()
    fl = Counter(f for s in lk["hold_flags"] for f in s.split(",") if f)
    rep["hold_flags_linked"] = dict(fl)
    rep["register_after_contract_linked"] = int(lk["register_after_contract"].sum())
    # values
    per = val.groupby("target_key").size()
    expected = set(hdr.loc[hdr["link_state"] != "not_applicable", "target_key"])
    rep["values"] = {
        "rows": len(val),
        "duplicate_key_variable": int(val.duplicated(["target_key", "variable"]).sum()),
        "targets_with_values": len(per),
        "targets_expected": len(expected),
        "targets_not_7_variables": int((per != len(VARIABLES)).sum()),
        "not_applicable_with_values": len(set(per.index) - expected),
        "value_present_outside_known_states": int(
            ((val["value_num"].notna() | val["value_text"].notna())
             & ~val["value_state"].isin(["confirmed", "candidates_agree"])).sum()
        ),
        "candidates_agree_approved": int(((val["value_state"] == "candidates_agree") & (val["use_approved"] == 1)).sum()),
    }
    lkv = val[val["target_key"].isin(set(lk["target_key"]))]
    rep["value_state_linked"] = {
        v: g["value_state"].value_counts().to_dict() for v, g in lkv.groupby("variable")
    }
    rep["use_approved_linked"] = {v: int(g["use_approved"].sum()) for v, g in lkv.groupby("variable")}
    rep["zone_contract_year_timing"] = lkv.loc[lkv["variable"] == "zone_contract_year", "timing"].value_counts(
        dropna=False).to_dict()
    rep["zone_contract_year_change_risk"] = lkv.loc[lkv["variable"] == "zone_contract_year", "change_risk"].value_counts().to_dict()
    rep["frozen_comparison"] = compare_frozen(frozen, hdr, val)
    return rep


def compare_frozen(frozen: pd.DataFrame, hdr: pd.DataFrame, val: pd.DataFrame) -> dict:
    fz = frozen.set_index("transaction_hash")
    h = hdr.set_index("target_key")
    inter = fz.index.intersection(h.index)
    out = {
        "frozen_rows": len(fz),
        "in_header": len(inter),
        "missing_from_header": int(len(fz) - len(inter)),
        "new_state_of_frozen": h.loc[inter, "link_state"].value_counts().to_dict(),
        "tier_same": int((h.loc[inter, "link_reason"] == fz.loc[inter, "match_tier"]).sum()),
    }
    wide = val[val["target_key"].isin(inter)].pivot(index="target_key", columns="variable",
                                                    values=["value_num", "value_text", "value_state"])

    def cmp(var, old_col, new_kind, norm=lambda x: x):
        st = wide[("value_state", var)].reindex(inter)
        new = wide[(new_kind, var)].reindex(inter)
        old = fz.loc[inter, old_col]
        has_old = old.notna() & (old.astype(str).str.strip() != "")
        has_new = st.isin(["confirmed", "candidates_agree"])
        both = has_old & has_new
        same = sum(norm(x) == norm(y) for x, y in zip(old[both], new[both]))
        return {
            "old_missing": int((~has_old).sum()),
            "new_missing": int((~has_new).sum()),
            "new_state": st.value_counts().to_dict(),
            "both": int(both.sum()),
            "same": int(same),
            "same_rate": round(same / int(both.sum()), 4) if int(both.sum()) else None,
        }

    num = lambda x: None if x is None or x != x else int(float(x))  # noqa: E731
    out["structure"] = cmp("structure", "structure_raw", "value_text", lambda x: str(x).strip())
    out["floors_above"] = cmp("floors_above", "max_floor", "value_num", num)
    out["approve_year"] = cmp("approve_year", "approve_year", "value_num", num)
    # zone: frozen display label (first fine AL_D155 label) vs new labels, same canonical form
    old_zone = fz.loc[inter, "zone_labels"].map(lambda v: canonical_zone_label(list(v) if v is not None else []))
    zone = {}
    for var in ("zone_latest", "zone_contract_year"):
        st = wide[("value_state", var)].reindex(inter)
        new = wide[("value_text", var)].reindex(inter).map(lambda x: canonical_zone_label([x]) if isinstance(x, str) else None)
        has_old = old_zone.notna()
        has_new = new.notna()
        both = has_old & has_new
        zone[var] = {
            "old_missing": int((~has_old).sum()),
            "new_missing": int((~has_new).sum()),
            "new_state": st.value_counts().to_dict(),
            "both": int(both.sum()),
            "same": int((old_zone[both] == new[both]).sum()),
            "same_rate": round(int((old_zone[both] == new[both]).sum()) / int(both.sum()), 4) if int(both.sum()) else None,
        }
    out["zone_display_vs_new"] = zone
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--db", type=Path, default=OUT, help="SQLite output (default: verification folder)")
    args = ap.parse_args()
    db_path = args.db
    eng = get_built_engine()
    with eng.connect() as conn:
        before = ledger_snapshot(conn)
        frozen = pd.read_sql(text(FROZEN_SQL), conn)
    rows = pd.read_pickle(ROWS)
    zone = pd.read_pickle(ZONE_ROWS)
    with sqlite3.connect(f"file:{SHADOW}?mode=ro", uri=True) as s:
        pk = pd.read_sql("SELECT transaction_hash, bldrgst_pk, rule, n_candidates FROM pk_shadow", s)
        attr = pd.read_sql("SELECT * FROM attr_shadow", s)
    headers, values = build(before, rows, zone, pk, attr, zone_labels())
    write(headers, values, db_path)
    with eng.connect() as conn:
        after = ledger_snapshot(conn)
    rep = {"step": "7", "output": str(db_path), "rule_version": RULE_VERSION, "variables": list(VARIABLES)}
    rep.update(verify(before, after, rows, frozen, db_path))
    rep["file_bytes"] = db_path.stat().st_size
    args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=int), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("keys", "ledger_unchanged", "matching_input_vs_ledger", "link_state",
                                          "values")}, ensure_ascii=False, indent=1, default=int))


if __name__ == "__main__":
    main()
