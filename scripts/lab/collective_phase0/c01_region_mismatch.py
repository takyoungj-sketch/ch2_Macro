"""C-01 — beopjungri_code 앞 8자리 공식 읍면동명 vs 행 addr 읍면동 불일치 전수 + 수정 방식 시뮬레이션.

읽기 전용. 출력: logs/collective_phase0/c01_*.md|csv (지번 포함 표본은 로컬만).

판정 leaf = addr4(있으면) 아니면 addr3. 일반구 시(청주 등)는 addr3=구, addr4=동.
공식명 = region_codes(eupmyeondong_code = code[:8]) 이름 집합(활성·비활성 포함).

유형:
 (a) 동+리 모순: leaf 가 '동'/'가'로 끝나는데 addr5(리)가 있고 공식명과 다름
 (b) 읍·면 승격 표기 차이: leaf[:-1]==공식명[:-1], 끝 글자 읍/면 교차 (정상 변형)
 (c) 개편 전후 이름 차이: 공식 활성명과 다르나 같은 code8 비활성명과 일치, 또는 code8이 활성 목록에 없음
 (d) 기타: 같은 시군구의 다른 현행 읍면동명 등
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

import pandas as pd

from _db import OUT, engine, md_table, q

NAMES_ALL: dict = {}

TABLES = {
    # name: (db, sql_from, key_expr, extra_where)
    "collective_transactions": ("collective", "collective_transactions", "building_key", "is_valid", "asset_type"),
    "collective_building_stats": (
        "collective",
        "collective_building_stats",
        "building_key",
        "as_of_month = (select max(as_of_month) from collective_building_stats)",
        "asset_type",
    ),
    "collective_commercial_transactions": ("collective", "collective_commercial_transactions", "cluster_key", "is_valid", "asset_type"),
    "built_transactions": ("built", "built_transactions", "coalesce(addr3,'')||'|'||coalesce(addr4,'')||'|'||coalesce(addr5,'')||'|'||coalesce(lot_number,'')", "is_valid", "asset_type"),
    "rent_transactions": ("rent", "rent_transactions", "building_key", "is_valid", "asset_type"),
}


def load_region_codes():
    with engine("collective").connect() as c:
        rc = pd.DataFrame(
            q(c, "select sido_name, sigungu_code, sigungu_name, eupmyeondong_code, eupmyeondong_name, beopjungri_code, beopjungri_name, coalesce(is_active,true) act from region_codes"),
            columns=["sido", "sgg_code", "sgg", "emd_code", "emd", "bjr_code", "bjr", "act"],
        )
    names_all: dict[str, set] = defaultdict(set)
    names_act: dict[str, set] = defaultdict(set)
    for r in rc.itertuples():
        e = str(r.emd_code or "").strip()
        if not e:
            continue
        nm = str(r.emd or "").strip() or str(r.bjr or "").strip()  # 세종 동 지역은 읍면동명 공란
        names_all[e].add(nm)
        if r.act:
            names_act[e].add(nm)
    # 시군구(5) → 현행 읍면동명
    sgg_act: dict[str, set] = defaultdict(set)
    for e, ns in names_act.items():
        sgg_act[e[:5]].update(ns)
    return rc, names_all, names_act, sgg_act


def _swap_eup_myeon(s: str) -> str | None:
    if s.endswith("읍"):
        return s[:-1] + "면"
    if s.endswith("면"):
        return s[:-1] + "읍"
    return None


def leaf_of(a3, a4):
    a3 = str(a3 or "").strip() if a3 == a3 else ""
    a4 = str(a4 or "").strip() if a4 == a4 else ""
    if a4 and not (a4.endswith("리") and (a3.endswith("읍") or a3.endswith("면"))):
        return a4
    return a3


def classify(leaf, addr5, code, names_all, names_act, sgg_act):
    c8 = (code or "").strip()[:8]
    if not leaf or len(c8) < 8:
        return "skip"
    act = names_act.get(c8, set())
    allv = names_all.get(c8, set())
    if leaf in act:
        return "ok"
    if leaf in allv and not act:
        return "c"  # 폐지 코드, 행은 옛 이름 그대로
    sw = _swap_eup_myeon(leaf)
    if sw and (sw in act or sw in allv):
        return "b"
    if leaf in allv:
        return "c"
    if not act:
        return "c"  # 현행 목록에 없는 code8 (개편 전 코드)
    if (leaf.endswith("동") or leaf.endswith("가")) and addr5 and str(addr5).strip().endswith("리"):
        return "a"
    return "d"


def scan(names_all, names_act, sgg_act):
    rows_out = []
    detail = []
    for tname, (db, frm, key, where, at) in TABLES.items():
        sql = f"""
            select addr1, addr2, addr3, addr4, addr5, btrim(beopjungri_code::text) code, {at} at,
                   count(*) n, count(distinct {key}) k
            from {frm} where {where} and beopjungri_code is not null and btrim(beopjungri_code::text)<>''
            group by 1,2,3,4,5,6,7
        """
        try:
            with engine(db).connect() as c:
                g = pd.DataFrame(q(c, sql), columns=["a1", "a2", "a3", "a4", "a5", "code", "at", "n", "k"])
                # 단지(키) 단위 유일 수 — 불일치 키 집합 계산용
                gk = pd.DataFrame(
                    q(c, f"""select addr3, addr4, addr5, btrim(beopjungri_code::text) code, {at} at, {key} key
                              from {frm} where {where} and beopjungri_code is not null group by 1,2,3,4,5,6"""),
                    columns=["a3", "a4", "a5", "code", "at", "key"],
                )
        except Exception as ex:  # noqa: BLE001
            print(tname, "ERR", ex, file=sys.stderr)
            continue
        g["leaf"] = [leaf_of(a, b) for a, b in zip(g.a3, g.a4)]
        g["cls"] = [classify(l, a5, cd, names_all, names_act, sgg_act) for l, a5, cd in zip(g.leaf, g.a5, g.code)]
        gk["leaf"] = [leaf_of(a, b) for a, b in zip(gk.a3, gk.a4)]
        gk["cls"] = [classify(l, a5, cd, names_all, names_act, sgg_act) for l, a5, cd in zip(gk.leaf, gk.a5, gk.code)]
        tot_n = int(g.n.sum())
        for cls in ["a", "b", "c", "d"]:
            sub = g[g.cls == cls]
            keys = gk[gk.cls == cls]["key"].nunique()
            rows_out.append((tname, cls, int(sub.n.sum()), int(keys), round(100 * sub.n.sum() / max(tot_n, 1), 3)))
        bad = g[g.cls.isin(["a", "c", "d"])]
        by = bad.groupby(["a1", "at", "cls"]).agg(n=("n", "sum")).reset_index()
        for r in by.itertuples():
            detail.append((tname, r.a1, r.at, r.cls, int(r.n)))
        bad.assign(table=tname).to_csv(OUT / f"c01_mismatch_groups_{tname}.csv", index=False, encoding="utf-8-sig")
        print(tname, "done", tot_n, file=sys.stderr)
    return rows_out, detail


# ---------------- 1-2 시뮬레이션 ----------------

def current_code8_for_unit(a1, a2, gu, leaf, rc_idx, mode_c8):
    sgg = f"{a2} {gu}" if gu else (a2 or "")
    for name in [leaf, _swap_eup_myeon(leaf)]:
        if not name:
            continue
        hits = rc_idx.get((sgg.strip(), name))
        if hits and len(hits) == 1:
            return next(iter(hits)), "name"
    return mode_c8, "mode"


def simulate(rc, src: str):
    """src: building_stats(최신 as_of, 5y) | transactions(5y 창)."""
    rc_act = rc[rc.act]
    rc_idx: dict = defaultdict(set)
    for r in rc_act.itertuples():
        rc_idx[(str(r.sgg).strip(), str(r.emd).strip())].add(str(r.emd_code).strip())
    with engine("collective").connect() as c:
        if src == "building_stats":
            # 확장(expand)은 현행 코드처럼 as_of 무관 전체 행에서
            exp = pd.DataFrame(
                q(c, """select addr1,addr2,addr3,addr4, btrim(beopjungri_code::text) code
                        from collective_building_stats where beopjungri_code is not null group by 1,2,3,4,5"""),
                columns=["a1", "a2", "a3", "a4", "code"],
            )
            res = pd.DataFrame(
                q(c, """select addr1,addr2,addr3,addr4, btrim(beopjungri_code::text) code, count(*) k, sum(count) n
                        from collective_building_stats
                        where as_of_month=(select max(as_of_month) from collective_building_stats) and window_years=5
                        group by 1,2,3,4,5"""),
                columns=["a1", "a2", "a3", "a4", "code", "k", "n"],
            )
        else:
            exp = res = None
    if src != "building_stats":
        db, tbl, key = {
            "transactions": ("collective", "collective_transactions", "building_key"),
            "commercial": ("collective", "collective_commercial_transactions", "cluster_key"),
            "built": ("built", "built_transactions", "coalesce(addr4,'')||coalesce(addr5,'')||coalesce(lot_number,'')"),
        }[src]
        with engine(db).connect() as c:
            exp = pd.DataFrame(
                q(c, f"""select addr1,addr2,addr3,addr4, btrim(beopjungri_code::text) code
                        from {tbl} where is_valid and beopjungri_code is not null group by 1,2,3,4,5"""),
                columns=["a1", "a2", "a3", "a4", "code"],
            )
            res = pd.DataFrame(
                q(c, f"""select addr1,addr2,addr3,addr4, btrim(beopjungri_code::text) code, count(distinct {key}) k, count(*) n
                        from {tbl}
                        where is_valid and contract_date >= date '2021-11-01' and contract_date < date '2026-11-01'
                        group by 1,2,3,4,5"""),
                columns=["a1", "a2", "a3", "a4", "code", "k", "n"],
            )
    for df in (exp, res):
        df["leaf"] = [leaf_of(a, b) for a, b in zip(df.a3, df.a4)]
        has4 = df["leaf"] == df["a4"].fillna("").str.strip()
        df["gu"] = df["a3"].where(has4 & (df["leaf"] != ""), None)
        df["code"] = df["code"].fillna("").str.strip()
    exp = exp[(exp.leaf != "") & (exp.code != "")]
    unit_cols = ["a1", "a2", "gu", "leaf"]
    exp["gu"] = exp["gu"].fillna("")
    res["gu"] = res["gu"].fillna("")
    codes_by_unit = exp.groupby(unit_cols)["code"].apply(set).to_dict()
    # 코드별 결과 합 (code 매칭분)
    by_code = res[res.code != ""].groupby("code").agg(k=("k", "sum"), n=("n", "sum")).to_dict("index")
    # code NULL 행 (addr 매칭)
    null_unit = res[res.code == ""].groupby(unit_cols).agg(k=("k", "sum"), n=("n", "sum")).to_dict("index")
    out = []
    fallback = 0
    for unit, codes in codes_by_unit.items():
        a1, a2, gu, leaf = unit
        mode_c8 = Counter(c[:8] for c in codes).most_common(1)[0][0]
        cur8, how = current_code8_for_unit(a1, a2, gu, leaf, rc_idx, mode_c8)
        if how == "mode":
            fallback += 1
        kept = {c for c in codes if c[:8] == cur8}
        okn = {leaf, _swap_eup_myeon(leaf) or leaf}
        kept_b = {c for c in codes if (NAMES_ALL.get(c[:8], set()) & okn) or not NAMES_ALL.get(c[:8])}
        nu = null_unit.get(unit, {"k": 0, "n": 0})
        k0 = sum(by_code.get(c, {}).get("k", 0) for c in codes) + nu["k"]
        n0 = sum(by_code.get(c, {}).get("n", 0) for c in codes) + nu["n"]
        k1 = sum(by_code.get(c, {}).get("k", 0) for c in kept) + nu["k"]
        n1 = sum(by_code.get(c, {}).get("n", 0) for c in kept) + nu["n"]
        k2 = sum(by_code.get(c, {}).get("k", 0) for c in kept_b) + nu["k"]
        n2 = sum(by_code.get(c, {}).get("n", 0) for c in kept_b) + nu["n"]
        out.append(dict(a1=a1, a2=a2, gu=gu, leaf=leaf, codes=len(codes), kept=len(kept), how=how,
                        k0=int(k0), k1=int(k1), n0=int(n0), n1=int(n1), kept_b=len(kept_b), k2=int(k2), n2=int(n2)))
    df = pd.DataFrame(out)
    return df, fallback


def main():
    global NAMES_ALL
    rc, names_all, names_act, sgg_act = load_region_codes()
    NAMES_ALL = names_all
    rows_out, detail = scan(names_all, names_act, sgg_act)
    md = ["## 1-1 불일치 유형별 (행 수 / 키 수 / 행 비율%)", md_table(rows_out, ["표", "유형", "행", "키(단지·cluster)", "비율%"])]
    det = pd.DataFrame(detail, columns=["table", "sido", "asset", "cls", "n"])
    det.to_csv(OUT / "c01_detail_sido_asset.csv", index=False, encoding="utf-8-sig")
    piv = det.pivot_table(index=["table", "sido"], columns="cls", values="n", aggfunc="sum", fill_value=0).reset_index()
    md.append("\n### 시도별 (a/c/d 행 수)\n" + md_table(piv.values.tolist(), list(piv.columns)))
    piv2 = det.pivot_table(index=["table", "asset"], columns="cls", values="n", aggfunc="sum", fill_value=0).reset_index()
    md.append("\n### 유형별 (a/c/d 행 수)\n" + md_table(piv2.values.tolist(), list(piv2.columns)))

    for src in ["building_stats", "transactions", "commercial", "built"]:
        df, fb = simulate(rc, src)
        df.to_csv(OUT / f"c01_sim_{src}.csv", index=False, encoding="utf-8-sig")
        for tag, kc, nc, cc in (("A 앞8자리=현행코드", "k1", "n1", "kept"), ("B 코드 공식명=선택명(옛 이름 포함)", "k2", "n2", "kept_b")):
            dk = df[kc] - df.k0
            dn = df[nc] - df.n0
            mask = (dk != 0) | (dn != 0)
            ch = df.assign(dk=dk, dn=dn)[mask]
            md.append(
                f"## 1-2 시뮬레이션 {tag} ({src}) — 선택 단위 {len(df):,}개 · 이름매칭 실패(mode 대체) {fb:,}개 · "
                f"변화 단위 {len(ch):,}개 · 단지 합계 변화 {int(ch.dk.sum()):,} · 거래 합계 변화 {int(ch.dn.sum()):,}"
            )
            top = ch.assign(adn=ch.dn.abs()).sort_values("adn", ascending=False).head(20)
            md.append(md_table(
                top[["a1", "a2", "gu", "leaf", "codes", cc, "k0", kc, "n0", nc, "dn"]].values.tolist(),
                ["시도", "시군구", "구", "읍면동", "확장코드", "유지코드", "단지(현행)", "단지(수정)", "거래(현행)", "거래(수정)", "거래 증감"],
            ))
            by_sido = ch.groupby("a1").agg(units=("leaf", "count"), dk=("dk", "sum"), dn=("dn", "sum")).reset_index()
            md.append(md_table(by_sido.values.tolist(), ["시도", "변화 읍면동", "단지 증감", "거래 증감"]))
    reps = [("충청북도", "청주시", "흥덕구", "가경동"), ("전남광주통합특별시", "광산구", "", "수완동"),
            ("충청북도", "음성군", "", "대소면"), ("경기도", "부천시", "원미구", "춘의동"), ("경기도", "화성시", "효행구", "봉담읍")]
    rows = []
    for src in ["building_stats", "transactions", "commercial", "built"]:
        d = pd.read_csv(OUT / f"c01_sim_{src}.csv", encoding="utf-8-sig").fillna({"gu": ""})
        for a1, a2, gu, leaf in reps:
            hit = d[(d.a2 == a2) & (d.gu == gu) & (d.leaf.isin([leaf, _swap_eup_myeon(leaf)]))]
            if hit.empty:
                rows.append((src, f"{a2} {gu} {leaf}".replace("  ", " "), "-", "-", "-", "-", "-", "-"))
                continue
            h = hit.sum(numeric_only=True)
            rows.append((src, f"{a2} {gu} {leaf}".replace("  ", " "), int(h.k0), int(h.k1), int(h.k2), int(h.n0), int(h.n1), int(h.n2)))
    md.append("## 1-3 대표 지역 (현행 / A / B)" + chr(10) + chr(10) + md_table(rows, ["원장", "지역", "단지 현행", "단지 A", "단지 B", "거래 현행", "거래 A", "거래 B"]))
    (OUT / "c01_result.md").write_text("\n\n".join(md), encoding="utf-8")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
