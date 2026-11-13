"""Phase C-10 — 대표 주소 조인 변경(IS NOT DISTINCT FROM → =) 전후 building_stats 전국 행 단위 비교.

전 = collective_building_stats_p2_oldjoin (옛 조인으로 만든 as_of 2026-10-01 3·5·7년, 재실행 전 보존)
후 = collective_building_stats as_of 2026-10-01 (새 조인으로 다시 만든 것)
비교 열: id·computed_at·batch_id 를 뺀 전부. 창별 (전 − 후) / (후 − 전) 행 수가 둘 다 0이어야 통과.
리허설 DB(collective_stats_p2r) 읽기 전용. 출력: logs/collective_p2/c10_rep_join_compare.md (지번 없음)
"""
from __future__ import annotations

from sqlalchemy import text

from _db import OUT, engine_db, md_table

AS_OF = "2026-10-01"
SKIP = {"id", "computed_at", "batch_id"}


def main():
    eng = engine_db("collective_stats_p2r")
    with eng.connect() as c:
        assert c.execute(text("select current_database()")).scalar() == "collective_stats_p2r"
        cols = [r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'collective_building_stats' "
            "AND table_schema = 'public' ORDER BY ordinal_position")) if r[0] not in SKIP]
        old_cols = {r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'collective_building_stats_p2_oldjoin'"))}
        assert set(cols) <= old_cols, set(cols) - old_cols
        sel = ", ".join(cols)
        rows = []
        for w in (3, 5, 7):
            p = {"a": AS_OF, "w": w}
            new_q = f"SELECT {sel} FROM collective_building_stats WHERE as_of_month = :a AND window_years = :w"
            old_q = f"SELECT {sel} FROM collective_building_stats_p2_oldjoin WHERE as_of_month = :a AND window_years = :w"
            n_old = c.execute(text(f"SELECT count(*) FROM ({old_q}) q"), p).scalar()
            n_new = c.execute(text(f"SELECT count(*) FROM ({new_q}) q"), p).scalar()
            only_old = c.execute(text(f"SELECT count(*) FROM ({old_q} EXCEPT ALL {new_q}) q"), p).scalar()
            only_new = c.execute(text(f"SELECT count(*) FROM ({new_q} EXCEPT ALL {old_q}) q"), p).scalar()
            ok = only_old == 0 and only_new == 0 and n_old == n_new
            rows.append((f"{w}년", n_old, n_new, only_old, only_new, "OK" if ok else "[NG]"))
    L = ["# C-10 대표 주소 조인 변경 전후 building_stats (전국 행 단위)", "",
         f"비교 열 {len(cols)}개(id·computed_at·batch_id 제외), as_of {AS_OF}.", "",
         md_table(rows, ["창", "옛 조인 행", "새 조인 행", "옛에만", "새에만", "판정"])]
    (OUT / "c10_rep_join_compare.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    if any(r[-1] != "OK" for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
