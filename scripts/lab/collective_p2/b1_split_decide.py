"""Phase B-1 — 분할 목록 확정(읽기 전용). T 결정(2026-11-12) 반영.

입력: Phase A 산출(logs/collective_p2/a1_units.csv·a1_classified.csv) + 원장 동 단위 코드별 건수(SELECT).
규칙
  (a) 키: 동 단위마다 분할(단, 동 단위끼리 대표 법정동8이 같으면 나눌 수 없어 한 조각).
  (c) 키: 동 단위 대표 지번이 다르면 분할이 기본. 다음은 같은 조각으로 묶는다(유지 사유).
      ① 두 동이 region_code_history로 이어짐(from/to 앞 8자리)  ② 분양권 키 전체  ③ 대표 지번이 같음
      묶은 결과 조각이 1개면 키 유지.
  동 이름 1개(화성 코드 변형)는 Phase A에서 이미 제외(분할 안 함).
조각의 대표 법정동8 = 조각 안 거래가 가장 많은 앞 8자리. 조각 안의 다른 코드(코드 변형)도 그 값으로 붙인다.

출력
  pipeline/collective/data/p2_split_units.csv  (base_key, asset_type, emd8, unit_emd8, part, decision, reason)
      — 해시·코드만(지번 없음). 이전 스크립트와 적재기 분할 규칙이 이 파일을 읽는다.
  logs/collective_p2/b1_decisions.csv            (키별 판정·사유, 지번 포함 — gitignore)
  logs/collective_p2/b1_result.md
"""
from __future__ import annotations

import ast
import importlib.util
from collections import defaultdict

import pandas as pd

from _db import OUT, ROOT, engine, md_table, q

OUT_FROZEN = ROOT / "pipeline" / "collective" / "data" / "p2_split_units.csv"

spec = importlib.util.spec_from_file_location("bca", ROOT / "pipeline" / "build_collective_building_attributes.py")
bca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bca)


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def f(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def u(self, a, b):
        a, b = self.f(a), self.f(b)
        if a != b:
            self.p[max(a, b)] = min(a, b)


def main():
    U = pd.read_csv(OUT / "a1_units.csv", encoding="utf-8-sig", dtype={"bj": str, "lot": str, "road": str})
    R = pd.read_csv(OUT / "a1_classified.csv", encoding="utf-8-sig")
    U["emd8s"] = U["emd8s"].map(ast.literal_eval)
    cls = dict(zip(R["key"], R["cls"]))
    U = U[U["key"].isin(cls)].copy()
    hon = pd.read_csv(OUT / "a2_honam_keymap.csv", encoding="utf-8-sig")
    inv = defaultdict(list)
    for old, new in zip(hon.iloc[:, 0], hon["new_key"]):
        inv[new].append(old)

    with engine().connect() as c:
        hist = q(c, "SELECT left(from_code,8), left(to_code,8), change_type FROM region_code_history")
        # 동 단위 코드별 건수 (원 키 기준 → 표준화 키로 합산)
        keys = list(set(U["key"]) | {o for k in U["key"] for o in inv.get(k, [])})
        cnt = q(c, """SELECT building_key, left(beopjungri_code,8), count(*) FROM collective_transactions
                      WHERE building_key = ANY(:k) AND coalesce(building_name,'') <> '' GROUP BY 1,2""", k=keys)
    hlink = defaultdict(set)
    for a, b, _t in hist:
        if a and b and a != b:
            hlink[a].add(b)
            hlink[b].add(a)
    flat = {o: n for n, os in inv.items() for o in os}
    ecount: dict[tuple[str, str], int] = defaultdict(int)
    for k, e, n in cnt:
        ecount[(flat.get(k, k), e)] += int(n)

    frozen, dec = [], []
    stats = defaultdict(lambda: [0, 0])
    for key, d in U.groupby("key"):
        c0 = cls[key]
        recs = d.to_dict("records")
        asset = recs[0]["asset"]
        n = len(recs)
        uf = UF(n)
        reasons = set()
        if c0 == "c":
            if asset == "presale":
                for i in range(1, n):
                    uf.u(0, i)
                reasons.add("keep_presale")
            for i in range(n):
                for j in range(i + 1, n):
                    li, lj = bca.norm_lot(recs[i]["lot"]), bca.norm_lot(recs[j]["lot"])
                    if li and li == lj:
                        uf.u(i, j)
                        reasons.add("keep_same_lot")
                    if any(b in hlink.get(a, ()) for a in recs[i]["emd8s"] for b in recs[j]["emd8s"]):
                        uf.u(i, j)
                        reasons.add("keep_history_link")
        groups = defaultdict(list)
        for i in range(n):
            groups[uf.f(i)].append(i)
        # 조각 대표 법정동8
        parts = []
        nocode = False
        for g in groups.values():
            em = defaultdict(int)
            for i in g:
                for e in recs[i]["emd8s"]:
                    em[e] += ecount.get((key, e), 0)
            if not em:  # 법정동 코드 없는 동 단위 → 가장 큰 조각에 붙인다(적재 때도 코드 없는 행은 1조각)
                nocode = True
                continue
            rep = max(sorted(em), key=lambda e: em[e])
            parts.append((rep, sorted(em), g))
        if nocode:
            reasons.add("nocode_unit_to_part1")
        # 대표 코드가 같은 조각은 나눌 수 없음 → 합침
        by_rep = defaultdict(list)
        for rep, ems, g in parts:
            by_rep[rep].append((ems, g))
        if len(by_rep) < len(parts):
            reasons.add("same_unit_emd8_merged")
        n_parts = len(by_rep)
        if n_parts <= 1:
            decision = "keep"
            if not reasons:
                reasons.add("single_part")
        else:
            decision = "split"
            reasons.add("a_evidence" if c0 == "a" else "c_lot_diff")
        tx = int(d["n"].sum())
        stats[(c0, decision, "+".join(sorted(reasons)))][0] += 1
        stats[(c0, decision, "+".join(sorted(reasons)))][1] += tx
        ordered = sorted(by_rep.items(), key=lambda kv: -sum(ecount.get((key, e), 0) for ems, _ in kv[1] for e in ems))
        for part_no, (rep, lst) in enumerate(ordered, start=1):
            for ems, _g in lst:
                for e in ems:
                    frozen.append(dict(base_key=key, asset_type=asset, emd8=e, unit_emd8=rep,
                                       part=part_no if decision == "split" else 0, decision=decision,
                                       reason="+".join(sorted(reasons))))
        dec.append(dict(key=key, phase_a=c0, decision=decision, n_parts=n_parts, reasons="+".join(sorted(reasons)),
                        asset=asset, addr1=recs[0]["addr1"], addr2=recs[0]["addr2"], addr3=recs[0]["addr3"],
                        name=recs[0]["name"], tx=tx,
                        units="; ".join(f"{r['leaf_raw']}:{r['lot']}:{r['by_mode']}:n{r['n']}" for r in recs)))

    F = pd.DataFrame(frozen).drop_duplicates(["base_key", "emd8"])
    OUT_FROZEN.parent.mkdir(parents=True, exist_ok=True)
    F.sort_values(["base_key", "part", "emd8"]).to_csv(OUT_FROZEN, index=False, encoding="utf-8")
    D = pd.DataFrame(dec)
    D.to_csv(OUT / "b1_decisions.csv", index=False, encoding="utf-8-sig")

    rows = sorted(((a, b, c, v[0], v[1]) for (a, b, c), v in stats.items()), key=lambda r: (r[0], r[1], -r[3]))
    split = D[D.decision == "split"]
    new_keys = int(F[F.decision == "split"].drop_duplicates(["base_key", "part"]).shape[0])
    L = ["# B-1 분할 목록 확정", "",
         f"- region_code_history: {len(hist)}행, 유형 {sorted({t for *_x, t in hist})} — 분동·합동 기록 없음(①은 이 표 범위에서만 판정)",
         f"- 대상 키 {len(D):,}: 분할 {len(split):,}키 → 새 키 {new_keys:,} · 유지 {int((D.decision=='keep').sum()):,}키",
         f"- 분할 키 거래 {int(split.tx.sum()):,} · 유지 키 거래 {int(D.loc[D.decision=='keep','tx'].sum()):,}", "",
         md_table(rows, ["Phase A", "결정", "사유", "키", "거래"]), "",
         "키별 사유: logs/collective_p2/b1_decisions.csv · 고정 목록: pipeline/collective/data/p2_split_units.csv"]
    # 남양읍↔새솔동 확인
    ns = D[D.units.str.contains("새솔동", na=False) & D.units.str.contains("남양", na=False)]
    L.append(f"- 남양읍↔새솔동 동시 포함 키: {len(ns)} — 결정 {ns.decision.value_counts().to_dict()}")
    (OUT / "b1_result.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
