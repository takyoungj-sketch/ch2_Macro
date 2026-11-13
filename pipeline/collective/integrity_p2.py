"""집합 2단계 재발 방지 — 월간 정합성 검사(읽기 전용).

verify_monthly_integrity.py --collective 에서 부른다. 단독 실행도 된다:
    python pipeline/collective/integrity_p2.py [--deep]

검사
  1. 원장 3종(집합 주거·비주거·복합) 옛 시도명(광주광역시·전라남도) 행 = 0            → ERR
  2. 이름 키 중 동 이름 ≥2 이고 판정 목록(분할·유지) 밖인 키 = 0                       → WARN(판정 대기열)
     동 이름 = addr4(리 아님) 아니면 addr3. 화성 코드 변형처럼 이름이 하나면 해당 없음.
  3. annual 시도·연도·유형 합(count) = 원장 합(2019~)                                   → ERR
  4. (--deep) 최신 as_of building_stats 주소 세트가 그 창의 거래에 실제로 있는지(합성 주소 0) → ERR
  5. C-2형: 같은 키·같은 법정동 안에서 본번이 다르고 건축년도도 다른 3건+ 묶음이 있는 키 중 C-2 판정 표
     (collective_building_key_c2_units) 밖 → WARN(C-2 반영 뒤 기대 0). 표가 없거나 비었는데 C-2형이 있으면 그렇게 경고.
     판정 표의 분할 키에서 표에 없는 본번(적재 때 가까운 조각에 붙은 것 등) → WARN 「확인 필요」
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Protocol

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from admin_names import LEGACY_SIDO_TO_CURRENT  # noqa: E402
from collective.building_keys import (  # noqa: E402
    SPLIT_UNITS_PATH,
    c2_table_state,
    judged_keys_c2,
    load_split_units_c2,
    main_lot_of,
)

LEGACY = sorted(LEGACY_SIDO_TO_CURRENT)

LEAF_SQL = "CASE WHEN coalesce(addr4,'') <> '' AND addr4 !~ '리$' THEN addr4 ELSE addr3 END"

MULTI_LEAF_SQL = f"""
SELECT building_key FROM collective_transactions
WHERE coalesce(building_name,'') <> ''
GROUP BY building_key
HAVING count(DISTINCT regexp_replace({LEAF_SQL}, '[읍면]$', '#')) > 1
"""

ANNUAL_VS_LEDGER_SQL = """
WITH a AS (
  SELECT addr1, contract_year, asset_type, sum(count)::bigint AS n
  FROM collective_building_annual_stats WHERE contract_year >= 2019 GROUP BY 1,2,3
), l AS (
  SELECT addr1, contract_year, asset_type, count(*)::bigint AS n
  FROM collective_transactions
  WHERE is_valid = true AND unit_price IS NOT NULL AND unit_price > 0 AND contract_year >= 2019
  GROUP BY 1,2,3
)
SELECT coalesce(a.addr1, l.addr1), coalesce(a.contract_year, l.contract_year), coalesce(a.asset_type, l.asset_type),
       coalesce(a.n, 0), coalesce(l.n, 0)
FROM a FULL JOIN l ON a.addr1 = l.addr1 AND a.contract_year = l.contract_year AND a.asset_type = l.asset_type
WHERE coalesce(a.n, 0) <> coalesce(l.n, 0)
ORDER BY 1, 2, 3
"""

SYNTH_SQL = """
WITH m AS (
  SELECT window_years, period_start, period_end, building_key, asset_type,
         addr3, addr4, addr5, beopjungri_code, lot_number, road_name
  FROM collective_building_stats WHERE as_of_month = :as_of
)
SELECT m.window_years, count(*) FILTER (WHERE NOT EXISTS (
  SELECT 1 FROM collective_transactions t
  WHERE t.building_key = m.building_key AND t.asset_type = m.asset_type
    AND t.is_valid AND t.unit_price > 0 AND t.contract_date BETWEEN m.period_start AND m.period_end
    AND t.addr3 IS NOT DISTINCT FROM m.addr3 AND t.addr4 IS NOT DISTINCT FROM m.addr4
    AND t.addr5 IS NOT DISTINCT FROM m.addr5 AND t.beopjungri_code IS NOT DISTINCT FROM m.beopjungri_code
    AND t.lot_number IS NOT DISTINCT FROM m.lot_number AND t.road_name IS NOT DISTINCT FROM m.road_name))
FROM m GROUP BY 1 ORDER BY 1
"""


# C-2형: 3건+ 본번 묶음(분양권 제외)끼리 본번·건축년도(최빈)가 모두 다른 쌍이 있는 (키·유형·법정동)
C2_SHAPE_SQL = """
WITH g AS (
  SELECT building_key, asset_type, left(beopjungri_code, 10) AS bjd, split_part(btrim(lot_number), '-', 1) AS ml,
         count(*) AS n, mode() WITHIN GROUP (ORDER BY building_year) AS y
  FROM collective_transactions
  WHERE is_valid AND asset_type <> 'presale' AND beopjungri_code IS NOT NULL AND coalesce(btrim(lot_number), '') <> ''
  GROUP BY 1, 2, 3, 4
  HAVING count(*) >= 3
)
SELECT DISTINCT a.building_key, a.asset_type, a.bjd
FROM g a JOIN g b ON a.building_key = b.building_key AND a.asset_type = b.asset_type AND a.bjd = b.bjd
WHERE a.ml < b.ml AND a.y IS NOT NULL AND b.y IS NOT NULL AND a.y <> b.y
"""

C2_LOTS_SQL = """
SELECT building_key, left(beopjungri_code, 10), split_part(btrim(lot_number), '-', 1), count(*)
FROM collective_transactions
WHERE building_key IN :k AND coalesce(btrim(lot_number), '') <> ''
GROUP BY 1, 2, 3
"""


def check_c2_shape(rep, cconn) -> None:
    """5. C-2형 경고(실패 아님). 판정은 집합 DB 표 collective_building_key_c2_units. 출력은 키 앞 12자·법정동 코드·건수만."""
    from sqlalchemy import bindparam

    state, n_rows = c2_table_state(cconn)
    judged = judged_keys_c2(cconn)
    rows = cconn.execute(text(C2_SHAPE_SQL)).all()
    pend = [r for r in rows if r[0] not in judged]
    if pend and state != "ok":
        rep.warn(f"C-2 판정 표 {'없음' if state == 'missing' else '비어 있음'} — C-2형(같은 법정동·다른 본번·다른 건축년도 3건+) "
                 f"{len(pend):,}곳(키·법정동)이 판정 없이 남음")
    elif pend:
        rep.warn(f"C-2형 판정 밖 {len(pend):,}곳(키·법정동) — 판정 대기(판정 표 {n_rows:,}행)")
    else:
        rep.ok(f"C-2형 (키·법정동) {len(rows):,}곳 모두 판정 표 안")
    for k, a, bjd in pend[:10]:
        rep.info(f"{a} {bjd} {k[:12]}…")
    units = load_split_units_c2(cconn)
    if not units:
        return
    got = cconn.execute(text(C2_LOTS_SQL).bindparams(bindparam("k", expanding=True)), {"k": sorted(units)}).all()
    unknown: dict[tuple[str, str], int] = {}
    for k, bjd, ml, _n in got:
        frags = units.get(k, {}).get(str(bjd))
        if frags is None:
            continue
        if main_lot_of(ml) not in {f[0] for f in frags}:
            unknown[(k, str(bjd))] = unknown.get((k, str(bjd)), 0) + 1
    if unknown:
        rep.warn(f"C-2 분할 키의 판정 표에 없는 본번 {sum(unknown.values()):,}개 ({len(unknown):,}곳) — 확인 필요")
    else:
        rep.ok("C-2 분할 키의 본번이 모두 판정 표 안")


class _Rep(Protocol):
    def section(self, title: str) -> None: ...
    def ok(self, msg: str) -> None: ...
    def warn(self, msg: str) -> None: ...
    def err(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...


def judged_keys(conn, path: Path = SPLIT_UNITS_PATH) -> set[str]:
    """판정이 끝난 키: 목록의 유지 키 + (이전 뒤) 연결표의 분할 새 키."""
    keys: set[str] = set()
    if path.is_file():
        with path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("decision") == "keep":
                    keys.add(r["base_key"])
    if conn.execute(text("SELECT to_regclass('public.collective_building_key_map') IS NOT NULL")).scalar():
        keys |= {r[0] for r in conn.execute(text(
            "SELECT DISTINCT new_key FROM collective_building_key_map WHERE reason LIKE '%split%'"))}
    return keys


def check_collective_p2(rep: _Rep, cconn, bconn=None, *, deep: bool = False, as_of=None) -> None:
    rep.section("집합 2단계 — 키·행정명 재발 방지")
    for table, conn in (("collective_transactions", cconn), ("collective_commercial_transactions", cconn),
                        ("built_transactions", bconn)):
        if conn is None:
            continue
        n = int(conn.execute(text(f"SELECT count(*) FROM {table} WHERE addr1 = ANY(:l)"), {"l": LEGACY}).scalar() or 0)
        (rep.ok if n == 0 else rep.err)(f"{table} 옛 시도명 행 {n:,}")

    multi = {r[0] for r in cconn.execute(text(MULTI_LEAF_SQL))}
    pending = multi - judged_keys(cconn)
    if pending:
        rep.warn(f"동 이름 ≥2 이름 키 중 판정 목록 밖 {len(pending):,}개 — 분할 판정 대기(scripts/lab/collective_p2/b1_split_decide.py)")
    else:
        rep.ok(f"동 이름 ≥2 이름 키 {len(multi):,}개 모두 판정 목록 안")

    bad = cconn.execute(text(ANNUAL_VS_LEDGER_SQL)).all()
    if bad:
        rep.err(f"annual 합 ≠ 원장 합 {len(bad)}건(시도·연도·유형)")
        for r in bad[:10]:
            rep.info(f"{r[0]} {r[1]} {r[2]}: annual {int(r[3]):,} / 원장 {int(r[4]):,}")
    else:
        rep.ok("annual 시도·연도·유형 합 = 원장 합(2019~)")

    check_c2_shape(rep, cconn)

    if deep:
        a = as_of or cconn.execute(text("SELECT max(as_of_month) FROM collective_building_stats")).scalar()
        for w, n in cconn.execute(text(SYNTH_SQL), {"as_of": a}).all():
            (rep.ok if int(n) == 0 else rep.err)(f"building_stats {a} {w}년 합성 주소 행 {int(n):,}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--deep", action="store_true")
    a = p.parse_args(argv)
    sys.path.insert(0, str(REPO / "pipeline" / "collective"))
    from collective.db_utils import get_collective_engine

    class R:
        errors = 0
        warnings = 0

        def section(self, t): print(f"\n=== {t} ===")
        def ok(self, m): print(f"  [OK] {m}")
        def warn(self, m): self.warnings += 1; print(f"  [WARN] {m}")
        def err(self, m): self.errors += 1; print(f"  [ERR] {m}")
        def info(self, m): print(f"        {m}")

    rep = R()
    eng = get_collective_engine()
    try:
        from built.db_utils import get_built_engine
        beng = get_built_engine()
    except Exception:  # noqa: BLE001
        beng = None
    with eng.connect() as c:
        if beng is not None:
            with beng.connect() as b:
                check_collective_p2(rep, c, b, deep=a.deep)
        else:
            check_collective_p2(rep, c, None, deep=a.deep)
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
