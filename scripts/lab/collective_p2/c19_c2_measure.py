"""Phase C-2 측정 — 같은 법정동 안 동명 다른 건물 분리 규칙(T 예고)의 규모와 표본. 읽기 전용, 적용하지 않는다.

규칙(측정용 정의):
- 대상: 2단계 키(호남 표준화·동 분할 반영) 기준, 같은 (키, 유형, 법정동 10자리) 안 유효 거래(지번 있음).
- 본번 = 지번의 '-' 앞. 거래 3건 이상인 본번 묶음이 2개 이상이면 후보. 부번만 다르면 같은 본번 → 유지.
- 분양권: 유지(블록 지번).
- 연립·오피스텔: 3건+ 본번 묶음마다 나눈다.
- 아파트: 본번 묶음의 K-apt 단지코드(대표 PNU) 또는 표제부(공동주택) 건물명이 다를 때만 나눈다.
  같은 코드·같은 이름을 공유하는 묶음은 한 단지로 합친다(union-find). 근거가 없는 묶음은 가장 큰 묶음에 둔다.
- 3건 미만 본번은 가장 큰 묶음에 둔다(측정 가정).
DB: collective_stats_p2r(롤백 뒤 = 원본과 같음) · parcel_master_p2r(표제부 사본) — 모든 세션 읽기 전용.
2단계 키는 migrate_p2_keys.plan_collective 로 메모리에서만 계산한다(쓰기 없음).
출력: 표준출력(markdown, 지번 없음) + logs/collective_p2/c2_samples.csv (표본 30: 유지 10·분리 20, 지번 포함, gitignore)
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from _db import OUT, ROOT, engine_db, md_table

sys.path.insert(0, str(ROOT / "pipeline"))
from collective.migrate_p2_keys import (  # noqa: E402
    SPLIT_UNITS_PATH, Plan, _split_part_lookup, load_split_units, plan_collective)

TIMEOUT = 1_800_000
SEED = "c2-20261113"
MAIN_RAW = Path("D:/ch2/ch2_Macro/raw")

GROUPS = """
SELECT building_key, asset_type, beopjungri_code,
       split_part(btrim(lot_number), '-', 1) AS main_lot, count(*) AS n, max(display_name) AS name
FROM collective_transactions
WHERE is_valid AND beopjungri_code IS NOT NULL AND COALESCE(btrim(lot_number), '') <> ''
GROUP BY 1, 2, 3, 4
"""


def _ro(db):
    e = engine_db(db, timeout_ms=TIMEOUT)
    return e


def norm_name(s) -> str:
    if not isinstance(s, str):
        return ""
    s = re.sub(r"[^0-9A-Za-z가-힣]", "", s).lower()
    s = re.sub(r"(아파트|apt)$", "", s)
    return s


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def f(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def u(self, a, b):
        self.p[self.f(a)] = self.f(b)


def decide(asset: str, g: pd.DataFrame, kapt: dict, title: dict, dong: str):
    """(키·법정동) 한 묶음 → (결정, 사유, 부분 수, 옮겨지는 거래)."""
    big = g[g["n"] >= 3].sort_values("n", ascending=False).reset_index(drop=True)
    if len(big) < 2:
        return None
    if asset == "presale":
        return ("유지", "분양권", 1, 0)
    if asset in ("rowhouse", "officetel"):
        return ("분리", "본번 다름", len(big), int(g["n"].sum() - big["n"].iloc[0]))
    # 아파트
    ev = []
    for m in big["main_lot"]:
        ev.append((kapt.get((dong, m), set()), title.get((dong, m), set())))
    has_k = [bool(k) for k, _ in ev]
    has_t = [bool(t) for _, t in ev]
    uf = UF(len(big))
    for i in range(len(big)):
        for j in range(i + 1, len(big)):
            if (ev[i][0] & ev[j][0]) or (ev[i][1] & ev[j][1]):
                uf.u(i, j)
    # 근거 없는 묶음은 가장 큰 묶음(0)에 붙인다
    for i in range(len(big)):
        if not has_k[i] and not has_t[i]:
            uf.u(i, 0)
    comps = {}
    for i in range(len(big)):
        comps.setdefault(uf.f(i), []).append(i)
    if len(comps) == 1:
        if sum(has_k) >= 2:
            why = "아파트 K-apt 같음"
        elif sum(1 for a, b in zip(has_k, has_t) if a or b) >= 2:
            why = "아파트 표제부 같음"
        else:
            why = "아파트 근거 없음"
        return ("유지", why, 1, 0)
    root0 = uf.f(0)
    moved = int(g["n"].sum() - big.loc[comps[root0], "n"].sum()
                - g[g["n"] < 3]["n"].sum())
    why = "아파트 K-apt 다름" if sum(has_k) >= 2 else "아파트 표제부 다름"
    return ("분리", why, len(comps), moved)


def main():
    t0 = time.time()
    ce = _ro("collective_stats_p2r")
    with ce.connect() as c:
        assert c.execute(text("select current_database()")).scalar() == "collective_stats_p2r"
        km_n = c.execute(text("SELECT count(*) FROM collective_building_key_map")).scalar()
        plan = Plan()
        plan_collective(c, load_split_units(None), _split_part_lookup(SPLIT_UNITS_PATH), plan)
        grp = pd.read_sql(text(GROUPS), c)
    led = plan.ledger
    print(f"- 연결표 행 {km_n}(롤백 뒤 0 이어야 원본 상태) · 2단계로 키 바뀌는 행 {int((led['new_key'] != led['building_key']).sum()):,}"
          f" · 묶음 {len(grp):,} · 읽기 {time.time() - t0:,.0f}초\n")
    # 2단계 키 다시 매기기: (옛 키, 유형, 법정동) → 새 키. 한 묶음에 새 키가 둘 이상이면 센다
    led = led[led["new_key"] != led["building_key"]]
    mp = led.groupby(["building_key", "asset_type", "beopjungri_code"])["new_key"].agg(lambda s: s.mode().iat[0])
    multi = int(led.groupby(["building_key", "asset_type", "beopjungri_code"])["new_key"].nunique().gt(1).sum())
    grp["beopjungri_code"] = grp["beopjungri_code"].astype(str)
    mp.index = mp.index.set_levels(mp.index.levels[2].astype(str), level=2)
    idx = pd.MultiIndex.from_frame(grp[["building_key", "asset_type", "beopjungri_code"]])
    nk = mp.reindex(idx).to_numpy()
    grp["key2"] = [n if isinstance(n, str) else k for n, k in zip(nk, grp["building_key"])]
    grp = (grp.groupby(["key2", "asset_type", "beopjungri_code", "main_lot"], as_index=False)
           .agg(n=("n", "sum"), name=("name", "max"), old_key=("building_key", "first")))
    print(f"- 2단계 키로 다시 묶음: 새 키가 둘 이상인 (옛 키·법정동) {multi}\n")

    # 아파트 후보만 근거 조회
    cnt = grp[grp["n"] >= 3].groupby(["key2", "asset_type", "beopjungri_code"]).size()
    cand = cnt[cnt >= 2].reset_index()[["key2", "asset_type", "beopjungri_code"]]
    apt = grp.merge(cand[cand["asset_type"] == "apartment"], on=["key2", "asset_type", "beopjungri_code"])
    lots = apt[["beopjungri_code", "main_lot"]].drop_duplicates()
    lots = lots[lots["main_lot"].str.fullmatch(r"\d{1,4}")]
    lots["bun"] = lots["main_lot"].str.zfill(4)
    dongs = sorted(set(lots["beopjungri_code"]))
    from parcel_master.load_kapt_pnu import load_pnu_map

    # 정션은 해제했다 → 원본 저장소 raw 의 K-apt 필지 파일을 경로로 직접 읽는다(읽기만)
    kdir = next(d for d in (MAIN_RAW / "raw addition").iterdir() if d.is_dir() and "K-apt" in d.name)
    src = sorted(f for f in kdir.iterdir() if f.suffix.lower() == ".xlsx" and "필지" in f.name and not f.name.startswith("~"))[-1]
    pm = load_pnu_map(src)
    pm["pnu"] = pm["pnu"].astype(str).str.strip()
    pm = pm[pm["pnu"].str.len() == 19]
    kapt: dict = {}
    for code, p in zip(pm["danji_code"].astype(str), pm["pnu"]):
        if p[10] == "1":
            kapt.setdefault((p[:10], str(int(p[11:15]))), set()).add(code)
    pe = _ro("parcel_master_p2r")
    with pe.connect() as c:
        assert c.execute(text("select current_database()")).scalar() == "parcel_master_p2r"
        tb = pd.read_sql(text("""
            SELECT beopjungri_code, substr(pnu, 12, 4) AS bun, building_name
            FROM building
            WHERE main_purpose = '공동주택' AND substr(pnu, 11, 1) = '1' AND beopjungri_code IN :d
        """).bindparams(__import__("sqlalchemy").bindparam("d", expanding=True)), c, params={"d": dongs})
    title: dict = {}
    for d, b, nm in zip(tb["beopjungri_code"].astype(str), tb["bun"], tb["building_name"]):
        k = norm_name(nm)
        if k:
            title.setdefault((d, str(int(b))), set()).add(k)
    print(f"- 아파트 후보 본번 {len(lots):,} · K-apt 대표 PNU 있는 본번 {sum(1 for d, m in zip(lots.beopjungri_code, lots.main_lot) if (d, m) in kapt):,}"
          f" · 표제부 이름 있는 본번 {sum(1 for d, m in zip(lots.beopjungri_code, lots.main_lot) if (d, m) in title):,}\n")

    recs = []
    sub = grp.merge(cand, on=["key2", "asset_type", "beopjungri_code"])
    for (k, a, d), g in sub.groupby(["key2", "asset_type", "beopjungri_code"], sort=False):
        r = decide(a, g, kapt, title, d)
        if r is None:
            continue
        big = g[g["n"] >= 3].sort_values("n", ascending=False)
        recs.append(dict(key2=k, asset_type=a, beopjungri_code=d, name=g["name"].max(), decision=r[0], why=r[1],
                         parts=r[2], moved_tx=r[3], tx=int(g["n"].sum()), small_tx=int(g[g["n"] < 3]["n"].sum()),
                         lots=" / ".join(f"{m}:{n}" for m, n in zip(big["main_lot"], big["n"])),
                         kapt=" / ".join(",".join(sorted(kapt.get((d, m), []))) or "-" for m in big["main_lot"]) if a == "apartment" else "",
                         title=" / ".join(",".join(sorted(title.get((d, m), [])))[:40] or "-" for m in big["main_lot"]) if a == "apartment" else ""))
    df = pd.DataFrame(recs)
    tot_keys = grp.groupby("asset_type")["key2"].nunique()
    tot_tx = grp.groupby("asset_type")["n"].sum()
    rows = []
    for a in ["apartment", "officetel", "presale", "rowhouse"]:
        s = df[df["asset_type"] == a]
        sp = s[s["decision"] == "분리"]
        rows.append((a, f"{s['key2'].nunique():,}", f"{sp['key2'].nunique():,}", f"{int(sp['parts'].sum() - len(sp)):,}",
                     f"{int(sp['tx'].sum()):,}", f"{int(sp['moved_tx'].sum()):,}", f"{int(tot_keys.get(a, 0)):,}", f"{int(tot_tx.get(a, 0)):,}"))
    sp = df[df["decision"] == "분리"]
    rows.append(("합", f"{df['key2'].nunique():,}", f"{sp['key2'].nunique():,}", f"{int(sp['parts'].sum() - len(sp)):,}",
                 f"{int(sp['tx'].sum()):,}", f"{int(sp['moved_tx'].sum()):,}", f"{int(tot_keys.sum()):,}", f"{int(tot_tx.sum()):,}"))
    print(md_table(rows, ["유형", "후보 키", "분리 키", "늘어나는 키", "분리 키 거래", "새 키로 옮겨지는 거래", "전체 키", "전체 거래"]))
    print()
    why = df.groupby(["asset_type", "decision", "why"]).agg(keys=("key2", "nunique"), tx=("tx", "sum")).reset_index()
    print(md_table([tuple(f"{v:,}" if isinstance(v, (int,)) or hasattr(v, "dtype") and str(v).isdigit() else str(v)
                          for v in r) for r in why.itertuples(index=False)], ["유형", "결정", "사유", "키", "거래"]))
    print(f"\n- 3건 미만 본번(가장 큰 묶음에 둠) 거래: 분리 키 안 {int(sp['small_tx'].sum()):,}")

    keep = df[df["decision"] == "유지"].copy()
    split = df[df["decision"] == "분리"].copy()
    for x in (keep, split):
        x["o"] = (x["key2"] + x["beopjungri_code"] + SEED).map(lambda s: __import__("hashlib").md5(s.encode()).hexdigest())
    # 유지 10: 사유별 고르게 · 분리 20: 유형·사유별 고르게
    ks = keep.sort_values("o").groupby("why", group_keys=False).head(4).sort_values("o").head(10)
    ss = split.sort_values("o").groupby(["asset_type", "why"], group_keys=False).head(7).sort_values("o").head(20)
    smp = pd.concat([ks, ss]).drop(columns="o")
    smp.to_csv(OUT / "c2_samples.csv", index=False, encoding="utf-8-sig")
    print(f"\n표본 {len(smp)}건(유지 {len(ks)} · 분리 {len(ss)}) → logs/collective_p2/c2_samples.csv · 전체 {time.time() - t0:,.0f}초")
    print("표본 구성: " + ", ".join(f"{a}/{d}/{w} {n}" for (a, d, w), n in smp.groupby(["asset_type", "decision", "why"]).size().items()))
    df.to_csv(OUT / "c2_all_candidates.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
