"""RENT-001 v5 read-only judgment file. Prints counts only."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "scripts" / "ops" / "collective_p2_verify"))

from admin_names import LEGACY_SIDO_TO_CURRENT  # noqa: E402
from build_stats_v2 import period_bounds_for_window  # noqa: E402
from collective.building_keys import (  # noqa: E402
    _key_raw_for,
    building_key_raw_series,
    c2_key,
    load_split_units,
)
from collective.db_utils import get_collective_engine  # noqa: E402
from ops_guards import assert_local_target  # noqa: E402
from parcel_master.db_utils import get_parcel_engine  # noqa: E402
from rent.db_utils import get_rent_engine  # noqa: E402

OUT_CSV = REPO / "logs" / "rent_c2" / "rent_c2_units_v1.csv"
OUT_JSON = REPO / "logs" / "rent_c2" / "RENT-001_v5_20261119.json"
COLS = [
    "base_key",
    "asset_type",
    "beopjungri_code",
    "main_lot",
    "part",
    "decision",
    "evidence",
    "source",
    "collective_sha256",
    "note",
]
SOURCE = "rent_c2_20261119"
COLLECTIVE_SHA = "372e114bf7c664ca5489660596adc7969f04302d6d0a68b1f7f84ee0aabe62e5"
SNAPSHOT = "2026-07"
TYPES = ("apartment", "rowhouse", "officetel")


def norm_lot(raw) -> str:
    s = str(raw or "").strip()
    if s.isdigit():
        return s.lstrip("0") or "0"
    return s


def lot_key(ml: str):
    return (0, int(ml)) if str(ml).isdigit() else (1, str(ml))


def timed(conn, sql, params=None):
    started = time.perf_counter()
    try:
        rows = conn.execute(text(sql), params or {}).mappings().all()
    except OperationalError as exc:
        return None, round(time.perf_counter() - started, 3), type(exc).__name__
    return rows, round(time.perf_counter() - started, 3), None


def recover_raw_of(conn, pairs: list[tuple[str, str]]) -> dict[tuple[str, str], str]:
    """분할 조각의 원문. 읽기만 하고, 없으면 그 키는 결과에 넣지 않는다."""
    keys = sorted({key for key, _asset in pairs})
    if not keys:
        return {}
    rows = conn.execute(
        text(
            """
            SELECT rtrim(building_key) AS building_key, asset_type,
                   addr1, addr2, addr3, addr4, building_name, lot_number, road_name,
                   count(*)::bigint AS n
            FROM rent_transactions
            WHERE is_valid AND asset_type IN ('apartment', 'rowhouse', 'officetel')
              AND building_key = ANY(CAST(:keys AS char(64)[]))
            GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
            """
        ),
        {"keys": keys},
    ).mappings().all()
    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_key[(str(row["building_key"]).strip(), str(row["asset_type"]).strip())].append(dict(row))
    c01 = load_split_units()
    found_of: dict[tuple[str, str], str] = {}
    for key, asset in pairs:
        variants = by_key.get((key, asset), [])
        if not variants:
            continue
        frames = [pd.DataFrame(variants)]
        alt = []
        for row in variants:
            copied = dict(row)
            addr = copied.get("addr1")
            copied["addr1"] = LEGACY_SIDO_TO_CURRENT.get(addr, addr) if isinstance(addr, str) else addr
            alt.append(copied)
        frames.append(pd.DataFrame(alt))
        found = None
        for frame in frames:
            raws = building_key_raw_series(frame, asset)
            for raw in raws.tolist():
                found = _key_raw_for(str(raw), key, c01)
                if found is not None:
                    break
            if found is not None:
                break
        if found is not None:
            found_of[(key, asset)] = found
    return found_of


def write_units_csv(rows: list[dict], path: Path) -> str:
    ordered = sorted(
        rows,
        key=lambda r: (r["asset_type"], r["beopjungri_code"], r["base_key"], lot_key(r["main_lot"]), int(r["part"])),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ordered)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    timings = []
    rent_eng = get_rent_engine()
    col_eng = get_collective_engine()
    par_eng = get_parcel_engine()
    for eng in (rent_eng, col_eng, par_eng):
        assert_local_target(eng)

    with col_eng.connect() as conn:
        rows, sec, err = timed(
            conn,
            "SELECT current_setting('transaction_read_only') AS ro, current_setting('statement_timeout') AS st",
        )
        timings.append({"id": "S_collective", "seconds": sec, "error": err})
        if err or not rows or rows[0]["ro"] != "on":
            raise SystemExit("collective not read-only")
        units, sec, err = timed(
            conn,
            """
            SELECT base_key, asset_type, beopjungri_code, main_lot, part, decision
            FROM collective_building_key_c2_units
            """,
        )
        timings.append({"id": "Q_c2_units", "seconds": sec, "error": err, "rows": 0 if units is None else len(units)})
        keymap, sec, err = timed(
            conn,
            """
            SELECT old_key, new_key, asset_type, split_part, coalesce(reason, '') AS reason
            FROM collective_building_key_map
            """,
        )
        timings.append({"id": "Q_key_map", "seconds": sec, "error": err, "rows": 0 if keymap is None else len(keymap)})
    if not units or keymap is None:
        raise SystemExit("collective reads failed")

    split_keys = set()
    judged = set()
    keep = set()
    part_of = {}
    ambiguous_part = set()
    unit_rows = []
    for r in units:
        key = str(r["base_key"] or "").strip()
        asset = str(r["asset_type"] or "").strip()
        b10 = str(r["beopjungri_code"] or "")[:10]
        ml = norm_lot(r["main_lot"])
        decision = str(r["decision"] or "")
        part = int(r["part"]) if r["part"] is not None and str(r["part"]).strip() != "" else 0
        unit_rows.append((key, asset, b10, ml, part, decision))
        if decision == "split":
            split_keys.add(key)
            judged.add((key, b10))
            slot = (key, asset, b10, ml)
            if slot in part_of and part_of[slot] != part:
                ambiguous_part.add(slot)
            part_of[slot] = part
        elif decision == "keep":
            keep.add((key, b10))

    map_forward = defaultdict(set)
    map_c2 = defaultdict(set)
    map_opts = defaultdict(set)
    for r in keymap:
        old = str(r["old_key"] or "").strip()
        new = str(r["new_key"] or "").strip()
        asset = str(r["asset_type"] or "").strip()
        part = int(r["split_part"] or 0)
        reason = str(r["reason"] or "")
        map_forward[(old, asset, part)].add(new)
        map_opts[(new, asset)].add((old, part))
        if "c2" in reason:
            map_c2[(old, asset, part)].add(new)
    ambiguous_map_keys = sum(1 for opts in map_opts.values() if len(opts) > 1)

    with rent_eng.connect() as conn:
        rows, sec, err = timed(
            conn,
            "SELECT current_setting('transaction_read_only') AS ro, current_setting('statement_timeout') AS st",
        )
        timings.append({"id": "S_rent", "seconds": sec, "error": err})
        if err or not rows or rows[0]["ro"] != "on":
            raise SystemExit("rent not read-only")
        asof_rows, sec, err = timed(
            conn,
            """
            SELECT max(as_of_month) AS as_of
            FROM rent_building_stats
            WHERE window_years = 5
            """,
        )
        timings.append({"id": "Q_asof", "seconds": sec, "error": err})
        as_of = asof_rows[0]["as_of"] if asof_rows and asof_rows[0]["as_of"] else None
        if as_of is not None and not isinstance(as_of, date):
            as_of = date.fromisoformat(str(as_of)[:10])
        if as_of is not None and as_of.day != 1:
            as_of = as_of.replace(day=1)
        p_start, p_end = period_bounds_for_window(as_of, 5) if as_of else (None, None)
        matched, sec, err = timed(
            conn,
            """
            SELECT building_key, asset_type, left(beopjungri_code, 10) AS b10,
                   split_part(btrim(lot_number), '-', 1) AS ml_raw,
                   CASE WHEN coalesce(btrim(lot_ji), '') <> '' THEN btrim(lot_ji)
                        ELSE split_part(btrim(lot_number), '-', 2) END AS sub_raw,
                   building_year,
                   regexp_replace(btrim(coalesce(building_name, '')), '\\s+', '', 'g') AS name_key,
                   count(*)::bigint AS n
            FROM rent_transactions
            WHERE is_valid AND asset_type IN ('apartment', 'rowhouse', 'officetel')
              AND building_key = ANY(CAST(:keys AS char(64)[]))
              AND beopjungri_code IS NOT NULL
              AND coalesce(btrim(lot_number), '') <> ''
            GROUP BY 1, 2, 3, 4, 5, 6, 7
            """,
            {"keys": list(split_keys)},
        )
        timings.append({"id": "Q_matched_grain", "seconds": sec, "error": err, "rows": 0 if matched is None else len(matched)})
        candidates, sec, err = timed(
            conn,
            """
            WITH judged AS (
              SELECT unnest(CAST(:judged_keys AS text[])) AS building_key,
                     unnest(CAST(:judged_bjd AS text[])) AS b10
            ), grain AS (
              SELECT building_key, asset_type, left(beopjungri_code, 10) AS b10,
                     split_part(btrim(lot_number), '-', 1) AS ml_raw,
                     CASE WHEN coalesce(btrim(lot_ji), '') <> '' THEN btrim(lot_ji)
                          ELSE split_part(btrim(lot_number), '-', 2) END AS sub_raw,
                     building_year,
                     regexp_replace(btrim(coalesce(building_name, '')), '\\s+', '', 'g') AS name_key,
                     count(*)::bigint AS n
              FROM rent_transactions
              WHERE is_valid AND asset_type IN ('apartment', 'rowhouse', 'officetel')
                AND beopjungri_code IS NOT NULL
                AND coalesce(btrim(lot_number), '') <> ''
              GROUP BY 1, 2, 3, 4, 5, 6, 7
            ), lots AS (
              SELECT building_key, asset_type, b10,
                     CASE WHEN ml_raw ~ '^[0-9]+$'
                          THEN coalesce(nullif(ltrim(ml_raw, '0'), ''), '0')
                          ELSE btrim(ml_raw) END AS ml,
                     sum(n)::bigint AS n
              FROM grain
              GROUP BY 1, 2, 3, 4
            ), parents AS (
              SELECT l.building_key, l.asset_type, l.b10
              FROM lots l
              WHERE NOT EXISTS (
                SELECT 1 FROM judged j
                WHERE j.building_key = l.building_key AND j.b10 = l.b10
              )
              GROUP BY 1, 2, 3
              HAVING count(*) FILTER (WHERE l.n >= 3) >= 2
            )
            SELECT g.*
            FROM grain g
            JOIN parents p
              ON p.building_key = g.building_key
             AND p.asset_type = g.asset_type
             AND p.b10 = g.b10
            """,
            {
                "judged_keys": [k for k, _b in judged],
                "judged_bjd": [b for _k, b in judged],
            },
        )
        timings.append({"id": "Q_rent_only_grain", "seconds": sec, "error": err, "rows": 0 if candidates is None else len(candidates)})
    if matched is None or candidates is None:
        raise SystemExit("rent grain failed")

    def pack(rows):
        out = []
        for r in rows:
            out.append(
                {
                    "key": str(r["building_key"] or "").strip(),
                    "asset": str(r["asset_type"] or "").strip(),
                    "b10": str(r["b10"] or ""),
                    "ml": norm_lot(r["ml_raw"]),
                    "sub": norm_lot(r["sub_raw"]) if str(r["sub_raw"] or "").strip() else "",
                    "year": int(r["building_year"]) if r["building_year"] and int(r["building_year"]) > 0 else None,
                    "name": str(r["name_key"] or ""),
                    "n": int(r["n"]),
                }
            )
        return out

    def group_rows(rows):
        groups = defaultdict(list)
        for row in rows:
            groups[(row["key"], row["asset"], row["b10"])].append(row)
        return groups

    matched_rows = [r for r in pack(matched) if (r["key"], r["b10"]) in judged]
    matched_groups = group_rows(matched_rows)
    candidate_groups = group_rows(pack(candidates))

    def lot_n(group):
        lots = defaultdict(int)
        for row in group:
            lots[row["ml"]] += row["n"]
        return lots

    unmatched_lots = defaultdict(set)
    unmatched_tx = 0
    for gid, group in matched_groups.items():
        for row in group:
            slot = (gid[0], gid[1], gid[2], row["ml"])
            if part_of.get(slot) is None or slot in ambiguous_part:
                unmatched_lots[gid].add(row["ml"])
                unmatched_tx += row["n"]

    b10s = sorted({r["b10"] for r in matched_rows + pack(candidates) if r["b10"]})
    with par_eng.connect() as conn:
        rows, sec, err = timed(
            conn,
            "SELECT current_setting('transaction_read_only') AS ro, current_setting('statement_timeout') AS st",
        )
        timings.append({"id": "S_parcel", "seconds": sec, "error": err})
        if err or not rows or rows[0]["ro"] != "on":
            raise SystemExit("parcel not read-only")
        titles, sec, err = timed(
            conn,
            """
            SELECT beopjungri_code AS b10, pnu, mgmt_pk,
                   left(approve_date, 4) AS y,
                   regexp_replace(btrim(coalesce(building_name, '')), '\\s+', '', 'g') AS bname
            FROM building
            WHERE snapshot = :snap
              AND beopjungri_code = ANY(CAST(:b10s AS char(10)[]))
            """,
            {"snap": SNAPSHOT, "b10s": b10s},
        )
        timings.append({"id": "Q_title", "seconds": sec, "error": err, "rows": 0 if titles is None else len(titles)})
    if titles is None:
        raise SystemExit("title read failed")
    title_by_bun = defaultdict(list)
    for r in titles:
        pnu = str(r["pnu"] or "")
        if len(pnu) < 19:
            continue
        year_s = str(r["y"] or "")
        year = int(year_s) if year_s.isdigit() and int(year_s) > 0 else None
        title_by_bun[(str(r["b10"]).strip(), norm_lot(pnu[11:15]))].append(
            {
                "ji": norm_lot(pnu[15:19]),
                "pk": str(r["mgmt_pk"] or ""),
                "year": year,
                "name": str(r["bname"] or ""),
            }
        )

    def titles_for(b10, ml, sub):
        rows = title_by_bun.get((b10, ml), [])
        if sub:
            return [t for t in rows if t["ji"] == sub], rows
        return rows, rows

    def profile(items):
        pks = {t["pk"] for t in items if t["pk"]}
        years = {t["year"] for t in items if t["year"]}
        names = {t["name"] for t in items if t["name"]}
        return pks, years, names

    def lot_evidence(group, qualifying_only, strict):
        lots = lot_n(group)
        chosen = [ml for ml, n in lots.items() if n >= 3] if qualifying_only else list(lots)
        evidences = []
        for ml in chosen:
            rows = [r for r in group if r["ml"] == ml]
            subs = {r["sub"] for r in rows if r["sub"]}
            sub = next(iter(subs)) if len(subs) == 1 else ""
            exact, bun_rows = titles_for(group[0]["b10"], ml, sub if len(subs) == 1 else "")
            use = exact if len(subs) == 1 and sub else bun_rows
            pks, years, names = profile(use)
            rent_years = {r["year"] for r in rows if r["year"]}
            rent_names = {r["name"] for r in rows if r["name"]}
            clean = bool(pks) and len(years) == 1 and len(names) == 1
            year = next(iter(years)) if len(years) == 1 else None
            name = next(iter(names)) if len(names) == 1 else None
            if strict:
                agrees = clean and bool(rent_years) and rent_years <= years and bool(rent_names) and rent_names == names
            else:
                agrees = clean and rent_years <= years and (not rent_names or rent_names == names)
            evidences.append(
                {
                    "ml": ml,
                    "n": lots[ml],
                    "clean": clean,
                    "agrees": agrees,
                    "year": year,
                    "name": name,
                }
            )
        return evidences

    def label_of(ev):
        if len(ev) < 2 or any(not e["clean"] or not e["agrees"] for e in ev):
            return "다"
        years = {e["year"] for e in ev}
        names = {e["name"] for e in ev}
        if len(years) == 1 and len(names) == 1 and all(e["name"] for e in ev):
            return "나"
        if len(years) > 1 or len(names) > 1:
            return "가"
        return "다"

    def row_out(key, asset, b10, ml, part, decision, evidence, note=""):
        return {
            "base_key": key,
            "asset_type": asset,
            "beopjungri_code": b10,
            "main_lot": ml,
            "part": int(part),
            "decision": decision,
            "evidence": evidence,
            "source": SOURCE,
            "collective_sha256": COLLECTIVE_SHA,
            "note": note,
        }

    out_rows = []
    copied_slots = set()
    for key, asset, b10, ml, part, decision in unit_rows:
        if decision != "split":
            continue
        if (key, asset, b10) not in matched_groups:
            continue
        out_rows.append(row_out(key, asset, b10, ml, part, "split", "collective_reuse"))
        copied_slots.add((key, asset, b10, ml))

    want_keys = set(split_keys)
    for (new, _asset), opts in map_opts.items():
        if any(old in split_keys for old, _part in opts):
            want_keys.add(new)
    with col_eng.connect() as conn:
        col_rows, sec, err = timed(
            conn,
            """
            SELECT building_key, asset_type, left(beopjungri_code, 10) AS b10,
                   split_part(btrim(lot_number), '-', 1) AS ml_raw,
                   count(*)::bigint AS n
            FROM collective_transactions
            WHERE is_valid AND asset_type IN ('apartment', 'rowhouse', 'officetel')
              AND building_key = ANY(CAST(:keys AS char(64)[]))
              AND beopjungri_code IS NOT NULL
              AND coalesce(btrim(lot_number), '') <> ''
            GROUP BY 1, 2, 3, 4
            """,
            {"keys": list(want_keys)},
        )
        timings.append({"id": "Q_collective_lots", "seconds": sec, "error": err, "rows": 0 if col_rows is None else len(col_rows)})
    if col_rows is None:
        raise SystemExit("collective lots failed")
    collective_parts = defaultdict(set)
    for r in col_rows:
        key = str(r["building_key"] or "").strip()
        asset = str(r["asset_type"] or "").strip()
        opts = map_opts.get((key, asset))
        if opts is None:
            opts = {(key, 0)}
        if len(opts) != 1:
            continue
        base, part = next(iter(opts))
        collective_parts[(base, asset, str(r["b10"] or ""), norm_lot(r["ml_raw"]))].add(part)

    pending_tx = pending_rows = pending_groups = 0
    ledger_tx = ledger_rows = ledger_groups = 0
    title_tx = title_rows = title_groups = 0
    for gid, lots in unmatched_lots.items():
        group = matched_groups[gid]
        counts = lot_n(group)
        kinds = set()
        for ml in sorted(lots, key=lot_key):
            n = counts[ml]
            parts = collective_parts.get((gid[0], gid[1], gid[2], ml), set())
            if len(parts) == 1:
                part = next(iter(parts))
                out_rows.append(row_out(gid[0], gid[1], gid[2], ml, part, "split", "collective_ledger"))
                ledger_tx += n
                ledger_rows += 1
                kinds.add("ledger")
                continue
            ev = lot_evidence([r for r in group if r["ml"] == ml], False, False)
            e = ev[0] if ev else None
            part_sigs = defaultdict(set)
            for row in group:
                slot = (gid[0], gid[1], gid[2], row["ml"])
                part = part_of.get(slot)
                if part is None:
                    continue
                _pks, years, names = profile(titles_for(gid[2], row["ml"], "")[1])
                if len(years) == 1 and len(names) == 1:
                    part_sigs[part].add((next(iter(names)), next(iter(years))))
            sig = (e["name"], e["year"]) if e and e["clean"] and e["agrees"] else None
            owners = [p for p, sigs in part_sigs.items() if sig and sig in sigs and len(sigs) == 1]
            if sig and len(owners) == 1:
                out_rows.append(row_out(gid[0], gid[1], gid[2], ml, owners[0], "split", "title_register"))
                title_tx += n
                title_rows += 1
                kinds.add("title")
            else:
                out_rows.append(row_out(gid[0], gid[1], gid[2], ml, 0, "pending", ""))
                pending_tx += n
                pending_rows += 1
                kinds.add("pending")
        if "pending" in kinds:
            pending_groups += 1
        elif kinds == {"ledger"}:
            ledger_groups += 1
        elif "title" in kinds:
            title_groups += 1

    downgrade = one_sig_keep = conflict_groups = 0
    rent_split_groups = rent_split_pieces = rent_moved_tx = rent_part0_tx = rent_split_tx = 0
    rent_keep_na = rent_keep_da = rent_keep_reuse = 0
    keep48_na = keep48_da = 0
    rent_only_pending_rows = rent_only_pending_tx = 0
    for gid, group in candidate_groups.items():
        v4 = label_of(lot_evidence(group, True, False))
        strict_ev = lot_evidence(group, True, True)
        strict = label_of(strict_ev)
        is_keep48 = (gid[0], gid[2]) in keep
        if is_keep48:
            rent_keep_reuse += 1
            note = ""
            if strict == "가":
                conflict_groups += 1
                note = "conflict"
            elif strict == "다":
                keep48_da += 1
                note = "review"
            else:
                keep48_na += 1
            counts = lot_n(group)
            for ml in sorted(counts, key=lot_key):
                out_rows.append(row_out(gid[0], gid[1], gid[2], ml, 0, "keep", "collective_reuse", note))
            continue
        if v4 == "가" and strict == "다":
            downgrade += 1
        if v4 == "가" and strict == "나":
            one_sig_keep += 1
        counts = lot_n(group)
        if strict == "가":
            buckets = defaultdict(lambda: {"lots": [], "n": 0})
            for e in strict_ev:
                buckets[(e["name"], e["year"])]["lots"].append(e["ml"])
                buckets[(e["name"], e["year"])]["n"] += e["n"]
            pieces = sorted(buckets.values(), key=lambda p: (-p["n"], lot_key(min(p["lots"], key=lot_key))))
            part_of_sig = {}
            sig_by_part = {}
            for i, piece in enumerate(pieces):
                sig = next(sig for sig, b in buckets.items() if b is piece)
                part_of_sig[sig] = i
                sig_by_part[i] = sig
            rent_split_groups += 1
            rent_split_pieces += len(pieces)
            rent_split_tx += sum(counts.values())
            assigned = {}
            for e in strict_ev:
                assigned[e["ml"]] = part_of_sig[(e["name"], e["year"])]
            for ml, n in counts.items():
                if ml in assigned:
                    continue
                ev = lot_evidence([r for r in group if r["ml"] == ml], False, True)
                e = ev[0] if ev else None
                sig = (e["name"], e["year"]) if e and e["clean"] and e["agrees"] and e["name"] else None
                owners = [p for p, s in sig_by_part.items() if sig and s == sig]
                if sig and len(owners) == 1:
                    assigned[ml] = owners[0]
                else:
                    assigned[ml] = None
            for ml, n in counts.items():
                part = assigned[ml]
                if part is None:
                    out_rows.append(row_out(gid[0], gid[1], gid[2], ml, 0, "pending", ""))
                    rent_only_pending_rows += 1
                    rent_only_pending_tx += n
                else:
                    out_rows.append(row_out(gid[0], gid[1], gid[2], ml, part, "split", "title_register"))
                    if part != 0:
                        rent_moved_tx += n
                    else:
                        rent_part0_tx += n
        elif strict == "나":
            rent_keep_na += 1
            for ml in counts:
                out_rows.append(row_out(gid[0], gid[1], gid[2], ml, 0, "keep", "title_register"))
        else:
            rent_keep_da += 1
            for ml in counts:
                out_rows.append(row_out(gid[0], gid[1], gid[2], ml, 0, "keep", "", "review"))

    need_keys = {gid[0] for gid in matched_groups} | {
        gid[0] for gid, group in candidate_groups.items() if label_of(lot_evidence(group, True, True)) == "가" and (gid[0], gid[2]) not in keep
    }
    raw_rows, sec, err = None, None, None
    with rent_eng.connect() as conn:
        raw_rows, sec, err = timed(
            conn,
            """
            SELECT rtrim(building_key) AS building_key, asset_type,
                   addr1, addr2, addr3, addr4, building_name, lot_number, road_name,
                   count(*)::bigint AS n
            FROM rent_transactions
            WHERE is_valid AND asset_type IN ('apartment', 'rowhouse', 'officetel')
              AND building_key = ANY(CAST(:keys AS char(64)[]))
            GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
            """,
            {"keys": list(need_keys)},
        )
        timings.append({"id": "Q_raw", "seconds": sec, "error": err, "rows": 0 if raw_rows is None else len(raw_rows)})
    if raw_rows is None:
        raise SystemExit("raw recovery failed")
    by_key = defaultdict(list)
    for r in raw_rows:
        by_key[(str(r["building_key"]).strip(), str(r["asset_type"]).strip())].append(dict(r))
    c01 = load_split_units()

    def recover(key, asset):
        variants = by_key.get((key, asset), [])
        if not variants:
            return None
        frames = [pd.DataFrame(variants)]
        alt = []
        for row in variants:
            copied = dict(row)
            addr = copied.get("addr1")
            copied["addr1"] = LEGACY_SIDO_TO_CURRENT.get(addr, addr) if isinstance(addr, str) else addr
            alt.append(copied)
        frames.append(pd.DataFrame(alt))
        for frame in frames:
            raws = building_key_raw_series(frame, asset)
            for raw in raws.tolist():
                found = _key_raw_for(str(raw), key, c01)
                if found is not None:
                    return found
        return None

    raw_of = {}
    missing_raw = 0
    for key, asset in {(gid[0], gid[1]) for gid in matched_groups} | {
        (gid[0], gid[1])
        for gid in candidate_groups
        if label_of(lot_evidence(candidate_groups[gid], True, True)) == "가" and (gid[0], gid[2]) not in keep
    }:
        found = recover(key, asset)
        if found is None:
            missing_raw += 1
        else:
            raw_of[(key, asset)] = found

    equal_parts = differ_parts = ambiguous_c2 = no_c2_map = 0
    checked_groups = set()
    for key, asset, b10, ml, part, decision in unit_rows:
        if decision != "split" or part == 0 or (key, asset, b10) not in matched_groups:
            continue
        checked_groups.add((key, asset, b10))
        raw = raw_of.get((key, asset))
        if raw is None:
            differ_parts += 1
            continue
        expected = c2_key(raw, f"p{part}")
        got = map_c2.get((key, asset, part), set())
        if len(got) == 1 and next(iter(got)) == expected:
            equal_parts += 1
        elif len(got) > 1:
            ambiguous_c2 += 1
        elif len(got) == 1:
            differ_parts += 1
        else:
            no_c2_map += 1

    def piece_key(key, asset, part):
        if int(part) == 0:
            return key
        raw = raw_of.get((key, asset))
        if raw is None:
            return None
        return c2_key(raw, f"p{int(part)}")

    pk_count = defaultdict(int)
    assets_for_base = defaultdict(set)
    bjd_for_nz = defaultdict(set)
    split_parts = defaultdict(set)
    assets_for_piece = defaultdict(set)
    bases_for_piece = defaultdict(set)
    bjd_for_piece = defaultdict(set)
    for r in out_rows:
        pk_count[(r["base_key"], r["asset_type"], r["beopjungri_code"], r["main_lot"])] += 1
        assets_for_base[r["base_key"]].add(r["asset_type"])
        if r["decision"] == "split":
            split_parts[(r["base_key"], r["beopjungri_code"])].add(int(r["part"]))
            if int(r["part"]) != 0:
                bjd_for_nz[(r["base_key"], int(r["part"]))].add(r["beopjungri_code"])
        pk = piece_key(r["base_key"], r["asset_type"], r["part"])
        if pk and int(r["part"]) != 0 and r["decision"] == "split":
            assets_for_piece[pk].add(r["asset_type"])
            bases_for_piece[pk].add(r["base_key"])
            bjd_for_piece[(pk, int(r["part"]))].add(r["beopjungri_code"])
    pk_dup = sum(1 for n in pk_count.values() if n > 1)
    base_multi_asset = sum(1 for a in assets_for_base.values() if len(a) > 1)
    nz_multi_bjd = sum(1 for b in bjd_for_nz.values() if len(b) > 1)
    missing_part0 = sum(1 for parts in split_parts.values() if 0 not in parts)
    piece_multi_asset = sum(1 for a in assets_for_piece.values() if len(a) > 1)
    piece_multi_base = sum(1 for b in bases_for_piece.values() if len(b) > 1)
    piece_multi_bjd = sum(1 for b in bjd_for_piece.values() if len(b) > 1)

    matched_gids = set(matched_groups)
    new_keys = set()
    reused_piece_keys = set()
    for r in out_rows:
        if r["decision"] != "split" or int(r["part"]) == 0:
            continue
        pk = piece_key(r["base_key"], r["asset_type"], r["part"])
        if not pk:
            continue
        gid = (r["base_key"], r["asset_type"], r["beopjungri_code"])
        if gid in matched_gids:
            reused_piece_keys.add(pk)
        else:
            new_keys.add(pk)
    overlap = {"rent": None, "collective": None}
    if new_keys:
        sql = """
            SELECT count(DISTINCT rtrim(building_key))::bigint AS n
            FROM {table}
            WHERE rtrim(building_key) = ANY(CAST(:keys AS text[]))
        """
        with rent_eng.connect() as conn:
            rows, sec, err = timed(conn, sql.format(table="rent_transactions"), {"keys": list(new_keys)})
            timings.append({"id": "Q_overlap_rent", "seconds": sec, "error": err})
            overlap["rent"] = None if err or not rows else int(rows[0]["n"])
        with col_eng.connect() as conn:
            rows, sec, err = timed(conn, sql.format(table="collective_transactions"), {"keys": list(new_keys)})
            timings.append({"id": "Q_overlap_collective", "seconds": sec, "error": err})
            overlap["collective"] = None if err or not rows else int(rows[0]["n"])

    summary = {
        "matched_groups": len(matched_groups),
        "rent_only_groups": len(candidate_groups),
        "unmatched_tx": unmatched_tx,
        "unmatched_groups": len(unmatched_lots),
        "keep48": rent_keep_reuse,
        "ambiguous_map_keys": ambiguous_map_keys,
        "ambiguous_c2_slots": len(ambiguous_part),
        "copied_split_rows": sum(1 for r in out_rows if r["evidence"] == "collective_reuse" and r["decision"] == "split"),
        "ledger_rows": ledger_rows,
        "ledger_tx": ledger_tx,
        "ledger_groups_all_lots": ledger_groups,
        "title_rows": title_rows,
        "title_tx": title_tx,
        "title_groups": title_groups,
        "pending_rows_matched": pending_rows,
        "pending_tx_matched": pending_tx,
        "pending_groups_matched": pending_groups,
        "downgrade_ga_to_da": downgrade,
        "one_signature_keep": one_sig_keep,
        "keep48_conflict_ga": conflict_groups,
        "rent_split_groups": rent_split_groups,
        "rent_split_pieces": rent_split_pieces,
        "rent_moved_tx": rent_moved_tx,
        "rent_part0_tx": rent_part0_tx,
        "rent_split_tx": rent_split_tx,
        "keep48_na": keep48_na,
        "keep48_da": keep48_da,
        "rent_keep_na": rent_keep_na,
        "rent_keep_da": rent_keep_da,
        "rent_keep_reuse": rent_keep_reuse,
        "rent_only_pending_rows": rent_only_pending_rows,
        "rent_only_pending_tx": rent_only_pending_tx,
        "key_equal_parts": equal_parts,
        "key_differ_parts": differ_parts,
        "key_ambiguous_c2_parts": ambiguous_c2,
        "key_no_c2_map_parts": no_c2_map,
        "key_checked_groups": len(checked_groups),
        "missing_raw": missing_raw,
        "pk_dup": pk_dup,
        "base_multi_asset": base_multi_asset,
        "nz_part_multi_bjd": nz_multi_bjd,
        "split_missing_part0": missing_part0,
        "piece_multi_asset": piece_multi_asset,
        "piece_multi_base": piece_multi_base,
        "piece_multi_bjd": piece_multi_bjd,
        "new_piece_keys": len(new_keys),
        "new_keys_also_reused_piece": len(new_keys & reused_piece_keys),
        "overlap_rent": overlap["rent"],
        "overlap_collective": overlap["collective"],
        "rows": len(out_rows),
        "timings": timings,
    }
    blocked = differ_parts > 0 or any(
        timings and t.get("seconds") is not None and t["seconds"] > 300 for t in timings
    )
    summary["blocked"] = blocked
    if not blocked and pk_dup == 0:
        digest = write_units_csv(out_rows, OUT_CSV)
        summary["N_r"] = len(out_rows)
        summary["H_r"] = digest
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "timings"}, ensure_ascii=False))
    for t in timings:
        print(t["id"], t["seconds"], t.get("error"))
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
