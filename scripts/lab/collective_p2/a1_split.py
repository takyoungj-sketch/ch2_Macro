"""Phase A-1 — 이름 키 안 다법정동 판정 (읽기 전용).

순서: 호남 옛 시도명 표준화 키(A-2와 같은 규칙)로 먼저 합친 뒤 판정한다.
동 단위 = leaf 이름(addr4가 리가 아니면 addr4, 아니면 addr3; 읍↔면 같은 단위).
같은 키 안 leaf 이름은 같은데 앞 8자리만 다른 것은 「코드 변형」(화성 개편 등)으로 본다.

판정(동 단위 쌍):
  (a) 다른 단지: K-apt 단일 매칭 코드가 서로 다름 | 대표 건축연도 차 >1 | 두 읍면동이 인접하지 않음
  (b) 경계 걸침: 같은 K-apt 코드 & 건축연도 차 ≤1 & 인접
  (c) 그 밖(근거 부족)
키: 쌍 중 하나라도 (a) → (a), 모두 (b) → (b), 나머지 (c).
지오코드는 키 단위(동 단위 좌표 없음)라 거리 대신 region_neighbors 인접 그래프를 쓴다.

산출: logs/collective_p2/a1_*.csv·a1_result.md (지번 포함 → gitignore 폴더만).
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from _db import OUT, ROOT, engine, md_table, q

sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "pipeline" / "collective"))
from collective.building_keys import derive_building_key, normalize_building_name_for_key, normalize_name  # noqa: E402

OLD_SIDO = ("광주광역시", "전라남도")
NEW_SIDO = "전남광주통합특별시"
KAPT_XLSX = Path(r"D:\ch2\ch2_Macro\raw\raw addition\K-apt공동주택관리정보시스템\20261002_단지_기본정보.xlsx")
W7 = "2019-11-01"
W5 = "2021-11-01"

t0 = time.time()


def log(*a):
    print(f"[{time.time()-t0:7.1f}s]", *a, flush=True)


def leaf_norm(s: str) -> str:
    s = normalize_name(s)
    if len(s) >= 2 and s[-1] in ("읍", "면"):
        return s[:-1] + "#"
    return s


def load_attr_module():
    spec = importlib.util.spec_from_file_location("bca", ROOT / "pipeline" / "build_collective_building_attributes.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def honam_key_map(c) -> dict[str, set[str]]:
    """옛 시도명 행의 키 → addr1만 새 이름으로 바꿔 재계산한 키."""
    rows = q(
        c,
        """SELECT DISTINCT asset_type, building_key, addr1, addr2, addr3, addr4, building_name, lot_number, road_name
           FROM collective_transactions WHERE addr1 = ANY(:olds)""",
        olds=list(OLD_SIDO),
    )
    m: dict[str, set[str]] = defaultdict(set)
    recheck_bad = 0
    for r in rows:
        old_re = derive_building_key(asset_type=r[0], addr1=r[2], addr2=r[3], addr3=r[4], addr4=r[5],
                                     building_name=r[6], lot_number=r[7], road_name=r[8])
        if old_re != r[1]:
            recheck_bad += 1
        new = derive_building_key(asset_type=r[0], addr1=NEW_SIDO, addr2=r[3], addr3=r[4], addr4=r[5],
                                  building_name=r[6], lot_number=r[7], road_name=r[8])
        m[r[1]].add(new)
    log(f"honam distinct combos={len(rows):,} old keys={len(m):,} recompute-mismatch={recheck_bad}")
    return m


GROUP_SQL = """
SELECT asset_type, building_key,
       left(beopjungri_code, 8) AS emd8,
       CASE WHEN coalesce(addr4,'') <> '' AND addr4 !~ '리$' THEN addr4 ELSE addr3 END AS leaf,
       max(addr1) AS addr1, max(addr2) AS addr2, max(addr3) AS addr3,
       max(display_name) AS display_name,
       count(*) AS n,
       count(*) FILTER (WHERE contract_date >= DATE '2019-11-01') AS n7,
       count(*) FILTER (WHERE contract_date >= DATE '2021-11-01') AS n5,
       mode() WITHIN GROUP (ORDER BY beopjungri_code) AS bj,
       mode() WITHIN GROUP (ORDER BY lot_number) AS lot,
       mode() WITHIN GROUP (ORDER BY road_name) AS road,
       mode() WITHIN GROUP (ORDER BY building_year) AS by_mode,
       min(building_year) AS by_min, max(building_year) AS by_max,
       max(contract_date) AS last_date
FROM collective_transactions
WHERE coalesce(building_name,'') <> ''
GROUP BY 1,2,3,4
"""


def main():
    eng = engine("collective")
    with eng.connect() as c:
        kmap = honam_key_map(c)
        one_to_n = sum(1 for v in kmap.values() if len(v) > 1)
        log("honam 1:N =", one_to_n)
        g = pd.read_sql(GROUP_SQL, c)
        log(f"groups={len(g):,}")
        rc = pd.read_sql("SELECT beopjungri_code FROM region_codes", c)
    with engine("land").connect() as lc:
        nb = q(lc, "SELECT code, neighbor_code FROM region_neighbors WHERE level='eupmyeondong'")
    nbr: dict[str, set[str]] = defaultdict(set)
    for a, b in nb:
        nbr[a].add(b)
        nbr[b].add(a)
    graph_codes = set(nbr)

    flat = {k: next(iter(v)) for k, v in kmap.items()}
    g["key_std"] = g["building_key"].map(lambda k: flat.get(k, k))
    g["leaf_n"] = g["leaf"].fillna("").map(leaf_norm)

    # 키별 emd8 수(표준화 후)
    emd_per_key = g.groupby("key_std")["emd8"].nunique()
    leaf_per_key = g.groupby("key_std")["leaf_n"].nunique()
    multi_emd_keys = set(emd_per_key[emd_per_key >= 2].index)
    multi_leaf_keys = set(leaf_per_key[leaf_per_key >= 2].index)
    code_variant_keys = multi_emd_keys - multi_leaf_keys
    log(f"multi emd8 keys={len(multi_emd_keys):,} multi leaf keys={len(multi_leaf_keys):,} code-variant only={len(code_variant_keys):,}")
    # 원 키 기준(표준화 전)도 기록
    emd_raw = g.groupby("building_key")["emd8"].nunique()
    raw_multi = int((emd_raw >= 2).sum())

    # 동 단위 집계
    sub = g[g["key_std"].isin(multi_emd_keys | multi_leaf_keys)].copy()
    units = []
    for (k, leaf), d in sub.groupby(["key_std", "leaf_n"]):
        d = d.sort_values("n", ascending=False)
        top = d.iloc[0]
        units.append(dict(
            key=k, leaf=leaf, leaf_raw=top["leaf"], asset=top["asset_type"],
            addr1=NEW_SIDO if top["addr1"] in OLD_SIDO else top["addr1"], addr2=top["addr2"], addr3=top["addr3"],
            name=top["display_name"], emd8s=sorted(set(d["emd8"].dropna())),
            n=int(d["n"].sum()), n7=int(d["n7"].sum()), n5=int(d["n5"].sum()),
            bj=top["bj"], lot=top["lot"], road=top["road"],
            by_mode=top["by_mode"], by_min=d["by_min"].min(), by_max=d["by_max"].max(),
            last_date=str(d["last_date"].max()),
        ))
    U = pd.DataFrame(units)
    log(f"dong units={len(U):,}")

    # K-apt 매칭(동 단위 대표 행)
    bca = load_attr_module()
    with eng.connect() as c:
        region_map = bca.load_region_map(c)
    kapt = bca.load_kapt(region_map, KAPT_XLSX)
    ki = kapt[kapt["beopjungri_code"] != ""].reset_index(drop=True)
    by_lot, by_name, by_core, names_in_bj, by_road = bca.build_kapt_indexes(ki)
    codes, tiers = [], []
    for r in U.itertuples(index=False):
        row = pd.Series({"beopjungri_code": r.bj, "display_name": r.name, "lot_number": r.lot, "road_name": r.road})
        tier, idxs = bca.match_one(row, by_lot=by_lot, by_name=by_name, by_core=by_core,
                                   names_in_bj=names_in_bj, by_road=by_road)
        tiers.append(tier)
        codes.append(str(ki.iloc[idxs[0]]["단지코드"]) if len(idxs) == 1 and tier != "no_match" else "")
    U["kapt"] = codes
    U["kapt_tier"] = tiers
    log("kapt matched units:", int((U["kapt"] != "").sum()), "/", len(U))

    def adjacent(e1: list[str], e2: list[str]):
        known = [e for e in e1 + e2 if e in graph_codes]
        if not known or not any(e in graph_codes for e in e1) or not any(e in graph_codes for e in e2):
            return None
        return any(b in nbr[a] or a == b for a in e1 for b in e2)

    res = []
    for k, d in U.groupby("key"):
        if d["leaf"].nunique() < 2:
            continue
        recs = d.to_dict("records")
        pair_cls, reasons = [], Counter()
        for x, y in itertools.combinations(recs, 2):
            r_a = []
            if x["kapt"] and y["kapt"] and x["kapt"] != y["kapt"]:
                r_a.append("kapt_diff")
            yd = None
            if pd.notna(x["by_mode"]) and pd.notna(y["by_mode"]):
                yd = abs(int(x["by_mode"]) - int(y["by_mode"]))
                if yd > 1:
                    r_a.append("year_diff")
            adj = adjacent(x["emd8s"], y["emd8s"])
            if adj is False:
                r_a.append("not_adjacent")
            if r_a:
                pair_cls.append("a")
                reasons.update(r_a)
            elif x["kapt"] and x["kapt"] == y["kapt"] and yd is not None and yd <= 1 and adj:
                pair_cls.append("b")
            else:
                pair_cls.append("c")
        cls = "a" if "a" in pair_cls else ("b" if all(p == "b" for p in pair_cls) else "c")
        mixed = cls == "a" and any(p != "a" for p in pair_cls)
        top = d.sort_values("n", ascending=False).iloc[0]
        res.append(dict(
            key=k, cls=cls, mixed=mixed, asset=top["asset"], addr1=top["addr1"], addr2=top["addr2"], addr3=top["addr3"],
            name=top["name"], n_units=len(d), n=int(d["n"].sum()), n7=int(d["n7"].sum()), n5=int(d["n5"].sum()),
            min_unit_n=int(d["n"].min()), reasons="+".join(sorted(reasons)),
            units=json.dumps([{kk: (str(v) if not isinstance(v, (int, float, str)) else v) for kk, v in r.items()
                               if kk in ("leaf_raw", "emd8s", "n", "bj", "lot", "road", "by_mode", "kapt", "kapt_tier")}
                              for r in recs], ensure_ascii=False),
        ))
    R = pd.DataFrame(res)
    R.to_csv(OUT / "a1_classified.csv", index=False, encoding="utf-8-sig")
    U.to_csv(OUT / "a1_units.csv", index=False, encoding="utf-8-sig")

    lines = ["# A-1 결과 (로컬, 읽기 전용)", ""]
    lines.append(f"- 이름 키 총 {g['building_key'].nunique():,}개(표준화 전) / {g['key_std'].nunique():,}개(호남 표준화 후)")
    lines.append(f"- 표준화 전 다법정동(앞 8자리 ≥2) 키: {raw_multi:,}")
    lines.append(f"- 표준화 후 다법정동 키: {len(multi_emd_keys):,} — 그중 leaf 이름 1개(코드 변형만): {len(code_variant_keys):,}, leaf ≥2: {len(multi_leaf_keys & multi_emd_keys):,}")
    lines.append(f"- leaf ≥2지만 앞 8자리 1개: {len(multi_leaf_keys - multi_emd_keys):,}")
    lines.append(f"- 호남 옛 키 {len(kmap):,}개, 1:N {one_to_n}")
    lines.append("")
    s = R.groupby("cls").agg(keys=("key", "count"), tx=("n", "sum"), tx7=("n7", "sum"), tx5=("n5", "sum")).reset_index()
    lines.append("## 판정별")
    lines.append(md_table([tuple(int(v) if not isinstance(v, str) else v for v in r) for r in s.itertuples(index=False)],
                          ["판정", "키", "거래(전체)", "거래(7년 창)", "거래(5년 창)"]))
    lines.append("")
    lines.append(f"- (a) 중 일부 쌍은 (b)/(c)인 혼합 키: {int(R['mixed'].sum()):,}")
    lines.append("- (a) 사유(쌍 기준 빈도): " + str(dict(Counter(itertools.chain.from_iterable(
        x.split("+") for x in R.loc[R.cls == 'a', 'reasons'] if x)))))
    lines.append("")
    for col, title in (("asset", "유형별"), ("addr1", "시도별")):
        p = R.pivot_table(index=col, columns="cls", values="n", aggfunc=["count", "sum"], fill_value=0)
        p.columns = [f"{a}_{b}" for a, b in p.columns]
        p = p.reset_index()
        lines.append(f"## {title} (count_=키, sum_=거래)")
        lines.append(md_table([tuple(int(v) if not isinstance(v, str) else v for v in r) for r in p.itertuples(index=False)], list(p.columns)))
        lines.append("")
    # 최소 단위 거래 수 분포(오기 의심 판단용)
    lines.append("## (a) 키의 가장 작은 동 단위 거래 수")
    bins = pd.cut(R.loc[R.cls == "a", "min_unit_n"], [0, 1, 2, 5, 10, 30, 10**9], labels=["1", "2", "3-5", "6-10", "11-30", "31+"])
    lines.append(md_table([(str(k), int(v)) for k, v in bins.value_counts().sort_index().items()], ["최소 단위 n", "키"]))
    cs = R[R.cls == "c"].sample(n=min(30, int((R.cls == "c").sum())), random_state=20261112)
    cs.to_csv(OUT / "a1_c_sample30.csv", index=False, encoding="utf-8-sig")
    lines.append("")
    lines.append(f"(c) 표본 {len(cs)}건: logs/collective_p2/a1_c_sample30.csv")

    # 대안: 전국 키 규칙을 코드 기반(asset|emd8|name)으로 바꿀 때
    named = g.copy()
    named["code_key"] = named["asset_type"] + "|" + named["emd8"].fillna("") + "|" + named["display_name"].fillna("")
    old_to_new = named.groupby("key_std")["code_key"].nunique()
    new_to_old = named.groupby("code_key")["key_std"].nunique()
    alt = dict(
        old_keys=int(named["key_std"].nunique()), new_keys=int(named["code_key"].nunique()),
        old_split=int((old_to_new >= 2).sum()), new_merged=int((new_to_old >= 2).sum()),
        changed_hash=int(named["key_std"].nunique()),
    )
    lines.append("")
    lines.append("## 대안(전국 코드 기반 키) 파급 — 근사(이름=display_name 원문)")
    lines.append(json.dumps(alt, ensure_ascii=False))
    (OUT / "a1_result.md").write_text("\n".join(lines), encoding="utf-8")
    pd.Series({k: sorted(v)[0] for k, v in kmap.items()}).to_csv(OUT / "a2_honam_keymap.csv", header=["new_key"], encoding="utf-8-sig")
    log("done")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
