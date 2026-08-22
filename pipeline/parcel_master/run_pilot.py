"""축약대장 Track B 파일럿: 원본 인벤토리 → 표제부 집합 적재 → K-apt PNU → 대조.

  cd pipeline
  python -m parcel_master.run_pilot
  python -m parcel_master.run_pilot --skip-load
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from parcel_master import contrast, load_kapt_pnu, load_title_pilot, setup_db
from parcel_master.paths import PILOT_SIDO, REPO, land_ledger_dir, zone_dir

INV = REPO / "docs" / "lab" / "parcel_source_inventory.json"


def inventory() -> dict:
    expected = ["11", "12", "26", "27", "28", "30", "31", "36", "41", "43", "44", "47", "48", "50", "51", "52"]
    zone, land = zone_dir(), land_ledger_dir()
    c155, c003 = [], []
    pref12 = Counter()
    for d in sorted(zone.glob("AL_D155_*")):
        code = d.name.split("_")[2]
        csvs = list(d.glob("*.csv"))
        size = sum(p.stat().st_size for p in csvs)
        c155.append({"sido": code, "dir": d.name, "gb": round(size / 1e9, 2)})
        if code == "12" and csvs:
            import pandas as pd

            chunk = pd.read_csv(
                csvs[0],
                usecols=["법정동코드"],
                dtype=str,
                nrows=8000,
                encoding="cp949",
            )
            for v in chunk["법정동코드"].astype(str):
                pref12[v[:2]] += 1
    for d in sorted(land.glob("AL_D003_*")):
        code = d.name.split("_")[2]
        csvs = list(d.glob("*.csv"))
        size = sum(p.stat().st_size for p in csvs)
        c003.append({"sido": code, "dir": d.name, "gb": round(size / 1e9, 2)})
    have155 = {x["sido"] for x in c155}
    have003 = {x["sido"] for x in c003}
    report = {
        "al_d155": c155,
        "al_d003": c003,
        "missing_155": [s for s in expected if s not in have155],
        "missing_003": [s for s in expected if s not in have003],
        "al_d155_12_prefix_head": dict(pref12),
        "note": "전남광주 폴더·법정동 모두 통합코드 12. 구코드 29·46 폴더 없음. Track B는 이 파일을 적재하지 않음.",
    }
    INV.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("inventory", INV)
    print("missing_155", report["missing_155"], "missing_003", report["missing_003"])
    print("AL_D155_12 prefix", report["al_d155_12_prefix_head"])
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--skip-load", action="store_true", help="이미 적재됐으면 대조만")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--sido", nargs="+", default=list(PILOT_SIDO))
    args = p.parse_args()
    inventory()
    if args.skip_load:
        contrast.main()
        return
    setup_db.main()
    load_title_pilot.run(tuple(args.sido), args.refresh, skip_ledger=False)
    load_kapt_pnu.main()
    contrast.main()


if __name__ == "__main__":
    main()
