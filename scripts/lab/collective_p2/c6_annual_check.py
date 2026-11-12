"""Phase C-6 — annual 정리 결과(조건 2) + 표본 단지 10곳 장기 추세(2010~2026) 전후 비교.

- 2019~2020 남은 묵은 행: 유형·연도·시도·출처(장기 ingest / 원장 빌더)·원장 근거 여부
- 2010~2018 행 수 전후(삭제 0 확인)
- 표본 10곳(시드 20261112): 호남 병합 키 3 · 인천 3 · 그 밖 시도 4. 2020 이전 count·median 이 하나라도 바뀌면 실패.
  호남 표본은 「후」 새 키 기준이고, 「전」은 같은 새 키 행(2019~2020 은 개편 재적재 때 만든 새 이름 행)이다.
"""
from __future__ import annotations

import sys

import pandas as pd
from sqlalchemy import text

from _db import OUT, ROOT, engine, engine_db, md_table

sys.path.insert(0, str(ROOT / "pipeline"))
from collective.mart_replace import stale_annual_report  # noqa: E402

T = "collective_building_annual_stats"


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
        # 표본 10곳
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
            keys = sorted(r[0] for r in ca.execute(text(sql)))
            s = pd.Series(keys).sample(n=min(quota[k], len(keys)), random_state=20261112).tolist() if keys else []
            sample += [(k, x) for x in s]
        q = f"SELECT contract_year, count, median FROM {T} WHERE building_key=:k ORDER BY 1"
        res, fail = [], 0
        for grp, k in sample:
            x = {r[0]: (int(r[1]), float(r[2])) for r in cb.execute(text(q), {"k": k})}
            y = {r[0]: (int(r[1]), float(r[2])) for r in ca.execute(text(q), {"k": k})}
            pre = sorted({yr for yr in set(x) | set(y) if yr <= 2020})
            changed = [yr for yr in pre if x.get(yr) is None or y.get(yr) is None
                       or x[yr][0] != y[yr][0] or abs(x[yr][1] - y[yr][1]) > 1e-6]
            post_changed = [yr for yr in sorted(set(x) | set(y)) if yr > 2020 and x.get(yr) != y.get(yr)]
            fail += bool(changed)
            res.append((grp, k[:12], f"{min(set(x)|set(y))}~{max(set(x)|set(y))}", len(pre),
                        ",".join(map(str, changed)) or "없음", ",".join(map(str, post_changed)) or "없음",
                        "FAIL" if changed else "OK"))
        L.append("## 표본 10곳 장기 추세(2020 이전 값 변하면 실패)")
        L.append(md_table(res, ["묶음", "키(앞 12)", "연도", "2020 이전 연도 수", "2020 이전 바뀐 연도", "2021~ 바뀐 연도", "판정"]))
        L.append(f"\n- 표본 실패 {fail} / {len(res)}")
    (OUT / "c6_annual.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
