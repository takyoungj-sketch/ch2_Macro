"""아파트·오피스텔 층 효용 0차 — 적격 단지 수.

가격·지수·계수는 집계하지 않는다.
재실행 (backend에서): python -m app.apt_floor_lab.screen
"""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.collective.db import get_collective_engine
from app.land_lab.area_elasticity_screen import period_bounds_for_window

WINDOW_YEARS = 5
ASSETS = ("apartment", "officetel")
N_MIN = 50
N1_MIN = 5
OTHER_BIN_MIN = 5
MAX_FLOOR_MIN = 2
REPORT_MIN_BUILDINGS = 30
LOW_RATIO = 0.30
MID_RATIO = 0.70

TIER_ORDER = ("metro", "metro_city", "other_urban", "nonurban", "sejong", "unknown")
TIER_LABELS = {
    "metro": "수도권",
    "metro_city": "광역시",
    "other_urban": "기타 도시",
    "nonurban": "비도시",
    "sejong": "세종",
    "unknown": "미분류",
}
BAND_ORDER = ("le15", "m16_25", "ge26")
BAND_LABELS = {"le15": "≤15층", "m16_25": "16–25층", "ge26": "≥26층"}
ALT_BAND_ORDER = ("le20", "m21_30", "ge31")
ALT_BAND_LABELS = {"le20": "≤20층", "m21_30": "21–30층", "ge31": "≥31층"}

ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "lab" / "apt_floor_utility_screen.json"
OUT_CSV = ROOT / "docs" / "lab" / "apt_floor_utility_screen.csv"


def experiment_floor_bin(floor: float | None, max_floor: float | None) -> str | None:
    """제품 아파트 상대층과 같은 칸. 지하(floor<1)는 넣지 않는다."""
    if floor is None or max_floor is None:
        return None
    try:
        f = float(floor)
        mx = float(max_floor)
    except (TypeError, ValueError):
        return None
    if f < 1 or mx < 1:
        return None
    if f == 1:
        return "f1"
    if f == mx:
        return "top"
    ratio = f / mx if mx > 0 else 0.5
    if f > 1 and ratio <= LOW_RATIO:
        return "low"
    if LOW_RATIO < ratio <= MID_RATIO:
        return "mid"
    if ratio > MID_RATIO and f < mx:
        return "high"
    return "mid"


def place_name(addr3: str | None, addr4: str | None) -> str:
    """읍·면·동 이름. 구가 addr3이면 동은 addr4다."""
    a3 = (addr3 or "").strip()
    a4 = (addr4 or "").strip()
    if a3.endswith("구") and a4:
        return a4
    return a3 or a4


def legal_kind(place: str | None) -> str:
    name = (place or "").strip()
    if name.endswith("읍"):
        return "eup"
    if name.endswith("면"):
        return "myeon"
    if name.endswith("리"):
        return "ri"
    if name.endswith("동") or name.endswith("가"):
        return "dong"
    return "other"


def region_tier(addr1: str | None, place: str | None) -> str:
    """계층 순서: 세종 → 수도권(읍·면 포함) → 광역시 → 그 밖 동 → 그 밖 읍·면·리."""
    sido = (addr1 or "").strip()
    kind = legal_kind(place)
    if sido.startswith("세종"):
        return "sejong"
    if sido.startswith(("서울", "인천", "경기")):
        return "metro"
    if sido.startswith(("부산", "대구", "광주", "대전", "울산")):
        return "metro_city"
    if kind == "dong":
        return "other_urban"
    if kind in {"eup", "myeon", "ri"}:
        return "nonurban"
    return "unknown"


def height_band(max_floor: float | None) -> str | None:
    if max_floor is None:
        return None
    mx = float(max_floor)
    if mx <= 15:
        return "le15"
    if mx <= 25:
        return "m16_25"
    return "ge26"


def height_band_alt(max_floor: float | None) -> str | None:
    if max_floor is None:
        return None
    mx = float(max_floor)
    if mx <= 20:
        return "le20"
    if mx <= 30:
        return "m21_30"
    return "ge31"


def is_eligible(
    *,
    n: int,
    n_1: int,
    n_low: int,
    n_mid: int,
    n_high: int,
    n_top: int,
    max_floor: float | None,
) -> bool:
    if n < N_MIN or n_1 < N1_MIN:
        return False
    if max_floor is None or float(max_floor) < MAX_FLOOR_MIN:
        return False
    return any(v >= OTHER_BIN_MIN for v in (n_low, n_mid, n_high, n_top))


def _cell(key: str, labels: dict[str, str], buildings: int, txns: int) -> dict[str, Any]:
    return {
        "key": key,
        "label": labels.get(key, key),
        "buildings": buildings,
        "txns": txns,
        "reportable": buildings >= REPORT_MIN_BUILDINGS,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """건물 1행(가격 없음)을 계층·대역 건수로 모은다."""
    funnel = {
        "buildings": 0,
        "max_floor_ge2": 0,
        "n_ge50": 0,
        "n50_n1_0": 0,
        "n50_n1_1_to_4": 0,
        "n1_ge5": 0,
        "eligible": 0,
        "eligible_txns": 0,
    }
    tier_b: dict[str, int] = {k: 0 for k in TIER_ORDER}
    tier_t: dict[str, int] = {k: 0 for k in TIER_ORDER}
    band_b: dict[str, int] = {k: 0 for k in BAND_ORDER}
    band_t: dict[str, int] = {k: 0 for k in BAND_ORDER}
    alt_b: dict[str, int] = {k: 0 for k in ALT_BAND_ORDER}
    alt_t: dict[str, int] = {k: 0 for k in ALT_BAND_ORDER}
    cross: dict[tuple[str, str], list[int]] = {}
    metro_legal = {"dong": 0, "eup_myeon_ri": 0, "other": 0}
    metro_legal_tx = {"dong": 0, "eup_myeon_ri": 0, "other": 0}

    for row in rows:
        n = int(row["n"])
        n_1 = int(row["n_1"])
        mx = row.get("max_floor")
        funnel["buildings"] += 1
        if mx is not None and float(mx) >= MAX_FLOOR_MIN:
            funnel["max_floor_ge2"] += 1
        if n >= N_MIN:
            funnel["n_ge50"] += 1
            if n_1 <= 0:
                funnel["n50_n1_0"] += 1
            elif n_1 < N1_MIN:
                funnel["n50_n1_1_to_4"] += 1
        if n >= N_MIN and n_1 >= N1_MIN:
            funnel["n1_ge5"] += 1
        if not row.get("eligible"):
            continue
        funnel["eligible"] += 1
        funnel["eligible_txns"] += n
        tier = str(row["tier"])
        band = str(row["band"])
        tier_b[tier] = tier_b.get(tier, 0) + 1
        tier_t[tier] = tier_t.get(tier, 0) + n
        if band in band_b:
            band_b[band] += 1
            band_t[band] += n
        alt = row.get("band_alt")
        if alt in alt_b:
            alt_b[alt] += 1
            alt_t[alt] += n
        slot = cross.setdefault((tier, band), [0, 0])
        slot[0] += 1
        slot[1] += n
        if tier == "metro":
            kind = row.get("legal_kind")
            bucket = "dong" if kind == "dong" else "eup_myeon_ri" if kind in {"eup", "myeon", "ri"} else "other"
            metro_legal[bucket] += 1
            metro_legal_tx[bucket] += n

    tiers = [_cell(k, TIER_LABELS, tier_b.get(k, 0), tier_t.get(k, 0)) for k in TIER_ORDER if tier_b.get(k, 0)]
    bands = [_cell(k, BAND_LABELS, band_b[k], band_t[k]) for k in BAND_ORDER]
    alt_bands = [_cell(k, ALT_BAND_LABELS, alt_b[k], alt_t[k]) for k in ALT_BAND_ORDER]
    cross_rows = []
    for tier in TIER_ORDER:
        for band in BAND_ORDER:
            buildings, txns = cross.get((tier, band), [0, 0])
            if buildings == 0:
                continue
            item = _cell(f"{tier}|{band}", {}, buildings, txns)
            item["tier"] = tier
            item["tier_label"] = TIER_LABELS.get(tier, tier)
            item["band"] = band
            item["band_label"] = BAND_LABELS.get(band, band)
            cross_rows.append(item)

    nonurban_n = tier_b.get("nonurban", 0)
    sejong_n = tier_b.get("sejong", 0)
    return {
        "funnel": funnel,
        "tiers": tiers,
        "bands": bands,
        "alt_bands": alt_bands,
        "cross": cross_rows,
        "metro_legal_split": {
            "buildings": metro_legal,
            "txns": metro_legal_tx,
            "note": "수도권 안의 동/읍·면 참고. 본표 계층은 시도가 먼저다.",
        },
        "nonurban_open": nonurban_n >= REPORT_MIN_BUILDINGS,
        "sejong_own_row": sejong_n >= REPORT_MIN_BUILDINGS,
    }


def annotate(raw: dict[str, Any]) -> dict[str, Any]:
    mx = raw.get("max_floor")
    try:
        mx_f = float(mx) if mx is not None else None
    except (TypeError, ValueError):
        mx_f = None
    n = int(raw.get("n") or 0)
    n_1 = int(raw.get("n_1") or 0)
    n_low = int(raw.get("n_low") or 0)
    n_mid = int(raw.get("n_mid") or 0)
    n_high = int(raw.get("n_high") or 0)
    n_top = int(raw.get("n_top") or 0)
    addr1 = str(raw.get("addr1") or "")
    addr3 = str(raw.get("addr3") or "")
    addr4 = str(raw.get("addr4") or "")
    place = place_name(addr3, addr4)
    eligible = is_eligible(
        n=n, n_1=n_1, n_low=n_low, n_mid=n_mid, n_high=n_high, n_top=n_top, max_floor=mx_f
    )
    return {
        "building_key": str(raw.get("building_key") or "").strip(),
        "addr1": addr1,
        "addr2": str(raw.get("addr2") or ""),
        "addr3": addr3,
        "addr4": addr4,
        "place": place,
        "legal_kind": legal_kind(place),
        "tier": region_tier(addr1, place),
        "band": height_band(mx_f),
        "band_alt": height_band_alt(mx_f),
        "n": n,
        "n_1": n_1,
        "n_low": n_low,
        "n_mid": n_mid,
        "n_high": n_high,
        "n_top": n_top,
        "max_floor": mx_f,
        "eligible": eligible,
    }


def build_screen_sql() -> str:
    return """
        WITH tx AS (
            SELECT
                t.building_key,
                t.addr1,
                t.addr2,
                t.addr3,
                t.addr4,
                t.floor
            FROM collective_transactions t
            WHERE t.asset_type = :asset
              AND t.is_valid = TRUE
              AND t.contract_date >= :p_start
              AND t.contract_date <= :p_end
              AND t.unit_price > 0
              AND t.exclusive_area > 0
              AND t.floor >= 1
              AND t.building_key IS NOT NULL
              AND t.building_key <> ''
        ),
        mx AS (
            SELECT building_key, MAX(floor)::float8 AS max_floor
            FROM tx
            GROUP BY building_key
        )
        SELECT
            t.building_key,
            MAX(t.addr1) AS addr1,
            MAX(t.addr2) AS addr2,
            MAX(t.addr3) AS addr3,
            MAX(t.addr4) AS addr4,
            COUNT(*)::int AS n,
            COUNT(*) FILTER (WHERE t.floor = 1)::int AS n_1,
            COUNT(*) FILTER (
                WHERE t.floor > 1 AND t.floor = m.max_floor
            )::int AS n_top,
            COUNT(*) FILTER (
                WHERE t.floor > 1
                  AND t.floor < m.max_floor
                  AND (t.floor::float8 / m.max_floor) <= 0.30
            )::int AS n_low,
            COUNT(*) FILTER (
                WHERE t.floor > 1
                  AND t.floor < m.max_floor
                  AND (t.floor::float8 / m.max_floor) > 0.30
                  AND (t.floor::float8 / m.max_floor) <= 0.70
            )::int AS n_mid,
            COUNT(*) FILTER (
                WHERE t.floor > 1
                  AND t.floor < m.max_floor
                  AND (t.floor::float8 / m.max_floor) > 0.70
            )::int AS n_high,
            m.max_floor
        FROM tx t
        JOIN mx m ON m.building_key = t.building_key
        GROUP BY t.building_key, m.max_floor
    """


def latest_as_of_month(conn: Connection) -> date:
    raw = conn.execute(
        text(
            """
            SELECT MAX(contract_date)::date
            FROM collective_transactions
            WHERE is_valid = TRUE
              AND asset_type IN ('apartment', 'officetel')
              AND contract_date IS NOT NULL
            """
        )
    ).scalar()
    if raw is None:
        raise RuntimeError("아파트·오피스텔 contract_date 없음")
    d = raw if isinstance(raw, date) else date.fromisoformat(str(raw)[:10])
    return date(d.year, d.month, 1)


def fetch_buildings(conn: Connection, asset: str, p_start: date, p_end: date) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(build_screen_sql()),
        {"asset": asset, "p_start": p_start, "p_end": p_end},
    ).mappings()
    return [annotate(dict(r)) for r in rows]


def _decisions(by_asset: dict[str, Any]) -> dict[str, Any]:
    apt = by_asset["apartment"]
    off = by_asset["officetel"]
    return {
        "nonurban_experiment1": "open" if apt["nonurban_open"] else "closed",
        "sejong": "own_row" if apt["sejong_own_row"] else "excluded",
        "officetel_nonurban": "open" if off["nonurban_open"] else "closed",
        "officetel_sejong": "own_row" if off["sejong_own_row"] else "excluded",
        "note": "가격 계수 없음. 보고 최소는 적격 단지 30곳. 15/16층은 단절이 아니다.",
    }


def run_screen(engine: Engine) -> dict[str, Any]:
    with engine.connect() as conn:
        as_of = latest_as_of_month(conn)
        p_start, p_end = period_bounds_for_window(as_of, WINDOW_YEARS)
        by_asset: dict[str, Any] = {}
        eligible_rows: list[dict[str, Any]] = []
        for asset in ASSETS:
            buildings = fetch_buildings(conn, asset, p_start, p_end)
            by_asset[asset] = summarize(buildings)
            for row in buildings:
                if not row["eligible"]:
                    continue
                eligible_rows.append({"asset_type": asset, **row})
    payload = {
        "as_of": as_of.isoformat(),
        "period_start": p_start.isoformat(),
        "period_end": p_end.isoformat(),
        "window_years": WINDOW_YEARS,
        "gate": {
            "n_min": N_MIN,
            "n_1_min": N1_MIN,
            "other_bin_min": OTHER_BIN_MIN,
            "max_floor_min": MAX_FLOOR_MIN,
            "report_min_buildings": REPORT_MIN_BUILDINGS,
            "basement": "excluded",
            "price": "not aggregated",
        },
        "region_rule": "세종 → 수도권(읍·면 포함) → 광역시 → 그 밖 동(기타 도시) → 그 밖 읍·면·리(비도시)",
        "by_asset": by_asset,
        "decisions": _decisions(by_asset),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(eligible_rows)
    return payload


def _write_csv(rows: list[dict[str, Any]]) -> None:
    fields = [
        "asset_type",
        "building_key",
        "tier",
        "band",
        "band_alt",
        "legal_kind",
        "n",
        "n_1",
        "n_low",
        "n_mid",
        "n_high",
        "n_top",
        "max_floor",
        "addr1",
        "addr2",
        "addr3",
        "addr4",
        "place",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    engine = get_collective_engine()
    if engine is None:
        raise RuntimeError("COLLECTIVE_DATABASE_URL 없음")
    payload = run_screen(engine)
    apt = payload["by_asset"]["apartment"]["funnel"]
    off = payload["by_asset"]["officetel"]["funnel"]
    print(
        json.dumps(
            {
                "as_of": payload["as_of"],
                "period": [payload["period_start"], payload["period_end"]],
                "apartment_eligible": apt["eligible"],
                "officetel_eligible": off["eligible"],
                "decisions": payload["decisions"],
                "json": str(OUT_JSON),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
