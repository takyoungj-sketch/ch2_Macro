"""Phase C-6 — annual 정리 결과(조건 2) + 표본 단지 10곳 장기 추세(2010~2026) 전후 비교.

- 2019~2020 남은 묵은 행: 유형·연도·시도·출처(장기 ingest / 원장 빌더)·원장 근거 여부
- 2010~2018 행 수 전후(삭제 0 확인)
- 고정 연도(2019~2020) annual 합 = 원장 합(전 지역)·원장 근거 없는 행 0(prune_fixed_annual_orphans_p2.verify, T 결정 2026-11-16)
- C-2 분할 키 2019~2020 범위 교체 검증(c2_annual_replace_p2.verify): 대상 행 통계 = 원장 재계산, 원장 근거 없는 대상 행 0
- 표본 10곳(시드 20261112): 호남 병합 키 3 · 인천 3 · 그 밖 시도 4. 2020 이전 count·median 이 하나라도 바뀌면 실패.
  비교 단위는 (유형·연도). 고정 연도 정리 보존 표에 있는 (키·유형·연도)만 비교에서 빼고, 같은 키의 나머지 연도는 비교한다.
  C-2 대상 키는 2019~2020 범위 교체가 정상이라 표본에서 키째 뺀다.
  호남 표본은 「후」 새 키 기준이고, 「전」은 같은 새 키 행(2019~2020 은 개편 재적재 때 만든 새 이름 행)이다.
"""
from __future__ import annotations

import sys

import pandas as pd
from sqlalchemy import text

from _db import OUT, ROOT, engine, engine_db, md_table

sys.path.insert(0, str(ROOT / "pipeline"))
from collective import c2_annual_replace_p2 as c2a  # noqa: E402
from collective import prune_fixed_annual_orphans_p2 as pfo  # noqa: E402
from collective.mart_replace import stale_annual_report  # noqa: E402

T = "collective_building_annual_stats"


def orphan_cells(c) -> set[tuple[str, str, int]]:
    """고정 연도 정리(prune_fixed_annual_orphans_p2)가 지운 (키·유형·연도) — 보존 표 기준."""
    return {(str(k).strip(), str(a), int(y)) for k, a, y in c.execute(text(
        f"SELECT building_key, asset_type, contract_year FROM {pfo.KEEP}"))}


def compare_sample_key(cb, ca, key: str, orphan: set) -> dict:
    """표본 키 하나의 전후 비교 — (유형·연도) 단위. 정리 보존 표에 있는 (키·유형·연도)만 빼고 나머지는 모두 비교한다."""
    q = text(f"SELECT asset_type, contract_year, count, median FROM {T} WHERE building_key=:k")
    x = {(r[0], int(r[1])): (int(r[2]), float(r[3])) for r in cb.execute(q, {"k": key})}
    y = {(r[0], int(r[1])): (int(r[2]), float(r[3])) for r in ca.execute(q, {"k": key})}
    cells = sorted(set(x) | set(y), key=lambda t: (t[1], t[0]))
    skipped = [c for c in cells if (key, c[0], c[1]) in orphan]
    live = [c for c in cells if (key, c[0], c[1]) not in orphan]
    pre = [c for c in live if c[1] <= 2020]
    changed = [c for c in pre if x.get(c) is None or y.get(c) is None
               or x[c][0] != y[c][0] or abs(x[c][1] - y[c][1]) > 1e-6]
    post = [c for c in live if c[1] > 2020 and x.get(c) != y.get(c)]
    fmt = lambda cs: [f"{a}:{yr}" for a, yr in cs]  # noqa: E731
    years = [c[1] for c in cells]
    return {"span": f"{min(years)}~{max(years)}" if years else "—", "n_pre": len(pre), "changed": fmt(changed),
            "post_changed": fmt(post), "skipped": fmt(skipped), "fail": bool(changed)}


def main():
    b, a = engine("collective"), engine_db("collective_stats_p2r")
    L = ["# C-6 annual 정리·장기 추세", ""]
    with a.connect() as ca, b.connect() as cb:
        cur_batch = ca.execute(text(f"SELECT batch_id FROM {T} ORDER BY computed_at DESC LIMIT 1")).scalar()
        cnt = lambda c, w: int(c.execute(text(f"SELECT count(*) FROM {T} WHERE {w}")).scalar())  # noqa: E731
        L.append(md_table([
            ("2010~2018 행", cnt(cb, "contract_year <= 2018"), cnt(ca, "contract_year <= 2018")),
            ("2019~2020 행", cnt(cb, "contract_year in (2019,2020)"), cnt(ca, "contract_year in (2019,2020)")),
            ("2019~2020 옛 시도명 행", cnt(cb, "contract_year in (2019,2020) and addr1 in ('광주광역시','전라남도')"),
             cnt(ca, "contract_year in (2019,2020) and addr1 in ('광주광역시','전라남도')")),
            ("2021~ 행", cnt(cb, "contract_year >= 2021"), cnt(ca, "contract_year >= 2021")),
            ("2021~ 이번 batch 아닌 행", "—", cnt(ca, f"contract_year >= 2021 and batch_id is distinct from '{cur_batch}'")),
        ], ["구분", "전", "후"]))
        L.append("")
        rep = stale_annual_report(ca, T, "collective_transactions", "building_key", batch_id=cur_batch)
        L.append("## 2019~2020 남은 묵은 행(이번 batch 아님)")
        L.append(md_table(rep, ["유형", "연도", "시도", "출처", "작성일", "원장에 같은 키·연도 있음", "행", "거래"]))
        L.append("")
        # 분할 옛 키에 붙은 묵은 행(이중 집계 후보)
        split_old = ca.execute(text("""SELECT count(*), coalesce(sum(a.count),0) FROM collective_building_annual_stats a
            WHERE a.contract_year IN (2019,2020) AND a.building_key IN (SELECT DISTINCT old_key FROM collective_building_key_map
            WHERE reason LIKE '%split%')""")).one()
        L.append(f"- 그중 분할 옛 키 행: {int(split_old[0]):,}행 / {int(split_old[1]):,}건(새 조각 행과 겹침 → 이중 집계 후보, 삭제 안 함)")
        L.append("")
        # 고정 연도 annual 합 = 원장 합(전 지역) — 원장 근거 없는 행 정리 뒤
        forows = pfo.verify(ca)
        L.append("## 고정 연도(2019~2020) annual 합 = 원장 합(전 지역)")
        L.append(md_table([(n, e, g, "OK" if ok else "FAIL") for n, e, g, ok in forows], ["지표", "기대", "실제", "판정"]))
        bad = ca.execute(text(pfo.FIXED_SUM_SQL)).all()
        if bad:
            L.append(md_table([(r[0], r[1], r[2], int(r[3]), int(r[4])) for r in bad[:20]],
                              ["시도", "연도", "유형", "annual", "원장"]))
        has_keep = ca.execute(text("SELECT to_regclass(:t)"), {"t": pfo.KEEP}).scalar()
        kept = ca.execute(text(f"SELECT count(*), coalesce(sum(count), 0) FROM {pfo.KEEP}")).one() if has_keep else (0, 0)
        L.append(f"\n- 정리로 지운 행(보존 표): {int(kept[0]):,}행 / {int(kept[1]):,}건 · 항목 실패 "
                 f"{sum(1 for r in forows if not r[3])} / {len(forows)}")
        L.append("")
        # C-2 분할 키 2019~2020 범위 교체(Codex 검토)
        c2rows = c2a.verify(ca)
        c2fail = sum(1 for r in c2rows if not r[3])
        L.append("## C-2 분할 키 2019~2020 annual(원장 재계산과 일치)")
        L.append(md_table([(n, e, g, "OK" if ok else "FAIL") for n, e, g, ok in c2rows], ["지표", "기대", "실제", "판정"]))
        L.append(f"\n- C-2 항목 실패 {c2fail} / {len(c2rows)}")
        L.append("")
        c2keys = set(c2a.targets(ca)["building_key"])
        # 고정 연도 정리로 지워진 행은 (키·유형·연도) 단위로만 비교에서 뺀다 — 같은 키의 다른 연도(2010~2018 포함)·
        # 다른 유형은 계속 비교한다(Codex Phase D 5)
        orphan = orphan_cells(ca) if has_keep else set()
        # 표본 10곳(C-2 대상 키는 2019~2020 범위 교체가 정상이라 키째 뺀다)
        pick = {
            "호남 병합": """SELECT DISTINCT m.new_key FROM collective_building_key_map m JOIN collective_building_annual_stats a
                         ON a.building_key=m.new_key AND a.contract_year<=2018 WHERE m.reason='honam_sido'""",
            "인천": """SELECT building_key FROM collective_building_annual_stats WHERE addr1='인천광역시'
                      GROUP BY 1 HAVING min(contract_year)<=2012 AND max(contract_year)>=2025""",
            "그 밖": """SELECT building_key FROM collective_building_annual_stats WHERE addr1 NOT IN ('인천광역시','전남광주통합특별시')
                      AND asset_type='apartment' GROUP BY 1 HAVING min(contract_year)<=2012 AND max(contract_year)>=2025""",
        }
        quota = {"호남 병합": 3, "인천": 3, "그 밖": 4}
        sample = []
        for k, sql in pick.items():
            keys = sorted(r[0] for r in ca.execute(text(sql)) if r[0] not in c2keys)
            s = pd.Series(keys).sample(n=min(quota[k], len(keys)), random_state=20261112).tolist() if keys else []
            sample += [(k, x) for x in s]
        res, fail, n_skip = [], 0, 0
        for grp, k in sample:
            row = compare_sample_key(cb, ca, k, orphan)
            fail += row["fail"]
            n_skip += len(row["skipped"])
            res.append((grp, k[:12], row["span"], row["n_pre"], ",".join(row["changed"]) or "없음",
                        ",".join(row["post_changed"]) or "없음", ",".join(row["skipped"]) or "없음",
                        "FAIL" if row["fail"] else "OK"))
        L.append("## 표본 10곳 장기 추세(2020 이전 값 변하면 실패)")
        L.append(md_table(res, ["묶음", "키(앞 12)", "연도", "2020 이전 (유형·연도) 수", "2020 이전 바뀐 (유형·연도)",
                                "2021~ 바뀐 (유형·연도)", "고정 연도 정리로 뺀 (유형·연도)", "판정"]))
        L.append(f"\n- 표본 실패 {fail} / {len(res)} · 정리 행으로 비교에서 뺀 (유형·연도) {n_skip}개"
                 f"(정리 보존 표 (키·유형·연도) {len(orphan):,}개 기준, 키째 빼지 않음)")
    (OUT / "c6_annual.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
