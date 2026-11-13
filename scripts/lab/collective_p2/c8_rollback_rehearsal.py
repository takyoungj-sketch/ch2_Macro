"""Phase C-8 — 롤백 리허설 + 수정 전 덤프와 행 단위 비교.

1) migrate_p2_keys --rollback · fix_p2_deal_types --rollback (원장·부속 표·연결표, 리허설 DB)
2) 빌더가 다시 만든 mart 는 덤프에서 표 단위로 되돌린다(TRUNCATE 후 pg_restore --data-only -t) — 운영 롤백과 같은 방식
3) 모든 원래 표를 행 단위 해시로 비교: 기준 = 덤프와 같은 상태인 로컬 원본 DB(읽기 전용, 이 단계 동안 변경 없음)
   표 해시 = md5(정렬된 행 md5 이어붙이기). 시퀀스 현재값은 비교하지 않는다(행 데이터 아님).
출력: logs/collective_p2/c8_rollback.md
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from _db import OUT, ROOT, md_table

sys.path.insert(0, str(ROOT / "pipeline"))
from collective.migrate_p2_keys import REHEARSAL_RE, server_url_from_env  # noqa: E402

PY = r"D:\ch2\ch2_Macro\backend\.venv\Scripts\python.exe"
PG = Path(r"C:\Program Files\PostgreSQL\18\bin")
DUMPS = OUT / "dumps"
PAIRS = {"collective_stats": "collective_stats_p2r", "built_stats": "built_stats_p2r", "rent_stats": "rent_stats_p2r"}
MARTS = {
    "collective_stats": ["collective_building_stats", "collective_building_rolling_stats", "collective_building_annual_stats",
                         "collective_presale_lifetime_stats", "market_stats", "market_annual_stats",
                         "collective_commercial_cluster_stats", "collective_commercial_cluster_rolling_stats",
                         "collective_commercial_cluster_annual_stats", "collective_building_attributes", "builder_master"],
    "built_stats": ["built_scope_stats"],
    "rent_stats": ["rent_building_stats", "rent_building_rolling_stats"],
}
P2_TABLES = {"collective_building_key_map", "collective_cluster_key_map", "rent_building_key_map", "p2_migration_log"}


# 리허설이 만든 표의 이름 꼴: 이전 전 보존(*_p2_before), 조인 변경 전 결과 보존(*_p2_oldjoin, C-10)
REHEARSAL_SUFFIXES = ("_p2_before", "_p2_oldjoin")


def classify(t: str, before, after) -> str:
    """표 하나의 롤백 비교 결과. before/after = (행 수, 해시) 또는 None."""
    if before is not None and after is not None:
        return "같음" if before == after else "다름"
    if after is not None:
        if t in P2_TABLES or t.endswith(REHEARSAL_SUFFIXES):
            return "이전이 만든 표(원본에 없음)"
        return "원본에 없음"
    return "리허설에 없음"


def eng(db, ro):
    u = make_url(server_url_from_env()).set(database=db, drivername="postgresql+psycopg2")
    opts = "-c statement_timeout=0" + (" -c default_transaction_read_only=on" if ro else "")
    return create_engine(u, connect_args={"options": opts})


def run(cmd):
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"실패: {cmd[:3]}\n{r.stderr[-3000:]}")
    return round(time.time() - t0, 1), r.stdout[-1500:]


def table_hashes(e) -> dict[str, tuple[int, str]]:
    out = {}
    with e.connect() as c:
        tabs = [r[0] for r in c.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1"))]
        for t in tabs:
            n, h = c.execute(text(f'SELECT count(*), md5(coalesce(string_agg(x, \'\' ORDER BY x), \'\')) '
                                  f'FROM (SELECT md5(t::text) x FROM "{t}" t) z')).one()
            out[t] = (int(n), h)
    return out


def main():
    timings = []
    base = ["--collective-db", "collective_stats_p2r", "--built-db", "built_stats_p2r", "--rent-db", "rent_stats_p2r"]
    s, _ = run([PY, str(ROOT / "pipeline" / "collective" / "fix_p2_deal_types.py"), "--collective-db", "collective_stats_p2r", "--rollback"])
    timings.append(("거래유형 되돌리기", s))
    s, _ = run([PY, str(ROOT / "pipeline" / "collective" / "migrate_p2_keys.py"), *base, "--rollback"])
    timings.append(("키 이전 되돌리기(원장·부속 표·연결표)", s))
    u = make_url(server_url_from_env())
    env = {**os.environ, "PGPASSWORD": u.password or "", "PGHOST": u.host or "localhost",
           "PGPORT": str(u.port or 5432), "PGUSER": u.username or "postgres"}
    for src, tables in MARTS.items():
        dst = PAIRS[src]
        assert REHEARSAL_RE.match(dst)
        e = eng(dst, ro=False)
        with e.begin() as c:
            assert c.execute(text("SELECT current_database()")).scalar() == dst
            have = [t for t in tables if c.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{t}"}).scalar()]
            c.execute(text("TRUNCATE " + ", ".join(have)))
        t0 = time.time()
        args = [str(PG / "pg_restore.exe"), "--data-only", "--no-owner", "-d", dst]
        for t in have:
            args += ["-t", t]
        r = subprocess.run(args + [str(DUMPS / f"{src}.dir")], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise SystemExit(r.stderr[-3000:])
        timings.append((f"mart 덤프 복원 {dst} ({len(have)}표)", round(time.time() - t0, 1)))
    rows = []
    for src, dst in PAIRS.items():
        t0 = time.time()
        hb, ha = table_hashes(eng(src, ro=True)), table_hashes(eng(dst, ro=True))
        for t in sorted(set(hb) | set(ha)):
            rows.append((src, t, hb[t][0] if t in hb else "—", ha[t][0] if t in ha else "—", classify(t, hb.get(t), ha.get(t))))
        timings.append((f"행 해시 비교 {src}", round(time.time() - t0, 1)))
    diff = [r for r in rows if r[4] in ("다름", "리허설에 없음", "원본에 없음")]
    L = ["# C-8 롤백 리허설", "", md_table(timings, ["단계", "초"]), "",
         f"- 원래 표 비교: {sum(1 for r in rows if r[4] == '같음')}표 같음 · **차이 {len(diff)}표**", "",
         md_table(diff or [("—", "—", "—", "—", "차이 없음")], ["DB", "표", "원본 행", "리허설 행", "결과"]), "",
         "이전이 만든 표(남김, 비어 있거나 기록용): " + ", ".join(sorted({r[1] for r in rows if r[4].startswith('이전이')}))]
    (OUT / "c8_rollback.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    return 1 if diff else 0


if __name__ == "__main__":
    raise SystemExit(main())
