"""C-2 불확실 271쌍 — 현재 표제부(mart_djy_03, 2026-07)만으로 1차 분류(키 없이, 읽기 전용). 규칙 적용 없음.

대조 단위: 본번 묶음의 **거래에 실제로 나온 지번(본번-부번)** 의 표제부만 쓴다. 본번 전체를 보면 같은 본번의 다른 부번
건물(대조동 4번지에는 부번마다 다른 건물이 10곳 넘게 있음)이 섞여 사용승인일 비교가 무의미해진다(첫 실행에서 확인).

분류(쌍 = 같은 2단계 키·법정동 안 3건+ 본번 묶음들):
  같은 단지 후보 : 한 본번에만 같은 이름(거래 단지명과 맞는) 표제부 주건축물이 있고, 다른 본번(들)에는 건물이 없음
                   (필지를 걸친 한 건물 — 부속지번으로 확인할 대상이기도 함)
  다른 단지 후보 : 모든 본번에 표제부 주건축물이 있고, 사용승인일이 겹치지 않으며 동명칭 체계도 다름
  API 확인 대상  : 나머지(총괄표제부·표제부·부속지번 API 로 확인)

- 원천: raw/raw addition/건축물대장(건축허브)/국토교통부_건축물대장_표제부+(2026년+07월)/mart_djy_03.txt — 읽기만(원본 저장소 경로).
- 키·법정동·본번 묶음은 c21(3칸 분류, T=10)과 같은 계산으로 리허설 DB(롤백 뒤 = 원본, 읽기 전용)에서 다시 만든다.
- 출력(지번 포함 → logs/ 에만, 커밋하지 않음):
    logs/collective_p2/c2_register_firstpass.csv     쌍마다 1차 칸·근거·본번별 표제부 요약
    logs/collective_p2/c2_register_rows.csv          쓰인 표제부 행(본번별 건물명·동명칭·사용승인일·용도·세대)
    logs/collective_p2/c2_api_targets.csv            API 확인 대상 (시군구코드·법정동코드·본번) 목록
  표준출력: 칸별 건수·거래 수, API 대상 지번 수·예상 호출 수, 시험 사례 2건(정익제이원·어울림)과 어울림 316건 중복 여부
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

import c20_c2_remeasure as c20
import c21_c2_three_way as c21
from _db import OUT, engine_db, md_table

RAW = Path("D:/ch2/ch2_Macro/raw/raw addition/건축물대장(건축허브)/국토교통부_건축물대장_표제부+(2026년+07월)/mart_djy_03.txt")
# 표제부(mart_djy_03) 열 번호(첫 행으로 확인: 60 = 사용승인일)
C = dict(pk=0, kind=2, plat=5, bld_nm=7, sgg=8, bjd=9, plat_gb=10, bun=11, ji=12, dong_nm=22, atch=23,
         purps=35, etc_purps=36, hhld=40, use_apr=60)
CALLS_PER_LOT = 3          # 총괄표제부·표제부·부속지번 (본번 단위 조회, 한 번에 100행)
TESTS = [("정익제이원", "대조동", ("4", "6")), ("어울림", "복대동", ("3366", "3367"))]


def dong_scheme(nm: str) -> str:
    s = (nm or "").strip()
    if not s:
        return "없음"
    if re.fullmatch(r"제?\s*\d+\s*동?", s):
        return "숫자"
    if re.fullmatch(r"[A-Za-z]\s*동?", s):
        return "영문"
    if re.fullmatch(r"[가-하]\s*동", s):
        return "가나다"
    return "기타"


def scan(lots: set[tuple[str, str]]) -> pd.DataFrame:
    """(법정동10, 본번) 집합에 드는 표제부 행만(주건축물·부속 모두, 판단은 뒤에서). 읽기만."""
    want_bjd = {b for b, _ in lots}
    rows = []
    t0 = time.time()
    with RAW.open("rb") as f:
        for i, raw in enumerate(f):
            line = raw.decode("utf-8", "replace")
            p = line.split("|", 13)
            if len(p) < 13:
                continue
            bjd10 = p[C["sgg"]] + p[C["bjd"]]
            if bjd10 not in want_bjd or p[C["plat_gb"]] != "0":
                continue
            bun = str(int(p[C["bun"]])) if p[C["bun"]].isdigit() else p[C["bun"]]
            if (bjd10, bun) not in lots:
                continue
            q = line.rstrip("\r\n").split("|")
            rows.append(dict(bjd10=bjd10, bun=bun, ji=q[C["ji"]], pk=q[C["pk"]], kind=q[C["kind"]], bld_nm=q[C["bld_nm"]],
                             dong_nm=q[C["dong_nm"]], atch=q[C["atch"]], purps=q[C["purps"]], etc_purps=q[C["etc_purps"]],
                             hhld=q[C["hhld"]], use_apr=q[C["use_apr"]], plat=q[C["plat"]]))
    print(f"- 표제부 2026-07 훑기 {i + 1:,}행 · 맞는 행 {len(rows):,} · {time.time() - t0:,.0f}초")
    return pd.DataFrame(rows)


def _ji(v) -> str:
    s = str(v or "").strip()
    return str(int(s)) if s.isdigit() else (s or "0")


def lot_summary(reg: pd.DataFrame, bjd: str, lot: str, key_sig, jis: set[str] | None = None) -> dict:
    r = reg[(reg["bjd10"] == bjd) & (reg["bun"] == lot)] if len(reg) else reg
    if jis is not None and len(r):
        r = r[[_ji(j) in jis for j in r["ji"]]]
    main = r[r["atch"] == "0"] if len(r) else r
    named = main[[bool(key_sig) and bool(c20.name_sig(n)) and c20.names_match({c20.name_sig(n)}, {key_sig})
                  for n in main["bld_nm"]]] if len(main) else main
    return {"n_main": len(main), "n_named": len(named),
            "names": sorted({n for n in main["bld_nm"] if n}), "apr": sorted({a for a in main["use_apr"] if a}),
            "schemes": sorted({dong_scheme(d) for d in main["dong_nm"]}) if len(main) else [],
            "dongs": sorted({d for d in main["dong_nm"] if d})[:12], "jis": sorted(jis or [])}


def classify(groups: list[dict]) -> tuple[str, str]:
    have = [g for g in groups if g["n_main"] > 0]
    if len(have) == 1 and have[0]["n_named"] > 0 and all(g["n_main"] == 0 for g in groups if g is not have[0]):
        return "같은 단지 후보", "한 본번에만 같은 이름 표제부·다른 본번은 건물 없음(필지 걸친 건물?)"
    if len(have) == len(groups) and len(groups) >= 2:
        aprs = [set(g["apr"]) for g in groups]
        disjoint = all(not (aprs[i] & aprs[j]) for i in range(len(aprs)) for j in range(i + 1, len(aprs)))
        sch = [set(g["schemes"]) for g in groups]
        scheme_diff = all(sch[i] != sch[j] for i in range(len(sch)) for j in range(i + 1, len(sch)))
        if disjoint and scheme_diff and all(aprs):
            return "다른 단지 후보", "모든 본번에 표제부·사용승인일 겹치지 않음·동명칭 체계 다름"
        if disjoint and all(aprs):
            return "API 확인 대상", "사용승인일은 다르나 동명칭 체계 같음"
        return "API 확인 대상", "사용승인일 겹침(같은 단지일 수 있음)"
    if not have:
        return "API 확인 대상", "어느 본번에도 표제부 주건축물 없음"
    return "API 확인 대상", "일부 본번에만 표제부(이름 불일치 포함)"


def main():
    t0 = time.time()
    sub, ev, _c01 = c21.load()
    new = c21.run(sub, ev, c21.T_MAIN)
    unc = new[new["cls"] == c21.UNC].sort_values("tx", ascending=False).reset_index(drop=True)
    unc["확인ID"] = [f"C2U-{i + 1:04d}" for i in range(len(unc))]          # c21 CSV 와 같은 순서·번호
    groups = sub.merge(unc[["key2", "asset_type", "beopjungri_code"]], on=["key2", "asset_type", "beopjungri_code"])
    lots = {(str(b), str(m)) for b, m in zip(groups["beopjungri_code"], groups["main_lot"]) if str(m).isdigit()}
    # 시험 사례 지번도 함께
    test_rows = []
    for nm, dong, ls in TESTS:
        g = sub[(sub["name"].astype(str).str.contains(nm)) & (sub["dong"].astype(str).str.contains(dong))
                & (sub["main_lot"].isin(ls))]
        test_rows.append((nm, dong, ls, g))
        lots |= {(str(b), str(m)) for b, m in zip(g["beopjungri_code"], g["main_lot"])}
    print(f"- 불확실 {len(unc):,}쌍 · 본번 {len(lots):,}개(시험 사례 포함) · 묶음 다시 만들기 {time.time() - t0:,.0f}초")
    reg = scan(lots)
    # 거래에 실제로 나온 지번(본번-부번): (법정동10, 단지명, 본번) → {부번}
    eng = engine_db("collective_stats_p2r", timeout_ms=600_000)
    names = sorted(set(groups["name"].astype(str)) | {str(n) for _nm, _d, _l, gg in test_rows for n in gg["name"]})
    with eng.connect() as c:
        lt = pd.read_sql(text("""
            SELECT left(beopjungri_code, 10) AS bjd, display_name AS name, btrim(lot_number) AS lot, count(*) AS n
            FROM collective_transactions
            WHERE is_valid AND display_name = ANY(:nm) AND coalesce(btrim(lot_number), '') <> ''
            GROUP BY 1, 2, 3"""), c, params={"nm": names})
    sublots: dict[tuple[str, str, str], set[str]] = {}
    for b, nm, lot in zip(lt["bjd"].astype(str), lt["name"].astype(str), lt["lot"]):
        main_, _, sub_ = lot.partition("-")
        main_ = str(int(main_)) if main_.isdigit() else main_
        sublots.setdefault((b, nm, main_), set()).add(_ji(sub_))

    recs = []
    for _, u in unc.iterrows():
        g = groups[(groups["key2"] == u["key2"]) & (groups["asset_type"] == u["asset_type"])
                   & (groups["beopjungri_code"] == u["beopjungri_code"])].sort_values("n", ascending=False)
        big = g[g["n"] >= 3]
        key_sig = c20.name_sig(g["name"].iloc[0])
        nm0 = str(g["name"].iloc[0])
        b0 = str(u["beopjungri_code"])
        gs = [{"lot": m, "n": int(n), **lot_summary(reg, b0, str(m), key_sig, sublots.get((b0, nm0, str(m)), set()))}
              for m, n in zip(big["main_lot"], big["n"])]
        cls, why = classify(gs)
        recs.append({"확인ID": u["확인ID"], "유형": c21.KO[u["asset_type"]], "법정동코드": u["beopjungri_code"],
                     "시군구": g["sigungu"].iloc[0], "동": g["dong"].iloc[0], "단지명(거래)": g["name"].iloc[0],
                     "거래 합": int(u["tx"]), "1차 칸": cls, "근거": why, "불확실 사유(c21)": "; ".join(u["reasons"]),
                     "본번별 표제부": " / ".join(
                         f"{x['lot']}-{'·'.join(x['jis'])}({x['n']}건): 주건물 {x['n_main']} · 이름맞음 {x['n_named']} · 건물명 {','.join(x['names'])[:40] or '-'}"
                         f" · 사용승인 {','.join(x['apr'])[:40] or '-'} · 동명칭 {','.join(x['dongs'])[:40] or '-'}({'/'.join(x['schemes']) or '-'})"
                         for x in gs)})
    df = pd.DataFrame(recs)
    df.to_csv(OUT / "c2_register_firstpass.csv", index=False, encoding="utf-8-sig")
    if len(reg):
        reg.to_csv(OUT / "c2_register_rows.csv", index=False, encoding="utf-8-sig")

    rows = []
    for cl in ("같은 단지 후보", "다른 단지 후보", "API 확인 대상"):
        x = df[df["1차 칸"] == cl]
        top = x[x["확인ID"] <= "C2U-0100"]
        rows.append((cl, f"{len(x):,}", f"{int(x['거래 합'].sum()):,}", f"{len(top):,}"))
    print("\n## 1차 분류 (표제부 2026-07 만)\n")
    print(md_table(rows, ["칸", "쌍", "거래", "그중 거래 상위 100 안"]))
    why = df.groupby(["1차 칸", "근거"]).agg(n=("확인ID", "size"), tx=("거래 합", "sum")).reset_index()
    print()
    print(md_table([(r["1차 칸"], r["근거"], f"{r.n:,}", f"{int(r.tx):,}") for _, r in why.iterrows()], ["칸", "근거", "쌍", "거래"]))
    print()
    print(md_table([(t, cl, f"{n:,}") for (t, cl), n in df.groupby(["유형", "1차 칸"]).size().items()], ["유형", "칸", "쌍"]))

    api = df[df["1차 칸"] == "API 확인 대상"]
    api_pairs = unc[unc["확인ID"].isin(api["확인ID"])][["key2", "asset_type", "beopjungri_code"]]
    tg = groups.merge(api_pairs, on=["key2", "asset_type", "beopjungri_code"])
    tlots = sorted({(str(b)[:5], str(b)[5:], str(m)) for b, m in zip(tg["beopjungri_code"], tg["main_lot"]) if str(m).isdigit()})
    pd.DataFrame(tlots, columns=["sigunguCd", "bjdongCd", "bun"]).to_csv(OUT / "c2_api_targets.csv", index=False)
    top_pairs = unc[unc["확인ID"].isin(api[api["확인ID"] <= "C2U-0100"]["확인ID"])][["key2", "asset_type", "beopjungri_code"]]
    tg100 = groups.merge(top_pairs, on=["key2", "asset_type", "beopjungri_code"])
    tl100 = {(str(b), str(m)) for b, m in zip(tg100["beopjungri_code"], tg100["main_lot"]) if str(m).isdigit()}
    print(f"\n- API 확인 대상: {len(api):,}쌍 · 지번(본번) {len(tlots):,}개 → 예상 호출 {len(tlots) * CALLS_PER_LOT:,}회"
          f"(본번마다 총괄표제부·표제부·부속지번 각 1회, 100행 넘는 본번은 페이지 추가)")
    print(f"  · 그중 거래 상위 100 안: 지번 {len(tl100):,}개 → {len(tl100) * CALLS_PER_LOT:,}회")

    # 시험 사례
    print("\n## 시험 사례\n")
    reg_cols = ["bun", "ji", "kind", "bld_nm", "dong_nm", "atch", "purps", "etc_purps", "hhld", "use_apr"]
    for nm, dong, ls, g in test_rows:
        print(f"### {nm} ({dong} {'·'.join(ls)}번지)\n")
        print(g[["key2", "asset_type", "beopjungri_code", "main_lot", "n", "byear", "name"]].assign(
            key2=g["key2"].str[:12]).to_string(index=False))
        if len(g):
            b = str(g["beopjungri_code"].iloc[0])
            r = reg[(reg["bjd10"] == b) & (reg["bun"].isin(ls))] if len(reg) else reg
            js = {m: sublots.get((b, str(g["name"].iloc[0]), m), set()) for m in ls}
            r = r[[(_ji(j) in js.get(bn, set())) for bn, j in zip(r["bun"], r["ji"])]] if len(r) else r
            print(f"\n표제부(2026-07) — 거래에 나온 지번만 {', '.join(f'{m}-{sorted(v)}' for m, v in js.items())}:")
            print(r[reg_cols].sort_values(["bun", "ji", "atch", "dong_nm"]).to_string(index=False) if len(r) else "(행 없음)")
            # 같은 거래가 두 본번에 중복 집계됐는지
            with eng.connect() as c:
                tx = pd.read_sql(text("""
                    SELECT split_part(btrim(lot_number), '-', 1) AS ml, lot_number, contract_date, price, exclusive_area, floor,
                           transaction_hash
                    FROM collective_transactions
                    WHERE building_key = ANY(:k) AND left(beopjungri_code, 10) = :b AND is_valid
                      AND split_part(btrim(lot_number), '-', 1) = ANY(:ls)"""),
                    c, params={"k": sorted(set(g["key2"]) | set(g.get("old_key", g["key2"]))), "b": b, "ls": list(ls)})
            sig = ["contract_date", "price", "exclusive_area", "floor"]
            a_, b_ = (tx[tx["ml"] == ls[0]], tx[tx["ml"] == ls[1]])
            ma = a_.groupby(sig).size()
            mb = b_.groupby(sig).size()
            both = ma.index.intersection(mb.index)
            same_n = int(sum(min(ma[k], mb[k]) for k in both))
            share = same_n / max(min(len(a_), len(b_)), 1)
            print(f"\n거래: {ls[0]} {len(a_)}건 · {ls[1]} {len(b_)}건 · 같은 (계약일·가격·면적·층) 거래 {same_n}건({share:.0%})"
                  f" → {'같은 거래가 두 지번에 실림(중복 집계)' if share >= 0.9 else '서로 다른 거래(중복 아님)'}")
            yy = tx.assign(y=pd.to_datetime(tx["contract_date"]).dt.year).groupby(["ml", "y"]).size().unstack(0).fillna(0).astype(int)
            print("계약연도별 거래(두 지번):\n" + yy.to_string())
            print(f"지번 표기: {sorted(set(a_['lot_number']))[:5]} / {sorted(set(b_['lot_number']))[:5]} · "
                  f"transaction_hash 겹침 {len(set(a_['transaction_hash']) & set(b_['transaction_hash']))}")
        print()
    print(f"전체 {time.time() - t0:,.0f}초 · 결과 logs/collective_p2/c2_register_firstpass.csv (지번 포함, 로컬)")


if __name__ == "__main__":
    sys.exit(main())
