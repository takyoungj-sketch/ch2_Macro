"""Phase C-2 재측정 3차 (T 지시 2026-11-14) — 확실 분할 / 확실 유지 / 불확실 3칸 + Cursor 확인용 CSV. 읽기 전용, 적용 안 함.

아파트 (본번 묶음 쌍마다)
  - K-apt 단지코드가 둘 다 있으면 결정적: 다름 → 확실 분할, 겹침 → 확실 유지
  - 아니면 표제부 근거 행(거래 이름과 맞는 행, 없으면 사용승인연도 = 거래 건축년도인 행 — c20 과 같음):
      승인연도 겹치지 않음 + 이름 다름          → 확실 분할
      승인연도 겹치지 않음 + 이름 같음          → 분할(정체성·연도 다름, 이름은 보조). 단 연도 차 ≤ 2 → 불확실(추가 기준)
      승인연도 겹침(또는 한쪽 없음) + 이름 다름 → 불확실 「K-apt 없이 이름만 다름」
      승인연도 겹침 + 이름 같음                 → 확실 유지
  - 근거가 한쪽이라도 없음: 거래 건축년도가 다르면 불확실(추가 기준), 같으면 확실 유지
  이름 비교: 공백·기호·아파트·APT 제거, 글자 정렬(단어 순서 무시), 차수(N차·N단지)는 둘 다 있고 다를 때만 다름.
연립·오피스텔 (안, T=10): 건축년도 다름 → 확실 분할 / 같은 해·본번 차 > T → 확실 분할 /
  같은 해·본번 차 ≤ T → 불확실 「건축년도 같고 본번 가까움」 / 건축년도 없음·본번 비교 불가 → 불확실
3건 미만 본번: 같은 건축년도 묶음이 한 부분에만 있으면 붙임 / 여러 부분에 있거나, 없지만 ±1년 묶음이 있으면 불확실(기본: 가장 큰
  후보에 붙임) / 둘 다 없으면 별도 소형 키.
불확실은 기본값 「분할하지 않음」(그 쌍을 묶음)으로 센다.
출력: 표준출력(markdown, 지번 없음) · logs/collective_p2/c2_uncertain_for_cursor.csv · logs/collective_p2/c2_t_samples.csv (지번 포함, gitignore)
"""
from __future__ import annotations

import hashlib
import sys
import time

import pandas as pd
from sqlalchemy import bindparam, text

import c20_c2_remeasure as c20
from _db import OUT, ROOT, engine_db, md_table

sys.path.insert(0, str(ROOT / "pipeline"))
from collective.migrate_p2_keys import (  # noqa: E402
    SPLIT_UNITS_PATH, Plan, _split_part_lookup, load_split_units, plan_collective)

TIMEOUT = 1_800_000
SEED = "c2-3way-20261114"
T_MAIN = 10
T_CANDIDATES = (5, 10, 20)
YEAR_GAP_UNCERTAIN = 2

GROUPS = """
SELECT building_key, asset_type, beopjungri_code,
       split_part(btrim(lot_number), '-', 1) AS main_lot, count(*) AS n, max(display_name) AS name,
       mode() WITHIN GROUP (ORDER BY building_year) AS byear,
       max(addr1) AS sido, max(addr2) AS sigungu, max(concat_ws(' ', addr3, addr4)) AS dong,
       count(*) FILTER (WHERE addr4 IS NOT NULL AND btrim(addr4) <> '') AS n_addr4
FROM collective_transactions
WHERE is_valid AND beopjungri_code IS NOT NULL AND COALESCE(btrim(lot_number), '') <> ''
GROUP BY 1, 2, 3, 4
"""

CERT, KEEP, UNC = "확실 분할", "확실 유지", "불확실"


def load():
    t0 = time.time()
    ce = engine_db("collective_stats_p2r", timeout_ms=TIMEOUT)
    with ce.connect() as c:
        assert c.execute(text("select current_database()")).scalar() == "collective_stats_p2r"
        assert c.execute(text("SHOW transaction_read_only")).scalar() == "on"
        assert c.execute(text("SELECT count(*) FROM collective_building_key_map")).scalar() == 0   # 롤백 뒤 원본 상태
        plan = Plan()
        plan_collective(c, load_split_units(None), _split_part_lookup(SPLIT_UNITS_PATH), plan)
        grp = pd.read_sql(text(GROUPS), c)
    led = plan.ledger
    led = led[led["new_key"] != led["building_key"]]
    mp = led.groupby(["building_key", "asset_type", "beopjungri_code"])["new_key"].agg(lambda s: s.mode().iat[0])
    mp.index = mp.index.set_levels(mp.index.levels[2].astype(str), level=2)
    grp["beopjungri_code"] = grp["beopjungri_code"].astype(str)
    nk = mp.reindex(pd.MultiIndex.from_frame(grp[["building_key", "asset_type", "beopjungri_code"]])).to_numpy()
    grp["key2"] = [n if isinstance(n, str) else k for n, k in zip(nk, grp["building_key"])]
    grp = (grp.sort_values("n", ascending=False)
           .groupby(["key2", "asset_type", "beopjungri_code", "main_lot"], as_index=False)
           .agg(n=("n", "sum"), name=("name", "first"), byear=("byear", "first"), sido=("sido", "first"),
                sigungu=("sigungu", "first"), dong=("dong", "first")))
    cnt = grp[grp["n"] >= 3].groupby(["key2", "asset_type", "beopjungri_code"]).size()
    cand = cnt[cnt >= 2].reset_index()[["key2", "asset_type", "beopjungri_code"]]
    sub = grp.merge(cand, on=["key2", "asset_type", "beopjungri_code"])
    # C-01(동 분할) 대상 행이 구 있는 시(addr4 있음)에 얼마나 있는지 — 키 구성 기록용
    sp = led[led["reason"].str.contains("split", na=False)]
    a4 = sp["addr4"].fillna("").str.strip() != "" if "addr4" in sp.columns else pd.Series(False, index=sp.index)
    c01 = dict(rows=len(sp), rows_gu=int(a4.sum()), keys=sp["building_key"].nunique(),
               keys_gu=sp.loc[a4, "building_key"].nunique())
    print(f"- 묶음 {len(grp):,} · 후보 (키·법정동) {len(cand):,} · 읽기 {time.time() - t0:,.0f}초")

    dongs = sorted(set(sub.loc[sub["asset_type"] == "apartment", "beopjungri_code"]))
    from parcel_master.load_kapt_pnu import load_pnu_map

    kdir = next(d for d in (c20.MAIN_RAW / "raw addition").iterdir() if d.is_dir() and "K-apt" in d.name)
    src = sorted(f for f in kdir.iterdir() if f.suffix.lower() == ".xlsx" and "필지" in f.name and not f.name.startswith("~"))[-1]
    pm = load_pnu_map(src)
    pm["pnu"] = pm["pnu"].astype(str).str.strip()
    pm = pm[pm["pnu"].str.len() == 19]
    ev: dict = {}

    def slot(d, m):
        return ev.setdefault(d, {}).setdefault(m, {"kapt": set(), "rows": []})
    dset = set(dongs)
    for code, p in zip(pm["danji_code"].astype(str), pm["pnu"]):
        if p[10] == "1" and p[:10] in dset:
            slot(p[:10], str(int(p[11:15])))["kapt"].add(code)
    pe = engine_db("parcel_master_p2r", timeout_ms=TIMEOUT)
    with pe.connect() as c:
        assert c.execute(text("select current_database()")).scalar() == "parcel_master_p2r"
        tb = pd.read_sql(text("""
            SELECT beopjungri_code, substr(pnu, 12, 4) AS bun, building_name, left(approve_date, 4) AS ay
            FROM building
            WHERE main_purpose = '공동주택' AND substr(pnu, 11, 1) = '1' AND beopjungri_code IN :d
        """).bindparams(bindparam("d", expanding=True)), c, params={"d": dongs or ["-"]})
    for d, b, nm, ay in zip(tb["beopjungri_code"].astype(str), tb["bun"], tb["building_name"], tb["ay"]):
        slot(d, str(int(b)))["rows"].append((c20.name_sig(nm), ay if isinstance(ay, str) and ay.isdigit() else None,
                                             nm.strip() if isinstance(nm, str) else ""))
    return sub, ev, c01


def apt_pair(ei, ej, yi_tx, yj_tx):
    """(분류, 근거). 분류 ∈ 확실 분할·확실 유지·불확실."""
    ki, kj = ei["kapt"], ej["kapt"]
    if ki and kj:
        return (CERT, "K-apt 다름") if not (ki & kj) else (KEEP, "K-apt 같음")
    ti, tj = ei["names"], ej["names"]
    if ti and tj:
        nm = c20.names_match(ti, tj)
        yi, yj = ei["years"], ej["years"]
        if yi and yj and not (yi & yj):
            if not nm:
                return CERT, "표제부 이름·승인연도 다름"
            gap = min(abs(int(a) - int(b)) for a in yi for b in yj)
            if gap <= YEAR_GAP_UNCERTAIN:
                return UNC, f"이름 같음·승인연도 {gap}년 차(가까움)"
            return CERT, f"이름 같음·승인연도 {gap}년 차"
        if not nm:
            return UNC, "K-apt 없이 이름만 다름"
        return KEEP, "표제부 이름 같음·승인연도 겹침"
    if pd.notna(yi_tx) and pd.notna(yj_tx) and yi_tx != yj_tx:
        return UNC, "근거 없음·거래 건축년도 다름"
    return KEEP, "근거 없음·거래 건축년도 같음"


def rh_pair(yi, yj, li, lj, T):
    if pd.isna(yi) or pd.isna(yj):
        return UNC, "건축년도 없음"
    if yi != yj:
        return CERT, "건축년도 다름"
    if li is None or lj is None:
        return UNC, "본번 비교 불가"
    d = abs(li - lj)
    if d > T:
        return CERT, f"같은 해·본번 차 >{T}"
    return UNC, f"같은 해·본번 가까움(≤{T})"


def judge(asset, g, ev, T):
    """(키·법정동) 하나. T=None 이면 연립·오피스텔 현행(3건+ 본번마다)."""
    big = g[g["n"] >= 3].sort_values("n", ascending=False).reset_index(drop=True)
    small = g[g["n"] < 3].reset_index(drop=True)
    if len(big) < 2:
        return None
    tx = int(g["n"].sum())
    if asset == "presale":
        return dict(tx=tx, cls=KEEP, decision="유지", reasons=["분양권"], parts=1, moved=0, small_keys=0, small_keys_tx=0,
                    small_unc=0, comp=[0] * len(big), pairs={})
    pairs = {}
    if asset == "apartment":
        e = [c20.group_evidence(ev.get(m), nm, y) for m, nm, y in zip(big["main_lot"], big["name"], big["byear"])]
        for i in range(len(big)):
            for j in range(i + 1, len(big)):
                pairs[(i, j)] = apt_pair(e[i], e[j], big["byear"][i], big["byear"][j])
    elif T is None:
        for i in range(len(big)):
            for j in range(i + 1, len(big)):
                pairs[(i, j)] = (CERT, "본번 다름(현행)")
    else:
        lots = [c20._num(m) for m in big["main_lot"]]
        for i in range(len(big)):
            for j in range(i + 1, len(big)):
                pairs[(i, j)] = rh_pair(big["byear"][i], big["byear"][j], lots[i], lots[j], T)
    # 확실 분할이 아닌 쌍(유지·불확실)은 묶는다 = 불확실은 분할하지 않음
    comps = c20.components(len(big), lambda i, j: pairs[(i, j)][0] != CERT)
    comps.sort(key=lambda c: -big.loc[c, "n"].sum())
    comp_of = [0] * len(big)
    for ci, c in enumerate(comps):
        for i in c:
            comp_of[i] = ci
    conflict = any(v[0] == CERT and comp_of[i] == comp_of[j] for (i, j), v in pairs.items())
    split = len(comps) > 1
    # 3건 미만 본번
    sk = skt = sunc = 0
    main_small = int(small["n"].sum())
    if (asset in ("rowhouse", "officetel") and T is not None) or (asset == "apartment" and split):
        main_small = 0
        for y, n in zip(small["byear"], small["n"]):
            same = {comp_of[i] for i, by in enumerate(big["byear"]) if pd.notna(y) and by == y}
            near = {comp_of[i] for i, by in enumerate(big["byear"]) if pd.notna(y) and pd.notna(by) and abs(by - y) <= 1}
            if len(same) == 1:
                tgt = next(iter(same))
            elif len(same) > 1 or near:
                sunc += 1
                tgt = min(same or near)          # 불확실 → 가장 큰 후보 부분에 붙임(분할하지 않음)
            else:
                sk += 1
                skt += int(n)
                continue
            if tgt == 0:
                main_small += int(n)
    main_tx = int(big.loc[[i for i in range(len(big)) if comp_of[i] == 0], "n"].sum()) + main_small
    unc_pairs = [v[1] for v in pairs.values() if v[0] == UNC]
    if unc_pairs or sunc or conflict:
        cls = UNC
    elif split or sk:
        cls = CERT
    else:
        cls = KEEP
    reasons = sorted({v[1] for v in pairs.values() if v[0] == UNC}) + (["3건 미만 붙일 묶음 애매"] if sunc else []) + \
        (["확실 분할 쌍이 불확실 쌍으로 이어짐"] if conflict else [])
    if cls != UNC:
        reasons = sorted({v[1] for v in pairs.values()}) + (["소형 별도 키"] if sk else [])
    return dict(tx=tx, cls=cls, decision="분리" if (split or sk) else "유지", reasons=reasons, parts=len(comps),
                moved=tx - main_tx, small_keys=sk, small_keys_tx=skt, small_unc=sunc, comp=comp_of, pairs=pairs)


def run(sub, ev, T):
    recs = []
    for (k, a, d), g in sub.groupby(["key2", "asset_type", "beopjungri_code"], sort=False):
        r = judge(a, g, ev.get(d, {}), T)
        if r is not None:
            recs.append({"key2": k, "asset_type": a, "beopjungri_code": d, **r})
    return pd.DataFrame(recs)


TYPES = ["apartment", "officetel", "rowhouse", "presale"]
KO = {"apartment": "아파트", "officetel": "오피스텔", "rowhouse": "연립", "presale": "분양권"}


def main():
    t0 = time.time()
    sub, ev, c01 = load()
    print(f"- C-01 분할 대상(2단계 동 분할) 원장 행 {c01['rows']:,} 중 addr4 있음(구 있는 시) {c01['rows_gu']:,}"
          f" · 옛 키 {c01['keys']:,} 중 {c01['keys_gu']:,}\n")

    # 2. 안별 규모
    cur = run(sub, ev, None)
    res = {t: run(sub, ev, t) for t in T_CANDIDATES}
    rows = []
    for label, df, types in [("현행(3건+ 본번마다)", cur, ["officetel", "rowhouse"])] + \
            [(f"안 T={t}", res[t], ["officetel", "rowhouse"]) for t in T_CANDIDATES] + [("새 아파트 규칙", res[T_MAIN], ["apartment"])]:
        for a in types:
            s = df[df["asset_type"] == a]
            sp = s[s["decision"] == "분리"]
            rows.append((label, KO[a], f"{len(s):,}", f"{len(sp):,}", f"{int((sp['parts'] - 1).sum() + sp['small_keys'].sum()):,}",
                         f"{int(sp['moved'].sum()):,}", f"{int(s['small_keys'].sum()):,}", f"{int(s['small_keys_tx'].sum()):,}"))
    print("## 안별 규모 (불확실은 분할하지 않음)\n")
    print(md_table(rows, ["안", "유형", "후보 (키·법정동)", "분리", "늘어나는 키", "옮겨지는 거래", "소형 키", "소형 키 거래"]))

    new = res[T_MAIN]
    # 4. 3칸
    rows = []
    for a in TYPES:
        s = new[new["asset_type"] == a]
        line = [KO[a]]
        for cl in (CERT, KEEP, UNC):
            x = s[s["cls"] == cl]
            line += [f"{len(x):,}", f"{int(x['tx'].sum()):,}"]
        rows.append(tuple(line))
    tot = [("합",) + tuple(v for cl in (CERT, KEEP, UNC) for v in
                           (f"{int((new['cls'] == cl).sum()):,}", f"{int(new.loc[new['cls'] == cl, 'tx'].sum()):,}"))]
    print(f"\n## 3칸 분류 (새 규칙, 연립·오피스텔 T={T_MAIN}) — (키·법정동) 수 / 거래\n")
    print(md_table(rows + tot, ["유형", "확실 분할", "거래", "확실 유지", "거래", "불확실", "거래"]))
    ur = new[new["cls"] == UNC].explode("reasons").groupby(["asset_type", "reasons"]).agg(
        n=("key2", "size"), tx=("tx", "sum")).reset_index()
    print("\n### 불확실 사유 (한 (키·법정동)에 사유 여럿이면 각각 셈)\n")
    print(md_table([(KO[r.asset_type], r.reasons, f"{r.n:,}", f"{int(r.tx):,}") for r in ur.itertuples()],
                   ["유형", "사유", "(키·법정동)", "거래"]))
    cr = new[new["cls"] != UNC].explode("reasons").groupby(["asset_type", "cls", "reasons"]).agg(
        n=("key2", "size"), tx=("tx", "sum")).reset_index()
    print("\n### 확실 분할·확실 유지 근거\n")
    print(md_table([(KO[r.asset_type], r.cls, r.reasons, f"{r.n:,}", f"{int(r.tx):,}") for r in cr.itertuples()],
                   ["유형", "칸", "근거", "(키·법정동)", "거래"]))
    # 3. 소형
    print(f"\n## 3건 미만 본번 (T={T_MAIN})\n")
    print(md_table([(KO[a], f"{int(new.loc[new.asset_type == a, 'small_keys'].sum()):,}",
                     f"{int(new.loc[new.asset_type == a, 'small_keys_tx'].sum()):,}",
                     f"{int(new.loc[new.asset_type == a, 'small_unc'].sum()):,}") for a in TYPES[:3]],
                   ["유형", "별도 소형 키", "소형 키 거래", "붙일 묶음 애매(불확실, 기본 붙임)"]))

    # 1. 지난 표본 아파트 6건
    old = pd.read_csv(OUT / "c2_samples.csv", dtype=str)
    old = old[(old["asset_type"] == "apartment") & (old["decision"] == "분리")]
    m = old.merge(new, on=["key2", "asset_type", "beopjungri_code"], suffixes=("_old", ""))
    print("\n## 지난 표본 아파트 분리 6건 → 새 규칙\n")
    print(md_table([(i + 1, r.name, r.why, r.cls, r.decision, "; ".join(r.reasons)) for i, r in enumerate(m.itertuples())],
                   ["#", "이름", "지난 판정", "새 칸", "새 결정", "근거"]))

    # 5. Cursor CSV
    def groups_text(g, comp):
        big = g[g["n"] >= 3].sort_values("n", ascending=False).reset_index(drop=True)
        sm = g[g["n"] < 3]
        parts = [f"본번 {mm}: 건축 {int(y) if pd.notna(y) else '-'}년·{n}건(부분{comp[i]})"
                 for i, (mm, y, n) in enumerate(zip(big["main_lot"], big["byear"], big["n"]))]
        parts += [f"본번 {mm}: 건축 {int(y) if pd.notna(y) else '-'}년·{n}건(3건 미만)" for mm, y, n in zip(sm["main_lot"], sm["byear"], sm["n"])]
        return " / ".join(parts)

    def question(a, reasons):
        if a == "apartment":
            return "같은 법정동의 이 본번들 거래가 한 아파트 단지인가, 서로 다른 단지인가?"
        if any("가까움" in x for x in reasons):
            return "같은 해 지은 가까운 본번의 같은 이름 건물들이 한 단지(한 건축물)인가, 따로 지은 다른 건물인가?"
        return "이 본번들의 같은 이름 건물이 한 단지인가, 다른 건물인가?"

    unc = new[new["cls"] == UNC].sort_values("tx", ascending=False).reset_index(drop=True)
    crow = []
    for i, r in unc.iterrows():
        g = sub[(sub["key2"] == r["key2"]) & (sub["asset_type"] == r["asset_type"]) & (sub["beopjungri_code"] == r["beopjungri_code"])]
        e = ev.get(r["beopjungri_code"], {})
        big = g[g["n"] >= 3].sort_values("n", ascending=False)
        crow.append({
            "확인ID": f"C2U-{i + 1:04d}", "유형": KO[r["asset_type"]], "시도": g["sido"].iloc[0], "시군구": g["sigungu"].iloc[0],
            "동": g["dong"].iloc[0], "단지명(원문)": g.sort_values("n", ascending=False)["name"].iloc[0],
            "본번 그룹(건축년도·거래 수)": groups_text(g, r["comp"]), "거래 합": r["tx"],
            "K-apt 코드(본번 순)": " / ".join(",".join(sorted(e.get(mm, {}).get("kapt", []))) or "-" for mm in big["main_lot"])
            if r["asset_type"] == "apartment" else "",
            "불확실 사유": "; ".join(r["reasons"]), "확인할 질문": question(r["asset_type"], r["reasons"]),
            "판정(같은 단지/다른 단지/확인 불가)": "", "근거 URL": "", "이유": "",
        })
    cdf = pd.DataFrame(crow)
    cdf.to_csv(OUT / "c2_uncertain_for_cursor.csv", index=False, encoding="utf-8-sig")
    cum = cdf["거래 합"].cumsum() / max(cdf["거래 합"].sum(), 1)
    print(f"\n## Cursor 확인용 CSV: {len(cdf):,}건 → logs/collective_p2/c2_uncertain_for_cursor.csv (거래 수 내림차순)")
    for top in (50, 100, 150, 200, 300):
        if top < len(cdf):
            print(f"- 상위 {top}건 = 불확실 거래의 {cum.iloc[top - 1] * 100:.0f}% "
                  f"(유형: {', '.join(f'{k} {v}' for k, v in cdf.head(top)['유형'].value_counts().items())})")
    print(f"- 거래 수 분포: {cdf['거래 합'].describe(percentiles=[.5, .9]).round(0).to_dict()}")

    # 6. T 판정용 표본 30
    def detail(r):
        g = sub[(sub["key2"] == r["key2"]) & (sub["asset_type"] == r["asset_type"]) & (sub["beopjungri_code"] == r["beopjungri_code"])]
        g = g.sort_values("n", ascending=False)
        e = ev.get(r["beopjungri_code"], {})
        nm = g["name"].iloc[0]
        sig = c20.name_sig(nm)
        gx = [c20.group_evidence(e.get(mm), n_, y) for mm, n_, y in zip(g["main_lot"], g["name"], g["byear"])]
        apt = r["asset_type"] == "apartment"
        return {"유형": KO[r["asset_type"]], "칸": r["cls"], "결정": r["decision"], "판정 근거": "; ".join(r["reasons"]),
                "이름(원문)": nm, "이름(정규화|차수)": f"{sig[0]}|{sig[1]}" if sig else "", "시도": g["sido"].iloc[0],
                "시군구": g["sigungu"].iloc[0], "동": g["dong"].iloc[0],
                "본번 그룹(건축년도·거래 수)": groups_text(g, r["comp"]),
                "K-apt 코드": " / ".join(",".join(sorted(e.get(mm, {}).get("kapt", []))) or "-" for mm in g["main_lot"]) if apt else "",
                "표제부 근거 행": " / ".join(f"[{x['how']}]" + ",".join(sorted(x["raw"]))[:50] for x in gx) if apt else "",
                "사용승인연도": " / ".join(",".join(sorted(x["years"])) or "-" for x in gx) if apt else "",
                "늘어나는 부분": r["parts"] - 1 + r["small_keys"], "옮겨지는 거래": r["moved"]}
    new = new.assign(o=(new["key2"] + new["beopjungri_code"] + SEED).map(lambda s: hashlib.md5(s.encode()).hexdigest()))
    keep = new[new["decision"] == "유지"].sort_values("o")
    split = new[new["decision"] == "분리"].sort_values("o")
    ks = pd.concat([keep[(keep.asset_type == "apartment") & (keep.cls == KEEP)].head(2),
                    keep[(keep.asset_type == "apartment") & (keep.cls == UNC)].head(2),
                    keep[(keep.asset_type == "rowhouse")].head(3), keep[(keep.asset_type == "officetel")].head(2),
                    keep[keep.asset_type == "presale"].head(1)])
    ks = pd.concat([ks, keep[~keep.index.isin(ks.index)].head(10 - len(ks))])
    ss = pd.concat([split[split.asset_type == "apartment"].head(6),
                    split[(split.asset_type == "rowhouse") & (split.cls == CERT)].head(6),
                    split[(split.asset_type == "rowhouse") & (split.cls == UNC)].head(2),
                    split[(split.asset_type == "officetel") & (split.cls == CERT)].head(4),
                    split[(split.asset_type == "officetel") & (split.cls == UNC)].head(2)])
    ss = pd.concat([ss, split[~split.index.isin(ss.index)].head(20 - len(ss))])
    smp = pd.DataFrame([detail(r) for _, r in pd.concat([ks, ss]).iterrows()])
    smp.to_csv(OUT / "c2_t_samples.csv", index=False, encoding="utf-8-sig")
    print(f"\n표본 {len(smp)}건(유지 {len(ks)} · 분리 {len(ss)}) → logs/collective_p2/c2_t_samples.csv · 전체 {time.time() - t0:,.0f}초")
    print("표본 구성: " + ", ".join(f"{a}/{d}/{c} {n}" for (a, d, c), n in smp.groupby(["유형", "결정", "칸"]).size().items()))


if __name__ == "__main__":
    main()
