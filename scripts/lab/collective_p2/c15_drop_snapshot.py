"""Phase C — 리허설에 잘못 생긴 속성 판(202610) 지우기 (T 결정 2026-11-13, (가) 202607 에 새 키만).

collective_building_attributes·builder_master 에서 snapshot_ym = <판> 행만 지운다.
원본(로컬 collective_stats, 읽기 전용)에 그 판이 있으면 지우지 않는다(리허설이 만든 판이 아님).
쓰기는 리허설 DB 만(assert_rehearsal_db). 한 트랜잭션.

  python c15_drop_snapshot.py 202610            # 드라이런
  python c15_drop_snapshot.py 202610 --apply
"""
from __future__ import annotations

import json
import sys

from sqlalchemy import text

from _db import ROOT, engine

sys.path.insert(0, str(ROOT / "pipeline"))
from collective.migrate_p2_keys import assert_rehearsal_db, engine_for  # noqa: E402

DB = "collective_stats_p2r"
TABLES = ("collective_building_attributes", "builder_master")


def drop(ym: str, apply: bool) -> dict:
    with engine("collective").connect() as c:
        orig = {t: int(c.execute(text(f"SELECT count(*) FROM {t} WHERE snapshot_ym = :y"), {"y": ym}).scalar()) for t in TABLES}
    if any(orig.values()):
        raise SystemExit(f"원본에 {ym} 판이 있음 — 지우지 않음: {orig}")
    eng = engine_for(DB, read_only=not apply)
    out = {"snapshot_ym": ym, "original_rows": orig}
    with (eng.begin() if apply else eng.connect()) as c:
        if apply:
            assert_rehearsal_db(c, DB)
        for t in TABLES:
            n = int(c.execute(text(f"SELECT count(*) FROM {t} WHERE snapshot_ym = :y"), {"y": ym}).scalar())
            out[f"{t}_before"] = n
            if apply:
                out[f"{t}_deleted"] = int(c.execute(text(f"DELETE FROM {t} WHERE snapshot_ym = :y"), {"y": ym}).rowcount or 0)
                if out[f"{t}_deleted"] != n:
                    raise RuntimeError(f"{t} 삭제 수 불일치 — 롤백")
    eng.dispose()
    return out


if __name__ == "__main__":
    print(json.dumps(drop(sys.argv[1], "--apply" in sys.argv), ensure_ascii=False))
