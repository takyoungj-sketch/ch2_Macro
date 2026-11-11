"""C-04 — 아파트 '동' 결측 (읽기 전용).

3-1 DB 계약월별 결측률(전국·시도)
3-2 보관 원천 CSV(2607~2611 업데이트, raw base) 같은 계약월의 동 채움률 비교 — 늦게 공개되는지
3-3 동 있음/없음 의미 중복(같은 키·계약일·가격·면적·층) 수
3-4 5년 창 단지별 결측률 분포
출력: logs/collective_phase0/c04_result.md
"""
from __future__ import annotations

import csv

csv.field_size_limit(10**9)
import io
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from _db import OUT, ROOT, engine, md_table, q

RAW = Path(r"D:\ch2\ch2_Macro\raw")  # 원본 폴더 raw (읽기만)
if not RAW.is_dir():
    RAW = ROOT / "raw"


def db_monthly():
    with engine("collective").connect() as c:
        rows = q(
            c,
            """select to_char(contract_date,'YYYY-MM') ym, addr1, count(*) n,
                      count(*) filter (where coalesce(btrim(dong),'')='') miss
               from collective_transactions
               where is_valid and asset_type='apartment' and contract_date >= '2024-01-01' and contract_date < '2026-11-01'
               group by 1,2""",
        )
    df = pd.DataFrame(rows, columns=["ym", "a1", "n", "miss"])
    nat = df.groupby("ym")[["n", "miss"]].sum().reset_index()
    nat["rate"] = (100 * nat.miss / nat.n).round(1)
    piv = df.assign(rate=(100 * df.miss / df.n).round(1)).pivot_table(index="a1", columns="ym", values="rate")
    cols = [c for c in piv.columns if c >= "2025-10"]
    md = [
        "### 3-1 전국 계약월별 아파트 동 결측률",
        md_table(nat.values.tolist(), ["계약월", "거래", "동 결측", "결측률%"]),
        "### 3-1 시도별 결측률% (2025-10 이후)",
        md_table([[i] + list(r) for i, r in zip(piv.index, piv[cols].values)], ["시도"] + cols),
    ]
    return md


def _read_molit_csv(path: Path):
    raw = path.read_bytes()
    for enc in ("cp949", "utf-8-sig"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    lines = txt.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith('"NO"'))
    rd = csv.reader(io.StringIO("\n".join(lines[start:])))
    header = next(rd)
    i_ym = header.index("계약년월")
    i_dong = header.index("동")
    for row in rd:
        if len(row) <= i_dong:
            continue
        yield row[i_ym], row[i_dong]


def raw_compare():
    """cycle 폴더별로 같은 계약월의 동 채움률."""
    targets = {}
    for d in sorted(RAW.glob("26*업데이트")):
        for sub in d.glob("아파트_*"):
            targets[d.name] = sub
    base = RAW / "raw base" / "아파트_2021_2026"
    if base.is_dir():
        targets["raw base"] = base
    res = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for label, folder in targets.items():
        for f in sorted(folder.glob("*.csv")):
            for ym, dong in _read_molit_csv(f):
                if not re.fullmatch(r"\d{6}", ym) or ym < "202501":
                    continue
                cell = res[ym][label]
                cell[0] += 1
                if dong.strip() not in ("", "-"):
                    cell[1] += 1
    labels = list(targets)
    rows = []
    for ym in sorted(res):
        r = [ym]
        for lb in labels:
            n, filled = res[ym][lb]
            r.append(f"{n:,} / {100 * (n - filled) / n:.1f}%" if n else "")
        rows.append(r)
    return ["### 3-2 원천 CSV 다운로드 시점별 (거래 / 동 결측률)", md_table(rows, ["계약월"] + labels)]


def dup_and_dist():
    with engine("collective").connect() as c:
        dup = q(
            c,
            """with x as (
                 select building_key, contract_date, price, exclusive_area, floor,
                        count(*) filter (where coalesce(btrim(dong),'')='') e,
                        count(*) filter (where coalesce(btrim(dong),'')<>'') f
                 from collective_transactions where is_valid and asset_type='apartment' and contract_date >= '2024-01-01'
                 group by 1,2,3,4,5)
               select count(*) filter (where e>0 and f>0), sum(least(e,f)) filter (where e>0 and f>0), count(*) filter (where e+f>1) from x""",
        )
        dist = q(
            c,
            """with b as (
                 select building_key, count(*) n, count(*) filter (where coalesce(btrim(dong),'')='') miss
                 from collective_transactions where is_valid and asset_type='apartment'
                   and contract_date >= '2021-11-01' and contract_date < '2026-11-01' group by 1)
               select case when miss=0 then '0%' when miss*1.0/n < 0.05 then '0~5%' when miss*1.0/n < 0.1 then '5~10%'
                           when miss*1.0/n < 0.2 then '10~20%' when miss*1.0/n < 0.3 then '20~30%' when miss*1.0/n < 0.5 then '30~50%'
                           when miss < n then '50~100%' else '100%' end g,
                      count(*), sum(n), sum(miss)
               from b group by 1 order by min(miss*1.0/n)""",
        )
    md = [
        "### 3-3 같은 키·계약일·가격·면적·층에서 동 있음/없음이 함께 있는 묶음 (2024~)",
        md_table(dup, ["동있음+없음 묶음", "중복 의심 행(작은 쪽 합)", "같은 조건 2건 이상 묶음"]),
        "### 3-4 5년 창(2021-11~2026-10) 아파트 단지별 동 결측률 분포",
        md_table(dist, ["결측률 구간", "단지", "거래", "동 결측 거래"]),
    ]
    return md


def main():
    md = ["## C-04"] + db_monthly() + raw_compare() + dup_and_dist()
    (OUT / "c04_result.md").write_text("\n\n".join(md), encoding="utf-8")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
