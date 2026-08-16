#!/usr/bin/env python3
"""유형별·권역 층화 읍면동 샘플 → Twin Lab fixture JSON.

예:
  cd pipeline
  python -m twin_lab.select_bench_eupmyeondong --asset-type commercial --sido-prefix 43 --n 60 --out fixtures/twin_bench_commercial_chungbuk.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "pipeline"))

from sqlalchemy import text  # noqa: E402

from app.built.db import get_built_engine  # noqa: E402

# 읍면동 코드 앞 2자리 → 권역 라벨 (거칠게)
_BASIN = {
    "11": "seoul",
    "26": "busan",
    "27": "daegu",
    "28": "incheon",
    "29": "gwangju",
    "30": "daejeon",
    "31": "ulsan",
    "36": "sejong",
    "41": "gyeonggi",
    "42": "gangwon",
    "43": "chungbuk",
    "44": "chungnam",
    "45": "jeonbuk",
    "46": "jeonnam",
    "47": "gyeongbuk",
    "48": "gyeongnam",
    "50": "jeju",
    "51": "gangwon",
    "52": "jeonbuk",
}

_DEFAULT_MIN_N = {
    "commercial": 30,
    "factory": 20,
    "detached": 40,
}


def _basin(code: str) -> str:
    return _BASIN.get(str(code)[:2], "other")


def _n_bucket(n: int) -> str:
    if n < 40:
        return "small"
    if n < 100:
        return "mid"
    return "large"


def fetch_eup_counts(
    conn,
    *,
    asset_type: str,
    year_from: int,
    year_to: int,
    sido_prefix: str | None,
    min_n: int,
) -> list[dict[str, Any]]:
    """built ledger 기준 읍면동별 건수 (eupmyeondong_code 8자리)."""
    params: dict[str, Any] = {
        "asset": asset_type,
        "yf": year_from,
        "yt": year_to,
        "min_n": min_n,
    }
    sido_sql = ""
    if sido_prefix:
        sido_sql = "AND LEFT(eupmyeondong_code, 2) = :sp"
        params["sp"] = sido_prefix.zfill(2)[:2]

    # 컬럼명은 built ledger 관례 — 없으면 에러로 드러냄
    # built_transactions: addr2≈시군구명, addr3≈읍면동명 (표시용)
    q = text(
        f"""
        SELECT
          LEFT(TRIM(eupmyeondong_code), 8) AS eup_code,
          MAX(NULLIF(TRIM(addr3), '')) AS eup_name,
          MAX(NULLIF(TRIM(addr2), '')) AS sigungu_name,
          COUNT(*)::int AS n
        FROM built_transactions
        WHERE asset_type = :asset
          AND contract_year BETWEEN :yf AND :yt
          AND is_valid IS DISTINCT FROM FALSE
          AND eupmyeondong_code IS NOT NULL
          AND LENGTH(TRIM(eupmyeondong_code)) >= 8
          {sido_sql}
        GROUP BY LEFT(TRIM(eupmyeondong_code), 8)
        HAVING COUNT(*) >= :min_n
        ORDER BY n DESC
        """
    )
    rows = conn.execute(q, params).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        code = str(r[0]).strip()[:8]
        out.append(
            {
                "eup_code": code,
                "eup_name": (r[1] or "").strip() or code,
                "sigungu_name": (r[2] or "").strip(),
                "n": int(r[3]),
                "basin": _basin(code),
                "n_bucket": _n_bucket(int(r[3])),
            }
        )
    return out


def stratified_sample(
    rows: list[dict[str, Any]],
    *,
    n_target: int,
    seed: int,
    holdout_frac: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """basin × n_bucket 층에서 균등 추출 후 holdout 분할."""
    rng = random.Random(seed)
    by_strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_strata[(r["basin"], r["n_bucket"])].append(r)

    strata_keys = sorted(by_strata.keys())
    if not strata_keys:
        return [], []

    per = max(1, n_target // len(strata_keys))
    picked: list[dict[str, Any]] = []
    for key in strata_keys:
        pool = list(by_strata[key])
        rng.shuffle(pool)
        take = min(per, len(pool))
        picked.extend(pool[:take])

    # 부족분 랜덤 보충
    if len(picked) < n_target:
        remain = [r for r in rows if r not in picked]
        rng.shuffle(remain)
        picked.extend(remain[: n_target - len(picked)])

    rng.shuffle(picked)
    picked = picked[:n_target]
    n_hold = max(1, int(round(len(picked) * holdout_frac))) if len(picked) >= 5 else 0
    holdout = picked[:n_hold]
    dev = picked[n_hold:]
    return dev, holdout


def to_fixture(
    *,
    asset_type: str,
    year_from: int,
    year_to: int,
    dev: list[dict[str, Any]],
    holdout: list[dict[str, Any]],
    sido_prefix: str | None,
    seed: int,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for group, rows in (("dev", dev), ("holdout", holdout)):
        for r in rows:
            label = f"{r['sigungu_name']} {r['eup_name']}".strip() or r["eup_code"]
            cases.append(
                {
                    "case_id": f"{r['eup_code']}_{group}",
                    "label": label,
                    "role": "primary" if group == "dev" else "holdout",
                    "admin_level": "eupmyeondong",
                    "region_codes": [r["eup_code"]],
                    "sample_group": group,
                    "strata": {
                        "basin": r["basin"],
                        "n_bucket": r["n_bucket"],
                        "tx_n": r["n"],
                    },
                    "notes": f"stratified seed={seed}",
                }
            )
    return {
        "version": "1.1",
        "description": f"Twin Lab stratified eup sample — {asset_type}",
        "defaults": {
            "asset_type": asset_type,
            "profile_version": "v2.1-national",
            "window_years": 3,
            "contract_year_from": year_from,
            "contract_year_to": year_to,
            "lift_delta_pp": 0.5,
            "twin_top_k": 5,
            "twin_scope_eup": "region",
            "twin_scope_beop": "same_sigungu",
            "sido_prefix": sido_prefix,
            "sample_seed": seed,
        },
        "cases": cases,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Stratified eupmyeondong sampler for Twin Lab")
    p.add_argument("--asset-type", default="commercial", choices=["commercial", "factory", "detached"])
    p.add_argument("--year-from", type=int, default=2019)
    p.add_argument("--year-to", type=int, default=2025)
    p.add_argument("--sido-prefix", default="43", help="법정 앞2자리. 빈 문자열=전국")
    p.add_argument("--min-n", type=int, default=None)
    p.add_argument("--n", type=int, default=60, help="목표 읍면동 수")
    p.add_argument("--holdout-frac", type=float, default=0.3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    min_n = args.min_n if args.min_n is not None else _DEFAULT_MIN_N[args.asset_type]
    sido = (args.sido_prefix or "").strip() or None

    eng = get_built_engine()
    if eng is None:
        raise SystemExit("BUILT_DATABASE_URL not configured")

    with eng.connect() as conn:
        rows = fetch_eup_counts(
            conn,
            asset_type=args.asset_type,
            year_from=args.year_from,
            year_to=args.year_to,
            sido_prefix=sido,
            min_n=min_n,
        )

    print(f"eligible eup={len(rows)} min_n={min_n} sido={sido or 'ALL'}", flush=True)
    if len(rows) < 5:
        raise SystemExit("eligible 읍면동 부족 — min-n 또는 sido-prefix 조정")

    dev, holdout = stratified_sample(
        rows, n_target=args.n, seed=args.seed, holdout_frac=args.holdout_frac
    )
    fixture = to_fixture(
        asset_type=args.asset_type,
        year_from=args.year_from,
        year_to=args.year_to,
        dev=dev,
        holdout=holdout,
        sido_prefix=sido,
        seed=args.seed,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote {args.out} cases={len(fixture['cases'])} dev={len(dev)} holdout={len(holdout)} as_of={date.today()}",
        flush=True,
    )


if __name__ == "__main__":
    main()
