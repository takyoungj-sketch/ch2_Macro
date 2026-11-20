"""RENT-001 반영본 동기 검사(--sync-mode c2-applied).

기존 prod_sync_check 비교는 그대로 두고, 이 모드만 두 비교를 추가로 요구한다.
  1. 적용 전 백업 대 운영: 차이는 rent_building_geocodes 행 수뿐이고 운영 행 수가 백업 이상이다.
  2. 로컬 rent_stats 대 적용 전 백업: 거래 수·id 최대·id 합·기준월이 같고, 그 밖 차이는 허용 목록뿐이다.
  3. 판정 표는 6,054행 이상이고, 적재 로그 detail.file_sha256 에 승인 해시가 있다.

결과 파일은 판정 뒤에 남기는 기록이다. 통과 파일을 읽어 가드를 대신하지 않는다.
"""
from __future__ import annotations

import json
from pathlib import Path

BACKUP_DB = "rent_stats_pre_c2_20261120"
LOCAL_DB = "rent_stats"
MODE = "c2-applied"
MIN_UNITS = 6054
APPROVED_SHA256 = "2660f8e2d75728caa06c6e7899141d8f7cbfbb7698c2bd89637b53ea22506681"
NEW_TABLES = frozenset({
    "rent_building_key_c2_units",
    "rent_c2_migration_log",
    "rent_transactions_rc2_before",
    "rent_building_geocodes_rc2_before",
})
ROW_DIFF_TABLES = frozenset({
    "rent_building_key_map",
    "rent_building_stats",
    "rent_building_rolling_stats",
    "rent_sale_building_map",
    "rent_building_geocodes",
})
_FIELDS = ("rows", "max_as_of_month", "recent_months")


def _sync():
    import prod_sync_check as sync
    return sync


def _geo_rows(snap: dict) -> int | None:
    rec = (snap.get("tables") or {}).get("rent_building_geocodes")
    if not isinstance(rec, dict) or "rows" not in rec:
        return None
    return int(rec["rows"])


def backup_vs_ops(backup: dict, ops: dict) -> tuple[dict, list[str]]:
    """기존 compare 결과에 좌표 행 수 조건만 더한다. compare 자체는 바꾸지 않는다."""
    why: list[str] = []
    if backup.get("db") != BACKUP_DB:
        why.append(f"백업 스냅샷 DB 가 {BACKUP_DB} 가 아님")
    if ops.get("db") != LOCAL_DB:
        why.append(f"운영 스냅샷 DB 가 {LOCAL_DB} 가 아님")
    cmp = _sync().compare(backup, ops)
    allowed = list(cmp["allowed_diff"])
    detail = {
        "compare_status": cmp["status"],
        "diff": list(cmp["diff"]),
        "allowed_diff": allowed,
        "unverified": list(cmp["unverified"]),
        "geocode_backup": _geo_rows(backup),
        "geocode_ops": _geo_rows(ops),
    }
    if cmp["diff"] or cmp["unverified"] or cmp["status"] != "pass":
        why.append("백업 대 운영에 좌표 행 수 밖의 차이가 있음")
    if len(allowed) > 1 or (allowed and not (allowed[0][0] == "rent_building_geocodes" and allowed[0][1] == "rows")):
        why.append("백업 대 운영의 허용 차이가 좌표 행 수가 아님")
    if detail["geocode_backup"] is None or detail["geocode_ops"] is None:
        why.append("좌표 행 수가 없음")
    elif detail["geocode_ops"] < detail["geocode_backup"]:
        why.append("운영 좌표 행 수가 백업보다 적음")
    return detail, why


def _ledger_ok(left: dict, right: dict) -> list[str]:
    why = []
    for key in ("count", "id_max", "id_sum"):
        if left.get(key) != right.get(key):
            why.append(f"거래 {key} 가 다름")
    return why


def local_vs_backup(local: dict, backup: dict, ledger_local: dict, ledger_backup: dict) -> tuple[dict, list[str]]:
    why: list[str] = []
    if local.get("db") != LOCAL_DB:
        why.append(f"로컬 스냅샷 DB 가 {LOCAL_DB} 가 아님")
    if backup.get("db") != BACKUP_DB:
        why.append(f"백업 스냅샷 DB 가 {BACKUP_DB} 가 아님")
    why.extend(_ledger_ok(ledger_local, ledger_backup))
    left, right = local.get("tables") or {}, backup.get("tables") or {}
    allowed_rows = []
    for name in sorted(set(left) | set(right)):
        a, b = left.get(name), right.get(name)
        if a is None or b is None:
            if a is not None and b is None and name in NEW_TABLES:
                continue
            why.append(f"{name} 표가 허용 목록 밖에서 한쪽에만 있음")
            continue
        if "status" in a or "status" in b or "rows" not in a or "rows" not in b:
            why.append(f"{name} 행 수를 확인하지 못함")
            continue
        for field in _FIELDS:
            if a.get(field) == b.get(field):
                continue
            if field == "rows" and name in ROW_DIFF_TABLES:
                allowed_rows.append((name, int(a["rows"]), int(b["rows"])))
                continue
            why.append(f"{name} {field} 가 허용 목록 밖")
    detail = {
        "ledger_local": {k: ledger_local.get(k) for k in ("count", "id_max", "id_sum")},
        "ledger_backup": {k: ledger_backup.get(k) for k in ("count", "id_max", "id_sum")},
        "allowed_row_diffs": allowed_rows,
    }
    return detail, why


def judge(*, backup: dict, ops: dict, local: dict, ledger_local: dict, ledger_backup: dict,
          units_rows: int | None, hash_present: bool) -> dict:
    """두 비교와 판정 표·승인 해시를 한 결과로 만든다. 기존 모드의 결과 형식은 쓰지 않는다."""
    left, why_left = backup_vs_ops(backup, ops)
    right, why_right = local_vs_backup(local, backup, ledger_local, ledger_backup)
    why = why_left + why_right
    if units_rows is None or int(units_rows) < MIN_UNITS:
        why.append(f"판정 표가 {MIN_UNITS}행 미만")
    if hash_present is not True:
        why.append("적재 로그에 승인 해시가 없음")
    return {
        "kind": "rent_c2_sync",
        "sync_mode": MODE,
        "status": "pass" if not why else "diff",
        "failures": why,
        "units_rows": None if units_rows is None else int(units_rows),
        "approved_sha256_present": bool(hash_present),
        "backup_vs_ops": left,
        "local_vs_backup": right,
    }


def accept_report(report: dict, targets: list[str], confirm: list[str]) -> None:
    """judge 가 만든 통과 결과만 받는다. status 만 바꾼 파일은 거절한다."""
    if targets != [LOCAL_DB]:
        raise ValueError("C-2 반영본 모드는 rent_stats 만 허용한다")
    if sorted(x for x in confirm if x) != [LOCAL_DB]:
        raise ValueError("confirm-db 가 rent_stats 가 아님")
    if not isinstance(report, dict) or report.get("sync_mode") != MODE or report.get("kind") != "rent_c2_sync":
        raise ValueError("C-2 반영본 검사 결과가 아님")
    if report.get("failures"):
        raise ValueError("C-2 반영본 동기 검사가 통과가 아님: " + "; ".join(map(str, report["failures"])))
    if report.get("status") != "pass":
        raise ValueError("C-2 반영본 동기 검사가 통과가 아님")
    ops = report.get("backup_vs_ops") or {}
    if ops.get("diff") or ops.get("unverified"):
        raise ValueError("백업 대 운영 차이가 남아 있음")
    if ops.get("geocode_ops") is None or ops.get("geocode_backup") is None:
        raise ValueError("좌표 행 수가 없음")
    if int(ops["geocode_ops"]) < int(ops["geocode_backup"]):
        raise ValueError("운영 좌표 행 수가 백업보다 적음")
    local = report.get("local_vs_backup") or {}
    if local.get("ledger_local") != local.get("ledger_backup"):
        raise ValueError("거래 식별 값이 다름")
    for key in ("count", "id_max", "id_sum"):
        if (local.get("ledger_local") or {}).get(key) is None:
            raise ValueError("거래 식별 값이 없음")
    if report.get("units_rows") is None or int(report["units_rows"]) < MIN_UNITS:
        raise ValueError("판정 표 행 수가 승인 미만")
    if report.get("approved_sha256_present") is not True:
        raise ValueError("적재 로그에 승인 해시가 없음")


def measure(conn, *, units: bool) -> dict:
    """읽기 전용 연결에서 거래 식별 값과, 로컬이면 판정 표·승인 해시를 센다."""
    from sqlalchemy import text

    row = conn.execute(text(
        "SELECT count(*)::bigint, max(id)::bigint, sum(id)::numeric FROM rent_transactions"
    )).one()
    out = {"count": int(row[0]), "id_max": int(row[1]), "id_sum": int(row[2])}
    if not units:
        return out
    exists = conn.execute(text("SELECT to_regclass('public.rent_building_key_c2_units') IS NOT NULL")).scalar()
    out["units_rows"] = int(conn.execute(text(
        "SELECT count(*)::bigint FROM rent_building_key_c2_units"
    )).scalar()) if exists else None
    log_exists = conn.execute(text("SELECT to_regclass('public.rent_c2_migration_log') IS NOT NULL")).scalar()
    out["hash_present"] = bool(conn.execute(text(
        "SELECT EXISTS (SELECT 1 FROM rent_c2_migration_log "
        "WHERE step = 'load_rent_c2_units' AND detail->>'file_sha256' = :h)"
    ), {"h": APPROVED_SHA256}).scalar()) if log_exists else False
    return out


def load_snap(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "tables" not in data:
        raise ValueError(f"스냅샷 형식이 아님: {Path(path).name}")
    return data


def write_report(path: Path, report: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """스냅샷 3개와 로컬 읽기로 판정만 한다. 데이터베이스에는 쓰지 않는다."""
    import argparse
    import sys

    p = argparse.ArgumentParser(description="RENT-001 반영본 동기 검사")
    p.add_argument("--backup-snapshot", type=Path, required=True)
    p.add_argument("--ops-snapshot", type=Path, required=True)
    p.add_argument("--local-snapshot", type=Path, required=True)
    p.add_argument("--result-out", type=Path, required=True)
    a = p.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    sys.path[:0] = [str(root / "pipeline"), str(root / "pipeline" / "collective")]
    from collective import migrate_p2_keys as mig

    base = mig.server_url_from_env()
    local_eng = mig.engine_for(LOCAL_DB, read_only=True, base_url=base)
    backup_eng = mig.engine_for(BACKUP_DB, read_only=True, base_url=base)
    try:
        with local_eng.connect() as conn:
            measured = measure(conn, units=True)
        with backup_eng.connect() as conn:
            ledger_backup = measure(conn, units=False)
    finally:
        local_eng.dispose()
        backup_eng.dispose()
    report = judge(
        backup=load_snap(a.backup_snapshot), ops=load_snap(a.ops_snapshot), local=load_snap(a.local_snapshot),
        ledger_local=measured, ledger_backup=ledger_backup,
        units_rows=measured.get("units_rows"), hash_present=bool(measured.get("hash_present")),
    )
    write_report(a.result_out, report)
    ops = report["backup_vs_ops"]
    led = report["local_vs_backup"]["ledger_local"]
    print(f"status={report['status']} geocode_backup={ops['geocode_backup']} geocode_ops={ops['geocode_ops']}")
    print(f"ledger={led.get('count')} {led.get('id_max')} {led.get('id_sum')}")
    print(f"units={report['units_rows']} hash={report['approved_sha256_present']}")
    if report["failures"]:
        print("failures=" + "; ".join(report["failures"]))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
