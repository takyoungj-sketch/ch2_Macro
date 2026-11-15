"""C-2 판정 확정(파일만 — 리허설 DB 에도 쓰지 않음). 읽기 전용.

입력: c21(3칸, T=10) 재계산 + c24_state.pkl(대장 판정: 표제부 2026-07 + 건축HUB API 캐시)
규칙(T 2026-11-15):
  - 불확실 271쌍: 대장 판정(같은 단지 → 유지 · 다른 단지 → 분할 · 불확실 → 분할 안 함)
  - 아파트 차수별 단지(대장이 따로 있고 승인일이 다른 아파트 쌍)는 K-apt 로 정한다:
      두 지번이 K-apt 코드 하나로 묶임 → 유지 / 코드가 다르거나 없고 승인일 차이 ≥ 1년 → 분할 / 1년 미만 → 유지
    (건물명·차수가 다른 쌍은 이 규칙 밖 — 그대로 분할)
  - 「확실 유지」 재점검 7쌍(아파트): 위 규칙 적용
  - c21 확실 분할 → 분할(c21 의 묶음 그대로), 확실 유지·분양권 → 유지
출력(지번 포함, logs/ 에만): logs/collective_p2/c2_units_final.csv — collective_building_key_c2_units 열 + 참고 열
  · split: (키·법정동)의 3건+ 본번마다 한 행, part 0 = 가장 큰 조각(옛 키 유지)
  · keep : (키·법정동)마다 한 행(main_lot '')
  3건 미만 본번은 행을 만들지 않는다 — 키 이전·월간 적재 때 apply_building_key_split_c2 규칙(같은 건축년도 조각 / 3건+ 새 조각 /
  3건 미만 가장 가까운 조각 + 확인 필요)이 정한다.
"""
from __future__ import annotations

import datetime as dt
import pickle
import sys

import pandas as pd

import c20_c2_remeasure as c20
import c21_c2_three_way as c21
import c24_register_judge as c24
from _db import OUT, md_table

YEAR_DAYS = 365


def _d(s: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(str(s)[:8], "%Y%m%d").date()
    except ValueError:
        return None


def min_gap_days(a: set[str], b: set[str]) -> int | None:
    da = [x for x in (_d(s) for s in a) if x]
    db = [x for x in (_d(s) for s in b) if x]
    if not da or not db:
        return None
    return min(abs((x - y).days) for x in da for y in db)


def kapt_by_exact_lot():
    """K-apt 단지 코드 ↔ 정확한 지번(법정동10·본번·부번). 필지고유번호 파일(원본 저장소 raw, 읽기만)."""
    from parcel_master.load_kapt_pnu import load_pnu_map

    kdir = next(d for d in (c20.MAIN_RAW / "raw addition").iterdir() if d.is_dir() and "K-apt" in d.name)
    src = sorted(f for f in kdir.iterdir() if f.suffix.lower() == ".xlsx" and "필지" in f.name and not f.name.startswith("~"))[-1]
    pm = load_pnu_map(src)
    out: dict[tuple[str, str, str], set[str]] = {}
    for code, p in zip(pm["danji_code"].astype(str), pm["pnu"].astype(str).str.strip()):
        if len(p) == 19 and p[10] == "1":
            out.setdefault((p[:10], str(int(p[11:15])), str(int(p[15:19]))), set()).add(code)
    return out


def apt_phase_rule(gi_a: dict, gi_b: dict, ka: set[str], kb: set[str]) -> tuple[str, str]:
    """아파트 차수별 단지 규칙. (분할|유지, 근거)."""
    gap = min_gap_days(gi_a["apr"], gi_b["apr"])
    if ka and kb and (ka & kb):
        return "유지", f"K-apt 코드 하나({','.join(sorted(ka & kb))})"
    code = f"K-apt {','.join(sorted(ka)) or '없음'} / {','.join(sorted(kb)) or '없음'}"
    if gap is None:
        return "유지", f"{code} · 승인일 없음"
    if gap >= YEAR_DAYS:
        return "분할", f"{code} · 승인일 차이 {gap}일(≥1년)"
    return "유지", f"{code} · 승인일 차이 {gap}일(<1년)"


def main() -> int:
    st = pickle.load((OUT / "c24_state.pkl").open("rb"))
    info, work = st["info"], st["work"]
    kapt = kapt_by_exact_lot()
    sub, ev, _ = c21.load()
    new = c21.run(sub, ev, c21.T_MAIN)
    gkey = ["key2", "asset_type", "beopjungri_code"]
    groups = {k: g.sort_values("n", ascending=False) for k, g in sub.groupby(gkey)}

    def lot_kapt(bjd, lot, jis):
        s = set()
        for j in jis or {"0"}:
            s |= kapt.get((bjd, lot, j), set())
        return s

    # 대장 판정 쌍: (키·법정동) → 묶음 나누기(union-find, 「다르지 않음」 쌍을 묶음)
    reg_parts: dict[tuple, dict] = {}
    recheck_rows = []
    for w in work:
        r = w["row"]
        k = (r["key2"], r["asset_type"], str(r["beopjungri_code"]))
        if w["label"] == "대조군":
            continue
        gs = w["gs"]
        gi = [info.get((w["b0"], g["lot"])) for g in gs]
        n = len(gs)
        uf = c20.UF(n)
        pair_notes = []
        for i in range(n):
            for j in range(i + 1, n):
                if w["label"] == "불확실" and w["local"].startswith(c24.DIFF):        # 규칙 1·2(로컬)
                    verdict, why = "분할", w["local_why"]
                elif gi[i] is None or gi[j] is None:
                    verdict, why = "유지", "대장 미조회"
                else:
                    c, why = c24.api_pair(gi[i], gi[j])
                    verdict = "분할" if c == c24.DIFF else "유지"
                    # 아파트 차수별 단지: 별개 대장 + 승인일 다름(건물명은 같음)이면 K-apt 규칙
                    if r["asset_type"] == "apartment" and c == c24.DIFF and "건물명" not in why:
                        ka = lot_kapt(w["b0"], gs[i]["lot"], gs[i]["jis"])
                        kb = lot_kapt(w["b0"], gs[j]["lot"], gs[j]["jis"])
                        verdict, why2 = apt_phase_rule(gi[i], gi[j], ka, kb)
                        why = f"{why} → {why2}"
                    if w["label"] == "확실 유지 재점검" and w["local"] == "유지 그대로":
                        verdict, why = "유지", w["local_why"]
                if verdict == "유지":
                    uf.u(i, j)
                pair_notes.append((gs[i]["lot"], gs[j]["lot"], verdict, why))
        if w["label"] == "불확실":
            fin = next((o for o in st["out"] if o["단위"] == "불확실" and o["확인ID"] == r.get("확인ID")), None)
            if fin and fin["최종"] != c24.DIFF:                                          # 같은 단지·불확실 → 분할 안 함
                uf = c20.UF(n)
                for i in range(1, n):
                    uf.u(0, i)
        comps: dict[int, list[int]] = {}
        for i in range(n):
            comps.setdefault(uf.f(i), []).append(i)
        order = sorted(comps.values(), key=lambda c: -sum(gs[i]["n"] for i in c))
        part_of = {gs[i]["lot"]: p for p, c in enumerate(order) for i in c}
        reg_parts[k] = {"label": w["label"], "parts": part_of, "notes": pair_notes}
        if w["label"] == "확실 유지 재점검" and w["local"] == "뒤집힘 후보":
            for a_, b_, v, why in pair_notes:
                ia = [g["lot"] for g in gs].index(a_)
                ib = [g["lot"] for g in gs].index(b_)
                recheck_rows.append((w["name"], f"{w['sigungu']} {w['dong']}", int(r["tx"]),
                                     f"{a_}-{'·'.join(sorted(gs[ia]['jis']))}: {','.join(sorted((gi[ia] or {}).get('apr', set()))) or '-'}",
                                     f"{b_}-{'·'.join(sorted(gs[ib]['jis']))}: {','.join(sorted((gi[ib] or {}).get('apr', set()))) or '-'}",
                                     f"{','.join(sorted(lot_kapt(w['b0'], a_, gs[ia]['jis']))) or '없음'} / "
                                     f"{','.join(sorted(lot_kapt(w['b0'], b_, gs[ib]['jis']))) or '없음'}",
                                     v, why))

    rows, summ = [], []
    for _, r in new.iterrows():
        k = (r["key2"], r["asset_type"], str(r["beopjungri_code"]))
        g = groups[k]
        big = g[g["n"] >= 3]
        if k in reg_parts:
            src = {"불확실": "대장 판정", "확실 유지 재점검": "재점검"}[reg_parts[k]["label"]]
            parts = reg_parts[k]["parts"]
        elif r["cls"] == c21.CERT and r["decision"] == "분리":
            src = "C-2 재측정 확실 분할"
            parts = {str(m): int(c) for m, c in zip(big["main_lot"], r["comp"])}
        else:
            src = "C-2 재측정 확실 유지" if r["cls"] == c21.KEEP else "C-2 재측정 불확실(기타)"
            parts = {}
        split = len(set(parts.values())) > 1
        if split:
            for m, n, y in zip(big["main_lot"], big["n"], big["byear"]):
                if str(m) not in parts:
                    continue
                rows.append({"base_key": r["key2"], "asset_type": r["asset_type"], "beopjungri_code": k[2], "main_lot": str(m),
                             "building_year": int(y) if pd.notna(y) else None, "part": parts[str(m)], "decision": "split",
                             "source": "c2_final_20261115", "note": src, "n_tx": int(n)})
            moved = int(sum(n for m, n in zip(big["main_lot"], big["n"]) if parts.get(str(m), 0) != 0))
        else:
            rows.append({"base_key": r["key2"], "asset_type": r["asset_type"], "beopjungri_code": k[2], "main_lot": "",
                         "building_year": None, "part": None, "decision": "keep", "source": "c2_final_20261115", "note": src,
                         "n_tx": int(r["tx"])})
            moved = 0
        summ.append({"src": src, "type": c21.KO[r["asset_type"]], "split": split, "new_parts": len(set(parts.values())) - 1 if split else 0,
                     "moved": moved, "tx": int(r["tx"])})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "c2_units_final.csv", index=False, encoding="utf-8-sig")
    s = pd.DataFrame(summ)

    print("## 「확실 유지」 재점검 7쌍 — 아파트 차수별 단지 규칙(K-apt·승인일)\n")
    print(md_table(recheck_rows, ["단지", "위치", "거래", "지번 A: 승인일", "지번 B: 승인일", "K-apt A / B", "판정", "근거"]))
    print("\n## 확정 판정 — 출처별 (키·법정동) 수 · 분할 · 늘어나는 키 · 옮겨지는 거래\n")
    tab = s.groupby("src").agg(keys=("tx", "size"), split=("split", "sum"), new=("new_parts", "sum"), moved=("moved", "sum"),
                               tx=("tx", "sum")).reset_index()
    print(md_table([(r.src, f"{r.keys:,}", f"{int(r.split):,}", f"{int(r.new):,}", f"{int(r.moved):,}", f"{int(r.tx):,}")
                    for r in tab.itertuples()] +
                   [("합", f"{len(s):,}", f"{int(s['split'].sum()):,}", f"{int(s['new_parts'].sum()):,}", f"{int(s['moved'].sum()):,}",
                     f"{int(s['tx'].sum()):,}")],
                   ["출처", "(키·법정동)", "분할", "늘어나는 키", "옮겨지는 거래", "거래"]))
    print()
    t2 = s.groupby("type").agg(keys=("tx", "size"), split=("split", "sum"), new=("new_parts", "sum"), moved=("moved", "sum")).reset_index()
    print(md_table([(r.type, f"{r.keys:,}", f"{int(r.split):,}", f"{int(r.new):,}", f"{int(r.moved):,}") for r in t2.itertuples()],
                   ["유형", "(키·법정동)", "분할", "늘어나는 키", "옮겨지는 거래"]))
    ap = [n for k, v in reg_parts.items() if k[1] == "apartment" for n in v["notes"] if "K-apt" in n[3]]
    print(f"\n- 아파트 차수별 단지 규칙을 탄 쌍: {len(ap)} (분할 {sum(1 for n in ap if n[2] == '분할')} · 유지 {sum(1 for n in ap if n[2] == '유지')})")
    print(f"- 파일: logs/collective_p2/c2_units_final.csv · 행 {len(out):,}(split {int((out['decision'] == 'split').sum()):,} · "
          f"keep {int((out['decision'] == 'keep').sum()):,}) — 리허설 DB 에 쓰지 않음")
    print("- 옮겨지는 거래는 3건+ 본번 기준(3건 미만 본번은 적재 규칙이 정하므로 제외)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
