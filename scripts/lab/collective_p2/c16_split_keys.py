"""분할 새 키 목록 파일 — 연결표(collective_building_key_map, reason 에 split)의 new_key, 한 줄 하나.

리허설 DB 읽기 전용. 출력 경로 인자(기본 logs/collective_p2/p2_split_new_keys.txt). 키는 해시라 지번 없음.
속성(K-apt·title_fill)·공시지가 단계의 --keys-file 로 쓴다.
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

from _db import OUT, engine_db


def write_keys(path: Path) -> int:
    with engine_db("collective_stats_p2r").connect() as c:
        assert c.execute(text("select current_database()")).scalar() == "collective_stats_p2r"
        keys = sorted({r[0].strip() for r in c.execute(text(
            "SELECT DISTINCT new_key FROM collective_building_key_map WHERE reason LIKE '%split%'"))})
    if not keys:
        raise SystemExit("분할 새 키 0 — 연결표 확인")
    path.write_text("\n".join(keys) + "\n", encoding="utf-8")
    return len(keys)


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "p2_split_new_keys.txt"
    print(f"split new keys {write_keys(p):,} -> {p}")
