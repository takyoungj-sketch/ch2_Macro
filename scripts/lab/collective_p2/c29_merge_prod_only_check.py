"""Phase D 4 — 운영 전용 표 병합 리허설 검증(읽기 전용, 건수만 — 키·주소·좌표 원문을 내지 않는다).

  python c29_merge_prod_only_check.py snapshot --tag after1     # 대상 4표 (행 수, 행 해시) → logs/collective_p2/merge_rehearsal/snap_<tag>.json
  python c29_merge_prod_only_check.py check                     # C-2·C-01 키 위치 기록·고아 행 → merge_rehearsal/check.md
  python c29_merge_prod_only_check.py same --a after1 --b after2 # 두 스냅샷이 같은지(멱등)
  운영(런북 6.1): --dst-collective collective_stats --dst-rent rent_stats --src-collective <임시> --src-rent <임시>
     --out-dir logs/collective_p2/merge_ops  check --report <merge_prod_only.json>
  check --report 를 주면 병합 보고서의 표별 충돌 건수·「병합이 넣은 고아(원장에 없는 키)」를 같이 적고, 게이트(병합 고아 0 ·
  C-2/C-01 옛 키 남은 좌표 0 · 조각 키에 운영 좌표 0)를 판정한다(하나라도 어긋나면 종료 코드 1).

- 대상 = collective_stats_p2r · rent_stats_p2r, 원본 = 운영 덤프를 복원한 prodonly_*_p2r_src. 모두 읽기 전용 세션.
- 「C-2 키가 따라갔는지」: 병합 규칙상 C-2 옛 키(판정 표 split base_key) 좌표는 조각 키로 옮기지 않고 버린다(동이 갈려 좌표가 맞지 않음,
  키 이전 P2 와 같은 규칙). 그래서 확인은 ① 운영 행 중 C-2 옛 키 행 수(버린 수) ② 병합 뒤 C-2 옛 키·C-01 분할 옛 키에 남은 좌표 행 0
  ③ 조각 키에 운영 좌표가 붙지 않았음 ④ 원장에 없는 키의 좌표 행(고아) — 원래 로컬 것 / 병합으로 들어온 것 으로 나눔.
"""
from __future__ import annotations

import argparse
import importlib.util
import json

from sqlalchemy import text

from _db import OUT as LOGS, ROOT, engine_db, md_table

OUT = LOGS / "merge_rehearsal"
DST = {"collective": "collective_stats_p2r", "rent": "rent_stats_p2r"}
SRC = {"collective": "prodonly_collective_p2r_src", "rent": "prodonly_rent_p2r_src"}
TABLES = {"collective": ["collective_building_geocodes", "collective_commercial_map_geocodes", "qa_audit_run"],
          "rent": ["rent_building_geocodes"]}
# (쪽, 좌표 표, 키 열, 연결표, 원장, 원장 키 열, C-2 판정 표를 볼지)
GEO = [("collective", "collective_building_geocodes", "building_key", "collective_building_key_map",
        "collective_transactions", "building_key", True),
       ("collective", "collective_commercial_map_geocodes", "cluster_key", "collective_cluster_key_map",
        "collective_commercial_transactions", "cluster_key", False),
       ("rent", "rent_building_geocodes", "building_key", "rent_building_key_map", "rent_transactions", "building_key", False)]


def _mpo():
    spec = importlib.util.spec_from_file_location("mpo", ROOT / "scripts" / "ops" / "collective_p2_merge_prod_only.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def snapshot(tag: str) -> dict:
    out = {}
    for side, db in DST.items():
        with engine_db(db).connect() as c:
            for t in TABLES[side]:
                n, h = c.execute(text(f"SELECT count(*), md5(coalesce(string_agg(x, '' ORDER BY x), '')) "
                                      f"FROM (SELECT md5(t::text) x FROM {t} t) z")).one()
                out[f"{db}.{t}"] = [int(n), h]
            if side == "collective":
                out[f"{db}.qa_audit_run_id_seq"] = [int(c.execute(text("SELECT last_value FROM qa_audit_run_id_seq")).scalar()), ""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"snap_{tag}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def same(a: str, b: str) -> int:
    x = json.loads((OUT / f"snap_{a}.json").read_text(encoding="utf-8"))
    y = json.loads((OUT / f"snap_{b}.json").read_text(encoding="utf-8"))
    rows = [(k, x[k][0], y.get(k, ["—"])[0], "같음" if x[k] == y.get(k) else "다름") for k in sorted(x)]
    print(md_table(rows, ["표", f"행({a})", f"행({b})", "행·해시"]))
    return 0 if all(r[3] == "같음" for r in rows) else 1


def _report_tables(report: dict | None) -> dict:
    if not report:
        return {}
    return {(side, t["table"]): t for side, v in report.get("sides", {}).items() for t in v.get("tables", [])}


def check(report: dict | None = None) -> tuple[str, list[str]]:
    """(보고서 md, 게이트 실패 목록)."""
    mpo = _mpo()
    rep = _report_tables(report)
    fails: list[str] = []
    L = ["# Phase D 4 — 운영 전용 표 병합 검증(건수만)", "",
         f"- 대상 {DST['collective']} · {DST['rent']} / 원본 {SRC['collective']} · {SRC['rent']}", ""]
    for side, table, keycol, map_t, ledger, lkey, use_c2 in GEO:
        with engine_db(DST[side]).connect() as d, engine_db(SRC[side]).connect() as s:
            maps = [tuple(r) for r in d.execute(text(f"SELECT old_key, new_key, reason FROM {map_t}"))]
            c2b = mpo._c2_bases(d) if use_c2 else set()
            rules = mpo.key_rules(maps, c2b)
            c2_old = {k for k, (r, _) in rules.items() if r == mpo.DROP_C2}
            c01_old = {k for k, (r, _) in rules.items() if r == mpo.DROP_C01}
            frags = {n for o, n, r in maps if "c2" in str(r)} - c2b
            src_keys = [str(r[0]).strip() for r in s.execute(text(f"SELECT {keycol} FROM {table}"))]
            dst_keys = {str(r[0]).strip() for r in d.execute(text(f"SELECT {keycol} FROM {table}"))}
            led = {str(r[0]).strip() for r in d.execute(text(f"SELECT DISTINCT {lkey} FROM {ledger} WHERE {lkey} IS NOT NULL"))}
            # 운영 행이 병합 규칙으로 가는 곳
            mapped = {}
            for k in src_keys:
                rule, new = rules.get(k, (mpo.KEEP, None))
                if rule == mpo.REKEY:
                    mapped[k] = new
                elif rule == mpo.KEEP:
                    mapped[k] = k
            prod_targets = set(mapped.values())
            orphan = dst_keys - led
            rows = [
                ("연결표 행 / 옛 키 규칙: 재키·C-01 버림·C-2 버림", f"{len(maps):,}",
                 f"{sum(1 for r, _ in rules.values() if r == mpo.REKEY):,} · {len(c01_old):,} · {len(c2_old):,}"),
                ("운영 행 중 C-2 옛 키(버림 — 조각 키로 옮기지 않음)", "", f"{sum(1 for k in src_keys if k in c2_old):,}"),
                ("운영 행 중 C-01 분할 옛 키(버림)", "", f"{sum(1 for k in src_keys if k in c01_old):,}"),
                ("운영 행 중 1:1 재키", "", f"{sum(1 for k in src_keys if rules.get(k, (None,))[0] == mpo.REKEY):,}"),
                ("병합 뒤 C-2 옛 키에 남은 좌표 행(0 이어야 함)", "0", f"{len(dst_keys & c2_old):,}"),
                ("병합 뒤 C-01 분할 옛 키에 남은 좌표 행(0 이어야 함)", "0", f"{len(dst_keys & c01_old):,}"),
                ("C-2 조각 키 수 / 그중 좌표 행 있음", "", f"{len(frags):,} / {len(dst_keys & frags):,}"),
                ("  그중 운영 좌표가 붙은 조각 키(0 이어야 함)", "0", f"{len(dst_keys & frags & prod_targets):,}"),
                ("원장에 없는 키의 좌표 행(고아) 합", "", f"{len(orphan):,}"),
                ("  병합으로 들어올 수 있었던 키(운영 쪽 대상 키)", "", f"{len(orphan & prod_targets):,}"),
                ("  로컬에만 있던 키", "", f"{len(orphan - prod_targets):,}"),
            ] if use_c2 else [
                ("연결표 행 / 옛 키 규칙: 재키·C-01 버림·C-2 버림", f"{len(maps):,}",
                 f"{sum(1 for r, _ in rules.values() if r == mpo.REKEY):,} · {len(c01_old):,} · {len(c2_old):,}"),
                ("운영 행 중 C-01 분할 옛 키(버림)", "", f"{sum(1 for k in src_keys if k in c01_old):,}"),
                ("운영 행 중 1:1 재키", "", f"{sum(1 for k in src_keys if rules.get(k, (None,))[0] == mpo.REKEY):,}"),
                ("병합 뒤 C-01 분할 옛 키에 남은 좌표 행(0 이어야 함)", "0", f"{len(dst_keys & c01_old):,}"),
                ("원장에 없는 키의 좌표 행(고아) 합", "", f"{len(orphan):,}"),
                ("  병합으로 들어올 수 있었던 키(운영 쪽 대상 키)", "", f"{len(orphan & prod_targets):,}"),
                ("  로컬에만 있던 키", "", f"{len(orphan - prod_targets):,}"),
            ]
            if len(dst_keys & c2_old):
                fails.append(f"{table}: C-2 옛 키에 좌표 {len(dst_keys & c2_old)}")
            if len(dst_keys & c01_old):
                fails.append(f"{table}: C-01 분할 옛 키에 좌표 {len(dst_keys & c01_old)}")
            if use_c2 and len(dst_keys & frags & prod_targets):
                fails.append(f"{table}: 조각 키에 운영 좌표 {len(dst_keys & frags & prod_targets)}")
            t = rep.get((side, table))
            if t is not None:
                merged_orphan = int(t.get("insert_not_in_ledger", 0))
                rows += [("병합 보고서: 넣은 행 / 그중 원장에 없는 키(병합이 만든 고아, 0 이어야 함)", "— / 0",
                          f"{int(t.get('insert', 0)):,} / {merged_orphan:,}"),
                         ("병합 보고서: 같은 키 값 다름(로컬 유지) / 그중 좌표 다름", "기록",
                          f"{int(t.get('conflict_kept_local', 0)):,} / {int(t.get('conflict_coords', 0)):,}"),
                         ("병합 전부터 있던 고아(원장에 없는 키 − 병합 고아)", "기록", f"{len(orphan) - merged_orphan:,}")]
                if merged_orphan:
                    fails.append(f"{table}: 병합이 넣은 고아 {merged_orphan}")
            L += [f"## {DST[side]}.{table}", "", md_table(rows, ["항목", "기대", "실제"]), ""]
    if report is not None:
        qa = rep.get(("collective", "qa_audit_run"))
        if qa:
            L += ["## qa_audit_run", "", md_table([(k, qa.get(k)) for k in ("src", "dst_before", "insert_same_id",
                  "skip_identical", "skip_already_merged", "insert_new_id", "dst_after")], ["항목", "값"]), ""]
        L.append(f"- 게이트: {'통과' if not fails else '실패 — ' + '; '.join(fails)}")
    md = "\n".join(L)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "check.md").write_text(md, encoding="utf-8")
    return md, fails


def main(argv=None) -> int:
    global OUT
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dst-collective", default=DST["collective"])
    p.add_argument("--dst-rent", default=DST["rent"])
    p.add_argument("--src-collective", default=SRC["collective"])
    p.add_argument("--src-rent", default=SRC["rent"])
    p.add_argument("--out-dir", default=str(OUT))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot").add_argument("--tag", required=True)
    ck = sub.add_parser("check")
    ck.add_argument("--report", default="", help="collective_p2_merge_prod_only.py 의 --report-out JSON")
    s = sub.add_parser("same")
    s.add_argument("--a", required=True)
    s.add_argument("--b", required=True)
    a = p.parse_args(argv)
    DST.update(collective=a.dst_collective, rent=a.dst_rent)
    SRC.update(collective=a.src_collective, rent=a.src_rent)
    from pathlib import Path

    OUT = Path(a.out_dir)
    if a.cmd == "snapshot":
        print(json.dumps({k: v[0] for k, v in snapshot(a.tag).items()}, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "same":
        return same(a.a, a.b)
    report = json.loads(Path(a.report).read_text(encoding="utf-8")) if a.report else None
    md, fails = check(report)
    print(md)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
