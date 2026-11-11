"""집합 1단계 Phase 1 — expand_beopjungri_codes 수정 전(main 사본) vs 수정 후 비교.

전국 모든 읍면동 선택 단위에 대해 두 함수를 같은 입력으로 호출하고, 반환 코드로 거른
단지 수·거래 수를 비교한다. 읽기 전용(접속 옵션 default_transaction_read_only=on).

대상:
  collective_building_stats (최신 as_of_month, window_years=5 — 단지 목록)
  collective_transactions / collective_commercial_transactions / built_transactions (5년 계약일 창)

집계 방식(0단계 c01 과 같음): 코드별 (단지 수, 거래 수) 합 + 코드 NULL 행의 주소 매칭분.
단지 수는 코드 그룹별 고유 키 합이라 한 키가 여러 코드에 걸치면 중복 계산된다(0단계 한계와 동일).

출력: logs/collective_p1/compare_region_scope.md, compare_region_scope_<table>.csv (지번 없음, 로컬만)

실행 (worktree 루트에서):
  D:\\ch2\\ch2_Macro\\backend\\.venv\\Scripts\\python.exe scripts/lab/collective_p1/compare_region_scope.py [--limit N] [--tables a,b]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app import region_scope as new_mod  # noqa: E402
from app.config import settings  # noqa: E402
from app.flat_sido_region import FLAT_SIDO_ADDR2_TOKEN  # noqa: E402

_spec = importlib.util.spec_from_file_location("_region_scope_main", Path(__file__).with_name("_region_scope_main.py"))
old_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(old_mod)  # type: ignore[union-attr]

OUT = ROOT / "logs" / "collective_p1"
OUT.mkdir(parents=True, exist_ok=True)

WIN_FROM, WIN_TO = "2021-11-01", "2026-11-01"

# name: (db, table, key_expr, expand valid_sql, result window where)
TABLES = {
    "collective_building_stats": (
        "collective",
        "collective_building_stats",
        "building_key",
        None,
        "as_of_month = (select max(as_of_month) from collective_building_stats) and window_years = 5",
    ),
    "collective_transactions": (
        "collective",
        "collective_transactions",
        "building_key",
        "t.is_valid = true",
        f"is_valid and contract_date >= date '{WIN_FROM}' and contract_date < date '{WIN_TO}'",
    ),
    "collective_commercial_transactions": (
        "collective",
        "collective_commercial_transactions",
        "cluster_key",
        "t.is_valid = true",
        f"is_valid and contract_date >= date '{WIN_FROM}' and contract_date < date '{WIN_TO}'",
    ),
    "built_transactions": (
        "built",
        "built_transactions",
        "coalesce(addr4,'')||coalesce(addr5,'')||coalesce(lot_number,'')",
        "t.is_valid = true",
        f"is_valid and contract_date >= date '{WIN_FROM}' and contract_date < date '{WIN_TO}'",
    ),
}

N_EXPR = {"collective_building_stats": "sum(count)"}


def engine(db: str):
    url = {"collective": settings.collective_database_url, "built": settings.built_database_url}[db]
    return create_engine(url, connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=600000"})


def leaf_of(a3, a4) -> str:
    a3 = str(a3 or "").strip()
    a4 = str(a4 or "").strip()
    if a4 and not (a4.endswith("리") and (a3.endswith("읍") or a3.endswith("면"))):
        return a4
    return a3


def unit_kwargs(a1, a2, a3, a4):
    """선택 단위 → expand 입력. 일반구 시는 addr3=구 + addr4=동, 그 밖은 addr3=읍면동."""
    a2s = str(a2 or "").strip() or FLAT_SIDO_ADDR2_TOKEN
    leaf = leaf_of(a3, a4)
    a4s = str(a4 or "").strip()
    if a4s and leaf == a4s:
        return dict(addr1=a1, addr2=a2s, addr3=str(a3 or "").strip() or None, addr4_list=[leaf]), leaf
    return dict(addr1=a1, addr2=a2s, addr3=leaf), leaf


def run_table(name: str, limit: int | None) -> pd.DataFrame:
    db, tbl, key, valid_sql, win = TABLES[name]
    nexpr = N_EXPR.get(name, "count(*)")
    eng = engine(db)
    with eng.connect() as c:
        vs = "where is_valid" if valid_sql else ""
        units = c.execute(text(f"select distinct addr1, addr2, addr3, addr4 from {tbl} {vs}")).fetchall()
        res = pd.DataFrame(
            c.execute(
                text(
                    f"select addr1,addr2,addr3,addr4, btrim(coalesce(beopjungri_code::text,'')) code, "
                    f"count(distinct {key}) k, {nexpr} n from {tbl} where {win} group by 1,2,3,4,5"
                )
            ).fetchall(),
            columns=["a1", "a2", "a3", "a4", "code", "k", "n"],
        )
    by_code = res[res.code != ""].groupby("code").agg(k=("k", "sum"), n=("n", "sum")).to_dict("index")
    # 코드 NULL 행: 같은 주소 단위 매칭분(두 버전 공통)
    nul = res[res.code == ""].copy()
    nul["unit"] = [repr(unit_kwargs(a1, a2, a3, a4)[0]) for a1, a2, a3, a4 in zip(nul.a1, nul.a2, nul.a3, nul.a4)]
    null_by_unit = nul.groupby("unit").agg(k=("k", "sum"), n=("n", "sum")).to_dict("index")

    seen: set[str] = set()
    todo = []
    for a1, a2, a3, a4 in units:
        if not a1 or not leaf_of(a3, a4):
            continue
        kw, leaf = unit_kwargs(a1, a2, a3, a4)
        uk = repr(kw)
        if uk in seen:
            continue
        seen.add(uk)
        todo.append((kw, leaf, uk))
    if limit:
        todo = todo[:limit]
    out = []
    t0 = time.time()
    with eng.connect() as c:
        for i, (kw, leaf, uk) in enumerate(todo):
            old = set(old_mod.expand_beopjungri_codes(c, table=tbl, valid_sql=valid_sql, **kw))
            new = set(new_mod.expand_beopjungri_codes(c, table=tbl, valid_sql=valid_sql, **kw))
            nu = null_by_unit.get(uk, {"k": 0, "n": 0})
            k0 = sum(by_code.get(x, {}).get("k", 0) for x in old) + nu["k"]
            n0 = sum(by_code.get(x, {}).get("n", 0) for x in old) + nu["n"]
            k1 = sum(by_code.get(x, {}).get("k", 0) for x in new) + nu["k"]
            n1 = sum(by_code.get(x, {}).get("n", 0) for x in new) + nu["n"]
            out.append(
                dict(
                    a1=kw["addr1"], a2=kw["addr2"], gu=kw.get("addr3") if kw.get("addr4_list") else "", leaf=leaf,
                    codes_old=len(old), codes_new=len(new), extra_new=len(new - old),
                    k0=int(k0), k1=int(k1), n0=int(n0), n1=int(n1),
                )
            )
            if (i + 1) % 500 == 0:
                print(f"  {name} {i + 1}/{len(todo)} {time.time() - t0:.0f}s", file=sys.stderr)
    df = pd.DataFrame(out)
    df.to_csv(OUT / f"compare_region_scope_{name}.csv", index=False, encoding="utf-8-sig")
    return df


def md_table(rows, headers) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join("" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) for v in r) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tables", default=",".join(TABLES))
    args = ap.parse_args()
    md = [f"# Phase 1 비교 — expand_beopjungri_codes main vs 수정 후 ({time.strftime('%Y-%m-%d %H:%M')})"]
    summary = []
    frames = {}
    for name in args.tables.split(","):
        t0 = time.time()
        df = run_table(name, args.limit)
        frames[name] = df
        dk = df.k1 - df.k0
        dn = df.n1 - df.n0
        ch = df[(dk != 0) | (dn != 0)]
        summary.append((name, len(df), len(ch), int(dk.sum()), int(dn.sum()), int((df.extra_new > 0).sum()), f"{time.time() - t0:.0f}s"))
        print(summary[-1], file=sys.stderr)
    md.append(md_table(summary, ["표", "선택 단위", "변화 단위", "단지 증감", "거래 증감", "새 코드 추가 단위(0이어야 함)", "소요"]))
    if "collective_building_stats" in frames:
        df = frames["collective_building_stats"]
        df = df.assign(dk=df.k1 - df.k0, dn=df.n1 - df.n0)
        ch = df[(df.dk != 0) | (df.dn != 0)]
        top = ch.assign(adn=ch.dn.abs()).sort_values("adn", ascending=False).head(20)
        md.append("## building_stats 변화 상위 20")
        md.append(md_table(top[["a1", "a2", "gu", "leaf", "codes_old", "codes_new", "k0", "k1", "n0", "n1"]].values.tolist(),
                           ["시도", "시군구", "구", "읍면동", "코드(전)", "코드(후)", "단지(전)", "단지(후)", "거래(전)", "거래(후)"]))
        by = ch.groupby("a1").agg(units=("leaf", "count"), dk=("dk", "sum"), dn=("dn", "sum")).reset_index()
        md.append(md_table(by.values.tolist(), ["시도", "변화 읍면동", "단지 증감", "거래 증감"]))
    reps = [("청주시", "흥덕구", "가경동"), ("광산구", "", "수완동"), ("음성군", "", "대소읍"), ("부천시", "원미구", "춘의동"),
            ("화성시", "효행구", "봉담읍"), ("청주시", "청원구", "우암동"), ("청주시", "청원구", "내수읍")]
    rows = []
    for name, df in frames.items():
        d = df.fillna({"gu": ""})
        for a2, gu, leaf in reps:
            hit = d[(d.a2 == a2) & (d.gu == gu) & (d.leaf == leaf)]
            if hit.empty:
                rows.append((name, f"{a2} {gu} {leaf}", "-", "-", "-", "-"))
                continue
            h = hit.sum(numeric_only=True)
            rows.append((name, f"{a2} {gu} {leaf}".replace("  ", " "), int(h.k0), int(h.k1), int(h.n0), int(h.n1)))
    md.append("## 대표 지역 (전 → 후)")
    md.append(md_table(rows, ["표", "지역", "단지 전", "단지 후", "거래 전", "거래 후"]))
    (OUT / "compare_region_scope.md").write_text("\n\n".join(md), encoding="utf-8")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
