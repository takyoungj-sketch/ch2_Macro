"""C-2 연결 키 이전 계획 미리 보기(읽기 전용) — 판정 파일을 DB 에 넣지 않고 migrate_p2_keys.plan_collective 에 바로 준다.

- 접속: collective_stats_p2r, default_transaction_read_only=on(확인). 쓰기 없음.
- 출력: plan.counts['collective'] 건수와 c25 예상(옮겨지는 거래 14,002 = 3건+ 본번, 유효 거래) 대조. 지번·키를 내지 않는다.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "pipeline" / "collective"))

from sqlalchemy import text  # noqa: E402

from collective import load_c2_units as lc  # noqa: E402
from collective.building_keys import units_from_rows  # noqa: E402
from collective.migrate_p2_keys import (  # noqa: E402
    SPLIT_UNITS_PATH,
    Plan,
    _split_part_lookup,
    engine_for,
    load_split_units,
    plan_collective,
)


def main() -> int:
    t0 = time.time()
    df = lc.read_units(lc.DEFAULT_CSV)
    c2 = units_from_rows(df[["base_key", "beopjungri_code", "main_lot", "building_year", "part", "decision"]]
                         .itertuples(index=False, name=None))
    eng = engine_for("collective_stats_p2r", read_only=True)
    plan = Plan()
    with eng.connect() as c:
        assert c.execute(text("SELECT current_database()")).scalar() == "collective_stats_p2r"
        assert c.execute(text("SHOW transaction_read_only")).scalar() == "on"
        assert c.execute(text("SELECT count(*) FROM collective_building_key_map")).scalar() == 0
        plan_collective(c, load_split_units(None), _split_part_lookup(SPLIT_UNITS_PATH), plan, c2)
        led = plan.ledger
        mv = led[led["reason"].str.contains("c2_split")]
        valid_ids = sorted(int(x) for x in mv["id"])
        nvalid = 0
        for i in range(0, len(valid_ids), 50_000):
            nvalid += int(c.execute(text("SELECT count(*) FROM collective_transactions WHERE is_valid AND id = ANY(:i)"),
                                    {"i": valid_ids[i:i + 50_000]}).scalar() or 0)
    eng.dispose()
    cc = plan.counts["collective"]
    by_asset = mv.groupby("asset_type")["new_key"].nunique().to_dict()
    out = {"counts": cc, "problems": plan.problems, "c2_moved_rows_valid": nvalid,
           "c2_new_keys_by_asset": {k: int(v) for k, v in sorted(by_asset.items())},
           "c2_new_parts_by_asset": {a: sum(1 for r in plan.c2_new_parts if r["asset_type"] == a)
                                     for a in sorted({r["asset_type"] for r in plan.c2_new_parts})},
           "c25_expect": {"added_keys": 2045, "moved_tx_3plus_valid": 14002}, "sec": round(time.time() - t0)}
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
