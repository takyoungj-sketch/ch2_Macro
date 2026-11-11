"""P-01 — 직거래 더미 사전 조사 (읽기 전용). 4-1·4-2·4-3·4-5·4-6. 4-4는 p01_bootstrap.py.

출력: logs/collective_phase0/p01_result.md
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pandas as pd

from _db import OUT, engine, md_table, q

csv.field_size_limit(10**9)
RAW = Path(r"D:\ch2\ch2_Macro\raw")
DT = """case when deal_type='중개거래' then '중개' when deal_type='직거래' then '직거래'
             when coalesce(btrim(deal_type),'') in ('','-') then '미상' else '기타(비정상값)' end"""
W5 = "contract_date >= date '2021-11-01' and contract_date < date '2026-11-01'"


def counts():
    with engine("collective").connect() as c:
        nat = q(c, f"select asset_type, contract_year, {DT} dt, count(*) from collective_transactions where is_valid and contract_year>=2019 group by 1,2,3")
        sido = q(c, f"select addr1, asset_type, {DT} dt, count(*) from collective_transactions where is_valid and {W5} group by 1,2,3")
        first = q(c, """select asset_type, min(contract_date) filter (where deal_type in ('중개거래','직거래')),
                               min(contract_date) filter (where deal_type='직거래') from collective_transactions where is_valid group by 1""")
        mon = q(c, f"""select asset_type, to_char(contract_date,'YYYY-MM') ym, count(*), count(*) filter (where {DT}='미상')
                      from collective_transactions where is_valid and contract_date between '2021-08-01' and '2022-03-31' group by 1,2 order by 1,2""")
        com = q(c, f"select asset_type, contract_year, {DT} dt, count(*) from collective_commercial_transactions where is_valid and contract_year>=2019 group by 1,2,3")
    df = pd.DataFrame(nat, columns=["at", "y", "dt", "n"])
    piv = df.pivot_table(index=["at", "y"], columns="dt", values="n", fill_value=0).reset_index()
    md = ["### 4-1 전국 유형×계약연도×거래유형", md_table(piv.values.tolist(), [str(x) for x in piv.columns])]
    md += ["### 4-1 거래유형 첫 관측 계약일 (DB)", md_table(first, ["유형", "중개/직거래 첫 값", "직거래 첫 값"])]
    md += ["### 4-1 2021-08~2022-03 월별 미상 (DB)", md_table(mon, ["유형", "월", "거래", "미상"])]
    ds = pd.DataFrame(sido, columns=["a1", "at", "dt", "n"])
    ds = ds[ds["at"] == "apartment"].pivot_table(index="a1", columns="dt", values="n", fill_value=0)
    ds["직거래%"] = (100 * ds.get("직거래", 0) / ds.sum(axis=1)).round(1)
    md += ["### 4-1 5년 창 아파트 시도별", md_table([[i] + [int(v) if k != "직거래%" else v for k, v in r.items()] for i, r in ds.iterrows()], ["시도"] + list(ds.columns))]
    dc = pd.DataFrame(com, columns=["at", "y", "dt", "n"]).pivot_table(index=["at", "y"], columns="dt", values="n", fill_value=0).reset_index()
    md += ["### 4-5 비주거 집합 원장 거래유형", md_table(dc.values.tolist(), [str(x) for x in dc.columns])]
    return md


def raw_header_check():
    """원천 CSV에 거래유형 칸이 있는지 + 해당 연도 채움률 (표본 1개 시도)."""
    out = []
    probes = [
        ("raw long term/아파트_2010_2020", "서울특별시_아파트_매매_2020.csv"),
        ("raw long term/아파트_2010_2020", "서울특별시_아파트_매매_2019.csv"),
        ("raw long term/상업업무_2010_2020", None),
        ("2611업데이트/상업업무_202511_202610", None),
        ("2611업데이트/분양입주권_202511_202610", None),
    ]
    for folder, fname in probes:
        d = RAW / folder
        if not d.is_dir():
            out.append((folder, "-", "폴더 없음", ""))
            continue
        files = [d / fname] if fname else sorted(d.glob("서울*.csv"))[:1] or sorted(d.glob("*.csv"))[:1]
        for f in files:
            if not f.exists():
                continue
            txt = f.read_bytes().decode("cp949", errors="replace")
            lines = txt.splitlines()
            start = next(i for i, l in enumerate(lines) if l.startswith('"NO"'))
            rd = csv.reader(io.StringIO("\n".join(lines[start:])))
            h = next(rd)
            has = "거래유형" in h
            filled = n = 0
            if has:
                i = h.index("거래유형")
                ym_i = h.index("계약년월") if "계약년월" in h else None
                months = {}
                for row in rd:
                    if len(row) <= i:
                        continue
                    n += 1
                    v = row[i].strip()
                    ok = v in ("중개거래", "직거래")
                    filled += ok
                    if ym_i is not None:
                        m = months.setdefault(row[ym_i][:6], [0, 0])
                        m[0] += 1
                        m[1] += ok
                first = min((k for k, v in months.items() if v[1] > 0), default="") if has else ""
                out.append((folder, f.name, f"거래유형 칸 있음 · 채움 {filled:,}/{n:,}", f"첫 채움 계약월 {first}"))
            else:
                out.append((folder, f.name, "거래유형 칸 없음", ",".join(h[:3])))
    return ["### 4-1/4-5 원천 CSV 거래유형 칸", md_table(out, ["폴더", "파일", "결과", "비고"])]


def dist_ratio():
    with engine("collective").connect() as c:
        dist = q(c, f"""with b as (select building_key, asset_type, count(*) filter (where deal_type='직거래') d from collective_transactions
                         where is_valid and {W5} group by 1,2)
                       select asset_type, case when d=0 then '0' when d<5 then '1~4' when d<10 then '5~9' when d<20 then '10~19' else '20+' end g, count(*)
                       from b group by 1,2 order by 1, min(d)""")
        ratio = q(c, f"""with h as (
                           select building_key, asset_type, contract_year, (contract_month>6)::int hh,
                                  percentile_cont(0.5) within group (order by unit_price) filter (where deal_type='직거래') md,
                                  percentile_cont(0.5) within group (order by unit_price) filter (where deal_type='중개거래') mb,
                                  count(*) filter (where deal_type='직거래') nd, count(*) filter (where deal_type='중개거래') nb
                           from collective_transactions where is_valid and {W5} and unit_price>0 group by 1,2,3,4)
                         select asset_type, count(*), percentile_cont(array[0.1,0.25,0.5,0.75,0.9]) within group (order by md/mb),
                                avg((md/mb < 0.7)::int)
                         from h where nd>=1 and nb>=3 group by 1""")
        presale_garbage = q(c, """select contract_year, count(*) from collective_transactions where is_valid and asset_type='presale'
                                  and deal_type is not null and deal_type not in ('중개거래','직거래','-','') group by 1 order by 1""")
    md = ["### 4-2 5년 창 단지별 직거래 건수 분포", md_table(dist, ["유형", "직거래 건수", "단지"])]
    md += ["### 4-3 같은 단지·반기 직거래÷중개 중앙 단가 비율 (직거래≥1, 중개≥3)",
           md_table([(r[0], r[1], " / ".join(f"{x:.3f}" for x in r[2]), f"{100 * float(r[3]):.1f}%") for r in ratio],
                    ["유형", "단지×반기", "p10/p25/p50/p75/p90", "0.7배 미만"])]
    md += ["### 참고 — 분양권 deal_type 비정상값(중개사소재지 등) 연도별", md_table(presale_garbage, ["계약연도", "건"])]
    return md


def bulk():
    with engine("collective").connect() as c:
        res = q(c, """with g as (select asset_type, contract_year, contract_date, building_key, lot_number, count(*) n
                                  from collective_transactions where is_valid group by 1,2,3,4,5 having count(*)>=5)
                      select asset_type, contract_year, count(*), sum(n) from g where contract_year>=2019 group by 1,2 order by 1,2""")
        com = q(c, """with g as (select asset_type, contract_year, contract_date, cluster_key, lot_number, count(*) n
                                  from collective_commercial_transactions where is_valid group by 1,2,3,4,5 having count(*)>=5)
                      select asset_type, contract_year, count(*), sum(n) from g where contract_year>=2019 group by 1,2 order by 1,2""")
        top = q(c, f"""with t as (select cluster_key, contract_date, lot_number, count(*) n from collective_commercial_transactions
                                  where is_valid and {W5} group by 1,2,3),
                         s as (select cluster_key, sum(n) tot, sum(n) filter (where n>=5) bulk, max(n) mx from t group by 1)
                       select c.addr1, c.addr2, c.road_name, c.asset_type, s.tot, s.bulk, s.mx, round(100.0*s.bulk/s.tot,1)
                       from s join commercial_clusters c using (cluster_key) where s.bulk is not null and s.tot>=30
                       order by s.bulk*1.0/s.tot desc, s.tot desc limit 20""")
        topr = q(c, f"""with t as (select building_key, contract_date, lot_number, count(*) n from collective_transactions
                                   where is_valid and {W5} group by 1,2,3),
                          s as (select building_key, sum(n) tot, sum(n) filter (where n>=5) bulk, max(n) mx from t group by 1)
                        select b.addr1, b.addr2, b.addr3, b.asset_type, s.tot, s.bulk, s.mx, round(100.0*s.bulk/s.tot,1)
                        from s join collective_building_stats b on b.building_key=s.building_key
                             and b.as_of_month=(select max(as_of_month) from collective_building_stats) and b.window_years=5
                        where s.bulk is not null and s.tot>=30 order by s.bulk*1.0/s.tot desc, s.tot desc limit 20""")
        dn = q(c, """select contract_date, lot_number like '%*%' masked, count(*) from collective_commercial_transactions
                     where is_valid and road_name like '대농로%' and addr2 like '청주%' and contract_date between '2025-08-01' and '2025-08-31'
                     group by 1,2 order by 3 desc limit 3""")
    return [
        "### 4-6 주거 일괄 묶음(같은 계약일·지번·단지 ≥5건)", md_table(res, ["유형", "연도", "묶음", "거래"]),
        "### 4-6 비주거 일괄 묶음(같은 계약일·지번·cluster ≥5건)", md_table(com, ["유형", "연도", "묶음", "거래"]),
        "### 4-6 비주거 5년 창 묶음 비중 상위 20 (cluster 거래≥30)", md_table(top, ["시도", "시군구", "도로", "유형", "5년 거래", "묶음 거래", "최대 하루", "비중%"]),
        "### 4-6 주거 5년 창 묶음 비중 상위 20 (단지 거래≥30)", md_table(topr, ["시도", "시군구", "읍면동/구", "유형", "5년 거래", "묶음 거래", "최대 하루", "비중%"]),
        "### 대농로 2025-08 최대 일자(마스킹 여부)", md_table(dn, ["계약일", "마스킹 번지", "건"]),
    ]


def main():
    md = ["## P-01"] + counts() + raw_header_check() + dist_ratio() + bulk()
    (OUT / "p01_result.md").write_text("\n\n".join(md), encoding="utf-8")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
