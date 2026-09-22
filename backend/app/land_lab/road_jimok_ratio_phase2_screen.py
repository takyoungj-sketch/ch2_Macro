"""도로 지목 2차 스냅샷. 1차 JSON에 연도별 r과 회귀를 붙인다.

전국 창 1회 스캔이라 `ANY` 핫패스 규칙의 예외(파이프라인).
지목·용도는 고정 `IN` 목록이다.

재실행 (backend에서):
  python -m app.land_lab.road_jimok_ratio_phase2_screen
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app.db import engine
from app.land_lab.area_elasticity import AREA_MAX_SQM
from app.land_lab.road_jimok_ratio import GREENBELT_ZONES, NONURBAN_ZONES, URBAN_ZONES, enrich_public
from app.land_lab.road_jimok_ratio_phase2 import build_yearly, fit_regressions
from app.land_lab.road_jimok_ratio_screen import OUT
from app.region_canonical import region_codes_join_on_canonical
from app.region_sido import is_retired_sido_code, is_retired_sido_name

_ZONES = tuple(sorted(URBAN_ZONES | NONURBAN_ZONES | GREENBELT_ZONES))
_ZONE_SQL = ", ".join(f"'{z}'" for z in _ZONES)
_JIMOK_SQL = "'도', '도로', '대', '전', '답'"


def fetch_trades(period_start: str, period_end: str) -> pd.DataFrame:
    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    sql = f"""
        SELECT
            btrim(r.sido_code::text) AS sido_code,
            btrim(r.sido_name::text) AS sido_name,
            btrim(r.eupmyeondong_code::text) AS eup_code,
            btrim(lt.zone_type_resolved::text) AS zone_type,
            btrim(lt.land_category_resolved::text) AS land_category,
            lt.contract_year::int AS contract_year,
            btrim(lt.road_condition::text) AS road_condition,
            lt.area_sqm::float8 AS area_sqm,
            lt.unit_price_per_sqm::float8 AS unit_price_per_sqm
        FROM land_transactions_resolved lt
        {join_sql}
        WHERE lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND COALESCE(lt.is_partial_ownership, FALSE) = FALSE
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          AND lt.area_sqm > 0
          AND lt.area_sqm < :area_max
          AND lt.unit_price_per_sqm > 0
          AND lt.contract_year IS NOT NULL
          AND btrim(COALESCE(lt.beopjungri_code::text, '')) <> ''
          AND btrim(lt.land_category_resolved::text) IN ({_JIMOK_SQL})
          AND btrim(lt.zone_type_resolved::text) IN ({_ZONE_SQL})
          AND btrim(COALESCE(r.eupmyeondong_code::text, '')) <> ''
    """
    df = pd.read_sql(
        text(sql),
        engine,
        params={"p_start": period_start, "p_end": period_end, "area_max": AREA_MAX_SQM},
    )
    if df.empty:
        return df
    keep = [
        not is_retired_sido_code(str(code or ""))
        and not is_retired_sido_name(str(name or ""))
        for code, name in zip(df["sido_code"], df["sido_name"])
    ]
    return df.loc[keep].drop(columns=["sido_code", "sido_name"])


def year_aggs(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    agg = (
        df.groupby(
            ["contract_year", "eup_code", "zone_type", "land_category"],
            sort=False,
        )
        .agg(
            n=("unit_price_per_sqm", "size"),
            p50=("unit_price_per_sqm", "median"),
            mean_px=("unit_price_per_sqm", "mean"),
        )
        .reset_index()
    )
    return agg.to_dict(orient="records")


def attach_phase2(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "ready":
        raise RuntimeError("1차 스냅샷이 없습니다")
    print("fetch trades", flush=True)
    df = fetch_trades(payload["period_start"], payload["period_end"])
    print(f"trades={len(df)}", flush=True)
    payload["yearly"] = build_yearly(
        year_aggs(df),
        as_of_month=payload["as_of_month"],
        period_start=payload["period_start"],
        period_end=payload["period_end"],
        window_years=int(payload.get("window_years") or 5),
    )
    print("fit", flush=True)
    payload["regression"] = fit_regressions(df)
    enrich_public(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    public_path = path.with_name("land_road_jimok_ratio_public.json")
    public_path.write_text(
        json.dumps(payload["public"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    p = argparse.ArgumentParser(description="도로 지목 2차 — 연도별 r, 칸 안 회귀")
    p.add_argument("--out", default=str(OUT))
    args = p.parse_args()
    payload = attach_phase2(Path(args.out))
    for year in payload["yearly"]:
        bits = []
        for band in year["bands"]:
            cut = band["cuts"]["10"]
            bits.append(f"{band['id']}={cut['n_cells']}:{cut['r_p50']}")
        flag = " partial" if year["partial"] else ""
        print(f"{year['year']}{flag} " + " ".join(bits), flush=True)
    for band in payload["regression"]["bands"]:
        cut = band["cuts"]["10"]
        print(
            f"reg {band['id']} cells={cut['n_cells']} factor={cut['factor']} beta={cut['beta']}",
            flush=True,
        )
    print(f"wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
