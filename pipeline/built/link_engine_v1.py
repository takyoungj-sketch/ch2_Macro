"""Plan step 8: composite contract rows for a version definition, for all keys or a key subset.

A version definition fixes the inputs: register editions (title/summary caches), land trait releases
(slim asof bits up to a cut-off) and the transaction key universe. A transaction's result depends only
on its own ledger row and those inputs, never on other transactions, so a full build and an incremental
recompute of the affected keys must give the same rows. That is what the step 8 tests check.

Rules are those of steps 4-C (matching, time_fallback), 4-D (zone at contract time), 4-E (management key
and building attributes) and 7 (contract shape), with three points made explicit for versioning:
  - a tie decision reads each candidate's register row from the edition the transaction used
    (4-E read whichever stored version came last);
  - the register-kind flag looks only at editions inside the definition;
  - a second zone at the contract-time base is kept (zone2_contract_year, zone_count_contract_year).
    ENGINE_V2 (D-078): the first zone stays the representative and keeps its normal use_approved; multi-zone
    is identified by zone_count_contract_year = 2, not by a hold flag. ENGINE_V1 held it (use_approved 0,
    hold flag multi_zone_contract_year).
Read-only on every source. Writes only to the SQLite path it is given.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "backend"))

from built.build_link_contract_shadow_v1 import (  # noqa: E402
    DIGEST_SQL, RULE_VERSION, SQLITE_DDL, VARIABLES, build, nn, zone_labels,
)
from built.db_utils import get_built_engine  # noqa: E402
from built.measure_link_quality_v1 import SIDOS  # noqa: E402
from built.measure_zone_asof_v1 import EMPTY_LABELS, classify, latest, next_base_check, pnus  # noqa: E402
from built.recover_address import CACHE, GROSS_TOL, PRIMARY, TX_SQL, build_parcels, lot_str, match_all, to_f, to_i  # noqa: E402
from built.register_ledger import connect as ledger_connect  # noqa: E402
from built.replay_enrichment_land_supply import INT64_MAX, SLIM  # noqa: E402
from built.replay_honam_bridge import BRIDGED, load_bridge  # noqa: E402
from built.resolve_tied_bldrgst_pk_v1 import RAW, building_attrs, decide  # noqa: E402
from built.snapshot_policy import apply_snapshot_policy  # noqa: E402

ENGINE_RULE = RULE_VERSION + "+ENGINE_V2"
ZONE_EXTRA = ("zone2_contract_year", "zone_count_contract_year")
VARIABLES_V11 = VARIABLES + ZONE_EXTRA
ALL_SNAPSHOTS = ("2024-09", "2025-07", "2026-07")
NO_SIDO = "none"

DEPS_DDL = """
CREATE TABLE ledger_link_deps_v1 (
    target_key TEXT PRIMARY KEY, sido TEXT NOT NULL, bjd TEXT, contract_year INTEGER, contract_month INTEGER,
    in_matching INTEGER NOT NULL, snapshot_used TEXT, snapshot_via TEXT, tier TEXT, n_exact INTEGER,
    parcel TEXT, match_pk TEXT, zone_status TEXT, zone_base TEXT, zone_stability TEXT, latest_zone1 TEXT,
    slim_land REAL, pnus TEXT
);
CREATE TABLE ledger_link_orphan_v1 (
    target_key TEXT PRIMARY KEY, orphaned_in TEXT NOT NULL, classification TEXT NOT NULL,
    header_json TEXT NOT NULL, values_json TEXT NOT NULL, parcel TEXT
);
CREATE TABLE ledger_link_change_v1 (
    target_key TEXT NOT NULL, change TEXT NOT NULL, causes TEXT NOT NULL, prev_digest TEXT, new_digest TEXT,
    PRIMARY KEY (target_key)
);
CREATE TABLE version_info (k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""

HEADER_COLS = ("domain", "target_kind", "target_key", "link_state", "link_reason", "link_level", "parcel_resolved",
               "building_id_state", "bldrgst_pk", "candidate_count", "hold_flags", "code_resolution",
               "register_snapshot", "register_after_contract", "trait_asof", "rule_version", "unverified",
               "verification_basis", "computed_cycle", "source_digest")
VALUE_COLS = ("target_key", "variable", "value_num", "value_text", "value_state", "value_level", "source",
              "basis_date", "timing", "change_risk", "use_approved")
DEPS_COLS = ("target_key", "sido", "bjd", "contract_year", "contract_month", "in_matching", "snapshot_used",
             "snapshot_via", "tier", "n_exact", "parcel", "match_pk", "zone_status", "zone_base", "zone_stability",
             "latest_zone1", "slim_land", "pnus")


@dataclass(frozen=True)
class Defn:
    """Inputs of one version. land_bits: highest slim asof bit included (None = every release)."""
    snapshots: tuple[str, ...] = ALL_SNAPSHOTS
    land_bits: int | None = None
    cycle: str = "202610"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Defn":
        return Defn(tuple(d["snapshots"]), d["land_bits"], d["cycle"])


# ---------------------------------------------------------------- land trait view

class SlimView:
    """Slim observations as seen through a release cut-off. Rows from later releases are dropped and
    the asof mask is cut, so ranking by latest release works as if those releases never arrived."""

    def __init__(self, land_bits: int | None):
        self.db = sqlite3.connect(SLIM.resolve().as_uri() + "?mode=ro", uri=True)
        self.db.execute("PRAGMA query_only=ON")
        self.db.execute("PRAGMA cache_size=-500000")
        self.allowed = None if land_bits is None else (1 << (land_bits + 1)) - 1

    def raw(self, pnu: int) -> list[tuple]:
        return self.db.execute(
            "SELECT price_year, price_month, asof_mask, conflict_mask, jimok_code, area, zone1_code, zone2_code"
            " FROM observation WHERE pnu=?", (pnu,)
        ).fetchall()

    @staticmethod
    def view(raw: list[tuple], allowed: int | None) -> list[tuple]:
        out = []
        for y, m, a, c, jimok, area, z1, z2 in raw:
            if allowed is not None:
                if not ((a | c) & allowed):
                    continue
                a &= allowed
            out.append((y, m, a, jimok, area, z1, z2))
        return out

    def rows(self, pnu: int) -> list[tuple]:
        return self.view(self.raw(pnu), self.allowed)


def land_from_rows(rows: list[tuple]) -> float | None:
    """Same choice as replay_enrichment_land_supply.slim_land: latest release, then base date; 대 only."""
    best = None
    for y, m, a, jimok, area, _, _ in rows:
        rank = (a.bit_length(), y, m)
        if best is None or rank > best[0]:
            best = (rank, jimok, area)
    if best and best[1] == "08":
        v = to_f(best[2])
        if v == v:
            return v
    return None


def parcel_pnu(bjd10: str, bun: int, ji: int, translate: dict | None) -> int | None:
    if not (len(bjd10) == 10 and bjd10.isdigit()) or bun > 9999 or ji > 9999:
        return None
    lookup = translate.get(bjd10) if translate is not None else bjd10
    if not lookup:
        return None
    pnu = int(f"{lookup}1{bun:04d}{ji:04d}")
    return pnu if pnu <= INT64_MAX else None


def slim_land(slim: SlimView, keys: set, translate: dict | None) -> dict[tuple[str, str], float]:
    out = {}
    for bjd10, bun, ji in sorted(keys):
        pnu = parcel_pnu(bjd10, bun, ji, translate)
        if pnu is None:
            continue
        v = land_from_rows(slim.rows(pnu))
        if v is not None:
            out[(bjd10, lot_str(bun, ji))] = v
    return out


def zone_bases(slim: SlimView, keys: list[int]) -> dict:
    b: dict = defaultdict(set)
    for pnu in keys:
        for y, m, _, _, _, z1, z2 in slim.rows(pnu):
            b[(int(y), int(m))].add((z1, z2))
    return b


def zone_fields(b: dict, year: int, month: int, labels: dict) -> tuple:
    """measure_zone_asof_v1 per-row logic: status, why, zone1, zone2, base, base_after, stability, latest."""
    cz = classify(b, year, month)
    lt = latest(b)
    label = labels.get(cz["zone"], "") if cz.get("zone") else ""
    if cz["status"] != "unknown" and not label:
        cz = {"status": "unknown", "why": "zone_code_empty", "obs": cz["obs"]}
    stability = None
    if label and cz["status"] != "adjacent_after":
        stability = next_base_check(b, cz["obs"][0], cz["zone"])
    obs = cz.get("obs") or []
    return (cz["status"], cz.get("why"), cz.get("zone"), cz.get("zone2"),
            f"{obs[0][0]}-{obs[0][1]:02d}-01" if obs else None,
            f"{obs[-1][0]}-{obs[-1][1]:02d}-01" if len(obs) > 1 else None, stability,
            lt[0] if lt else None, lt[1] if lt else None)


# ---------------------------------------------------------------- register editions

def edition_rows(ledger: sqlite3.Connection, snap: str, pks: list[str]) -> dict[str, bytes]:
    out = {}
    for i in range(0, len(pks), 900):
        chunk = pks[i:i + 900]
        q = ("SELECT o.pk, v.raw FROM title_observation o JOIN title_version v ON v.pk = o.pk AND v.raw_hash = o.raw_hash"
             f" WHERE o.snapshot = ? AND o.pk IN ({','.join('?' * len(chunk))})")
        for pk, raw in ledger.execute(q, [snap, *chunk]):
            out[pk] = raw
    return out


def register_kinds(ledger: sqlite3.Connection, pks: list[str], snaps: tuple[str, ...]) -> dict[str, str]:
    seen: dict[str, set] = defaultdict(set)
    for snap in snaps:
        for pk, raw in edition_rows(ledger, snap, pks).items():
            code = raw.split(b"|", 2)[1].strip()
            seen[pk].add({b"1": "일반", b"2": "집합"}.get(code, "기타"))
    return {pk: (next(iter(v)) if len(v) == 1 else "변경") for pk, v in seen.items()}


def attrs_at(ledger: sqlite3.Connection, snap: str, pks: list[str]) -> dict[str, dict]:
    out = {}
    for pk, raw in edition_rows(ledger, snap, pks).items():
        p = raw.decode("cp949", errors="replace").split("|")
        if len(p) > max(RAW.values()):
            out[pk] = {k: p[i].strip() for k, i in RAW.items()}
    return out


# ---------------------------------------------------------------- one sido

def _title_key(t: pd.DataFrame) -> pd.Series:
    return (t["sigungu_code"].str.strip() + t["bjd_code"].str.strip() + "|"
            + t["bun"].map(lambda b: str(to_i(b))) + t["ji"].map(lambda j: f"-{to_i(j)}" if to_i(j) else ""))


def tied_from_title(t: pd.DataFrame, parcels: set[str]) -> dict:
    """resolve_tied_bldrgst_pk_v1.tied_buildings on an already loaded edition."""
    key = _title_key(t)
    t = t[key.isin(parcels)].assign(parcel=key[key.isin(parcels)])
    out = defaultdict(list)
    for r in t.itertuples(index=False):
        out[r.parcel].append({
            "pk": r.pk.strip(), "gross": to_f(r.gross_area), "struct": r.struct_name.strip(),
            "use": r.use_name.strip(), "floors": r.floors_above.strip(), "approve": r.approve_date.strip()[:4],
        })
    return out


def compute_sido(sido: str, defn: Defn, keys: list[str] | None) -> dict:
    """Matching, management key, building attributes and zone for one sido. keys=None: every key."""
    eng = get_built_engine()
    with eng.connect() as c:
        tx = pd.read_sql(text(TX_SQL), c, params={"sido_like": f"{sido}%", "min_year": 2019})
    if keys is not None:
        tx = tx[tx["transaction_hash"].isin(set(keys))]
    tx = tx.sort_values("id").reset_index(drop=True)
    if tx.empty:
        return {"rows": pd.DataFrame(), "zone": pd.DataFrame(), "pk": pd.DataFrame(), "attr": pd.DataFrame()}
    folder = BRIDGED if sido == "12" else CACHE
    bridge = load_bridge()
    translate = bridge if sido == "12" else None
    slim = SlimView(defn.land_bits)
    ledger = ledger_connect()
    bjds = set(tx["beopjungri_code"].fillna("").astype(str).str.strip())
    titles, summs = {}, {}
    for snap in defn.snapshots:
        t = pd.read_csv(folder / f"title_{sido}_{snap}.csv", dtype=str, keep_default_na=False)
        s = pd.read_csv(folder / f"summary_{sido}_{snap}.csv", dtype=str, keep_default_na=False)
        titles[snap] = t[(t["sigungu_code"].str.strip() + t["bjd_code"].str.strip()).isin(bjds)].reset_index(drop=True)
        summs[snap] = s[(s["sigungu_code"].str.strip() + s["bjd_code"].str.strip()).isin(bjds)].reset_index(drop=True)
    keyset = set()
    for t in titles.values():
        for sg, bd, b, j in zip(t["sigungu_code"], t["bjd_code"], t["bun"], t["ji"]):
            bun = to_i(b)
            if bun is not None:
                keyset.add((sg.strip() + bd.strip(), bun, to_i(j) or 0))
    land = slim_land(slim, keyset, translate)
    results = {}
    for snap in defn.snapshots:
        parcels, idx = build_parcels(titles[snap], summs[snap], land)
        results[snap] = match_all(tx, parcels, idx)
    res = apply_snapshot_policy(results, policy="time_fallback", primary=PRIMARY)
    res["sido"] = sido
    res["slim_land"] = res["parcel"].map(
        lambda p: land.get(tuple(p.split("|")), math.nan) if isinstance(p, str) else math.nan
    )
    kinds = register_kinds(ledger, sorted(set(res["bldrgst_pk"].dropna())), defn.snapshots)
    res["register"] = [
        (kinds.get(pk, "원장없음") if isinstance(pk, str) else "동률") if isinstance(t, str) else None
        for pk, t in zip(res["bldrgst_pk"], res["tier"])
    ]
    # management key and attributes (4-E)
    linked = res[res["tier"].notna()]
    decided: dict = {}
    attr_rows: list = []
    for snap, g_all in linked.groupby("snapshot_used"):
        b = tied_from_title(titles[snap], set(g_all["parcel"]))
        g = g_all[g_all["register"] == "동률"]
        cand_by_hash = {}
        for r in g.itertuples(index=False):
            blds = [x for x in b.get(r.parcel, []) if not math.isnan(x["gross"])]
            if not blds:
                cand_by_hash[r.transaction_hash] = []
                continue
            near = min(abs(x["gross"] - r.gross_area) for x in blds)
            cand_by_hash[r.transaction_hash] = [
                x["pk"] for x in blds if abs(abs(x["gross"] - r.gross_area) - near) <= 1e-9 and near <= GROSS_TOL
            ]
        attrs = attrs_at(ledger, snap, sorted({pk for c in cand_by_hash.values() for pk in c}))
        for r in g.itertuples(index=False):
            cands = cand_by_hash[r.transaction_hash]
            if not cands:
                decided[r.transaction_hash] = (None, "held_no_candidates", 0, "")
                continue
            ym = int(r.contract_year) * 100 + int(r.contract_month or 12)
            pk, rule, hints = decide(cands, attrs, ym)
            decided[r.transaction_hash] = (pk, rule, len(set(cands)), ",".join(hints))
        attr_rows.extend(building_attrs(g_all, b, cand_by_hash, decided))
    pk_rows = []
    for r in linked.itertuples(index=False):
        pk, rule, n, _ = decided.get(r.transaction_hash, (r.bldrgst_pk, "unique_nearest", 1, ""))
        pk_rows.append((r.transaction_hash, pk, rule, n))
    # zone at contract time (4-D)
    labels = zone_labels()
    zrows = []
    for r in linked.itertuples(index=False):
        keys_p = pnus(r.parcel, bridge)
        b = zone_bases(slim, keys_p)
        zrows.append((r.transaction_hash, *zone_fields(b, int(r.contract_year), int(r.contract_month or 0), labels),
                      ",".join(str(k) for k in keys_p)))
    return {
        "rows": res[["transaction_hash", "sido", "asset_type", "contract_year", "contract_month", "tier", "fail",
                     "parcel", "bldrgst_pk", "register", "n_exact", "snapshot_used", "snapshot_via", "gross_area",
                     "slim_land"]].assign(bjd=tx.set_index("transaction_hash").reindex(res["transaction_hash"])
                                          ["beopjungri_code"].fillna("").astype(str).str.strip().values),
        "zone": pd.DataFrame(zrows, columns=["transaction_hash", "status", "why", "zone1_code", "zone2_code",
                                             "base_date", "base_date_after", "stability", "latest_year",
                                             "latest_zone1_code", "pnus"]),
        "pk": pd.DataFrame(pk_rows, columns=["transaction_hash", "bldrgst_pk", "rule", "n_candidates"]),
        "attr": pd.DataFrame(attr_rows, columns=["transaction_hash", "identification", "struct", "use", "floors",
                                                 "approve", "struct_conflict", "use_conflict", "floors_conflict",
                                                 "approve_conflict"]),
    }


# ---------------------------------------------------------------- compose

def zone2_labels() -> dict[str, str]:
    with sqlite3.connect(f"file:{SLIM}?mode=ro", uri=True) as db:
        out = {}
        for code, label in db.execute(
            "SELECT code, label FROM code_dictionary WHERE field = 'zone2' AND is_standard = 1 ORDER BY code"
        ):
            if label not in EMPTY_LABELS and code not in out:
                out[code] = label
        return out


def compose(ledger_rows: pd.DataFrame, parts: dict, defn: Defn) -> tuple[list, list, list]:
    """Contract rows (step 7 builder) plus the two zone variables and the dependency record."""
    empty = {
        "rows": ["transaction_hash", "tier", "fail", "snapshot_used", "register", "sido", "contract_year",
                 "contract_month", "slim_land", "parcel", "bldrgst_pk", "n_exact", "snapshot_via", "bjd"],
        "zone": ["transaction_hash", "status", "why", "zone1_code", "zone2_code", "base_date", "base_date_after",
                 "stability", "latest_year", "latest_zone1_code", "pnus"],
        "pk": ["transaction_hash", "bldrgst_pk", "rule", "n_candidates"],
        "attr": ["transaction_hash", "identification", "struct", "use", "floors", "approve", "struct_conflict",
                 "use_conflict", "floors_conflict", "approve_conflict"],
    }
    rows, zone, pk, attr = (parts[k] if len(parts[k]) else pd.DataFrame(columns=empty[k])
                            for k in ("rows", "zone", "pk", "attr"))
    headers, values = build(ledger_rows, rows, zone.drop(columns=["zone2_code", "pnus"]), pk, attr, zone_labels())
    labels2 = zone2_labels()
    z = zone.set_index("transaction_hash").to_dict("index") if not zone.empty else {}
    by_key: dict[str, dict] = defaultdict(dict)
    for v in values:
        by_key[v[0]][v[1]] = v
    hdr_out = []
    for h in headers:
        h = list(h)
        h[18] = defn.cycle
        h[15] = ENGINE_RULE
        key = h[2]
        if h[3] != "not_applicable":
            zc = by_key[key]["zone_contract_year"]
            z2 = labels2.get(str(nn(z.get(key, {}).get("zone2_code")) or ""), "") if zc[4] == "confirmed" else ""
            if zc[4] == "confirmed":
                if z2:
                    by_key[key]["zone2_contract_year"] = (key, "zone2_contract_year", None, z2, "confirmed", "parcel",
                                                          zc[6], zc[7], zc[8], zc[9], 0)
                else:
                    by_key[key]["zone2_contract_year"] = (key, "zone2_contract_year", None, None, "source_missing",
                                                          "parcel", zc[6], zc[7], zc[8], "none", 0)
                by_key[key]["zone_count_contract_year"] = (key, "zone_count_contract_year", 2.0 if z2 else 1.0, None,
                                                           "confirmed", "parcel", zc[6], zc[7], zc[8], zc[9], 0)
            else:
                for var in ZONE_EXTRA:
                    by_key[key][var] = (key, var, None, None, zc[4], "parcel", zc[6], None, None, "none", 0)
        hdr_out.append(tuple(h))
    val_out = [v for key in sorted(by_key) for var, v in sorted(by_key[key].items())]
    m = rows.set_index("transaction_hash").to_dict("index") if not rows.empty else {}
    deps = []
    for r in ledger_rows.itertuples(index=False):
        k = r.transaction_hash
        mr, zr = m.get(k), z.get(k, {})
        sido = r.sido
        if mr is None:
            deps.append((k, sido, r.beopjungri_code, r.contract_year, r.contract_month, 0) + (None,) * 12)
            continue
        deps.append((
            k, sido, mr["bjd"], int(mr["contract_year"]), nn(mr["contract_month"]) and int(mr["contract_month"]), 1,
            nn(mr["snapshot_used"]), nn(mr["snapshot_via"]), nn(mr["tier"]), nn(mr["n_exact"]) and int(mr["n_exact"]),
            nn(mr["parcel"]), nn(mr["bldrgst_pk"]), nn(zr.get("status")), nn(zr.get("base_date")),
            nn(zr.get("stability")), nn(zr.get("latest_zone1_code")),
            None if nn(mr["slim_land"]) is None else float(mr["slim_land"]), nn(zr.get("pnus")),
        ))
    return hdr_out, val_out, deps


# ---------------------------------------------------------------- build

def ledger_universe(keys_exclude: set[str] | None = None, sidos: tuple[str, ...] | None = None,
                    max_ym: int | None = None) -> pd.DataFrame:
    with get_built_engine().connect() as c:
        df = pd.read_sql(text(DIGEST_SQL), c)
    df["sido"] = df["sigungu_code"].fillna("").str[:2].replace("", NO_SIDO)
    if sidos is not None:
        df = df[df["sido"].isin(sidos)]
    if keys_exclude:
        df = df[~df["transaction_hash"].isin(keys_exclude)]
    if max_ym is not None:
        ym = df["contract_year"] * 100 + df["contract_month"].fillna(12)
        df = df[ym <= max_ym]
    return df.reset_index(drop=True)


def _worker(args):
    sido, defn_d, keys = args
    return sido, compute_sido(sido, Defn.from_dict(defn_d), keys)


def compute(ledger_rows: pd.DataFrame, defn: Defn, workers: int = 6) -> tuple[list, list, list, dict]:
    """Rows for exactly the keys in ledger_rows. Keys outside SIDOS get header rows only."""
    tasks = []
    for sido, g in ledger_rows.groupby("sido"):
        if sido in SIDOS:
            tasks.append((sido, defn.to_dict(), g["transaction_hash"].tolist()))
    parts = defaultdict(list)
    timing = {}
    if tasks:
        with ProcessPoolExecutor(max_workers=min(workers, len(tasks))) as ex:
            for sido, p in ex.map(_worker, tasks):
                for k, v in p.items():
                    if len(v):
                        parts[k].append(v)
                timing[sido] = len(p["rows"])
    merged = {k: (pd.concat(parts[k], ignore_index=True) if parts[k] else pd.DataFrame())
              for k in ("rows", "zone", "pk", "attr")}
    h, v, d = compose(ledger_rows, merged, defn)
    return h, v, d, {"matched_rows": int(len(merged["rows"])), "by_sido": timing}


def write_version(path: Path, headers: list, values: list, deps: list, info: dict) -> None:
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.executescript(SQLITE_DDL)
    db.executescript(DEPS_DDL)
    db.executemany(f"INSERT INTO ledger_link_header_v1 VALUES ({','.join('?' * 20)})", sorted(headers, key=lambda x: x[2]))
    db.executemany(f"INSERT INTO ledger_link_value_v1 VALUES ('built',{','.join('?' * 11)})", values)
    db.executemany(f"INSERT INTO ledger_link_deps_v1 VALUES ({','.join('?' * 18)})", sorted(deps))
    db.executemany("INSERT INTO version_info VALUES (?,?)",
                   [(k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) for k, v in info.items()])
    db.commit()
    db.close()


def counts(headers: list) -> dict:
    return dict(Counter(h[3] for h in headers))
