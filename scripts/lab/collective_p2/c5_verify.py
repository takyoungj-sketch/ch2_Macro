"""Phase C-5 — 검증 지표(전후 표). 전 = 로컬 원본 DB(읽기 전용, 덤프와 같은 상태), 후 = *_p2r(읽기 전용).

출력: logs/collective_p2/c5_verify.md (지번 없음 — 커밋 보고서에 옮길 수 있음), 실패 지표는 [NG].
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from _db import OUT, ROOT, engine, engine_db, md_table

sys.path.insert(0, str(ROOT / "pipeline"))
from collective.building_keys import load_split_units  # noqa: E402
from collective.integrity_p2 import MULTI_LEAF_SQL, SYNTH_SQL, judged_keys  # noqa: E402

AS_OF = "2026-10-01"
LEG = ["광주광역시", "전라남도"]
N = "전남광주통합특별시"
rows: list[tuple] = []


NAMED_KEY_COUNT_SQL = ("select count(*) from (select building_key from collective_transactions "
                       "where coalesce(building_name,'')<>'' group by building_key) z")
TIMEOUT_MS = 3_600_000  # 원본·리허설 원장 전체 집계(각 6.6M행)

# 임대 mart 합성 주소 행: mart (키·유형·대표 주소 6칸)과 같은 조합의 유효 거래가 그 창 기간에 하나도 없으면 합성.
# mart 키는 빌더와 같은 계산 키(빈 키 → 주소 해시)라 원장도 같은 식으로 계산한다.
_REP = ("addr3", "addr4", "addr5", "beopjungri_code", "lot_number", "road_name")


def _rent_key_sql() -> str:
    from rent.stats_pack import BUILDING_KEY_SQL

    return BUILDING_KEY_SQL


def rent_synth_rowwise_sql(tx: str = "rent_transactions", mart: str = "rent_building_stats") -> str:
    """기준(행 단위 대조): mart 행마다 원장 존재 확인. 정의는 분명하지만 운영 크기에서 1시간 넘음."""
    rep = " and ".join(f"t.{c} is not distinct from m.{c}" for c in _REP)
    return f"""
        with m as (select window_years, period_start, period_end, building_key, asset_type, {", ".join(_REP)}
                   from {mart} where as_of_month = :a)
        select m.window_years, count(*) filter (where not exists (
            select 1 from (select {_rent_key_sql()} as bk, * from {tx}) t
            where t.bk = m.building_key and t.asset_type = m.asset_type and t.is_valid
              and t.contract_date between m.period_start and m.period_end and {rep}))
        from m group by 1"""


def rent_synth_sql(tx: str = "rent_transactions", mart: str = "rent_building_stats") -> str:
    """새 방식: 창 기간마다 원장을 (계산 키·유형·대표 주소)로 한 번 집계 → mart 와 키 `=` 해시 조인(주소 칸은 NULL 같음 비교)."""
    cols = ", ".join(_REP)
    rep = " and ".join(f"g.{c} is not distinct from m.{c}" for c in _REP)
    # g 는 MATERIALIZED(한 번 집계) — 인라인되면 플래너가 mart 행마다 원장을 훑는 상관 하위 계획을 만든다.
    # g 는 대표 주소 6칸까지 묶었으므로 mart 행 하나에 맞는 g 행은 많아야 하나 → LEFT JOIN 후 짝 없는 행 수.
    return f"""
        with m as (select window_years, period_start, period_end, building_key, asset_type, {cols}
                   from {mart} where as_of_month = :a),
             p as materialized (select distinct window_years, period_start, period_end from m),
             g as materialized (
                   select p.window_years, {_rent_key_sql()} as bk, t.asset_type, {", ".join("t." + c for c in _REP)}
                   from {tx} t join p on t.contract_date between p.period_start and p.period_end
                   where t.is_valid
                   group by 1, 2, 3, {", ".join(str(i + 4) for i in range(len(_REP)))})
        select m.window_years, count(*) filter (where g.bk is null)
        from m left join g on g.window_years = m.window_years and g.bk = m.building_key
                          and g.asset_type = m.asset_type and {rep}
        group by 1"""


def add(name, before, after, ok, note=""):
    rows.append(("OK" if ok else "NG", name, before, after, note))


def one(c, sql, **p):
    return c.execute(text(sql), p).scalar()


def main():
    b, a = engine("collective", TIMEOUT_MS), engine_db("collective_stats_p2r", TIMEOUT_MS)
    bb, ab = engine("built", TIMEOUT_MS), engine_db("built_stats_p2r", TIMEOUT_MS)
    br, ar = engine("rent", TIMEOUT_MS), engine_db("rent_stats_p2r", TIMEOUT_MS)
    units = load_split_units()
    with b.connect() as cb, a.connect() as ca:
        # 1 원장 행 수·hash 중복
        for t in ("collective_transactions", "collective_commercial_transactions"):
            x, y = one(cb, f"select count(*) from {t}"), one(ca, f"select count(*) from {t}")
            add(f"{t} 행 수(삭제 0)", x, y, x == y)
            q = f"select count(*) from (select transaction_hash from {t} group by 1 having count(*)>1) z"
            x, y = one(cb, q), one(ca, q)
            add(f"{t} hash 중복 묶음", x, y, x == y, "이전 전과 같음(기존 중복은 범위 밖)")
            x, y = (one(c, f"select count(*) from {t} where addr1 = any(:l)", l=LEG) for c in (cb, ca))
            add(f"{t} 옛 시도명 행", x, y, y == 0)
        # 2 전남광주 2019·2020
        for yr, exp in ((2019, 47765), (2020, 67380)):
            y = one(ca, "select count(*) from collective_transactions where addr1=:n and contract_year=:y", n=N, y=yr)
            add(f"전남광주 {yr} 원장 행", one(cb, "select count(*) from collective_transactions where addr1=:n and contract_year=:y", n=N, y=yr), y, y == exp, f"기대 {exp:,}")
        # 3 키
        # count(DISTINCT) 는 정렬만 써서 원본에서 20분 제한을 넘겼다 → GROUP BY(해시 집계)로 같은 값
        qk = NAMED_KEY_COUNT_SQL
        kb, ka = one(cb, qk), one(ca, qk)
        exp = kb - 3967 + 168 - len(units) + 3447
        add("이름 키 수", kb, ka, ka == exp, f"예측 {exp:,} = 전 − 호남 옛 3,967 + 새 이름 168 − 분할 {len(units):,} + 조각 3,447")
        km = one(ca, "select count(*) from collective_building_key_map")
        add("연결표 행 수", "—", km, km == 7414, "예측 7,414(호남 3,967 + 분할 3,447)")
        sp = one(ca, "select count(distinct old_key) from collective_building_key_map where reason like '%split%'")
        add("분할 옛 키 수", "—", sp, sp == len(units))
        rem = one(ca, "select count(*) from collective_transactions where building_key = any(:k)", k=list(units))
        add("분할 대상 옛 키 남은 행", "—", rem, rem == 0)
        # 4 7년 building_stats
        q7 = "select coalesce(sum(count),0) from collective_building_stats where as_of_month=:a and window_years=7 and addr1 = any(:l)"
        x, y = one(cb, q7, a=AS_OF, l=LEG), one(ca, q7, a=AS_OF, l=LEG)
        add("7년 building_stats 옛 시도명 거래", x, y, y == 0)
        qn = "select coalesce(sum(count),0) from collective_building_stats where as_of_month=:a and window_years=7 and addr1=:n"
        x, y = one(cb, qn, a=AS_OF, n=N), one(ca, qn, a=AS_OF, n=N)
        add("7년 building_stats 전남광주 거래 증가", x, y, y - x == 76469, f"증가 {y - x:,} (기대 76,469)")
        for w in (3, 5):
            q = "select count(*), coalesce(sum(count),0) from collective_building_stats where as_of_month=:a and window_years=:w"
            x, y = tuple(cb.execute(text(q), {"a": AS_OF, "w": w}).one()), tuple(ca.execute(text(q), {"a": AS_OF, "w": w}).one())
            add(f"{w}년 building_stats 행/거래", f"{x[0]:,} / {x[1]:,}", f"{y[0]:,} / {y[1]:,}", x[1] == y[1], "거래 합 같아야 함(키만 바뀜)")
        # 5 rolling 7년 광산구·순천 아파트 버킷
        for sgg in ("광산구", "순천시"):
            q = """select count(distinct r.bucket_index) from collective_building_rolling_stats r
                   join collective_building_stats s on s.building_key=r.building_key and s.asset_type=r.asset_type
                    and s.as_of_month=r.as_of_month and s.window_years=r.window_years
                   where r.as_of_month=:a and r.window_years=7 and r.asset_type='apartment' and s.addr1=:n and s.addr2=:g"""
            x, y = one(cb, q, a=AS_OF, n=N, g=sgg), one(ca, q, a=AS_OF, n=N, g=sgg)
            q2 = """select count(*) filter (where nb < 7), count(*) from (select r.building_key, count(distinct r.bucket_index) nb
                   from collective_building_rolling_stats r join collective_building_stats s on s.building_key=r.building_key
                    and s.asset_type=r.asset_type and s.as_of_month=r.as_of_month and s.window_years=r.window_years
                   where r.as_of_month=:a and r.window_years=7 and r.asset_type='apartment' and s.addr1=:n and s.addr2=:g
                     and s.count >= 30 group by 1) z"""
            y2 = tuple(ca.execute(text(q2), {"a": AS_OF, "n": N, "g": sgg}).one())
            add(f"rolling 7년 {sgg} 아파트 버킷 종류", x, y, y == 7, f"7년 거래 30건+ 단지 중 버킷<7: {y2[0]}/{y2[1]}")
        # 6 annual 2019~2020 시도 합 = 원장 합
        q = """with an as (select addr1, contract_year, sum(count) n from collective_building_annual_stats where contract_year in (2019,2020) group by 1,2),
               l as (select addr1, contract_year, count(*) n from collective_transactions where is_valid and unit_price>0 and contract_year in (2019,2020) group by 1,2)
               select coalesce(an.addr1,l.addr1), coalesce(an.contract_year,l.contract_year), coalesce(an.n,0), coalesce(l.n,0)
               from an full join l using (addr1, contract_year) order by 1,2"""
        ann = ca.execute(text(q)).all()
        bad = [r for r in ann if int(r[2]) != int(r[3])]
        hon = [r for r in ann if r[0] in (N, *LEG)]
        add("annual 2019~2020 전남광주 합 = 원장 합", "—", "; ".join(f"{r[0]} {r[1]}: {int(r[2]):,}/{int(r[3]):,}" for r in hon),
            all(int(r[2]) == int(r[3]) for r in hon) and not any(r[0] in LEG for r in hon))
        add("annual 2019~2020 시도 합 ≠ 원장 합(전국)", "—", f"{len(bad)}건 / {len(ann)}", True,
            "조건 2② 로 호남 밖 묵은 행은 남김 → c6 보고")
        # 7 market_stats 7년 코드 12 ≥ 5년
        q = """select market_domain, window_years, sum(count) from market_stats where as_of_month=:a and region_level='sido'
               and region_code='12' and window_years in (5,7) group by 1,2"""
        m = {(r[0], r[1]): int(r[2]) for r in ca.execute(text(q), {"a": AS_OF})}
        mb = {(r[0], r[1]): int(r[2]) for r in cb.execute(text(q), {"a": AS_OF})}
        for at in sorted({k[0] for k in m}):
            add(f"market_stats 코드 12 {at} 7년 ≥ 5년", f"{mb.get((at, 7), 0):,} / {mb.get((at, 5), 0):,}",
                f"{m.get((at, 7), 0):,} / {m.get((at, 5), 0):,}", m.get((at, 7), 0) >= m.get((at, 5), 0))
        # 7b market_stats 3·5년 불변(프로필 근거)
        q = """select market_domain, region_level, region_code, window_years, count, median from market_stats
               where as_of_month=:a and window_years in (3,5)"""
        try:
            x = pd.read_sql(text(q), cb, params={"a": AS_OF})
            y = pd.read_sql(text(q), ca, params={"a": AS_OF})
            k = ["market_domain", "region_level", "region_code", "window_years"]
            mm = x.merge(y, on=k, how="outer", suffixes=("_b", "_a"), indicator=True)
            diff = mm[(mm["_merge"] != "both") | (mm["count_b"] != mm["count_a"]) | ((mm["median_b"] - mm["median_a"]).abs() > 1e-9)]
            add("market_stats 3·5년 행 불변", f"{len(x):,}", f"{len(y):,}", len(diff) == 0, f"차이 {len(diff)}행")
            diff.to_csv(OUT / "c5_market35_diff.csv", index=False, encoding="utf-8-sig")
        except Exception as ex:  # noqa: BLE001
            add("market_stats 3·5년", "—", f"실패 {type(ex).__name__}: {ex}"[:120], False)
        # 8 합성 주소·다법정동
        syn = {int(w): int(n) for w, n in ca.execute(text(SYNTH_SQL), {"as_of": AS_OF}).all()}
        synb = {int(w): int(n) for w, n in cb.execute(text(SYNTH_SQL), {"as_of": AS_OF}).all()}
        add("building_stats 합성 주소 행 3/5/7", str(synb), str(syn), all(v == 0 for v in syn.values()))
        multi = {r[0] for r in ca.execute(text(MULTI_LEAF_SQL))}
        pend = multi - judged_keys(ca)
        add("동 이름 ≥2 키 중 판정 밖", "—", len(pend), len(pend) == 0, f"동 이름 ≥2 키 {len(multi):,}(유지·분할 조각)")
        # 10 커버리지(최신 as_of 5년 단지 목록 기준)
        for nm, tbl in (("단지 속성", "collective_building_attributes"), ("공시지가", "collective_building_assessed_land_price"),
                        ("지오코드", "collective_building_geocodes")):
            q = f"""select count(*) filter (where exists (select 1 from {tbl} x where x.building_key=s.building_key)), count(*)
                    from collective_building_stats s where s.as_of_month=:a and s.window_years=5 and s.asset_type='apartment'"""
            x, y = tuple(cb.execute(text(q), {"a": AS_OF}).one()), tuple(ca.execute(text(q), {"a": AS_OF}).one())
            add(f"아파트 5년 단지 {nm} 커버리지", f"{x[0]:,}/{x[1]:,} ({x[0]/max(x[1],1):.2%})", f"{y[0]:,}/{y[1]:,} ({y[0]/max(y[1],1):.2%})",
                True, "떨어지면 c5_coverage_drop.csv")
        # 11 거래유형 잔여
        q = """select count(*) filter (where deal_type is not null and deal_type not in ('중개거래','직거래')), count(*) filter (where deal_type is null)
               from collective_transactions where asset_type='presale' and contract_date >= '2021-11-01' and contract_date < '2025-09-01'"""
        x, y = tuple(cb.execute(text(q)).one()), tuple(ca.execute(text(q)).one())
        add("N-1 분양권 비정상값 / 공란", f"{x[0]:,} / {x[1]:,}", f"{y[0]:,} / {y[1]:,}", y[0] == 0 and y[1] == 0)
        q = "select count(*) from collective_commercial_transactions where deal_type is null and contract_date >= '2021-11-01'"
        x, y = one(cb, q), one(ca, q)
        add("N-2 비주거 거래유형 공란(2021-11~)", x, y, y <= 1, "남는 1 = 실행 간 hash 충돌")
    with bb.connect() as cb, ab.connect() as ca:
        x, y = one(cb, "select count(*) from built_transactions"), one(ca, "select count(*) from built_transactions")
        add("built_transactions 행 수", x, y, x == y)
        x, y = (one(c, "select count(*) from built_transactions where addr1 = any(:l)", l=LEG) for c in (cb, ca))
        add("built_transactions 옛 시도명 행", x, y, y == 0)
        q = "select count(*) from built_scope_stats where as_of_month=:a and addr1 = any(:l)"
        x, y = one(cb, q, a=AS_OF, l=LEG), one(ca, q, a=AS_OF, l=LEG)
        add(f"built_scope_stats {AS_OF} 옛 시도명 행", x, y, y == 0)
    with br.connect() as cb, ar.connect() as ca:
        x, y = one(cb, "select count(*) from rent_transactions"), one(ca, "select count(*) from rent_transactions")
        add("rent_transactions 행 수", x, y, x == y)
        x, y = (one(c, "select count(*) from rent_transactions where building_key = any(:k)", k=list(units)) for c in (cb, ca))
        add("임대 분할 대상 옛 키 행", x, y, y == 0)
        # 행마다 원장 열 building_key 로 찾던 옛 쿼리는 계산 키 행(원장 빈 키 367만)을 못 찾아 1시간 제한을 넘기고
        # 그 행을 합성으로 잘못 셌다 → 원장도 계산 키로 한 번 집계해 조인(rent_synth_sql, 행 단위 기준과 같음을 테스트)
        syn = {int(r[0]): int(r[1]) for r in ca.execute(text(rent_synth_sql()), {"a": AS_OF}).all()}
        add("임대 mart 합성 주소 행 3/5/7", "2,836/4,037/4,714(A-3)", str(syn), all(v == 0 for v in syn.values()))
        x, y = one(cb, "select count(*) from rent_sale_building_map"), one(ca, "select count(*) from rent_sale_building_map")
        add("rent_sale_building_map 행", x, y, True, "c7 에서 연결 실측")
    out = ["# C-5 검증 지표 (전 = 로컬 원본, 후 = *_p2r)", "", md_table(rows, ["판정", "지표", "전", "후", "비고"])]
    (OUT / "c5_verify.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    return 1 if any(r[0] == "NG" for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
