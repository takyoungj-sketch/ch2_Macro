"""상권별 2021–2025 수익률 평균과 아파트 가격·수익률.

backend에서:
  python -m app.sangkwon_apt_yield.build
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from shapely import make_valid
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree
from sqlalchemy import text

from app.collective.db import get_collective_engine
from app.rent.db import get_rent_engine
from app.rent.sangkwon_agg import compound_annual

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lab" / "sangkwon_apt_yield.json"
NATIONAL = ROOT / "docs" / "lab" / "yield_compare_national.json"
EMD_CACHE = ROOT / "data" / "cache" / "emd_wgs84.jsonl"
EMD_DONE = ROOT / "data" / "cache" / "emd_sigungu_done.txt"

YEARS = (2021, 2022, 2023, 2024, 2025)
MIN_N = 30
NEAR_M = 1000.0
KINDS = ("office", "mid_retail", "small_retail", "strata")
YIELD_METRICS = ("income_yield", "capital_yield", "investment_yield", "rent")


def mean_present(values: dict[int, float | None]) -> tuple[float | None, int]:
    xs = [values[y] for y in YEARS if values.get(y) is not None]
    if not xs:
        return None, 0
    return sum(xs) / len(xs), len(xs)


def monthly_rent_manwon(by_quarter: dict[int, float | None]) -> float | None:
    """분기 임대료(천원/㎡) 네 개의 평균을 만원/㎡·월로. 한 분기라도 없으면 빈칸."""
    vals = [by_quarter.get(q) for q in (1, 2, 3, 4)]
    if any(v is None for v in vals):
        return None
    return sum(vals) / 4.0 * 0.1


def _round(v: float | None, nd: int = 2) -> float | None:
    if v is None:
        return None
    return round(v, nd)


def _load_r() -> dict[int, float]:
    data = json.loads(NATIONAL.read_text(encoding="utf-8"))
    out: dict[int, float] = {}
    for row in data["residential_counts"]["apartment"]:
        if row.get("r_pct") is not None:
            out[int(row["year"])] = float(row["r_pct"])
    return out


def _commercial(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT sec_nm, sido, asset_kind, metric, year, quarter, value
            FROM rent_sangkwon_quarterly
            WHERE floor_band = 'all'
              AND asset_kind IN ('office', 'mid_retail', 'small_retail', 'strata')
              AND metric IN ('income_yield', 'capital_yield', 'investment_yield', 'rent')
              AND year BETWEEN 2021 AND 2025
            """
        )
    ).mappings()
    bucket: dict[tuple, dict[str, dict[int, dict[int, float | None]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )
    sido_of: dict[tuple, str] = {}
    for row in rows:
        key = (row["asset_kind"], row["sec_nm"])
        sido_of[key] = row["sido"] or ""
        val = None if row["value"] is None else float(row["value"])
        bucket[key][row["metric"]][int(row["year"])][int(row["quarter"])] = val

    out = []
    for (kind, name), metrics in bucket.items():
        annual: dict[str, dict[int, float | None]] = {m: {} for m in YIELD_METRICS}
        for metric, years in metrics.items():
            for year, qs in years.items():
                if metric == "rent":
                    annual[metric][year] = monthly_rent_manwon(qs)
                else:
                    annual[metric][year] = compound_annual(qs)
        item: dict[str, Any] = {"asset_kind": kind, "sec_nm": name, "sido": sido_of[(kind, name)]}
        for metric, label in (
            ("income_yield", "income"),
            ("capital_yield", "capital"),
            ("investment_yield", "investment"),
            ("rent", "rent"),
        ):
            avg, n = mean_present(annual[metric])
            item[label] = _round(avg)
            item[f"n_{label}"] = n
        out.append(item)
    return out


def _geoms(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        text("SELECT sec_nm, sido, geom_geojson FROM rent_sangkwon")
    ).mappings()
    polys = []
    for row in rows:
        raw = row["geom_geojson"]
        if isinstance(raw, str):
            raw = json.loads(raw)
        if raw.get("type") == "Feature":
            raw = raw["geometry"]
        geom = make_valid(shape(raw))
        if geom.is_empty:
            continue
        polys.append({"sec_nm": row["sec_nm"], "sido": row["sido"] or "", "geom": geom})
    return polys


def _points(conn) -> list[tuple[str, Point]]:
    rows = conn.execute(
        text(
            """
            SELECT building_key, longitude, latitude
            FROM collective_building_geocodes
            WHERE status = 'ok' AND longitude IS NOT NULL AND latitude IS NOT NULL
            """
        )
    )
    return [(r[0], Point(float(r[1]), float(r[2]))) for r in rows]


def _sale_by_building(conn) -> dict[str, dict[int, tuple[float, int]]]:
    rows = conn.execute(
        text(
            """
            SELECT building_key, contract_year, sum(unit_price) AS s, count(*) AS n
            FROM collective_transactions
            WHERE asset_type = 'apartment'
              AND contract_year BETWEEN 2020 AND 2025
              AND unit_price > 0
            GROUP BY building_key, contract_year
            """
        )
    )
    out: dict[str, dict[int, tuple[float, int]]] = defaultdict(dict)
    for key, year, total, n in rows:
        out[key][int(year)] = (float(total), int(n))
    return out


def _rent_by_building(conn) -> dict[str, dict[int, tuple[float, float, int]]]:
    rows = conn.execute(
        text(
            """
            SELECT building_key, contract_year,
                   sum(monthly_per_m2) AS sm,
                   sum(COALESCE(deposit_per_m2, 0)) AS sd,
                   count(*) AS n
            FROM rent_transactions
            WHERE asset_type = 'apartment'
              AND contract_year BETWEEN 2021 AND 2025
              AND monthly_rent_manwon > 0
              AND monthly_per_m2 > 0
            GROUP BY building_key, contract_year
            """
        )
    )
    out: dict[str, dict[int, tuple[float, float, int]]] = defaultdict(dict)
    for key, year, sm, sd, n in rows:
        out[key][int(year)] = (float(sm), float(sd), int(n))
    return out


def _assign(polys: list[dict[str, Any]], points: list[tuple[str, Point]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    geoms = []
    for poly in polys:
        g = poly["geom"]
        buf = g.buffer(NEAR_M / 111_000.0)
        geoms.append((g, buf))
    tree = STRtree([g for g, _ in geoms])
    inside: dict[str, set[str]] = {p["sec_nm"]: set() for p in polys}
    near: dict[str, set[str]] = {p["sec_nm"]: set() for p in polys}
    for key, pt in points:
        hits = tree.query(pt)
        for idx in hits:
            geom, buf = geoms[int(idx)]
            name = polys[int(idx)]["sec_nm"]
            if geom.covers(pt):
                inside[name].add(key)
            elif buf.covers(pt):
                near[name].add(key)
    return inside, near


def _sale_by_dong(conn) -> dict[str, dict[int, tuple[float, int]]]:
    rows = conn.execute(
        text(
            """
            SELECT btrim(eupmyeondong_code), contract_year, sum(unit_price), count(*)
            FROM collective_transactions
            WHERE asset_type = 'apartment'
              AND contract_year BETWEEN 2020 AND 2025
              AND unit_price > 0
              AND eupmyeondong_code IS NOT NULL
              AND btrim(eupmyeondong_code) <> ''
            GROUP BY 1, 2
            """
        )
    )
    out: dict[str, dict[int, tuple[float, int]]] = defaultdict(dict)
    for code, year, total, n in rows:
        out[str(code)[:8]][int(year)] = (float(total), int(n))
    return out


def _rent_by_dong(conn) -> dict[str, dict[int, tuple[float, float, int]]]:
    rows = conn.execute(
        text(
            """
            SELECT btrim(eupmyeondong_code), contract_year,
                   sum(monthly_per_m2), sum(COALESCE(deposit_per_m2, 0)), count(*)
            FROM rent_transactions
            WHERE asset_type = 'apartment'
              AND contract_year BETWEEN 2021 AND 2025
              AND monthly_rent_manwon > 0
              AND monthly_per_m2 > 0
              AND eupmyeondong_code IS NOT NULL
              AND btrim(eupmyeondong_code) <> ''
            GROUP BY 1, 2
            """
        )
    )
    out: dict[str, dict[int, tuple[float, float, int]]] = defaultdict(dict)
    for code, year, sm, sd, n in rows:
        out[str(code)[:8]][int(year)] = (float(sm), float(sd), int(n))
    return out


def _building_dong(conn) -> dict[str, str]:
    rows = conn.execute(
        text(
            """
            SELECT building_key, min(btrim(eupmyeondong_code))
            FROM collective_transactions
            WHERE asset_type = 'apartment'
              AND building_key IS NOT NULL
              AND eupmyeondong_code IS NOT NULL
              AND btrim(eupmyeondong_code) <> ''
            GROUP BY building_key
            """
        )
    )
    return {key: str(code)[:8] for key, code in rows if key and code}


def _emd_code(feat: dict[str, Any]) -> str | None:
    props = feat.get("properties") or {}
    raw = props.get("ch2_code") or props.get("emd_cd")
    if raw is None:
        return None
    code = str(raw).strip()
    if len(code) >= 10 and code.endswith("00"):
        code = code[:8]
    elif len(code) > 8:
        code = code[:8]
    return code or None


def intersecting_codes(
    polys: list[dict[str, Any]],
    emds: list[tuple[str, BaseGeometry]],
) -> dict[str, list[str]]:
    """상권 도형과 면적이 겹치는 읍면동 코드. 경계만 맞닿은 동은 빼다."""
    if not emds:
        return {p["sec_nm"]: [] for p in polys}
    tree = STRtree([geom for _, geom in emds])
    out: dict[str, list[str]] = {}
    for poly in polys:
        geom = poly["geom"]
        codes: set[str] = set()
        for idx in tree.query(geom):
            emd = emds[int(idx)][1]
            if not geom.intersects(emd):
                continue
            shared = geom.intersection(emd)
            if shared.is_empty or shared.area <= 0:
                continue
            codes.add(emds[int(idx)][0])
        out[poly["sec_nm"]] = sorted(codes)
    return out


def _sigungu_codes(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT left(btrim(eupmyeondong_code), 5)
            FROM collective_transactions
            WHERE asset_type = 'apartment'
              AND eupmyeondong_code IS NOT NULL
              AND length(btrim(eupmyeondong_code)) >= 5
            """
        )
    )
    return sorted({str(row[0]) for row in rows if row[0]})


def _load_emd(sigungu: list[str]) -> list[tuple[str, BaseGeometry]]:
    """VWorld 읍면동 경계. 시군구 단위로 data/cache 에 쌓고 다시 받지 않는다."""
    EMD_CACHE.parent.mkdir(parents=True, exist_ok=True)
    have: dict[str, BaseGeometry] = {}
    if EMD_CACHE.exists():
        for line in EMD_CACHE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            have[rec["code"]] = make_valid(shape(rec["geometry"]))
    done = set(EMD_DONE.read_text(encoding="utf-8").split()) if EMD_DONE.exists() else set()
    missing = [code for code in sigungu if code not in done]
    if missing:
        from app.config import settings
        from app.map.vworld_client import _stamp_ch2_codes, fetch_features_soft

        key = (settings.vworld_api_key or "").strip()
        domain = (settings.vworld_api_domain or "localhost").strip()
        if not key:
            raise SystemExit("VWORLD_API_KEY 없음")
        with EMD_CACHE.open("a", encoding="utf-8") as cache, EMD_DONE.open("a", encoding="utf-8") as mark:
            for i, sig in enumerate(missing, start=1):
                fc = fetch_features_soft(
                    api_key=key,
                    domain=domain,
                    level="eupmyeondong",
                    attr_filter=f"emd_cd:like:{sig}%",
                    size=1000,
                )
                feats = list(fc.get("features") or [])
                _stamp_ch2_codes(feats, request_level="eupmyeondong", effective_level="eupmyeondong")
                for feat in feats:
                    code = _emd_code(feat)
                    geom = feat.get("geometry")
                    if not code or not geom:
                        continue
                    cache.write(json.dumps({"code": code, "geometry": geom}, ensure_ascii=False) + "\n")
                    have[code] = make_valid(shape(geom))
                mark.write(sig + "\n")
                mark.flush()
                cache.flush()
                print(f"emd {i}/{len(missing)} {sig} features={len(feats)}", flush=True)
                time.sleep(0.12)
    return list(have.items())


def _admin_codes(
    name: str,
    centroid: Point,
    inside: dict[str, set[str]],
    dong_of: dict[str, str],
    points: list[tuple[str, Point]],
    point_tree: STRtree,
) -> list[str]:
    codes = {dong_of[key] for key in inside.get(name, set()) if key in dong_of}
    if codes:
        return sorted(codes)
    idx = point_tree.nearest(centroid)
    key = points[int(idx)][0]
    code = dong_of.get(key)
    return [code] if code else []


def _zone_from_codes(
    codes: list[str],
    sales: dict[str, dict[int, tuple[float, int]]],
    rents: dict[str, dict[int, tuple[float, float, int]]],
    r_by_year: dict[int, float],
) -> dict[str, Any]:
    price: dict[int, float | None] = {}
    income: dict[int, float | None] = {}
    rent_level: dict[int, float | None] = {}
    for year in (2020, *YEARS):
        s = n = 0.0
        for code in codes:
            pair = sales.get(code, {}).get(year)
            if pair:
                s += pair[0]
                n += pair[1]
        price[year] = (s / n) if n >= MIN_N else None
        if year < 2021:
            continue
        sm = sd = nr = 0.0
        for code in codes:
            pair = rents.get(code, {}).get(year)
            if pair:
                sm += pair[0]
                sd += pair[1]
                nr += pair[2]
        if nr < MIN_N or year not in r_by_year:
            income[year] = None
            rent_level[year] = None
        else:
            monthly = (sm + sd * (r_by_year[year] / 100.0) / 12.0) / nr
            rent_level[year] = monthly
            sale = price.get(year)
            income[year] = None if not sale else 100.0 * (monthly * 12.0) / sale
    capital: dict[int, float | None] = {}
    invest: dict[int, float | None] = {}
    for year in YEARS:
        prev = price.get(year - 1)
        cur = price.get(year)
        capital[year] = None if not prev or not cur else (cur / prev - 1.0) * 100.0
        if income.get(year) is None or capital[year] is None:
            invest[year] = None
        else:
            invest[year] = income[year] + capital[year]
    inc, n_inc = mean_present(income)
    cap, n_cap = mean_present(capital)
    inv, n_inv = mean_present(invest)
    rent, n_rent = mean_present(rent_level)
    px, n_px = mean_present({y: price.get(y) for y in YEARS})
    return {
        "income": _round(inc),
        "n_income": n_inc,
        "capital": _round(cap),
        "n_capital": n_cap,
        "investment": _round(inv),
        "n_investment": n_inv,
        "rent": _round(rent, 3),
        "n_rent": n_rent,
        "sale_price": _round(px, 1),
        "n_sale_price": n_px,
        "n_buildings": 0,
        "n_dongs": len(codes),
    }


def _zone_stats(
    keys: set[str],
    sales: dict[str, dict[int, tuple[float, int]]],
    rents: dict[str, dict[int, tuple[float, float, int]]],
    r_by_year: dict[int, float],
) -> dict[str, Any]:
    price: dict[int, float | None] = {}
    income: dict[int, float | None] = {}
    rent_level: dict[int, float | None] = {}
    for year in (2020, *YEARS):
        s = n = 0.0
        for key in keys:
            pair = sales.get(key, {}).get(year)
            if pair:
                s += pair[0]
                n += pair[1]
        price[year] = (s / n) if n >= MIN_N else None
        if year < 2021:
            continue
        sm = sd = nr = 0.0
        for key in keys:
            pair = rents.get(key, {}).get(year)
            if pair:
                sm += pair[0]
                sd += pair[1]
                nr += pair[2]
        if nr < MIN_N or year not in r_by_year:
            income[year] = None
            rent_level[year] = None
        else:
            monthly = (sm + sd * (r_by_year[year] / 100.0) / 12.0) / nr
            rent_level[year] = monthly
            sale = price.get(year)
            income[year] = None if not sale else 100.0 * (monthly * 12.0) / sale
    capital: dict[int, float | None] = {}
    invest: dict[int, float | None] = {}
    for year in YEARS:
        prev = price.get(year - 1)
        cur = price.get(year)
        capital[year] = None if not prev or not cur else (cur / prev - 1.0) * 100.0
        if income.get(year) is None or capital[year] is None:
            invest[year] = None
        else:
            invest[year] = income[year] + capital[year]
    inc, n_inc = mean_present(income)
    cap, n_cap = mean_present(capital)
    inv, n_inv = mean_present(invest)
    rent, n_rent = mean_present(rent_level)
    px, n_px = mean_present({y: price.get(y) for y in YEARS})
    return {
        "income": _round(inc),
        "n_income": n_inc,
        "capital": _round(cap),
        "n_capital": n_cap,
        "investment": _round(inv),
        "n_investment": n_inv,
        "rent": _round(rent, 3),
        "n_rent": n_rent,
        "sale_price": _round(px, 1),
        "n_sale_price": n_px,
        "n_buildings": len(keys),
    }


def build() -> dict[str, Any]:
    r_by_year = _load_r()
    rent_eng = get_rent_engine()
    coll_eng = get_collective_engine()
    with rent_eng.connect() as conn:
        commercial = _commercial(conn)
        polys = _geoms(conn)
        rents = _rent_by_building(conn)
        rent_dong = _rent_by_dong(conn)
    with coll_eng.connect() as conn:
        points = _points(conn)
        sales = _sale_by_building(conn)
        sale_dong = _sale_by_dong(conn)
        dong_of = _building_dong(conn)
        sigungu = _sigungu_codes(conn)
    emds = _load_emd(sigungu)
    overlap_of = intersecting_codes(polys, emds)
    inside, near = _assign(polys, points)
    point_tree = STRtree([pt for _, pt in points])
    by_name = {p["sec_nm"]: p for p in polys}
    rows = []
    for item in commercial:
        name = item["sec_nm"]
        if name not in by_name:
            apt_in = apt_near = apt_admin = apt_overlap = None
        else:
            apt_in = _zone_stats(inside.get(name, set()), sales, rents, r_by_year)
            apt_near = _zone_stats(near.get(name, set()), sales, rents, r_by_year)
            codes = _admin_codes(name, by_name[name]["geom"].centroid, inside, dong_of, points, point_tree)
            apt_admin = _zone_from_codes(codes, sale_dong, rent_dong, r_by_year)
            apt_overlap = _zone_from_codes(overlap_of.get(name, []), sale_dong, rent_dong, r_by_year)
        rows.append(
            {
                **item,
                "rent": _round(item["rent"], 3),
                "inside": apt_in,
                "near": apt_near,
                "admin": apt_admin,
                "overlap": apt_overlap,
            }
        )
    rows.sort(key=lambda r: (r["asset_kind"], -(r["investment"] if r["investment"] is not None else -1e9), r["sec_nm"]))
    return {
        "years": list(YEARS),
        "min_n": MIN_N,
        "near_m": NEAR_M,
        "r_pct": {str(y): r_by_year.get(y) for y in YEARS},
        "notes": [
            "상업 칸은 그 해 1–4분기 복리(임대료는 네 분기 평균, 천원/㎡→만원/㎡·월)를 2021–2025 단순평균한 값이다. 다섯 해를 복리로 잇지 않는다.",
            "아파트 자본은 상권 안 실거래 ㎡당 매매가 평균의 전년 대비다. 매매가격지수가 아니다.",
            "아파트 소득은 전국 아파트 전환율로 보증금을 월세에 더한 뒤 그 상권 표본만 쓴다.",
            "인근은 폴리곤 밖, 경계에서 약 1km 안이다. 위경도 버퍼라 거리가 근사다.",
            "동일 행정구역은 상권 안 단지가 속한 읍면동 전체다. 안이 비면 중심에서 가장 가까운 단지의 읍면동이다. 읍면동 경계와 상권의 교차는 아니다.",
            "경계가 겹치는 읍면동은 VWorld 읍면동 경계와 상권 도형의 겹친 면적이 있는 동 전체다. 경계만 맞닿은 동은 빼다.",
            "2024년 3분기 상권 구획 변경 이후 도형이다. 이름이 같아도 그 이전과 같은 장소가 아니다.",
            "그 해 n이 30 미만이면 그 해는 평균에서 빠진다.",
        ],
        "rows": rows,
    }


def main() -> None:
    payload = build()
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} rows={len(payload['rows'])}")


if __name__ == "__main__":
    main()
