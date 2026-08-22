"""주소 매칭 vs PNU 조인 대조 — 대전·충북 아파트. 매칭 테이블은 바꾸지 않는다.

  python -m parcel_master.contrast
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from parcel_master.db_utils import get_collective_engine, get_parcel_engine
from parcel_master.paths import PILOT_SIDO, REPO
from parcel_master.pnu import pnu_from_tx

OUT = REPO / "docs" / "lab" / "parcel_master_pilot_contrast.json"

TX_SQL = """
SELECT
    building_key,
    MODE() WITHIN GROUP (ORDER BY beopjungri_code) AS beopjungri_code,
    MODE() WITHIN GROUP (ORDER BY lot_number) AS lot_number,
    COUNT(*)::int AS n_tx
FROM collective_transactions
WHERE is_valid = true
  AND asset_type = 'apartment'
  AND (beopjungri_code LIKE '30%' OR beopjungri_code LIKE '43%')
GROUP BY building_key
"""

ATTR_SQL = """
SELECT building_key, danji_code, match_tier, match_rule, households, n_tx
FROM collective_building_attributes
WHERE asset_type = 'apartment'
  AND snapshot_ym = (SELECT MAX(snapshot_ym) FROM collective_building_attributes)
"""


def _examples(rows: list[dict], n: int = 8) -> list[dict]:
    rows = sorted(rows, key=lambda r: r.get("n_tx") or 0, reverse=True)
    return rows[:n]


def main() -> None:
    coll = get_collective_engine()
    parcel = get_parcel_engine()
    with coll.connect() as conn:
        tx = pd.read_sql(text(TX_SQL), conn)
        attrs = pd.read_sql(text(ATTR_SQL), conn)
        bm = pd.read_sql(
            text(
                "SELECT danji_code, danji_name, pnu, beopjungri_code, lot_key, households "
                "FROM builder_master "
                "WHERE snapshot_ym = (SELECT MAX(snapshot_ym) FROM builder_master)"
            ),
            conn,
        )
    merged = tx.merge(attrs, on="building_key", how="left", suffixes=("", "_attr"))
    merged["tx_pnu"] = [
        pnu_from_tx(b, lot) for b, lot in zip(merged["beopjungri_code"], merged["lot_number"])
    ]

    by_pnu: dict[str, list[dict]] = defaultdict(list)
    for rec in bm.itertuples(index=False):
        if rec.pnu:
            by_pnu[str(rec.pnu)].append(
                {
                    "danji_code": rec.danji_code,
                    "danji_name": rec.danji_name,
                    "households": rec.households,
                }
            )

    buckets: dict[str, list[dict]] = defaultdict(list)
    for rec in merged.itertuples(index=False):
        pnu = rec.tx_pnu
        addr = rec.danji_code if pd.notna(rec.danji_code) else None
        tier = rec.match_tier if pd.notna(rec.match_tier) else None
        kapt = by_pnu.get(pnu, []) if pnu else []
        codes = [k["danji_code"] for k in kapt]
        item = {
            "building_key": rec.building_key,
            "beopjungri_code": rec.beopjungri_code,
            "lot_number": rec.lot_number,
            "tx_pnu": pnu,
            "match_tier": tier,
            "addr_danji": addr,
            "pnu_danji": codes,
            "n_tx": int(rec.n_tx or rec.n_tx_attr or 0),
        }
        if not pnu:
            buckets["tx_pnu_fail"].append(item)
        elif len(codes) == 0:
            buckets["pnu_no_kapt"].append(item)
        elif len(codes) > 1:
            buckets["pnu_multi_kapt"].append(item)
        elif addr and addr == codes[0]:
            buckets["agree"].append(item)
        elif addr and addr != codes[0]:
            buckets["conflict"].append(item)
        else:
            buckets["pnu_new"].append(item)

    addr_pnu_agree = addr_pnu_diff = addr_pnu_fail = 0
    for rec in bm.itertuples(index=False):
        derived = pnu_from_tx(rec.beopjungri_code, rec.lot_key)
        if not rec.pnu or not derived:
            addr_pnu_fail += 1
            continue
        if rec.pnu == derived:
            addr_pnu_agree += 1
        else:
            addr_pnu_diff += 1

    with parcel.connect() as conn:
        title_cov = conn.execute(
            text(
                """
                SELECT sido_code,
                       COUNT(*)::int AS n_building,
                       COUNT(DISTINCT pnu)::int AS n_pnu
                FROM building
                WHERE snapshot = (SELECT MAX(snapshot) FROM building)
                GROUP BY sido_code
                """
            )
        ).mappings().all()
        hh = conn.execute(
            text(
                """
                SELECT pnu, SUM(households)::int AS hh, COUNT(*)::int AS n_dong,
                       MIN(building_name) AS name
                FROM building
                WHERE snapshot = (SELECT MAX(snapshot) FROM building)
                  AND households IS NOT NULL
                GROUP BY pnu
                """
            )
        ).mappings().all()

    kapt_hh = {str(r.pnu): int(r.households) for r in bm.itertuples(index=False) if r.pnu and r.households}
    pnu_to_n = Counter(str(r.pnu) for r in bm.itertuples(index=False) if r.pnu)
    hh_cmp = []
    for row in hh:
        pnu = row["pnu"]
        if pnu_to_n.get(pnu, 0) != 1 or pnu not in kapt_hh:
            continue
        title_sum = row["hh"]
        kapt = kapt_hh[pnu]
        hh_cmp.append(
            {
                "pnu": pnu,
                "name": row["name"],
                "n_dong": row["n_dong"],
                "title_sum": title_sum,
                "kapt": kapt,
                "diff": title_sum - kapt,
            }
        )

    def n_tx(key: str) -> int:
        return int(sum(x["n_tx"] for x in buckets[key]))

    report = {
        "as_of": date.today().isoformat(),
        "sido": list(PILOT_SIDO),
        "n_buildings": int(len(merged)),
        "n_tx": int(merged["n_tx"].sum()),
        "buckets": {
            k: {"n": len(buckets[k]), "n_tx": n_tx(k)}
            for k in (
                "agree",
                "pnu_new",
                "conflict",
                "pnu_multi_kapt",
                "pnu_no_kapt",
                "tx_pnu_fail",
            )
        },
        "kapt_pnu_vs_lotkey": {
            "agree": addr_pnu_agree,
            "diff": addr_pnu_diff,
            "missing": addr_pnu_fail,
        },
        "title_latest_snapshot": [dict(r) for r in title_cov],
        "households_title_sum_vs_kapt_unique_pnu": {
            "n": len(hh_cmp),
            "exact": sum(1 for x in hh_cmp if x["diff"] == 0),
            "within_10pct": sum(
                1 for x in hh_cmp if abs(x["diff"]) <= 0.1 * max(x["kapt"], 1)
            ),
            "examples_big_diff": sorted(hh_cmp, key=lambda x: abs(x["diff"]), reverse=True)[:10],
        },
        "examples": {
            "conflict": _examples(buckets["conflict"]),
            "pnu_new": _examples(buckets["pnu_new"]),
            "pnu_multi_kapt": _examples(buckets["pnu_multi_kapt"]),
        },
        "note": (
            "매칭 테이블은 바꾸지 않음. pnu_new는 주소 규칙이 못 붙인 단지에 PNU가 유일 K-apt를 가리키는 건. "
            "pnu_multi_kapt는 분평주공3류(같은 필지 복수 단지). "
            "households 표제부 합은 동 단위 [40]이라 단지 세대수와 다를 수 있음."
        ),
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report["buckets"], ensure_ascii=False, indent=2))
    print("kapt_pnu_vs_lotkey", report["kapt_pnu_vs_lotkey"])
    print("households", {k: report["households_title_sum_vs_kapt_unique_pnu"][k] for k in ("n", "exact", "within_10pct")})
    print("wrote", OUT)


if __name__ == "__main__":
    main()
