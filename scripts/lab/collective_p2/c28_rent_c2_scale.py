"""임대 C-2 규모 측정(Codex 검토 5, 읽기 전용 — 결정 전 자료). 리허설과 별개로 돌린다.

- 접속: 로컬 collective_stats·rent_stats 읽기 전용(default_transaction_read_only=on 확인). 리허설 DB 는 쓰지 않는다.
- 매매 판정: logs/collective_p2/c2_units_final.csv(로컬). 매매 2단계 키 ↔ 지금 키는 migrate_p2_keys 계획(읽기만)으로 잇는다.
- (가) 임대 원장 본번·부번 채움 정도
- (나) 매매 C-2 판정 키와 같은 임대 키(지금 키 = 매매 옛 키, 같은 법정동)를 판정 표 본번으로 나누면: 영향 키·거래 수,
      본번이 판정 표에 있음/없음
- (다) 판정 표 밖 임대 전용 동명: 같은 (임대 키·법정동) 안에 3건+ 본번이 둘 이상인 묶음 수·거래 수(매매 C-2 재측정과 같은 후보 규칙)
- 출력은 건수만(logs/collective_p2/c28_rent_c2_scale.md). 키·지번을 내지 않는다.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import bindparam, text

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "pipeline" / "collective"))

from collective import load_c2_units as lc  # noqa: E402
from collective.building_keys import main_lot_of, units_from_rows  # noqa: E402
from collective.migrate_p2_keys import (  # noqa: E402
    SPLIT_UNITS_PATH,
    Plan,
    _split_part_lookup,
    engine_for,
    load_split_units,
    plan_collective,
)

OUT = ROOT / "logs" / "collective_p2"
ASSETS = ("apartment", "rowhouse", "officetel")


def _ro(name: str):
    e = engine_for(name, read_only=True)
    with e.connect() as c:
        assert c.execute(text("SELECT current_database()")).scalar() == name
        assert c.execute(text("SHOW transaction_read_only")).scalar() == "on"
    return e


def md(rows, head):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] +
                     ["| " + " | ".join(f"{x:,}" if isinstance(x, int) else str(x) for x in r) + " |" for r in rows])


def main() -> int:
    t0 = time.time()
    df = lc.read_units(lc.DEFAULT_CSV)
    c2 = units_from_rows(df[["base_key", "beopjungri_code", "main_lot", "building_year", "part", "decision"]]
                         .itertuples(index=False, name=None))
    ce, re_ = _ro("collective_stats"), _ro("rent_stats")
    # 매매: 지금 키(옛 키) × 법정동 → C-2 2단계 키(base)
    plan = Plan()
    with ce.connect() as c:
        plan_collective(c, load_split_units(None), _split_part_lookup(SPLIT_UNITS_PATH), plan, c2)
    led = plan.ledger
    led = led[led["pre_c2_key"].isin(set(c2))]
    old2base: dict[tuple[str, str], str] = {}
    for (o, b10), g in led.groupby([led["building_key"], led["beopjungri_code"].astype(str).str[:10]]):
        old2base[(o, b10)] = g["pre_c2_key"].mode().iat[0]
    for base, by in c2.items():                                    # 키가 그대로인 본 키
        for b10 in by:
            old2base.setdefault((base, b10), base)
    olds = sorted({o for o, _ in old2base})
    L = ["# 임대 C-2 규모(읽기 전용)", ""]
    with re_.connect() as r:
        fill = r.execute(text("""SELECT asset_type, count(*), count(*) FILTER (WHERE lot_number ~ '^[0-9]+(-[0-9]+)?$'),
            count(*) FILTER (WHERE lot_number ~ '^[0-9]+-[0-9]+$'), count(*) FILTER (WHERE beopjungri_code IS NOT NULL)
            FROM rent_transactions WHERE is_valid AND asset_type IN :a GROUP BY 1 ORDER BY 1""").bindparams(
            bindparam("a", expanding=True)), {"a": list(ASSETS)}).all()
        L += ["## (가) 임대 원장 본번·부번", "",
              md([(a, int(n), f"{int(x) / int(n):.1%}", f"{int(y) / int(n):.1%}", f"{int(z) / int(n):.1%}") for a, n, x, y, z in fill],
                 ["유형", "유효 거래", "지번(본번[-부번]) 있음", "부번까지", "법정동 코드"]), ""]
        frames = []
        for i in range(0, len(olds), 2000):
            frames.append(pd.read_sql(text("""SELECT building_key, asset_type, left(beopjungri_code, 10) AS b10,
                       split_part(btrim(lot_number), '-', 1) AS ml, count(*) AS n
                FROM rent_transactions WHERE is_valid AND building_key IN :k AND coalesce(btrim(lot_number), '') <> ''
                GROUP BY 1, 2, 3, 4""").bindparams(bindparam("k", expanding=True)), r, params={"k": olds[i:i + 2000]}))
        rt = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["building_key", "asset_type", "b10", "ml", "n"])
        allg = pd.read_sql(text("""SELECT building_key, asset_type, left(beopjungri_code, 10) AS b10,
                   split_part(btrim(lot_number), '-', 1) AS ml, count(*) AS n
            FROM rent_transactions WHERE is_valid AND asset_type IN ('apartment', 'rowhouse', 'officetel')
              AND beopjungri_code IS NOT NULL AND coalesce(btrim(lot_number), '') <> '' GROUP BY 1, 2, 3, 4"""), r)
    ce.dispose()
    re_.dispose()
    # (나) 판정 표 키
    rt["ml"] = rt["ml"].map(main_lot_of)
    rt["base"] = [old2base.get((k, b)) for k, b in zip(rt["building_key"], rt["b10"])]
    rt = rt[rt["base"].notna()].copy()

    def part_of(base, b10, ml):
        for m, _y, p in c2[base].get(b10, []):
            if m == ml:
                return p
        return None

    rt["part"] = [part_of(b, d, m) for b, d, m in zip(rt["base"], rt["b10"], rt["ml"])]
    unit = rt.groupby(["building_key", "b10"])
    keys_hit = unit.ngroups
    split_keys = int(unit["part"].apply(lambda s: len({p for p in s if p is not None}) > 1).sum())
    tx_all = int(rt["n"].sum())
    tx_moved = int(rt.loc[rt["part"].notna() & (rt["part"] != 0), "n"].sum())
    tx_unknown = int(rt.loc[rt["part"].isna(), "n"].sum())
    by_asset = rt[rt["part"].notna() & (rt["part"] != 0)].groupby("asset_type")["n"].sum().astype(int).to_dict()
    L += ["## (나) 매매 C-2 판정 표로 임대 키를 나누면", "",
          md([("판정 표 (키·법정동)이 있는 임대 (키·법정동)", keys_hit),
              ("그중 둘 이상 조각으로 나뉘는 것", split_keys),
              ("임대 키 수(나뉘는 것)", int(rt[rt.groupby(["building_key", "b10"])["part"].transform(
                  lambda s: len({p for p in s if p is not None}) > 1)]["building_key"].nunique())),
              ("대상 거래", tx_all), ("본 조각 밖으로 옮겨질 거래", tx_moved), ("본번이 판정 표에 없는 거래", tx_unknown),
              ("옮겨질 거래 유형별", str(by_asset))], ["항목", "값"]), ""]
    # (다) 판정 표 밖 임대 전용 동명 후보
    allg["ml"] = allg["ml"].map(main_lot_of)
    allg = allg.groupby(["building_key", "asset_type", "b10", "ml"], as_index=False)["n"].sum()
    judged = set(zip(rt["building_key"], rt["b10"]))
    big = allg[allg["n"] >= 3]
    cnt = big.groupby(["building_key", "asset_type", "b10"]).size()
    cand = cnt[cnt >= 2].reset_index()[["building_key", "asset_type", "b10"]]
    cand = cand[[(k, b) not in judged for k, b in zip(cand["building_key"], cand["b10"])]]
    sub = allg.merge(cand, on=["building_key", "asset_type", "b10"])
    tx = sub.groupby(["building_key", "asset_type", "b10"])["n"].agg(["sum", "max"])
    L += ["## (다) 판정 표 밖 임대 전용 동명 후보(같은 키·법정동 안 3건+ 본번 ≥ 2)", "",
          md([(a, int((cand["asset_type"] == a).sum()), int(cand.loc[cand["asset_type"] == a, "building_key"].nunique()),
               int(tx.loc[tx.index.get_level_values(1) == a, "sum"].sum()),
               int((tx.loc[tx.index.get_level_values(1) == a, "sum"] - tx.loc[tx.index.get_level_values(1) == a, "max"]).sum()))
              for a in ASSETS],
             ["유형", "(키·법정동)", "키", "거래", "가장 큰 본번 밖 거래(옮겨질 수 있는 최대)"]), "",
          f"- 읽기 {round(time.time() - t0)}초. 같은 이름의 다른 건물인지는 판정하지 않았다(매매 C-2 재측정 1단계와 같은 후보 규칙)."]
    md_txt = "\n".join(L)
    (OUT / "c28_rent_c2_scale.md").write_text(md_txt, encoding="utf-8")
    print(md_txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
