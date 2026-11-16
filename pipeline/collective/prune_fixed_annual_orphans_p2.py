"""집합 2단계 — 고정 연도(2019~2020) annual 중 원장 근거 없는 행 정리(리허설 4단계 끝, T 결정 2026-11-16).

왜: 2019~2020 annual 은 다시 계산하지 않는 고정 연도다. 행정구역 개편(예: 인천 2026 새 구 — 검단구·서해구·영종구·제물포구)
    으로 키가 바뀐 옛 계산 행이 남으면 시도·연도·유형 합이 원장보다 커진다(integrity_p2 ERR).
규칙(일반, 지역 한정 없음): 2019·2020 annual 행 중 원장(is_valid·unit_price>0)에 같은
    (building_key·asset_type·contract_year·addr1) 거래가 하나도 없는 행을 지운다.
    - annual 은 (키·유형·연도) 하나에 한 행(유일 인덱스) → 키·유형·연도·시도 비교가 그 행의 근거.
    - addr2 까지 비교하면 세종(addr2 NULL)이 거짓으로 걸린다 → 넣지 않는다(키가 지역을 담는다).
보존: 지운 행 전체를 `collective_building_annual_orphan_p2_before` 에(p2_saved_at). --rollback 으로 되살린다. 멱등.
가드: 쓰기는 리허설 DB(assert_rehearsal_db) 또는 --real-apply(런북 5절 조건). 드라이런 기본.

  python -m collective.prune_fixed_annual_orphans_p2 --collective-db collective_stats_p2r            # 드라이런(지역·유형별)
  python -m collective.prune_fixed_annual_orphans_p2 --collective-db collective_stats_p2r --apply
  python -m collective.prune_fixed_annual_orphans_p2 --collective-db collective_stats_p2r --verify   # c6 에서도 부름
  python -m collective.prune_fixed_annual_orphans_p2 --collective-db collective_stats_p2r --rollback
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

_PIPE = Path(__file__).resolve().parents[1]
for _p in (_PIPE, _PIPE / "collective"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from collective.migrate_p2_keys import (  # noqa: E402
    add_real_apply_args,
    assert_rehearsal_db,
    check_write_targets,
    engine_for,
)

T = "collective_building_annual_stats"
KEEP = "collective_building_annual_orphan_p2_before"
YEARS = (2019, 2020)
# 인천 2026 개편 새 구 — 보고에서 「예상한 곳」으로 묶고 나머지는 따로 표시
EXPECTED = {("인천광역시", g) for g in ("검단구", "서해구", "영종구", "제물포구")}

ORPHAN_WHERE = """a.contract_year IN (2019, 2020) AND NOT EXISTS (
    SELECT 1 FROM collective_transactions t
    WHERE t.is_valid = true AND t.unit_price IS NOT NULL AND t.unit_price > 0
      AND t.building_key = a.building_key AND t.asset_type = a.asset_type
      AND t.contract_year = a.contract_year AND t.addr1 IS NOT DISTINCT FROM a.addr1)"""

# 고정 연도 시도·연도·유형 합 = 원장 합(전 지역) — c6·verify
FIXED_SUM_SQL = """
WITH a AS (SELECT addr1, contract_year, asset_type, sum(count)::bigint n FROM collective_building_annual_stats
           WHERE contract_year IN (2019, 2020) GROUP BY 1, 2, 3),
     l AS (SELECT addr1, contract_year, asset_type, count(*)::bigint n FROM collective_transactions
           WHERE is_valid = true AND unit_price IS NOT NULL AND unit_price > 0 AND contract_year IN (2019, 2020)
           GROUP BY 1, 2, 3)
SELECT coalesce(a.addr1, l.addr1), coalesce(a.contract_year, l.contract_year), coalesce(a.asset_type, l.asset_type),
       coalesce(a.n, 0), coalesce(l.n, 0)
FROM a FULL JOIN l ON a.addr1 IS NOT DISTINCT FROM l.addr1 AND a.contract_year = l.contract_year
                  AND a.asset_type = l.asset_type
WHERE coalesce(a.n, 0) <> coalesce(l.n, 0) ORDER BY 1, 2, 3"""


def _exists(conn: Connection, t: str) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{t}"}).scalar())


def breakdown(conn: Connection) -> list[dict]:
    """지울 행 — 지역(addr1·addr2)·유형·연도별 행 수·거래 수."""
    rows = conn.execute(text(f"""SELECT a.addr1, a.addr2, a.asset_type, a.contract_year, count(*), coalesce(sum(a.count), 0)
        FROM {T} a WHERE {ORPHAN_WHERE} GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4""")).all()
    return [{"addr1": r[0], "addr2": r[1], "asset_type": r[2], "year": int(r[3]), "rows": int(r[4]), "tx": int(r[5]),
             "expected": (r[0], r[1]) in EXPECTED} for r in rows]


def summary(bd: list[dict]) -> dict:
    by_region: dict[str, list[int]] = {}
    by_asset: dict[str, list[int]] = {}
    for b in bd:
        for d, k in ((by_region, f"{b['addr1']} {b['addr2'] or '-'}"), (by_asset, b["asset_type"])):
            d.setdefault(k, [0, 0])
            d[k][0] += b["rows"]
            d[k][1] += b["tx"]
    unexpected = sorted({f"{b['addr1']} {b['addr2'] or '-'}" for b in bd if not b["expected"]})
    return {"rows": sum(b["rows"] for b in bd), "tx": sum(b["tx"] for b in bd),
            "by_region": {k: {"rows": v[0], "tx": v[1]} for k, v in sorted(by_region.items())},
            "by_asset": {k: {"rows": v[0], "tx": v[1]} for k, v in sorted(by_asset.items())},
            "unexpected_regions": unexpected}


def apply(eng, dbname: str) -> dict:
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        s = summary(breakdown(conn))
        if not _exists(conn, KEEP):
            conn.execute(text(f"CREATE TABLE {KEEP} AS SELECT a.*, now() AS p2_saved_at FROM {T} a WITH NO DATA"))
        cols = [r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:t "
            "ORDER BY ordinal_position"), {"t": T})]
        c = ", ".join(cols)
        saved = conn.execute(text(f"""INSERT INTO {KEEP} ({c}) SELECT {c} FROM {T} a WHERE {ORPHAN_WHERE}
            AND NOT EXISTS (SELECT 1 FROM {KEEP} k WHERE k.id = a.id)""")).rowcount or 0
        deleted = conn.execute(text(f"DELETE FROM {T} a WHERE {ORPHAN_WHERE}")).rowcount or 0
        if deleted != s["rows"]:
            raise RuntimeError(f"삭제 {deleted} ≠ 계획 {s['rows']} — 롤백")
        return {**s, "saved_rows": int(saved), "deleted_rows": int(deleted)}


def rollback(eng, dbname: str) -> dict:
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        if not _exists(conn, KEEP):
            return {"restored": 0}
        cols = [r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:t "
            "ORDER BY ordinal_position"), {"t": T})]
        c = ", ".join(cols)
        clash = int(conn.execute(text(f"""SELECT count(*) FROM {KEEP} k JOIN {T} a ON a.building_key = k.building_key
            AND a.asset_type = k.asset_type AND a.contract_year = k.contract_year""")).scalar() or 0)
        if clash:
            raise RuntimeError(f"되살릴 행과 같은 (키·유형·연도) 행이 이미 {clash}개 — 멈춤")
        restored = conn.execute(text(f"INSERT INTO {T} ({c}) SELECT {c} FROM {KEEP}")).rowcount or 0
        conn.execute(text(f"DROP TABLE {KEEP}"))
        return {"restored": int(restored)}


def verify(conn: Connection) -> list[tuple[str, object, object, bool]]:
    """(지표, 기대, 실제, 통과) — c6 에서도 쓴다."""
    orphan = int(conn.execute(text(f"SELECT count(*) FROM {T} a WHERE {ORPHAN_WHERE}")).scalar() or 0)
    bad = conn.execute(text(FIXED_SUM_SQL)).all()
    return [("고정 연도(2019~2020) annual 중 원장 근거 없는 행", 0, orphan, orphan == 0),
            ("고정 연도 annual 합 ≠ 원장 합(전 지역, 시도·연도·유형)", 0, len(bad), not bad)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collective-db", required=True)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true")
    g.add_argument("--rollback", action="store_true")
    g.add_argument("--verify", action="store_true")
    ap.add_argument("--base-url", default="")
    add_real_apply_args(ap)
    a = ap.parse_args(argv)
    if a.real_apply and (a.rollback or a.verify):
        raise SystemExit("--real-apply 는 적용만 한다(실제 DB 되돌리기는 런북의 로컬 덤프 복원)")
    if a.real_apply:
        a.apply = True
    base = a.base_url or None
    if a.apply or a.rollback:
        check_write_targets([a.collective_db], a, base_url=base)
    if a.rollback:
        print(json.dumps(rollback(engine_for(a.collective_db, read_only=False, base_url=base), a.collective_db)))
        return 0
    if a.apply:
        print(json.dumps(apply(engine_for(a.collective_db, read_only=False, base_url=base), a.collective_db),
                         ensure_ascii=False, indent=1))
        return 0
    with engine_for(a.collective_db, read_only=True, base_url=base).connect() as conn:
        if a.verify:
            rows = verify(conn)
            for name, exp, got, ok in rows:
                print(f"{'OK ' if ok else 'NG '} {name}: 기대 {exp} / 실제 {got}")
            for r in conn.execute(text(FIXED_SUM_SQL)).all()[:10]:
                print(f"    {r[0]} {r[1]} {r[2]}: annual {int(r[3]):,} / 원장 {int(r[4]):,}")
            return 0 if all(r[3] for r in rows) else 1
        print(json.dumps({"dry_run": True, **summary(breakdown(conn))}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
