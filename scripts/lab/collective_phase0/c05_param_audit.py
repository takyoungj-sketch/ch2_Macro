"""C-05 6-1 — 프론트가 보내는 파라미터 vs FastAPI 가 받는 파라미터 대조 (정적).

입력: logs/collective_phase0/c05_front.json (c05_frontend_params.cjs 결과)
백엔드: app.main 의 라우트를 직접 열어 query/body 필드 이름을 얻는다(서버 기동 없음, DB 조회 없음).
출력: logs/collective_phase0/c05_result.md, c05_table.csv
"""
from __future__ import annotations

import json
import re

import pandas as pd

from _db import OUT, md_table

from app.main import app  # noqa: E402

# 필터 의미가 있는 파라미터(무시되면 '필터 누락'), 그 외는 '단순 잉여'
FILTER_HINT = re.compile(
    r"^(addr\d|addr\d_list|ri_list|region_|contract_|year|cy_|period|window|asset_type|area|floor|age|building_year|deal|direct|"
    r"exclude|include|min_|max_|price|zone|use|road|dong|scope|as_of|bucket|types?)", re.I)


def backend_routes():
    out = []
    for r in app.routes:
        dep = getattr(r, "dependant", None)
        if dep is None:
            continue
        q = {p.alias or p.name for p in dep.query_params}
        body = set()
        for bp in dep.body_params:
            ann = getattr(bp.field_info, "annotation", None) or getattr(bp, "type_", None)
            fields = getattr(ann, "model_fields", None)
            if fields:
                for k, f in fields.items():
                    body.add(f.alias or k)
            else:
                body.add(bp.alias or bp.name)
        # 하위 의존성의 query
        stack = list(dep.dependencies)
        while stack:
            d = stack.pop()
            q |= {p.alias or p.name for p in d.query_params}
            stack.extend(d.dependencies)
        rx = "^" + re.sub(r"\{[^}]+\}", "[^/]+", r.path) + "$"
        for m in r.methods or []:
            out.append(dict(method=m.lower(), path=r.path, rx=rx, query=q, body=body))
    return out


def repro() -> str:
    """6-2 — 대농로(청주) 집합상가 cluster: 5년 창 n vs 날짜 필터 없는 번지별 합계 (SQL 재현)."""
    from _db import engine, q
    with engine("collective").connect() as c:
        keys = q(c, """select cluster_key, display_label, n_total from commercial_clusters
                       where addr2 like '청주%' and road_name like '대농로%' and asset_type='collective_shop' order by n_total desc limit 3""")
        out = []
        for k, lab, ntot in keys:
            r = q(c, """select count(*) filter (where contract_date >= '2021-11-01' and contract_date < '2026-11-01'),
                               count(*) filter (where contract_year between 2021 and 2026),
                               count(*) from collective_commercial_transactions where is_valid and cluster_key=:k""", k=k)[0]
            out.append((lab, ntot, r[0], r[1], r[2]))
    return "### 6-2 재현 — 대농로 cluster" + chr(10) * 2 + md_table(out, ["cluster", "n_total", "5년 창(계약일 기준, 화면 n)", "연도 필터만(2021~2026, addresses가 실제 쓰는 조건)", "전체"])


def main():
    front = json.loads((OUT / "c05_front.json").read_text(encoding="utf-8"))
    routes = backend_routes()
    rows = []
    for f in front:
        base = f["base"]
        if base.startswith("?"):
            base = {"frontend-collective": "/api/collective", "frontend-rent": "/api/rent"}.get(f["app"], "/api")
        if "getAll" in f["props"] and "append" in f["props"]:
            f["props"] = ["(URLSearchParams — 이름 정적 추출 불가)"]
        full = (base.rstrip("/") + "/" + f["path"].lstrip("/")).split("?")[0].replace("{x}", "X")
        hit = [r for r in routes if r["method"] == f["method"] and re.match(r["rx"], full)]
        # 정적 경로 우선
        hit.sort(key=lambda r: r["path"].count("{"))
        if not hit:
            rows.append(dict(app=f["app"], fn=f["fn"], file=f["file"], method=f["method"], path=full, kind=f["kind"], sent=",".join(f["props"]),
                             accepted="(라우트 없음)", ignored="", impact="라우트 없음/조건부 등록"))
            continue
        r = hit[0]
        acc = r["query"] if f["kind"] == "query" else r["body"]
        ign = sorted(p for p in f["props"] if p not in acc and not p.startswith("(URLSearchParams"))
        impact = ""
        if ign:
            impact = "필터 누락 의심" if any(FILTER_HINT.match(p) for p in ign) else "단순 잉여"
        rows.append(dict(app=f["app"], fn=f["fn"], file=f["file"], method=f["method"], path=r["path"], kind=f["kind"], sent=",".join(f["props"]),
                         accepted=",".join(sorted(acc)), ignored=",".join(ign), impact=impact))
    df = pd.DataFrame(rows).drop_duplicates(["app", "fn", "method", "path", "kind", "sent"])
    df.to_csv(OUT / "c05_table.csv", index=False, encoding="utf-8-sig")
    md = ["## C-05 6-1 정적 대조", f"프론트 호출 {len(df)}건 · 무시 파라미터 있는 호출 {int((df.ignored != '').sum())}건 "
          f"(필터 누락 의심 {int((df.impact == '필터 누락 의심').sum())} · 단순 잉여 {int((df.impact == '단순 잉여').sum())}) · 라우트 미일치 {int((df.accepted == '(라우트 없음)').sum())}"]
    bad = df[df.ignored != ""].sort_values(["impact", "app", "path"])
    md.append(md_table(bad[["path", "app", "fn", "kind", "ignored", "impact"]].values.tolist(),
                       ["API 경로", "앱", "호출 함수", "종류", "무시되는 파라미터", "영향"]))
    nr = df[df.accepted == "(라우트 없음)"]
    if len(nr):
        md.append("### 라우트 미일치(현재 설정에서 등록 안 됨 또는 경로 조립 차이)")
        md.append(md_table(nr[["path", "app", "fn", "method"]].values.tolist(), ["경로", "앱", "함수", "메서드"]))
    md.append(repro())
    (OUT / "c05_result.md").write_text("\n\n".join(md), encoding="utf-8")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
