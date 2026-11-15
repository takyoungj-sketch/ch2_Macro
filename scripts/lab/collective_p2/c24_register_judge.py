"""C-2 불확실 쌍·확실 유지 재점검 — 건축물대장(표제부 2026-07 + 건축HUB API 총괄표제부·표제부·부속지번)으로 판정(읽기 전용, 규칙 적용 없음).

T 규칙(2026-11-15):
 1. 연립·오피스텔: 정확한 지번(본번-부번)의 표제부 사용승인일이 서로 다르면 「다른 단지 후보」(API 없이).
 2. 대장 건물명에 차수·단지 번호(N차·N단지)가 있고 지번별로 다르면 「다른 단지」(어울림).
 3. 기존 「확실 유지」(분양권 제외 아파트·오피스텔)를 같은 방식으로 다시 본다 — 뒤집힘 후보는 API 로 확인.
 4. API 는 남은 대상에만(아파트 불확실 + 연립·오피스텔 미해결 + 같은 단지 후보 + 뒤집힘 후보 + 대조군 확인용).
 5. 최종(API): 같은 총괄표제부(PK)에 묶이거나 부속지번으로 서로 연결 → 같은 단지 /
    별개 대장(총괄 PK, 없으면 표제부 PK 가 겹치지 않음)이면서 건물명·사용승인일이 다름 → 다른 단지 / 그 밖 → 불확실(기본 분할 안 함).

  python c24_register_judge.py            # 대상만 세고 멈춤(API 호출 없음)
  python c24_register_judge.py --api --max-calls 900
출력(지번 포함, logs/ 에만): c2_uncertain_by_register.csv · c2_keep_recheck.csv · c2_control_register.csv
"""
from __future__ import annotations

import argparse
import re
import sys
import time

import pandas as pd
from sqlalchemy import text

import c20_c2_remeasure as c20
import c21_c2_three_way as c21
import c23_register_firstpass as c23
from _db import OUT, engine_db, md_table

CHASU = re.compile(r"제?\s*(\d+)\s*(차|단지)")
SAME, DIFF, UNC = "같은 단지", "다른 단지", "불확실"


def chasu_of(names) -> set[str]:
    out = set()
    for n in names:
        for num, kind in CHASU.findall(str(n or "")):
            out.add(f"{int(num)}{kind}")
    return out


def exact_register(reg: pd.DataFrame, bjd: str, lot: str, jis: set[str]) -> dict:
    r = reg[(reg["bjd10"] == bjd) & (reg["bun"] == lot)] if len(reg) else reg
    r = r[[c23._ji(j) in jis for j in r["ji"]]] if len(r) else r
    m = r[r["atch"] == "0"] if len(r) else r
    return {"pks": set(m["pk"]), "names": {n for n in m["bld_nm"] if n}, "apr": {a for a in m["use_apr"] if a},
            "dongs": sorted({d for d in m["dong_nm"] if d})[:10], "jis": jis}


def local_pass(asset: str, gs: list[dict]) -> tuple[str, str]:
    """API 없이 정할 수 있는 것(T 규칙 1·2). (칸, 근거). 칸 = 다른 단지 / API / 같은 단지 후보."""
    ch = [chasu_of(g["names"]) for g in gs]
    if all(ch) and all(ch[i] != ch[j] and not (ch[i] & ch[j]) for i in range(len(ch)) for j in range(i + 1, len(ch))):
        return DIFF, f"대장 건물명 차수·단지 번호가 지번별로 다름({' / '.join(','.join(sorted(c)) for c in ch)})"
    have = [g for g in gs if g["pks"]]
    if asset in ("rowhouse", "officetel") and len(have) == len(gs):
        a = [g["apr"] for g in gs]
        if all(a) and all(not (a[i] & a[j]) for i in range(len(a)) for j in range(i + 1, len(a))):
            return DIFF + " 후보", "연립·오피스텔: 정확한 지번 표제부 사용승인일이 다름"
    if len(have) == 1 and all(not g["pks"] for g in gs if g is not have[0]):
        return "같은 단지 후보", "한 지번에만 표제부·다른 지번은 건물 없음(필지 걸친 건물?)"
    return "API", "대장 확인 필요"


def api_lot(cl, bjd: str, lot: str, jis: set[str]) -> dict:
    sgg, bj = bjd[:5], bjd[5:]
    rec = [x for x in cl.items("recap", sgg, bj, lot) if c23._ji(x.get("ji")) in jis]
    tit = [x for x in cl.items("title", sgg, bj, lot) if c23._ji(x.get("ji")) in jis and str(x.get("mainAtchGbCd")) == "0"]
    atc = [x for x in cl.items("atch", sgg, bj, lot) if c23._ji(x.get("ji")) in jis]
    links = {(str(x.get("atchSigunguCd", "")) + str(x.get("atchBjdongCd", "")),
              str(int(x["atchBun"])) if str(x.get("atchBun", "")).isdigit() else str(x.get("atchBun")),
              c23._ji(x.get("atchJi"))) for x in atc}
    return {"recap_pks": {str(x.get("mgmBldrgstPk")) for x in rec}, "title_pks": {str(x.get("mgmBldrgstPk")) for x in tit},
            "names": {str(x.get("bldNm") or "").strip() for x in rec + tit if str(x.get("bldNm") or "").strip()},
            "apr": {str(x.get("useAprDay") or "") for x in rec + tit if x.get("useAprDay")},
            "links": links, "lot": (bjd, lot), "jis": jis,
            "rec_names": sorted({str(x.get("bldNm") or "") for x in rec}), "bylot": sorted({str(x.get("bylotCnt")) for x in rec})}


def api_pair(a: dict, b: dict) -> tuple[str, str]:
    def linked(x, y):
        return any(l[0] == y["lot"][0] and l[1] == y["lot"][1] and l[2] in y["jis"] for l in x["links"])

    if a["recap_pks"] & b["recap_pks"]:
        return SAME, "같은 총괄표제부"
    if linked(a, b) or linked(b, a):
        return SAME, "부속지번으로 연결"
    ida = a["recap_pks"] or a["title_pks"]
    idb = b["recap_pks"] or b["title_pks"]
    if ida and idb and not (ida & idb):
        names_diff = not c20.names_match({c20.name_sig(n) for n in a["names"] if c20.name_sig(n)} or {("", "")},
                                         {c20.name_sig(n) for n in b["names"] if c20.name_sig(n)} or {("", "")}) \
            if a["names"] and b["names"] else False
        ca, cb = chasu_of(a["names"]), chasu_of(b["names"])
        names_diff = names_diff or bool(ca and cb and not (ca & cb))
        apr_diff = bool(a["apr"] and b["apr"] and not (a["apr"] & b["apr"]))
        if names_diff or apr_diff:
            return DIFF, "별개 대장 · " + ("건물명 다름" if names_diff else "") + (" · " if names_diff and apr_diff else "") + \
                ("사용승인일 다름" if apr_diff else "")
        return UNC, "별개 대장이나 건물명·사용승인일 같음"
    if not ida or not idb:
        return UNC, "대장 없음(한쪽 이상)"
    return UNC, "같은 대장 PK(판정 보류)"


def combine(pairs: list[tuple[str, str]]) -> tuple[str, str]:
    cls = {c for c, _ in pairs}
    if cls == {SAME}:
        return SAME, "; ".join(sorted({w for _, w in pairs}))
    if DIFF in cls and SAME not in cls and UNC not in cls:
        return DIFF, "; ".join(sorted({w for _, w in pairs}))
    if DIFF in cls and SAME not in cls:
        return DIFF, "일부 쌍 다름·나머지 불확실: " + "; ".join(sorted({w for _, w in pairs}))
    return UNC, "; ".join(sorted({w for _, w in pairs}))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--max-calls", type=int, default=900)
    a = ap.parse_args(argv)
    t0 = time.time()
    sub, ev, _ = c21.load()
    new = c21.run(sub, ev, c21.T_MAIN)
    new = new.sort_values("tx", ascending=False).reset_index(drop=True)
    unc = new[new["cls"] == c21.UNC].reset_index(drop=True)
    unc["확인ID"] = [f"C2U-{i + 1:04d}" for i in range(len(unc))]
    keep = new[(new["cls"] == c21.KEEP) & new["asset_type"].isin(["apartment", "officetel"])].reset_index(drop=True)
    # 대조군: c2_t_samples.csv 의 확실 분할·확실 유지(분양권 제외) — (유형·이름·동·본번 목록)으로 new 와 맞춘다
    ts = pd.read_csv(OUT / "c2_t_samples.csv", dtype=str)
    ts = ts[ts["칸"].isin([c21.CERT, c21.KEEP]) & (ts["유형"] != "분양권")].copy()
    ko2 = {v: k for k, v in c21.KO.items()}

    def lots_of(txt):
        return tuple(sorted(re.findall(r"본번 (\S+?):", str(txt))))

    groups_all = sub
    gkey = ["key2", "asset_type", "beopjungri_code"]

    def big_of(row):
        g = groups_all[(groups_all["key2"] == row["key2"]) & (groups_all["asset_type"] == row["asset_type"])
                       & (groups_all["beopjungri_code"] == row["beopjungri_code"])].sort_values("n", ascending=False)
        return g

    ctrl = []
    for _, t in ts.iterrows():
        cand = new[new["asset_type"] == ko2.get(t["유형"])]
        for _, r in cand.iterrows():
            g = big_of(r)
            if str(g["name"].iloc[0]) == t["이름(원문)"] and str(g["dong"].iloc[0]) == t["동"] \
                    and tuple(sorted(g["main_lot"])) == lots_of(t["본번 그룹(건축년도·거래 수)"]):
                ctrl.append({**r.to_dict(), "truth": SAME if t["칸"] == c21.KEEP else DIFF, "확인ID": "CTRL"})
                break
    ctrl = pd.DataFrame(ctrl)
    print(f"- 불확실 {len(unc)} · 확실 유지(아파트·오피스텔) {len(keep)} · 대조군 {len(ctrl)}/{len(ts)} 맞춤 · {time.time() - t0:,.0f}초")

    units = [("불확실", unc), ("확실 유지 재점검", keep), ("대조군", ctrl)]
    lots = set()
    for _, df in units:
        for _, r in df.iterrows():
            g = big_of(r)
            lots |= {(str(b), str(m)) for b, m in zip(g["beopjungri_code"], g["main_lot"]) if str(m).isdigit()}
    reg = c23.scan(lots)
    eng = engine_db("collective_stats_p2r", timeout_ms=600_000)
    names = sorted({str(big_of(r)["name"].iloc[0]) for _, df in units for _, r in df.iterrows()})
    with eng.connect() as c:
        lt = pd.read_sql(text("""SELECT left(beopjungri_code, 10) AS bjd, display_name AS name, btrim(lot_number) AS lot
                                 FROM collective_transactions WHERE is_valid AND display_name = ANY(:nm)
                                   AND coalesce(btrim(lot_number), '') <> '' GROUP BY 1, 2, 3"""), c, params={"nm": names})
    sublots: dict = {}
    for b, nm, lot in zip(lt["bjd"].astype(str), lt["name"].astype(str), lt["lot"]):
        mn, _, sj = lot.partition("-")
        mn = str(int(mn)) if mn.isdigit() else mn
        sublots.setdefault((b, nm, mn), set()).add(c23._ji(sj))

    work = []
    for label, df in units:
        for _, r in df.iterrows():
            g = big_of(r)
            big = g[g["n"] >= 3]
            b0, nm0 = str(r["beopjungri_code"]), str(g["name"].iloc[0])
            gs = [{"lot": str(m), "n": int(n), **exact_register(reg, b0, str(m), sublots.get((b0, nm0, str(m)), set()))}
                  for m, n in zip(big["main_lot"], big["n"]) if str(m).isdigit()]
            if len(gs) < 2:
                cls, why = UNC, "숫자 본번 2개 미만"
            elif label == "확실 유지 재점검":
                # 3: 정확한 지번이 별개 대장이고 승인일이 다르거나 차수가 다르면 뒤집힘 후보 → API
                lc, lw = local_pass(r["asset_type"], gs)
                sep = all(gs[i]["pks"] and gs[j]["pks"] and not (gs[i]["pks"] & gs[j]["pks"])
                          for i in range(len(gs)) for j in range(i + 1, len(gs)))
                aprd = all(gs[i]["apr"] and gs[j]["apr"] and not (gs[i]["apr"] & gs[j]["apr"])
                           for i in range(len(gs)) for j in range(i + 1, len(gs)))
                if lc == DIFF:
                    cls, why = "뒤집힘 후보", lw
                elif sep and aprd:
                    cls, why = "뒤집힘 후보", "정확한 지번이 별개 표제부·사용승인일 다름"
                else:
                    cls, why = "유지 그대로", "정확한 지번 대장이 같거나 승인일 겹침"
            else:
                cls, why = local_pass(r["asset_type"], gs)
            work.append({"label": label, "row": r, "gs": gs, "b0": b0, "name": nm0, "dong": g["dong"].iloc[0],
                         "sigungu": g["sigungu"].iloc[0], "local": cls, "local_why": why})

    need = [w for w in work if (w["label"] == "불확실" and w["local"] in ("API", "같은 단지 후보"))
            or (w["label"] == "확실 유지 재점검" and w["local"] == "뒤집힘 후보")
            or (w["label"] == "대조군")]
    api_lots = sorted({(w["b0"], g["lot"]) for w in need for g in w["gs"]})
    print(f"- 로컬 판정 뒤 API 대상: {len(need)}건(불확실 {sum(w['label'] == '불확실' for w in need)} · "
          f"뒤집힘 후보 {sum(w['label'] == '확실 유지 재점검' for w in need)} · 대조군 {sum(w['label'] == '대조군' for w in need)}) · "
          f"지번(본번) {len(api_lots)} → 호출 약 {len(api_lots) * 3}회")
    rows = [(lbl, c, n) for (lbl, c), n in pd.Series([(w["label"], w["local"]) for w in work]).value_counts().sort_index().items()]
    print(md_table(rows, ["단위", "로컬 칸", "건"]))
    if not a.api:
        print("API 호출 없음(--api 로 실행)")
        return 0

    import bld_api

    cl = bld_api.Client(max_calls=a.max_calls)
    info: dict = {}
    stopped = None
    for bjd, lot in api_lots:
        jis = set().union(*[g["jis"] for w in need for g in w["gs"] if w["b0"] == bjd and g["lot"] == lot])
        try:
            info[(bjd, lot)] = api_lot(cl, bjd, lot, jis)
        except bld_api.ApiSkip as ex:
            print(f"  건너뜀: {ex}")
        except bld_api.ApiStop as ex:
            stopped = str(ex)
            break
    print(f"- API: 새 호출 {cl.calls} · 캐시 {cl.cached} · 조회한 지번 {len(info)}/{len(api_lots)} · 건너뛴 요청 {cl.skipped}"
          + (f" · 멈춤: {stopped}" if stopped else ""))

    out = []
    for w in work:
        r = w["row"]
        final, fwhy = None, ""
        if w["label"] == "불확실" and w["local"].startswith(DIFF):
            final, fwhy = DIFF, w["local_why"]
        elif w["label"] == "확실 유지 재점검" and w["local"] == "유지 그대로":
            final, fwhy = SAME, w["local_why"]
        elif all((w["b0"], g["lot"]) in info for g in w["gs"]):
            gi = [info[(w["b0"], g["lot"])] for g in w["gs"]]
            pairs = [api_pair(gi[i], gi[j]) for i in range(len(gi)) for j in range(i + 1, len(gi))]
            final, fwhy = combine(pairs)
            if w["local"] == DIFF and final != SAME:            # 차수 규칙(2)은 API 가 같은 단지라 하지 않으면 유지
                final, fwhy = DIFF, w["local_why"] + " · API: " + fwhy
        else:
            final, fwhy = UNC, "API 미조회(한도·중단)"
        out.append({"단위": w["label"], "확인ID": r.get("확인ID", ""), "유형": c21.KO[r["asset_type"]], "시군구": w["sigungu"],
                    "동": w["dong"], "단지명(거래)": w["name"], "법정동코드": w["b0"], "거래 합": int(r["tx"]),
                    "기존 칸": r["cls"], "로컬 칸": w["local"], "로컬 근거": w["local_why"], "최종": final, "최종 근거": fwhy,
                    "정답(대조군)": r.get("truth", ""),
                    "지번별 대장": " / ".join(
                        f"{g['lot']}-{'·'.join(sorted(g['jis']))}: 건물명 {','.join(sorted(g['names']))[:40] or '-'} · 승인 {','.join(sorted(g['apr']))[:30] or '-'}"
                        f" · 동 {','.join(g['dongs'])[:30] or '-'}"
                        + (f" · 총괄 {','.join(info[(w['b0'], g['lot'])]['rec_names'])[:30] or '없음'}"
                           f" · 부속지번 {len(info[(w['b0'], g['lot'])]['links'])}" if (w['b0'], g['lot']) in info else "")
                        for g in w["gs"])})
    df = pd.DataFrame(out)
    # 다음 단계(c25 확정 판정)가 쓰는 상태 — 지번 포함, logs/ 에만
    import pickle

    with (OUT / "c24_state.pkl").open("wb") as fh:
        pickle.dump({"work": [{k: v for k, v in w.items()} for w in work], "info": info, "out": out}, fh)
    df[df["단위"] == "불확실"].to_csv(OUT / "c2_uncertain_by_register.csv", index=False, encoding="utf-8-sig")
    df[df["단위"] == "확실 유지 재점검"].to_csv(OUT / "c2_keep_recheck.csv", index=False, encoding="utf-8-sig")
    df[df["단위"] == "대조군"].to_csv(OUT / "c2_control_register.csv", index=False, encoding="utf-8-sig")

    u = df[df["단위"] == "불확실"]
    print("\n## 불확실 271쌍 최종(대장)\n")
    print(md_table([(c, f"{(u['최종'] == c).sum():,}", f"{int(u.loc[u['최종'] == c, '거래 합'].sum()):,}",
                     f"{((u['최종'] == c) & (u['확인ID'] <= 'C2U-0100')).sum():,}") for c in (SAME, DIFF, UNC)],
                   ["칸", "쌍", "거래", "거래 상위 100 안"]))
    print()
    print(md_table([(t, c, n) for (t, c), n in u.groupby(["유형", "최종"]).size().items()], ["유형", "최종", "쌍"]))
    print()
    print(md_table([(c, w, n) for (c, w), n in u.groupby(["최종", "최종 근거"]).size().sort_values(ascending=False).head(15).items()],
                   ["최종", "근거", "쌍"]))
    k = df[df["단위"] == "확실 유지 재점검"]
    print(f"\n## 확실 유지 재점검(아파트·오피스텔 {len(k)}쌍): 뒤집힘(다른 단지) {(k['최종'] == DIFF).sum()} · "
          f"유지 확인 {(k['최종'] == SAME).sum()} · 불확실 {(k['최종'] == UNC).sum()}")
    for _, r in k[k["최종"] == DIFF].iterrows():
        print(f"  - {r['단지명(거래)']} ({r['시군구']} {r['동']}, {r['거래 합']}건): {r['최종 근거']}")
    cc = df[df["단위"] == "대조군"]
    if len(cc):
        dec = cc[cc["최종"] != UNC]
        ok = (dec["최종"] == dec["정답(대조군)"]).sum()
        print(f"\n## 대조군 {len(cc)}건: 판정 {len(dec)} · 정답 {ok} ({ok / max(len(dec), 1):.0%}) · 불확실 {len(cc) - len(dec)}")
        print(md_table([(tr, fi, n) for (tr, fi), n in cc.groupby(["정답(대조군)", "최종"]).size().items()], ["정답", "판정", "건"]))
        for _, r in cc[(cc["최종"] != UNC) & (cc["최종"] != cc["정답(대조군)"])].iterrows():
            print(f"  - 불일치: {r['단지명(거래)']} ({r['유형']}, {r['동']}) 정답 {r['정답(대조군)']} · 판정 {r['최종']} — {r['최종 근거']}")
    print(f"\n전체 {time.time() - t0:,.0f}초 · API 새 호출 {cl.calls}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
