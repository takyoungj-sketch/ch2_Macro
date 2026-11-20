"""Phase D 4 — 운영 전용 표 병합 리허설 검증(읽기 전용, 건수만 — 키·주소·좌표 원문을 내지 않는다).

  python c29_merge_prod_only_check.py snapshot --tag after1     # 대상 4표 (행 수, 행 해시) → logs/collective_p2/merge_rehearsal/snap_<tag>.json
  python c29_merge_prod_only_check.py check                     # C-2·C-01 키 위치 기록·고아 행 → merge_rehearsal/check.md
  python c29_merge_prod_only_check.py same --a after1 --b after2 # 두 스냅샷이 같은지(멱등)
  운영(런북 6.1): --dst-collective collective_stats --dst-rent rent_stats --src-collective <임시> --src-rent <임시>
     --out-dir logs/collective_p2/merge_ops  check --report <merge_prod_only.json>
  임대 1표: --rent-only --dst-rent rent_stats --src-rent <임시> check --report <merge_prod_only.json>
     집합 인자가 같이 오면 거부한다. 집합 DB 는 열지 않는다.
  check --report(필수) 는 병합 보고서를 엄격 판정한다(Codex 재검수 3): applied=true · collective·rent 두 쪽 · 네 표 모두 ·
  필수 카운터(정수) · 보고서의 원본/대상 DB 이름 = 이 검사의 --src-*/--dst-*. 하나라도 없으면 실패.
  그 위에 게이트(병합 고아 0 · C-2/C-01 옛 키 남은 좌표 0 · 조각 키에 운영 좌표 0). 어긋나면 종료 코드 1.
  python c29_merge_prod_only_check.py idempotent --report <두 번째 실행 보고서> --a <전 tag> --b <뒤 tag>
    → 멱등: insert 0 · update 0 · QA 같은 id 추가·새 id 0 · 네 표 행 수·해시와 QA 시퀀스(last_value·is_called) 같음.

- 대상 = collective_stats_p2r · rent_stats_p2r, 원본 = 운영 덤프를 복원한 prodonly_*_p2r_src. 모두 읽기 전용 세션.
- 「C-2 키가 따라갔는지」: 병합 규칙상 C-2 옛 키(판정 표 split base_key) 좌표는 조각 키로 옮기지 않고 버린다(동이 갈려 좌표가 맞지 않음,
  키 이전 P2 와 같은 규칙). 그래서 확인은 ① 운영 행 중 C-2 옛 키 행 수(버린 수) ② 병합 뒤 C-2 옛 키·C-01 분할 옛 키에 남은 좌표 행 0
  ③ 조각 키에 운영 좌표가 붙지 않았음 ④ 원장에 없는 키의 좌표 행(고아) — 원래 로컬 것 / 병합으로 들어온 것 으로 나눔.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys

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


def _tables(rent_only: bool = False) -> dict:
    return {"rent": list(TABLES["rent"])} if rent_only else TABLES


def snapshot(tag: str, *, rent_only: bool = False) -> dict:
    out = {}
    sides = {"rent": DST["rent"]} if rent_only else DST
    tables = _tables(rent_only)
    for side, db in sides.items():
        with engine_db(db).connect() as c:
            for t in tables[side]:
                n, h = c.execute(text(f"SELECT count(*), md5(coalesce(string_agg(x, '' ORDER BY x), '')) "
                                      f"FROM (SELECT md5(t::text) x FROM {t} t) z")).one()
                out[f"{db}.{t}"] = [int(n), h]
            if side == "collective":
                lv, called = c.execute(text("SELECT last_value, is_called FROM qa_audit_run_id_seq")).one()
                out[f"{db}.qa_audit_run_id_seq"] = [int(lv), f"is_called={bool(called)}"]
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
    if not isinstance(report, dict):
        return {}
    out = {}
    for side, v in (report.get("sides") or {}).items():
        for t in (v or {}).get("tables") or []:
            if isinstance(t, dict) and "table" in t:
                out[(side, t["table"])] = t
    return out


# 병합 보고서 엄격 판정(Codex 재검수 3): 네 표 · 필수 카운터 · applied · 원본/대상 DB 이름
RULE_KEYS = ("rule_only_prod_ok", "rule_only_local_ok", "rule_both_ok_prod_newer", "rule_both_ok_local_newer_or_same",
             "rule_both_failed")
GEO_COUNTERS = ("src", "unchanged", "rekeyed", "drop_c01", "drop_c2", "drop_not_in_ledger", "exists_local", "identical", "same_value_other_time",
                "conflict", "conflict_coords", *RULE_KEYS, "update", "kept_local", "insert", "insert_not_in_ledger",
                "dst_before", "dst_after")
QA_COUNTERS = ("src", "dst_before", "insert_same_id", "skip_identical", "skip_already_merged", "insert_new_id", "dst_after",
               "seq_last_value", "max_id_after")


def validate_report(report, dst: dict, src: dict, tables=None) -> list[str]:
    """보고서가 이 검사 대상의 「적용된」 병합 결과인지. 빠진 것·다른 것을 실패 목록으로(빈 목록 = 통과)."""
    tables = TABLES if tables is None else tables
    if not isinstance(report, dict):
        return ["병합 보고서 없음(--report)"]
    fails = []
    if report.get("applied") is not True:
        fails.append(f"보고서가 적용 결과가 아님(applied={report.get('applied')!r}) — 드라이런·중단 보고서")
    sides = report.get("sides")
    if not isinstance(sides, dict) or not sides:
        return fails + ["보고서에 sides 가 없거나 비었음"]
    for side, side_tables in tables.items():
        s = sides.get(side)
        if not isinstance(s, dict):
            fails.append(f"보고서에 {side} 쪽이 없음")
            continue
        if s.get("dst") != dst[side]:
            fails.append(f"{side}: 보고서 대상 DB {s.get('dst')!r} ≠ 검사 대상 {dst[side]!r}")
        if s.get("src") != src[side]:
            fails.append(f"{side}: 보고서 원본 DB {s.get('src')!r} ≠ 검사 원본 {src[side]!r}")
        got = {t.get("table"): t for t in (s.get("tables") or []) if isinstance(t, dict)}
        for t in side_tables:
            row = got.get(t)
            if row is None:
                fails.append(f"{side}.{t}: 보고서에 표 없음")
                continue
            if "status" in row:
                fails.append(f"{side}.{t}: 병합되지 않음({row['status']})")
                continue
            need = QA_COUNTERS if t == "qa_audit_run" else GEO_COUNTERS
            miss = [k for k in need if isinstance(row.get(k), bool) or not isinstance(row.get(k), int)]
            if miss:
                fails.append(f"{side}.{t}: 필수 카운터 없음 {miss}")
        extra = sorted(set(got) - set(side_tables))
        if extra:
            fails.append(f"{side}: 모르는 표 {extra}")
    extra_sides = sorted(set(sides) - set(tables))
    if extra_sides:
        fails.append(f"보고서에 모르는 쪽 {extra_sides}")
    return fails


def idempotent_fails(report, snap_a: dict, snap_b: dict, dst: dict, src: dict, tables=None) -> list[str]:
    """멱등(Codex 재검수 4): 두 번째 실행 보고서가 유효하고 insert 0 · update 0 · QA 새 id 0(같은 id 추가도 0),
    두 스냅샷(4표 행 수·해시 + QA 시퀀스 last_value·is_called)이 같다."""
    tables = TABLES if tables is None else tables
    fails = validate_report(report, dst, src, tables)
    for (side, t), row in _report_tables(report).items():
        if t == "qa_audit_run":
            for k in ("insert_same_id", "insert_new_id"):
                if row.get(k) != 0:
                    fails.append(f"{side}.{t}: {k}={row.get(k)!r} (0 이어야 함)")
        else:
            for k in ("insert", "update"):
                if row.get(k) != 0:
                    fails.append(f"{side}.{t}: {k}={row.get(k)!r} (0 이어야 함)")
    want = {f"{dst[s]}.{t}" for s, ts in tables.items() for t in ts}
    if any(t == "qa_audit_run" for ts in tables.values() for t in ts):
        want.add(f"{dst['collective']}.qa_audit_run_id_seq")
    for k in sorted(want):
        if k not in snap_a or k not in snap_b:
            fails.append(f"스냅샷에 {k} 없음")
        elif snap_a[k] != snap_b[k]:
            fails.append(f"스냅샷 다름: {k}")
    if any(t == "qa_audit_run" for ts in tables.values() for t in ts) and not any(
            "is_called" in str(v[1]) for k, v in snap_a.items() if k.endswith("_id_seq")):
        fails.append("스냅샷에 시퀀스 is_called 없음(옛 스냅샷 — 다시 뜰 것)")
    return fails


def check(report: dict | None = None, *, rent_only: bool = False) -> tuple[str, list[str]]:
    """(보고서 md, 게이트 실패 목록). 보고서가 없거나 엄격 판정(validate_report)을 못 넘으면 실패."""
    mpo = _mpo()
    rep = _report_tables(report)
    tables = _tables(rent_only)
    fails: list[str] = list(validate_report(report, DST, SRC, tables))
    where = (f"임대만 대상 {DST['rent']} / 원본 {SRC['rent']}" if rent_only
             else f"대상 {DST['collective']} · {DST['rent']} / 원본 {SRC['collective']} · {SRC['rent']}")
    L = ["# Phase D 4 — 운영 전용 표 병합 검증(건수만)", "", f"- {where}", ""]
    geo_rows = [g for g in GEO if g[0] == "rent"] if rent_only else GEO
    for side, table, keycol, map_t, ledger, lkey, use_c2 in geo_rows:
        with engine_db(DST[side]).connect() as d, engine_db(SRC[side]).connect() as s:
            maps = ([tuple(r) for r in d.execute(text(f"SELECT old_key, new_key, reason FROM {map_t}"))]
                    if mpo._exists(d, map_t) else [])          # 되돌린 옛 DB(reverse)에는 연결표가 없다
            if rent_only and side == "rent":
                use_c2 = True
                c2b = mpo._c2_bases(d, "rent_building_key_c2_units")
            else:
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
                rows += [("병합 보고서: 대상 원장에 없는 키라 버린 행(방향 " + str(t.get("direction", "forward")) + ")", "기록",
                          f"{int(t.get('drop_not_in_ledger', 0)):,}"),
                         ("병합 보고서: 넣은 행 / 그중 원장에 없는 키(병합이 만든 고아, 0 이어야 함)", "— / 0",
                          f"{int(t.get('insert', 0)):,} / {merged_orphan:,}"),
                         ("병합 보고서: 같은 키 값 다름 / 그중 좌표 다름", "기록",
                          f"{int(t.get('conflict', 0)):,} / {int(t.get('conflict_coords', 0)):,}"),
                         ("  규칙별: 운영만 ok · 로컬만 ok · 둘 다 ok 운영 최근 · 둘 다 ok 로컬 최근·같음 · 둘 다 실패", "기록",
                          " · ".join(f"{int(t.get('rule_' + r, 0)):,}" for r in
                                     ("only_prod_ok", "only_local_ok", "both_ok_prod_newer",
                                      "both_ok_local_newer_or_same", "both_failed"))),
                         ("  처리: 운영 값으로 바꿈 / 로컬 유지", "기록",
                          f"{int(t.get('update', 0)):,} / {int(t.get('kept_local', 0)):,}"),
                         ("병합 전부터 있던 고아(원장에 없는 키 − 병합 고아)", "기록", f"{len(orphan) - merged_orphan:,}")]
                if merged_orphan:
                    fails.append(f"{table}: 병합이 넣은 고아 {merged_orphan}")
            L += [f"## {DST[side]}.{table}", "", md_table(rows, ["항목", "기대", "실제"]), ""]
    qa = None if rent_only else rep.get(("collective", "qa_audit_run"))
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
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--rent-only" in raw and ("--src-collective" in raw or "--dst-collective" in raw):
        print("중단: 임대 1표 검사에서는 집합 인자를 받지 않는다", file=sys.stderr)
        return 2
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dst-collective", default=DST["collective"])
    p.add_argument("--dst-rent", default=DST["rent"])
    p.add_argument("--src-collective", default=SRC["collective"])
    p.add_argument("--src-rent", default=SRC["rent"])
    p.add_argument("--rent-only", action="store_true", help="임대 rent_building_geocodes 만 검사한다. 집합 DB 는 열지 않는다")
    p.add_argument("--out-dir", default=str(OUT))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot").add_argument("--tag", required=True)
    ck = sub.add_parser("check")
    ck.add_argument("--report", required=True, help="collective_p2_merge_prod_only.py 의 --report-out JSON(적용 결과)")
    s = sub.add_parser("same")
    s.add_argument("--a", required=True)
    s.add_argument("--b", required=True)
    idm = sub.add_parser("idempotent", help="두 번째 병합 실행이 아무것도 바꾸지 않았는지")
    idm.add_argument("--report", required=True, help="두 번째 실행 보고서")
    idm.add_argument("--a", required=True, help="두 번째 실행 전 스냅샷 tag")
    idm.add_argument("--b", required=True, help="두 번째 실행 뒤 스냅샷 tag")
    a = p.parse_args(raw)
    DST.update(collective=a.dst_collective, rent=a.dst_rent)
    SRC.update(collective=a.src_collective, rent=a.src_rent)
    from pathlib import Path

    OUT = Path(a.out_dir)
    if a.cmd == "snapshot":
        print(json.dumps({k: v[0] for k, v in snapshot(a.tag, rent_only=a.rent_only).items()}, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "same":
        return same(a.a, a.b)

    def _load(path):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    report = _load(a.report)
    if a.cmd == "idempotent":
        snaps = [_load(OUT / f"snap_{t}.json") or {} for t in (a.a, a.b)]
        fails = idempotent_fails(report, snaps[0], snaps[1], DST, SRC, _tables(a.rent_only) if a.rent_only else None)
        print("멱등: " + ("통과" if not fails else "실패 — " + "; ".join(fails)))
        return 1 if fails else 0
    md, fails = check(report, rent_only=a.rent_only)
    print(md)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
