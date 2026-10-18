"""Plan step 8: quarterly incremental update of the composite contract table, and its checks.

From a previous version and a new version definition:
  1. change set   — keys added / removed / ledger row changed; register editions added or removed;
                    land releases added. Rule-version changes are refused: those need a full rebuild.
  2. affected     — every key whose result can change, by cause (time choice of register edition,
                    fallback over editions, register kind, zone at contract time, land area, land-area
                    use in matching). Keys outside the affected set are not touched.
  3. recompute    — the same engine as a full build (link_engine_v1), on the affected keys only.
  4. splice       — copy the previous version, move removed keys to the orphan table (header and
                    values kept as JSON with the version and a classification), replace affected rows,
                    log each changed key with its causes and row digests.
compare_logical() compares two versions transaction by transaction on normalized content: keys,
link state, values and missing states. computed_cycle (when a row was computed) is excluded.
Writes only to the version path given. Sources are read-only.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.link_engine_v1 import (  # noqa: E402
    DEPS_COLS, ENGINE_RULE, HEADER_COLS, VALUE_COLS, Defn, SlimView, compute, land_from_rows, parcel_pnu,
    register_kinds, zone_fields, zone_labels,
)
from built.measure_link_quality_v1 import SIDOS  # noqa: E402
from built.recover_address import CACHE, to_i  # noqa: E402
from built.register_ledger import connect as ledger_connect  # noqa: E402
from built.replay_honam_bridge import BRIDGED, load_bridge  # noqa: E402
from built.snapshot_policy import contract_ym_series, pick_snapshot_series  # noqa: E402

LOGICAL_EXCLUDE = ("computed_cycle",)


def allowed(bits: int | None) -> int | None:
    return None if bits is None else (1 << (bits + 1)) - 1


def info(path: Path) -> dict:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        return {k: (json.loads(v) if v[:1] in ("{", "[") else v) for k, v in db.execute("SELECT k, v FROM version_info")}


def read_table(path: Path, table: str) -> pd.DataFrame:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        return pd.read_sql(f"SELECT * FROM {table}", db)


# ---------------------------------------------------------------- change set and affected keys

def _bjd_title_keys(sido: str, snaps: set[str], bjds: set[str]) -> set[tuple]:
    folder = BRIDGED if sido == "12" else CACHE
    keys = set()
    for snap in sorted(snaps):
        t = pd.read_csv(folder / f"title_{sido}_{snap}.csv", dtype=str, keep_default_na=False,
                        usecols=["sigungu_code", "bjd_code", "bun", "ji"])
        b10 = t["sigungu_code"].str.strip() + t["bjd_code"].str.strip()
        t = t[b10.isin(bjds)]
        for sg, bd, b, j in zip(t["sigungu_code"], t["bjd_code"], t["bun"], t["ji"]):
            bun = to_i(b)
            if bun is not None:
                keys.add((sg.strip() + bd.strip(), bun, to_i(j) or 0))
    return keys


def affected(prev: Path, new: Defn, ledger_new: pd.DataFrame) -> tuple[dict[str, set], dict]:
    old = Defn.from_dict(info(prev)["defn"])
    if info(prev).get("rule_version") != ENGINE_RULE:
        raise RuntimeError("rule version changed: full rebuild required, not an incremental update")
    deps = read_table(prev, "ledger_link_deps_v1")
    hdr = read_table(prev, "ledger_link_header_v1")[["target_key", "source_digest"]]
    t0 = time.time()
    keys_a, keys_b = set(deps["target_key"]), set(ledger_new["transaction_hash"])
    causes: dict[str, set] = defaultdict(set)
    causes["tx_removed"] = keys_a - keys_b
    causes["tx_added"] = keys_b - keys_a
    dg = ledger_new.set_index("transaction_hash")["digest"]
    h = hdr.set_index("target_key")["source_digest"]
    common = sorted(keys_a & keys_b)
    causes["tx_row_changed"] = set(h[common].index[(h[common] != dg[common]).values])
    m = deps[(deps["in_matching"] == 1) & deps["target_key"].isin(set(common))].copy()
    stats = {"previous_keys": len(keys_a), "new_keys": len(keys_b), "matching_rows_checked": int(len(m))}
    miss = (m["snapshot_via"] != "time") | m["tier"].isna()
    if tuple(sorted(old.snapshots)) != tuple(sorted(new.snapshots)):
        ym = contract_ym_series(m["contract_year"], m["contract_month"])
        pa = pick_snapshot_series(ym, sorted(old.snapshots))
        pb = pick_snapshot_series(ym, sorted(new.snapshots))
        causes["register_time_choice"] = set(m.loc[(pa != pb).values, "target_key"])
        causes["register_fallback"] = set(m.loc[miss.values, "target_key"])
        gone = set(old.snapshots) - set(new.snapshots)
        if gone:
            causes["register_edition_removed"] = set(m.loc[m["snapshot_used"].isin(gone), "target_key"])
        pks = sorted(set(m["match_pk"].dropna()))
        led = ledger_connect()
        ka, kb = register_kinds(led, pks, old.snapshots), register_kinds(led, pks, new.snapshots)
        moved = {pk for pk in pks if ka.get(pk) != kb.get(pk)}
        causes["register_kind"] = set(m.loc[m["match_pk"].isin(moved), "target_key"])
    if old.land_bits != new.land_bits:
        al, bl = allowed(old.land_bits), allowed(new.land_bits)
        slim = SlimView(None)
        labels = zone_labels()
        bridge = load_bridge()
        lk = m[m["tier"].notna()]
        n_read = 0
        for r in lk.itertuples(index=False):
            keys_p = [int(x) for x in (r.pnus or "").split(",") if x]
            raws = {p: slim.raw(p) for p in keys_p}
            n_read += len(keys_p)
            za = _zone_from(raws, al, int(r.contract_year), int(r.contract_month or 0), labels)
            zb = _zone_from(raws, bl, int(r.contract_year), int(r.contract_month or 0), labels)
            if za != zb:
                causes["land_zone"].add(r.target_key)
            bjd, lot = r.parcel.split("|")
            bun, _, ji = lot.partition("-")
            pnu = parcel_pnu(bjd, int(bun), int(ji or 0), bridge if r.sido == "12" else None) if bun.isdigit() else None
            if pnu is not None:
                raw = slim.raw(pnu)
                if land_from_rows(SlimView.view(raw, al)) != land_from_rows(SlimView.view(raw, bl)):
                    causes["land_area"].add(r.target_key)
        # land area is a tie-breaker in matching (A2); only rows that were not a plain A1 hit can move
        cand = m[(m["n_exact"].fillna(0) >= 2) | miss]
        n_title = 0
        for sido, g in cand.groupby("sido"):
            tkeys = _bjd_title_keys(sido, set(old.snapshots) | set(new.snapshots), set(g["bjd"]))
            n_title += len(tkeys)
            changed_bjd = set()
            for bjd10, bun, ji in tkeys:
                if bjd10 in changed_bjd:
                    continue
                pnu = parcel_pnu(bjd10, bun, ji, bridge if sido == "12" else None)
                if pnu is None:
                    continue
                raw = slim.raw(pnu)
                if land_from_rows(SlimView.view(raw, al)) != land_from_rows(SlimView.view(raw, bl)):
                    changed_bjd.add(bjd10)
            causes["land_matching"] |= set(g.loc[g["bjd"].isin(changed_bjd), "target_key"])
        stats.update({"land_linked_rows_checked": int(len(lk)), "land_pnus_read": n_read,
                      "land_matching_candidates": int(len(cand)), "land_title_parcels_read": n_title})
    stats["detect_seconds"] = round(time.time() - t0, 1)
    return causes, stats


def _zone_from(raws: dict, allow: int | None, year: int, month: int, labels: dict) -> tuple:
    b: dict = defaultdict(set)
    for raw in raws.values():
        for y, mo, _, _, _, z1, z2 in SlimView.view(raw, allow):
            b[(int(y), int(mo))].add((z1, z2))
    z = zone_fields(b, year, month, labels)
    # latest_year (index 7) is not supplied or stored; only the latest zone code is
    return z[:7] + z[8:]


# ---------------------------------------------------------------- splice

def row_digest(header: tuple | None, values: list[tuple]) -> str | None:
    if header is None:
        return None
    hd = {c: v for c, v in zip(HEADER_COLS, header) if c not in LOGICAL_EXCLUDE}
    vals = sorted(tuple(v) for v in values)
    return hashlib.md5(repr((sorted(hd.items()), vals)).encode()).hexdigest()


def _rows_by_key(db: sqlite3.Connection, keys: list[str]) -> tuple[dict, dict]:
    hdr, val = {}, defaultdict(list)
    for i in range(0, len(keys), 900):
        chunk = keys[i:i + 900]
        ph = ",".join("?" * len(chunk))
        for row in db.execute(f"SELECT * FROM ledger_link_header_v1 WHERE target_key IN ({ph})", chunk):
            hdr[row[2]] = row
        for row in db.execute(f"SELECT {','.join(VALUE_COLS)} FROM ledger_link_value_v1 WHERE target_key IN ({ph})", chunk):
            val[row[0]].append(row)
    return hdr, val


def _delete(db: sqlite3.Connection, keys: list[str]) -> None:
    for i in range(0, len(keys), 900):
        chunk = keys[i:i + 900]
        ph = ",".join("?" * len(chunk))
        for t in ("ledger_link_value_v1", "ledger_link_header_v1", "ledger_link_deps_v1"):
            db.execute(f"DELETE FROM {t} WHERE target_key IN ({ph})", chunk)


def incremental(prev: Path, out: Path, new: Defn, ledger_new: pd.DataFrame, version_id: str,
                workers: int = 6, fail_at: str | None = None) -> dict:
    """Splice into <out>.partial and rename on success; on any failure the partial file is removed."""
    try:
        return _incremental(prev, out, new, ledger_new, version_id, workers, fail_at)
    except BaseException:
        out.with_suffix(".partial").unlink(missing_ok=True)
        raise


def _incremental(prev: Path, out: Path, new: Defn, ledger_new: pd.DataFrame, version_id: str,
                 workers: int, fail_at: str | None) -> dict:
    t0 = time.time()
    causes, stats = affected(prev, new, ledger_new)
    removed = causes.pop("tx_removed")
    recompute = set().union(*causes.values()) - removed if causes else set()
    t1 = time.time()
    rows = ledger_new[ledger_new["transaction_hash"].isin(recompute)]
    h, v, d, cstats = compute(rows, new, workers=workers)
    t2 = time.time()
    if fail_at == "splice_before_copy":
        raise RuntimeError("injected failure before splice")
    tmp = out.with_suffix(".partial")
    tmp.unlink(missing_ok=True)
    shutil.copyfile(prev, tmp)
    db = sqlite3.connect(tmp)
    db.execute("DELETE FROM ledger_link_change_v1")
    old_hdr, old_val = _rows_by_key(db, sorted(recompute | removed))
    old_deps = {r[0]: r for r in db.execute("SELECT * FROM ledger_link_deps_v1").fetchall()} if removed else {}
    new_val = defaultdict(list)
    for x in v:
        new_val[x[0]].append(x)
    new_deps = {x[0]: x for x in d}
    # orphans
    added_parcels = {new_deps[k][10] for k in causes.get("tx_added", set()) if k in new_deps and new_deps[k][10]}
    added_bjds = {new_deps[k][2] for k in causes.get("tx_added", set()) if k in new_deps}
    orphan_cls = Counter()
    for k in sorted(removed):
        dep = old_deps.get(k)
        parcel = dep[10] if dep else None
        bjd = dep[2] if dep else None
        cls = ("rehashed_candidate" if parcel and parcel in added_parcels
               else "relocated_or_removed" if bjd in added_bjds else "removed")
        orphan_cls[cls] += 1
        db.execute("INSERT OR REPLACE INTO ledger_link_orphan_v1 VALUES (?,?,?,?,?,?)", (
            k, version_id, cls, json.dumps(dict(zip(HEADER_COLS, old_hdr.get(k) or ())), ensure_ascii=False),
            json.dumps([list(x) for x in sorted(old_val.get(k, []))], ensure_ascii=False), parcel))
    _delete(db, sorted(recompute | removed))
    if fail_at == "splice_mid":
        db.close()
        raise RuntimeError("injected failure in the middle of splice")
    db.executemany(f"INSERT INTO ledger_link_header_v1 VALUES ({','.join('?' * 20)})", h)
    db.executemany(f"INSERT INTO ledger_link_value_v1 VALUES ('built',{','.join('?' * 11)})", v)
    db.executemany(f"INSERT INTO ledger_link_deps_v1 VALUES ({','.join('?' * 18)})", d)
    key_causes = defaultdict(list)
    for c, ks in causes.items():
        for k in ks:
            key_causes[k].append(c)
    for k in key_causes:
        key_causes[k].sort()
    changed = Counter()
    new_hdr = {x[2]: x for x in h}
    for k in sorted(recompute):
        a = row_digest(old_hdr.get(k), old_val.get(k, []))
        b = row_digest(new_hdr.get(k), new_val.get(k, []))
        if a == b:
            changed["recomputed_same"] += 1
            continue
        if a is None:
            kind = "added"
        elif old_hdr[k][3] != new_hdr[k][3]:
            kind = "link_state_changed"
        elif old_hdr[k][7] != new_hdr[k][7] or old_hdr[k][8] != new_hdr[k][8]:
            kind = "identification_changed"
        else:
            kind = "value_changed"
        changed[kind] += 1
        db.execute("INSERT INTO ledger_link_change_v1 VALUES (?,?,?,?,?)", (k, kind, ",".join(key_causes[k]), a, b))
    for k in sorted(removed):
        changed["orphaned"] += 1
        db.execute("INSERT INTO ledger_link_change_v1 VALUES (?,?,?,?,?)",
                   (k, "orphaned", "tx_removed", row_digest(old_hdr.get(k), old_val.get(k, [])), None))
    parent = info(prev)
    meta = {"version_id": version_id, "parent": parent.get("version_id"), "defn": new.to_dict(),
            "rule_version": ENGINE_RULE, "built_by": "incremental"}
    db.execute("DELETE FROM version_info")
    db.executemany("INSERT INTO version_info VALUES (?,?)",
                   [(k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) for k, v in meta.items()])
    db.commit()
    db.execute("VACUUM")
    db.close()
    out.unlink(missing_ok=True)
    tmp.rename(out)
    return {
        "causes": {c: len(ks) for c, ks in sorted(causes.items())}, "removed": len(removed),
        "recomputed": len(recompute), "changed": dict(changed), "orphan_classification": dict(orphan_cls),
        "detect": stats, "seconds": {"detect": round(t1 - t0, 1), "recompute": round(t2 - t1, 1),
                                     "splice": round(time.time() - t2, 1), "total": round(time.time() - t0, 1)},
        "recompute_stats": cstats, "bytes": out.stat().st_size, "_touched": recompute | removed,
    }


# ---------------------------------------------------------------- logical comparison

def _norm(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    if isinstance(x, float):
        return round(x, 9)
    return x


def compare_logical(a: Path, b: Path, variables: tuple[str, ...] | None = None, with_deps: bool = True,
                    header_exclude: tuple[str, ...] = LOGICAL_EXCLUDE, keys: set[str] | None = None) -> dict:
    """Transaction-by-transaction comparison on normalized content (no byte layout, no computed_cycle)."""
    out: dict = {}
    ha, hb = read_table(a, "ledger_link_header_v1"), read_table(b, "ledger_link_header_v1")
    if keys is not None:
        ha, hb = ha[ha["target_key"].isin(keys)], hb[hb["target_key"].isin(keys)]
    ka, kb = set(ha["target_key"]), set(hb["target_key"])
    out["header"] = {"rows_a": len(ha), "rows_b": len(hb), "only_a": len(ka - kb), "only_b": len(kb - ka),
                     "duplicate_a": int(ha["target_key"].duplicated().sum()),
                     "duplicate_b": int(hb["target_key"].duplicated().sum())}
    j = ha.merge(hb, on="target_key", suffixes=("_a", "_b"))
    cols = [c for c in HEADER_COLS if c not in header_exclude and c not in ("target_key", "domain", "target_kind")]
    out["header"]["column_mismatch"] = {
        c: int(sum(_norm(x) != _norm(y) for x, y in zip(j[f"{c}_a"], j[f"{c}_b"]))) for c in cols
    }
    va, vb = read_table(a, "ledger_link_value_v1"), read_table(b, "ledger_link_value_v1")
    if keys is not None:
        va, vb = va[va["target_key"].isin(keys)], vb[vb["target_key"].isin(keys)]
    if variables:
        va, vb = va[va["variable"].isin(variables)], vb[vb["variable"].isin(variables)]
    pa = set(zip(va["target_key"], va["variable"]))
    pb = set(zip(vb["target_key"], vb["variable"]))
    out["value"] = {"rows_a": len(va), "rows_b": len(vb), "only_a": len(pa - pb), "only_b": len(pb - pa)}
    jv = va.merge(vb, on=["target_key", "variable"], suffixes=("_a", "_b"))
    vcols = [c for c in VALUE_COLS if c not in ("target_key", "variable")]
    out["value"]["column_mismatch"] = {
        c: int(sum(_norm(x) != _norm(y) for x, y in zip(jv[f"{c}_a"], jv[f"{c}_b"]))) for c in vcols
    }
    miss_a = jv["value_num_a"].isna() & jv["value_text_a"].isna()
    out["value"]["missing_state_mismatch"] = int(
        ((miss_a | (jv["value_num_b"].isna() & jv["value_text_b"].isna()))
         & (jv["value_state_a"] != jv["value_state_b"])).sum())
    bad_keys = set()
    for c in cols:
        bad_keys |= set(j.loc[[_norm(x) != _norm(y) for x, y in zip(j[f"{c}_a"], j[f"{c}_b"])], "target_key"])
    for c in vcols:
        bad_keys |= set(jv.loc[[_norm(x) != _norm(y) for x, y in zip(jv[f"{c}_a"], jv[f"{c}_b"])], "target_key"])
    bad_keys |= (ka ^ kb) | {k for k, _ in (pa ^ pb)}
    out["transactions_compared"] = len(ka | kb)
    out["transactions_mismatched"] = len(bad_keys)
    if with_deps:
        da, db_ = read_table(a, "ledger_link_deps_v1"), read_table(b, "ledger_link_deps_v1")
        jd = da.merge(db_, on="target_key", suffixes=("_a", "_b"))
        out["deps"] = {"only_a": len(set(da["target_key"]) - set(db_["target_key"])),
                       "only_b": len(set(db_["target_key"]) - set(da["target_key"])),
                       "column_mismatch": {c: int(sum(_norm(x) != _norm(y) for x, y in zip(jd[f"{c}_a"], jd[f"{c}_b"])))
                                           for c in DEPS_COLS if c != "target_key"}}
    out["identical"] = (out["transactions_mismatched"] == 0 and out["header"]["duplicate_a"] == 0
                        and out["header"]["duplicate_b"] == 0
                        and (not with_deps or (out["deps"]["only_a"] == 0 and out["deps"]["only_b"] == 0
                                               and not any(out["deps"]["column_mismatch"].values()))))
    out["_bad_keys"] = bad_keys
    return out


def untouched_check(prev: Path, cur: Path, touched: set[str]) -> dict:
    """Keys outside the affected set must be identical to the previous version, computed_cycle included."""
    ha, hb = read_table(prev, "ledger_link_header_v1"), read_table(cur, "ledger_link_header_v1")
    va, vb = read_table(prev, "ledger_link_value_v1"), read_table(cur, "ledger_link_value_v1")
    keep = set(ha["target_key"]) & set(hb["target_key"]) - touched
    a = ha[ha["target_key"].isin(keep)].sort_values("target_key").reset_index(drop=True)
    b = hb[hb["target_key"].isin(keep)].sort_values("target_key").reset_index(drop=True)
    av = va[va["target_key"].isin(keep)].sort_values(["target_key", "variable"]).reset_index(drop=True)
    bv = vb[vb["target_key"].isin(keep)].sort_values(["target_key", "variable"]).reset_index(drop=True)
    same_h = a.astype(str).equals(b.astype(str))
    same_v = av.astype(str).equals(bv.astype(str))
    return {"untouched_keys": len(keep), "headers_identical": bool(same_h), "values_identical": bool(same_v)}
