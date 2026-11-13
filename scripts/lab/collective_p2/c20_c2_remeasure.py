"""Phase C-2 재측정 (T 지시 2026-11-13) — 같은 법정동 동명 다른 본번 분리 규칙 후보. 읽기 전용, 적용하지 않는다.

1. 아파트: 정체성이 다를 때만 분리.
   - K-apt 단지코드가 두 본번 묶음 모두에 있는데 겹치지 않음 → 다름(결정적)
   - 아니면 표제부(공동주택): 이름이 서로 맞지 않고 사용승인연도도 겹치지 않음 → 다름
   - 이름 정규화: 공백·기호·「아파트」·「APT」 제거, 단어 순서 무시(정렬한 글자 비교), 차수(N차·N단지)는 떼어
     두 이름에 다 있는데 다를 때만 다르다고 본다.
   - 근거가 한쪽이라도 없으면 다르다고 보지 않는다(유지). 「다르지 않음」 쌍을 union-find 로 묶는다.
2. 연립·오피스텔: (현행) 3건+ 본번마다 분리 / (안) 건축년도가 다르면 분리, 같으면 본번 차이 ≤ T 일 때 유지.
   T 는 같은 해·다른 해 쌍의 본번 차이 분포를 보고 제안하고, T 후보별로 센다.
3. 3건 미만 본번: 건축년도가 같은 묶음이 있으면 거기(가장 큰 것)에, 없으면 별도 키 → 소형 키 수.
   연립·오피스텔(안)과, 아파트는 분리되는 (키·법정동)에만 적용(아파트 유지 단지를 소형 본번으로 쪼개지 않음).
4. 표본 30(유지 10·분리 20, 새 규칙) → logs/collective_p2/c2r_samples.csv (지번 포함, gitignore)
   + 지난 표본(c2_samples.csv) 아파트 분리 6건 재판정 → 표준출력(이름만, 지번 없음)
DB: collective_stats_p2r(롤백 뒤 = 원본) · parcel_master_p2r(표제부 사본). 모든 세션 읽기 전용(engine_db).
"""
from __future__ import annotations

import hashlib
import re
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import bindparam, text

from _db import OUT, ROOT, engine_db, md_table

sys.path.insert(0, str(ROOT / "pipeline"))
from collective.migrate_p2_keys import (  # noqa: E402
    SPLIT_UNITS_PATH, Plan, _split_part_lookup, load_split_units, plan_collective)

TIMEOUT = 1_800_000
SEED = "c2r-20261113"
MAIN_RAW = Path("D:/ch2/ch2_Macro/raw")
T_CANDIDATES = (2, 5, 10, 20, 50)

GROUPS = """
SELECT building_key, asset_type, beopjungri_code,
       split_part(btrim(lot_number), '-', 1) AS main_lot, count(*) AS n, max(display_name) AS name,
       mode() WITHIN GROUP (ORDER BY building_year) AS byear,
       max(concat_ws(' ', addr2, addr3, addr4)) AS dong
FROM collective_transactions
WHERE is_valid AND beopjungri_code IS NOT NULL AND COALESCE(btrim(lot_number), '') <> ''
GROUP BY 1, 2, 3, 4
"""

_CHASU = re.compile(r"제?\s*(\d+)\s*(차|단지)")


def name_sig(s) -> tuple[str, str] | None:
    """(정렬 글자 기본형, 차수). 정규화 뒤 비면 None."""
    if not isinstance(s, str):
        return None
    t = s.lower()
    ch = _CHASU.findall(t)
    chasu = ch[-1][0].lstrip("0") if ch else ""
    t = _CHASU.sub("", t)
    t = re.sub(r"아파트|apt", "", t)
    t = re.sub(r"[^0-9a-z가-힣]", "", t)
    if not t:
        return None
    return "".join(sorted(t)), chasu


def names_match(a: set, b: set) -> bool:
    for ba, ca in a:
        for bb, cb in b:
            if ba == bb and (not ca or not cb or ca == cb):
                return True
    return False


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


def _num(m):
    return int(m) if isinstance(m, str) and m.isdigit() else None


def group_evidence(slot: dict | None, name, byear) -> dict:
    """본번 묶음의 정체성 근거. 한 본번에는 부번마다 다른 건물이 있어 본번 전체 이름을 쓰면 엉뚱한 일치가 난다
    → 표제부 행을 (1) 거래 이름과 맞는 행, 없으면 (2) 사용승인연도 = 거래 건축년도인 행으로 좁힌다."""
    slot = slot or {"kapt": set(), "rows": []}
    key = name_sig(name)
    rows = [r for r in slot["rows"] if r[0] and key and names_match({r[0]}, {key})]
    how = "이름"
    if not rows and pd.notna(byear):
        rows = [r for r in slot["rows"] if r[1] == str(int(byear))]
        how = "연도"
    return {"kapt": slot["kapt"], "names": {r[0] for r in rows if r[0]}, "years": {r[1] for r in rows if r[1]},
            "raw": {r[2] for r in rows}, "how": how if rows else "없음"}


def apt_pair(ei, ej) -> tuple[bool, str]:
    """(다름?, 근거)"""
    ki, kj = ei["kapt"], ej["kapt"]
    if ki and kj:
        return (not (ki & kj), "K-apt " + ("다름" if not (ki & kj) else "같음"))
    ti, tj = ei["names"], ej["names"]
    if ti and tj:
        nm = names_match(ti, tj)
        yi, yj = ei["years"], ej["years"]
        if nm:
            if yi and yj and not (yi & yj):
                return (False, "표제부 이름 같음(승인연도 다름)")
            return (False, "표제부 이름 같음")
        if yi and yj:
            if yi & yj:
                return (False, "이름 다름·승인연도 겹침")
            return (True, "표제부 이름·승인연도 다름")
        return (False, "이름 다름·승인연도 없음")
    return (False, "근거 없음")


def components(n, linked):
    uf = UF(n)
    for i in range(n):
        for j in range(i + 1, n):
            if linked(i, j):
                uf.u(i, j)
    comps: dict[int, list[int]] = {}
    for i in range(n):
        comps.setdefault(uf.f(i), []).append(i)
    return list(comps.values())


def attach_small(big: pd.DataFrame, small: pd.DataFrame, comp_of: list[int]):
    """3건 미만 본번 → 같은 건축년도 큰 묶음의 부분(없으면 새 부분). (부분 번호 목록, 소형 키 수, 소형 키 거래)"""
    out, new_keys, new_tx = [], 0, 0
    for y, n in zip(small["byear"], small["n"]):
        hit = [i for i, by in enumerate(big["byear"]) if pd.notna(y) and by == y]
        if hit:
            out.append(comp_of[hit[0]])          # big 은 거래 내림차순 → 첫 번째가 가장 큰 묶음
        else:
            out.append(-1)
            new_keys += 1
            new_tx += int(n)
    return out, new_keys, new_tx


def judge(asset, g, ev, T):
    big = g[g["n"] >= 3].sort_values("n", ascending=False).reset_index(drop=True)
    small = g[g["n"] < 3]
    if len(big) < 2:
        return None
    res = {"tx": int(g["n"].sum()), "small_tx": int(small["n"].sum())}
    if asset == "presale":
        return {**res, "decision": "유지", "why": "분양권", "parts": 1, "moved": 0, "small_keys": 0, "small_keys_tx": 0,
                "basis": "분양권 유지", "comp": [0] * len(big)}
    if asset == "apartment":
        e = [group_evidence(ev.get(m), nm, y) for m, nm, y in zip(big["main_lot"], big["name"], big["byear"])]
        basis = {}

        def linked(i, j):
            d, b = apt_pair(e[i], e[j])
            basis[(i, j)] = b
            return not d
        comps = components(len(big), linked)
    else:
        years = list(big["byear"])
        lots = [_num(m) for m in big["main_lot"]]
        basis = {}

        def linked(i, j):
            if T is None:
                return False                                     # 현행: 본번마다 분리
            yi, yj = years[i], years[j]
            if pd.notna(yi) and pd.notna(yj) and yi != yj:
                basis[(i, j)] = "건축년도 다름"
                return False
            if lots[i] is None or lots[j] is None:
                basis[(i, j)] = "본번 비교 불가"
                return False
            d = abs(lots[i] - lots[j])
            basis[(i, j)] = f"같은 해·본번 차 {d}" + (" ≤T" if d <= T else " >T")
            return d <= T
        comps = components(len(big), linked)
    comp_of = [0] * len(big)
    for ci, c in enumerate(sorted(comps, key=lambda c: -big.loc[c, "n"].sum())):
        for i in c:
            comp_of[i] = ci
    split = len(comps) > 1
    sk = skt = 0
    small_parts = []
    if (asset in ("rowhouse", "officetel") and T is not None) or (asset == "apartment" and split):
        small_parts, sk, skt = attach_small(big, small, comp_of)
    main_tx = int(big.loc[[i for i in range(len(big)) if comp_of[i] == 0], "n"].sum()) + \
        int(sum(n for n, p in zip(small["n"], small_parts) if p == 0)) if small_parts else \
        int(big.loc[[i for i in range(len(big)) if comp_of[i] == 0], "n"].sum()) + res["small_tx"]
    moved = res["tx"] - main_tx
    b = "; ".join(sorted(set(basis.values()))) or ("본번 다름(현행)" if T is None and asset != "apartment" else "")
    if asset == "apartment":
        why = ("아파트 분리: " if split else "아파트 유지: ") + (
            "K-apt 다름" if split and any(v == "K-apt 다름" for v in basis.values()) else
            "표제부 이름·승인연도 다름" if split else
            "K-apt 같음" if any(v == "K-apt 같음" for v in basis.values()) else
            "표제부 이름 같음(승인연도 다름)" if any(v == "표제부 이름 같음(승인연도 다름)" for v in basis.values()) else
            "표제부 이름 같음" if any(v == "표제부 이름 같음" for v in basis.values()) else
            "이름 다름·승인연도 겹침" if any(v == "이름 다름·승인연도 겹침" for v in basis.values()) else "근거 부족")
    elif T is None:
        why = "본번 다름(현행)"
    else:
        why = ("분리: " if split else "유지: ") + (
            "건축년도 다름" if split and any(v == "건축년도 다름" for v in basis.values()) else
            "같은 해·본번 차 >T" if split else "같은 해·본번 차 ≤T")
    if not split and sk:
        why += " +소형 별도"
    return {**res, "decision": "분리" if (split or sk) else "유지", "why": why, "parts": len(comps), "moved": moved,
            "small_keys": sk, "small_keys_tx": skt, "basis": b, "comp": comp_of}


def main():
    t0 = time.time()
    ce = engine_db("collective_stats_p2r", timeout_ms=TIMEOUT)
    with ce.connect() as c:
        assert c.execute(text("select current_database()")).scalar() == "collective_stats_p2r"
        assert c.execute(text("SHOW transaction_read_only")).scalar() == "on"
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
           .agg(n=("n", "sum"), name=("name", "first"), byear=("byear", "first"), dong=("dong", "first")))
    cnt = grp[grp["n"] >= 3].groupby(["key2", "asset_type", "beopjungri_code"]).size()
    cand = cnt[cnt >= 2].reset_index()[["key2", "asset_type", "beopjungri_code"]]
    sub = grp.merge(cand, on=["key2", "asset_type", "beopjungri_code"])
    print(f"- 묶음 {len(grp):,} · 후보 (키·법정동) {len(cand):,} · 읽기 {time.time() - t0:,.0f}초")

    # 아파트 근거: K-apt 대표 PNU · 표제부(공동주택) 이름·승인연도 — 본번 단위
    apt = sub[sub["asset_type"] == "apartment"]
    dongs = sorted(set(apt["beopjungri_code"]))
    from parcel_master.load_kapt_pnu import load_pnu_map

    kdir = next(d for d in (MAIN_RAW / "raw addition").iterdir() if d.is_dir() and "K-apt" in d.name)
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
        slot(d, str(int(b)))["rows"].append((name_sig(nm), ay if isinstance(ay, str) and ay.isdigit() else None,
                                             nm.strip() if isinstance(nm, str) else ""))

    # 2. 본번 차이 분포(연립·오피스텔 후보, 3건+ 묶음 쌍)
    pairs = []
    for (k, a, d), g in sub[sub["asset_type"].isin(["rowhouse", "officetel"])].groupby(["key2", "asset_type", "beopjungri_code"]):
        b = g[g["n"] >= 3]
        rows = list(zip(b["main_lot"], b["byear"]))
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                li, lj = _num(rows[i][0]), _num(rows[j][0])
                if li is None or lj is None:
                    continue
                same = pd.notna(rows[i][1]) and rows[i][1] == rows[j][1]
                pairs.append((a, "같은 해" if same else "다른 해", abs(li - lj)))
    pr = pd.DataFrame(pairs, columns=["asset_type", "year", "diff"])
    qs = [0.25, 0.5, 0.75, 0.9]
    drows = []
    for (a, y), s in pr.groupby(["asset_type", "year"]):
        drows.append((a, y, f"{len(s):,}", *[f"{s['diff'].quantile(q):.0f}" for q in qs],
                      *[f"{(s['diff'] <= t).mean() * 100:.0f}%" for t in T_CANDIDATES]))
    print("\n## 연립·오피스텔 본번 차이 분포 (후보 키·법정동 안 3건+ 본번 쌍)\n")
    print(md_table(drows, ["유형", "건축년도", "쌍", "p25", "p50", "p75", "p90", *[f"≤{t}" for t in T_CANDIDATES]]))

    def run(T):
        recs = []
        for (k, a, d), g in sub.groupby(["key2", "asset_type", "beopjungri_code"], sort=False):
            r = judge(a, g, ev.get(d, {}), T)
            if r is not None:
                recs.append({"key2": k, "asset_type": a, "beopjungri_code": d, **r})
        return pd.DataFrame(recs)

    def summary(df, label):
        out = []
        for a in ["apartment", "officetel", "rowhouse", "presale"]:
            s = df[df["asset_type"] == a]
            sp = s[s["decision"] == "분리"]
            out.append((label, a, f"{len(s):,}", f"{len(sp):,}", f"{int((sp['parts'] - 1).sum() + sp['small_keys'].sum()):,}",
                        f"{int(sp['moved'].sum()):,}", f"{int(s['small_keys'].sum()):,}", f"{int(s['small_keys_tx'].sum()):,}"))
        return out

    cur = run(None)
    res = {t: run(t) for t in T_CANDIDATES}
    hdr = ["안", "유형", "후보 (키·법정동)", "분리", "늘어나는 키", "옮겨지는 거래", "소형 키(3건 미만 별도)", "소형 키 거래"]
    rows = summary(cur, "현행(본번마다)")
    for t in T_CANDIDATES:
        rows += [r for r in summary(res[t], f"안 T={t}") if r[1] in ("rowhouse", "officetel")]
    print("\n## 안별 규모 (아파트·분양권은 T 와 무관 — 현행 줄에 새 아파트 규칙)\n")
    print(md_table(rows, hdr))
    TP = 10
    new = res[TP]
    print(f"\n## 새 규칙(T={TP}) 사유별\n")
    w = new.groupby(["asset_type", "decision", "why"]).agg(keys=("key2", "size"), tx=("tx", "sum")).reset_index()
    print(md_table([(r.asset_type, r.decision, r.why, f"{r.keys:,}", f"{int(r.tx):,}") for r in w.itertuples()],
                   ["유형", "결정", "사유", "(키·법정동)", "거래"]))
    a_ev = sum(1 for d in ev.values() for m in d.values() if m["kapt"])
    t_ev = sum(1 for d in ev.values() for m in d.values() if m["rows"])
    print(f"\n- 아파트 근거: K-apt 대표 PNU 있는 본번 {a_ev:,} · 표제부 이름 있는 본번 {t_ev:,}")

    # 지난 표본 아파트 6건 재판정
    old = pd.read_csv(OUT / "c2_samples.csv", dtype=str)
    old = old[(old["asset_type"] == "apartment") & (old["decision"] == "분리")]
    m = old.merge(new, on=["key2", "asset_type", "beopjungri_code"], suffixes=("_old", ""))
    print("\n## 지난 표본 아파트 분리 6건 → 새 규칙\n")
    print(md_table([(i + 1, r.name, r.why_old, r.decision, r.why, r.basis) for i, r in enumerate(m.itertuples())],
                   ["#", "이름", "지난 판정", "새 결정", "새 사유", "쌍 근거"]))

    # 4. 표본 30
    def detail(r):
        g = sub[(sub["key2"] == r["key2"]) & (sub["beopjungri_code"] == r["beopjungri_code"])].sort_values("n", ascending=False)
        e = ev.get(r["beopjungri_code"], {})
        nm = g["name"].iloc[0]
        sig = name_sig(nm)
        gx = [group_evidence(e.get(m), n_, y) for m, n_, y in zip(g["main_lot"], g["name"], g["byear"])]
        return {
            "asset_type": r["asset_type"], "decision": r["decision"], "why": r["why"], "basis": r["basis"],
            "name": nm, "name_norm": f"{sig[0]}|{sig[1]}" if sig else "", "dong": g["dong"].iloc[0],
            "main_lots(거래)": " / ".join(f"{m}:{n}" for m, n in zip(g["main_lot"], g["n"])),
            "building_year": " / ".join(str(int(y)) if pd.notna(y) else "-" for y in g["byear"]),
            "part(3건+)": " / ".join(str(p) for p in r["comp"]),
            "kapt": " / ".join(",".join(sorted(e.get(m, {}).get("kapt", []))) or "-" for m in g["main_lot"]) if r["asset_type"] == "apartment" else "",
            "title_names(근거 행)": " / ".join(f"[{x['how']}]" + ",".join(sorted(x["raw"]))[:50] for x in gx) if r["asset_type"] == "apartment" else "",
            "approve_year(근거 행)": " / ".join(",".join(sorted(x["years"])) or "-" for x in gx) if r["asset_type"] == "apartment" else "",
            "parts": r["parts"], "moved_tx": r["moved"], "small_keys": r["small_keys"], "tx": r["tx"],
        }
    new = new.assign(o=(new["key2"] + new["beopjungri_code"] + SEED).map(lambda s: hashlib.md5(s.encode()).hexdigest()))
    keep = new[new["decision"] == "유지"].sort_values("o")
    split = new[new["decision"] == "분리"].sort_values("o")
    ks = pd.concat([keep[keep["asset_type"] == "apartment"].head(4), keep[keep["asset_type"] == "rowhouse"].head(3),
                    keep[keep["asset_type"] == "officetel"].head(2), keep[keep["asset_type"] == "presale"].head(1)])
    ss = pd.concat([split[split["asset_type"] == "apartment"].head(6),
                    split[(split["asset_type"] == "rowhouse") & split["why"].str.contains("건축년도")].head(4),
                    split[(split["asset_type"] == "rowhouse") & ~split["why"].str.contains("건축년도")].head(3),
                    split[(split["asset_type"] == "officetel") & split["why"].str.contains("건축년도")].head(3),
                    split[(split["asset_type"] == "officetel") & ~split["why"].str.contains("건축년도")].head(2)])
    ss = pd.concat([ss, split[~split.index.isin(ss.index)].head(20 - len(ss))])
    ks = pd.concat([ks, keep[~keep.index.isin(ks.index)].head(10 - len(ks))])
    smp = pd.DataFrame([detail(r) for _, r in pd.concat([ks, ss]).iterrows()])
    smp.to_csv(OUT / "c2r_samples.csv", index=False, encoding="utf-8-sig")
    new.drop(columns=["o", "comp"]).to_csv(OUT / "c2r_all_candidates.csv", index=False, encoding="utf-8-sig")
    print(f"\n표본 {len(smp)}건(유지 {len(ks)} · 분리 {len(ss)}) → logs/collective_p2/c2r_samples.csv · 전체 {time.time() - t0:,.0f}초")
    print("표본 구성: " + ", ".join(f"{a}/{d}/{w} {n}" for (a, d, w), n in smp.groupby(["asset_type", "decision", "why"]).size().items()))


if __name__ == "__main__":
    main()
