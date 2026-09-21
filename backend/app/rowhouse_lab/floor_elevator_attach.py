"""표제부 승용·비상 승강기 수 — 실험용 부착.

제품 `building` 스키마는 바꾸지 않는다. 원본 77열 [45]·[46]을 표본 행으로 검증한 뒤
적격 building_key 의 PNU에만 붙인다. 전수 웹검색 금지.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_PIPELINE = Path(__file__).resolve().parents[3] / "pipeline"
if str(_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_PIPELINE))

from parcel_master.paths import TITLE_COLS, title_path  # noqa: E402
from parcel_master.pnu import pnu_from_title_parts, pnu_from_tx  # noqa: E402
from parcel_master.title_fill import is_ancillary_only, is_rowhouse_dong  # noqa: E402

from app.rowhouse_lab.floor_elevator import (  # noqa: E402
    TITLE_EMGEN_ELVT_COL,
    TITLE_RIDE_ELVT_COL,
    elevator_from_counts,
)

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "docs" / "lab" / "rowhouse_elevator_title_cache.json"
CSV_OUT = ROOT / "docs" / "lab" / "rowhouse_elevator_attach.csv"
SNAPSHOT_DEFAULT = "2026-07"
NEED = TITLE_EMGEN_ELVT_COL


def _int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def title_index_ok(parts: list[str]) -> bool:
    """지상층[43]이 층수 범위, [45]·[46]이 작은 정수인지."""
    if len(parts) <= NEED:
        return False
    fl = _int(parts[TITLE_COLS["floors_above"]])
    ug = _int(parts[TITLE_COLS["floors_below"]]) or 0
    ride = _int(parts[TITLE_RIDE_ELVT_COL])
    emgen = _int(parts[TITLE_EMGEN_ELVT_COL])
    if fl is None or not (1 <= fl <= 80):
        return False
    if ug < 0 or ug > 20:
        return False
    if ride is None or emgen is None:
        return False
    if ride < 0 or emgen < 0 or ride > 30 or emgen > 30:
        return False
    return True


def parse_title_elvt(parts: list[str]) -> dict[str, Any] | None:
    if not title_index_ok(parts):
        return None
    pnu = pnu_from_title_parts(
        parts[TITLE_COLS["sigungu_code"]],
        parts[TITLE_COLS["bjd_code"]],
        parts[TITLE_COLS["plat_gb"]],
        parts[TITLE_COLS["bun"]],
        parts[TITLE_COLS["ji"]],
    )
    if not pnu:
        return None
    ride = _int(parts[TITLE_RIDE_ELVT_COL]) or 0
    emgen = _int(parts[TITLE_EMGEN_ELVT_COL]) or 0
    return {
        "pnu": pnu,
        "ledger_kind": (parts[TITLE_COLS["ledger_kind"]] or "").strip(),
        "main_purpose": (parts[TITLE_COLS["main_purpose"]] or "").strip(),
        "purpose_detail": (parts[TITLE_COLS["purpose_detail"]] or "").strip(),
        "dong_name": (parts[TITLE_COLS["dong_name"]] or "").strip(),
        "floors_above": _int(parts[TITLE_COLS["floors_above"]]),
        "ride": ride,
        "emgen": emgen,
        "elevator": bool(elevator_from_counts(ride, emgen)),
    }


def probe_title_indices(path: Path, *, n: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            rec = parse_title_elvt(parts)
            if rec is None or rec["ledger_kind"] != "집합":
                continue
            if not is_rowhouse_dong(rec["main_purpose"], rec["purpose_detail"]):
                continue
            out.append(
                {
                    "pnu": rec["pnu"],
                    "floors_above": rec["floors_above"],
                    "ride": rec["ride"],
                    "emgen": rec["emgen"],
                    "purpose_detail": rec["purpose_detail"][:40],
                }
            )
            if len(out) >= n:
                break
    return out


def pnu_mode_by_building(tx_rows: list[dict[str, Any]]) -> dict[str, str]:
    bj: dict[str, Counter[str]] = defaultdict(Counter)
    lot: dict[str, Counter[str]] = defaultdict(Counter)
    for r in tx_rows:
        k = str(r.get("building_key") or "").strip()
        if not k:
            continue
        b = str(r.get("beopjungri_code") or "").strip()
        lo = str(r.get("lot_number") or "").strip()
        if b:
            bj[k][b] += 1
        if lo:
            lot[k][lo] += 1
    out: dict[str, str] = {}
    for k in set(bj) | set(lot):
        b = bj[k].most_common(1)[0][0] if bj[k] else None
        lo = lot[k].most_common(1)[0][0] if lot[k] else None
        pnu = pnu_from_tx(b, lo)
        if pnu:
            out[k] = pnu
    return out


def aggregate_pnu_elevator(rows: list[dict[str, Any]]) -> dict[str, Any]:
    housing = [r for r in rows if is_rowhouse_dong(r.get("main_purpose"), r.get("purpose_detail"))]
    if not housing:
        housing = [
            r
            for r in rows
            if not is_ancillary_only(r.get("main_purpose"), r.get("purpose_detail"))
        ]
    if not housing:
        return {
            "elevator": None,
            "ride": None,
            "emgen": None,
            "n_dongs": 0,
            "mixed": False,
            "floors_above": None,
            "reason": "no_housing",
        }
    flags = [bool(r.get("elevator")) for r in housing]
    mixed = any(flags) and not all(flags)
    ride = sum(int(r.get("ride") or 0) for r in housing)
    emgen = sum(int(r.get("emgen") or 0) for r in housing)
    floors = [int(r["floors_above"]) for r in housing if r.get("floors_above") is not None]
    if mixed:
        return {
            "elevator": None,
            "ride": ride,
            "emgen": emgen,
            "n_dongs": len(housing),
            "mixed": True,
            "floors_above": max(floors) if floors else None,
            "reason": "mixed",
        }
    return {
        "elevator": any(flags),
        "ride": ride,
        "emgen": emgen,
        "n_dongs": len(housing),
        "mixed": False,
        "floors_above": max(floors) if floors else None,
        "reason": "",
    }


def scan_title_for_pnus(
    pnus: set[str],
    *,
    snapshot: str = SNAPSHOT_DEFAULT,
    cache_path: Path = CACHE,
    refresh: bool = False,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not pnus:
        return {}, {"ok": False, "reason": "no_pnu"}
    src = title_path(snapshot)
    meta: dict[str, Any] = {
        "ok": True,
        "snapshot": snapshot,
        "path": str(src),
        "n_pnu_want": len(pnus),
    }
    if cache_path.exists() and not refresh:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        if raw.get("snapshot") == snapshot and set(raw.get("want") or []) == pnus:
            rows_by = {k: v for k, v in (raw.get("rows_by_pnu") or {}).items()}
            meta["from_cache"] = True
            meta["n_pnu_hit"] = len(rows_by)
            meta["sample"] = raw.get("sample") or []
            return rows_by, meta
    if not src.exists():
        meta["ok"] = False
        meta["reason"] = "no_title_file"
        return {}, meta
    sample = probe_title_indices(src)
    if len(sample) < 3:
        meta["ok"] = False
        meta["reason"] = "index_probe_thin"
        meta["sample"] = sample
        return {}, meta
    if not all(title_index_ok_from_sample(s) for s in sample):
        meta["ok"] = False
        meta["reason"] = "index_probe_fail"
        meta["sample"] = sample
        return {}, meta
    rows_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    n_line = n_hit = 0
    with src.open(encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            n_line += 1
            parts = line.rstrip("\n").split("|")
            rec = parse_title_elvt(parts)
            if rec is None or rec["ledger_kind"] != "집합":
                continue
            if rec["pnu"] not in pnus:
                continue
            rows_by[rec["pnu"]].append(rec)
            n_hit += 1
            if n_line % 1_000_000 == 0:
                print(f"  title {n_line:,} hit={n_hit:,}", flush=True)
    meta["n_line"] = n_line
    meta["n_hit"] = n_hit
    meta["n_pnu_hit"] = len(rows_by)
    meta["sample"] = sample
    meta["from_cache"] = False
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "snapshot": snapshot,
                "want": sorted(pnus),
                "rows_by_pnu": rows_by,
                "sample": sample,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return dict(rows_by), meta


def title_index_ok_from_sample(sample: dict[str, Any]) -> bool:
    fl = sample.get("floors_above")
    ride = sample.get("ride")
    emgen = sample.get("emgen")
    try:
        return 1 <= int(fl) <= 80 and 0 <= int(ride) <= 30 and 0 <= int(emgen) <= 30
    except (TypeError, ValueError):
        return False


def attach_elevator(
    tx_rows: list[dict[str, Any]],
    *,
    snapshot: str = SNAPSHOT_DEFAULT,
    refresh: bool = False,
) -> tuple[dict[str, bool | None], dict[str, Any], list[dict[str, Any]]]:
    pnu_of = pnu_mode_by_building(tx_rows)
    pnus = set(pnu_of.values())
    rows_by, scan = scan_title_for_pnus(pnus, snapshot=snapshot, refresh=refresh)
    by_pnu_agg = {p: aggregate_pnu_elevator(rows_by.get(p) or []) for p in pnus}
    elev_by_key: dict[str, bool | None] = {}
    csv_rows: list[dict[str, Any]] = []
    n_yes = n_no = n_unk = n_mixed = n_nopnu = 0
    keys = sorted({str(r.get("building_key") or "").strip() for r in tx_rows if r.get("building_key")})
    for k in keys:
        pnu = pnu_of.get(k)
        if not pnu:
            n_nopnu += 1
            elev_by_key[k] = None
            csv_rows.append(
                {
                    "building_key": k,
                    "pnu": "",
                    "elevator": "",
                    "ride": "",
                    "emgen": "",
                    "n_dongs": 0,
                    "mixed": False,
                    "floors_above": "",
                    "reason": "no_pnu",
                }
            )
            continue
        agg = by_pnu_agg.get(pnu) or {"elevator": None, "reason": "miss"}
        ev = agg.get("elevator")
        elev_by_key[k] = ev if ev is None or isinstance(ev, bool) else None
        if agg.get("mixed"):
            n_mixed += 1
            n_unk += 1
        elif ev is True:
            n_yes += 1
        elif ev is False:
            n_no += 1
        else:
            n_unk += 1
        csv_rows.append(
            {
                "building_key": k,
                "pnu": pnu,
                "elevator": "" if ev is None else ("1" if ev else "0"),
                "ride": agg.get("ride") if agg.get("ride") is not None else "",
                "emgen": agg.get("emgen") if agg.get("emgen") is not None else "",
                "n_dongs": agg.get("n_dongs") or 0,
                "mixed": bool(agg.get("mixed")),
                "floors_above": agg.get("floors_above") if agg.get("floors_above") is not None else "",
                "reason": agg.get("reason") or "",
            }
        )
    summary = {
        "ok": bool(scan.get("ok")),
        "snapshot": snapshot,
        "from_cache": bool(scan.get("from_cache")),
        "reason": scan.get("reason") or "",
        "n_buildings": len(keys),
        "n_pnu": len(pnus),
        "n_pnu_hit": int(scan.get("n_pnu_hit") or 0),
        "n_yes": n_yes,
        "n_no": n_no,
        "n_unknown": n_unk,
        "n_mixed": n_mixed,
        "n_nopnu": n_nopnu,
        "sample": scan.get("sample") or [],
        "csv": CSV_OUT.name,
    }
    return elev_by_key, summary, csv_rows


def purpose_band_from_dongs(rows: list[dict[str, Any]]) -> str:
    """표제부 주용도·세부. 원장 housing_subtype(파일명)과 같지 않다."""
    blob = " ".join(f"{r.get('main_purpose') or ''} {r.get('purpose_detail') or ''}" for r in rows)
    yeon = "연립" in blob
    da = "다세대" in blob
    if yeon and da:
        return "both"
    if yeon:
        return "연립"
    if da:
        return "다세대"
    return "other"


def purpose_by_building(
    tx_rows: list[dict[str, Any]],
    rows_by_pnu: dict[str, list[dict[str, Any]]] | None = None,
    *,
    cache_path: Path = CACHE,
) -> dict[str, str]:
    pnu_of = pnu_mode_by_building(tx_rows)
    rows_by = rows_by_pnu
    if rows_by is None and cache_path.exists():
        try:
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw = {}
        rows_by = raw.get("rows_by_pnu") or {}
    if not rows_by:
        return {}
    pnu_purpose = {p: purpose_band_from_dongs(rs) for p, rs in rows_by.items()}
    return {k: pnu_purpose.get(p, "other") for k, p in pnu_of.items()}


def write_attach_csv(rows: list[dict[str, Any]], path: Path = CSV_OUT) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
