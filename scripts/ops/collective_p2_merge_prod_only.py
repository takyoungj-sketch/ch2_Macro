#!/usr/bin/env python3
"""집합 2단계 — 운영 전용 표(런북 2.5)를 로컬 반영본에 합친다(6.1, promote 직전).

운영에서 `pg_dump --data-only` 로 뜬 4개 표를 로컬 임시 DB(원본, 읽기만)에 복원한 뒤, 대상 DB(키 이전이 끝난 로컬 반영본)에 합친다.

  좌표 캐시 3표 — collective_building_geocodes(building_key) · collective_commercial_map_geocodes(cluster_key)
                  · rent_building_geocodes(building_key)
    1. 키 이전 적용(대상 DB 의 연결표 collective_building_key_map / collective_cluster_key_map / rent_building_key_map):
       - 연결표에 없는 키 → 그대로
       - 1:1(호남 시도명 등) → 새 키로 재키
       - C-01 분할 옛 키(reason 에 split, c2 아닌 것 · 새 키 여럿) → 버림(동이 갈려 좌표가 맞지 않음)
       - C-2 옛 키(reason 에 c2 · 대상 DB 판정 표의 split base_key) → 버림(키 이전이 로컬 좌표도 버린 것과 같게)
    2. 재키 뒤 같은 키가 둘이면 updated_at 이 늦은 쪽 하나(나머지는 「재키 겹침」으로 셈)
    3. 대상에 없는 키는 `INSERT … ON CONFLICT DO NOTHING`
    4. 대상에 이미 있는 키(같은 키):
       - 시각 열(updated_at·geocoded_at)을 뺀 값이 같으면 그대로(identical · same_value_other_time)
       - 값이 다르면(충돌) 규칙(T 결정 2026-11-16, 표 공통):
         한쪽만 status ok → ok 쪽 · 둘 다 ok → geocoded_at 이 더 최근인 쪽(같거나 없으면 로컬) · 둘 다 실패 → 로컬 유지.
         운영 쪽이 이기면 그 행 값으로 UPDATE(값은 고치지 않고 그대로 옮김). 규칙별 건수를 보고서에 적는다.
  QA 기록 qa_audit_run(collective_stats)
    0. 넣기 전에 대상 시퀀스를 max(대상 max(id), 원본 max(id)) + 1 로 올린다(새 id 가 어느 쪽 id 와도 겹치지 않게)
    1. 원본 id 가 대상에 없으면 그 id 로 추가
    2. 같은 id 가 있으면 id 를 뺀 모든 열을 비교 — 같으면 건너뜀
    3. 다르면 새 id(nextval)로 추가, 옛 id → 새 id 를 --remap-out CSV 에 남김
       (대상에 id 만 다르고 내용이 같은 행이 이미 있으면 지난 합치기에서 들어간 것 → 건너뜀, 다시 돌려도 중복 없음)
    4. 끝나면 시퀀스 last_value ≥ max(id) 확인 · 행 수 = 대상 원래 행 + 1번 + 3번

- 드라이런 기본(두 DB 모두 읽기 전용 접속): 단계별 건수만 낸다. --apply 로 DB 마다 한 트랜잭션.
- 쓰기 대상은 리허설 DB(…_p2r) 또는 실제 적용 모드(--real-apply · --confirm-db · --sync-result, 키 이전과 같은 가드)뿐.
  쓰기 직전 current_database() 를 다시 본다. 원본 DB 는 읽기 전용 세션으로만 연다(대상과 같은 이름이면 거부).
- 출력은 건수만(키·주소·좌표 원문 없음). QA id 대응 CSV 는 logs/ 아래(id 숫자만).
- 사전 확인(--manifest · --freeze-at, --real-apply 는 필수): manifest SHA-256·크기 = 덤프 파일, 덤프 시각 ≥ 동결 시각,
  운영 읽기 전용 표시, 원본 임시 DB 행 수 = manifest. 하나라도 어긋나면 아무것도 쓰기 전에 멈춘다.

  python scripts/ops/collective_p2_merge_prod_only.py --src-collective prod_only_tmp --src-rent prod_only_rent_tmp \\
      --dst-collective collective_stats_p2r --dst-rent rent_stats_p2r            # 드라이런
  … --apply                                                                     # 리허설 DB 에 합치기
  … --dst-collective collective_stats --dst-rent rent_stats --real-apply --confirm-db collective_stats \\
      --confirm-db rent_stats --sync-result … --sync-result …                    # 실제 로컬 반영본(런북 6.1)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "pipeline" / "collective"))

from collective.building_keys import C2_TABLE  # noqa: E402
from collective.migrate_p2_keys import (  # noqa: E402
    GuardError,
    add_real_apply_args,
    assert_rehearsal_db,
    check_write_targets,
    engine_for,
)

OUT = REPO / "logs" / "collective_p2"
# (DB 쪽, 표, 키 열, 연결표, C-2 판정 표를 볼지)
GEOCODES = [
    ("collective", "collective_building_geocodes", "building_key", "collective_building_key_map", True),
    ("collective", "collective_commercial_map_geocodes", "cluster_key", "collective_cluster_key_map", False),
    ("rent", "rent_building_geocodes", "building_key", "rent_building_key_map", False),
]
# 좌표 표 → (원장, 키 열): 넣는 행 중 원장에 없는 키(고아)를 센다 — 런북 6.1 게이트는 0
LEDGER = {"collective_building_geocodes": ("collective_transactions", "building_key"),
          "collective_commercial_map_geocodes": ("collective_commercial_transactions", "cluster_key"),
          "rent_building_geocodes": ("rent_transactions", "building_key")}
QA = "qa_audit_run"
REKEY, KEEP, DROP_C01, DROP_C2 = "rekey", "keep", "drop_c01", "drop_c2"


class MergeError(RuntimeError):
    pass


def _exists(c: Connection, t: str) -> bool:
    return bool(c.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{t}"}).scalar())


def _cols(c: Connection, t: str) -> list[tuple[str, str]]:
    return [(r[0], r[1]) for r in c.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=:t "
        "ORDER BY ordinal_position"), {"t": t})]


# --- 좌표 캐시 ----------------------------------------------------------------

def key_rules(map_rows: list[tuple[str, str, str]], c2_bases: set[str] = frozenset()) -> dict[str, tuple[str, str | None]]:
    """연결표 행 (old_key, new_key, reason) → 옛 키마다 (규칙, 새 키). 연결표에 없는 키는 규칙 없음(= 그대로)."""
    by_old: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for o, n, r in map_rows:
        by_old[str(o).strip()].append((str(n).strip(), str(r or "")))
    out: dict[str, tuple[str, str | None]] = {}
    for o, rows in by_old.items():
        reasons = {r for _, r in rows}
        news = {n for n, _ in rows}
        if any("c2" in r for r in reasons) or o in c2_bases:
            out[o] = (DROP_C2, None)
        elif any("split" in r for r in reasons) or len(news) > 1:
            out[o] = (DROP_C01, None)
        else:
            out[o] = (REKEY, next(iter(news)))
    for b in c2_bases:                     # 연결표에 없더라도 판정 표의 split base_key 는 C-2 옛 키
        out.setdefault(b, (DROP_C2, None))
    return out


def _ts(r: dict):
    v = r.get("updated_at")
    return (v is not None, v if v is not None else 0)


TS_COLS = {"updated_at", "geocoded_at"}     # 충돌 판정에서 빼는 시각 열(같은 좌표를 다른 때 받은 것은 충돌 아님)
COORD_COLS = ("longitude", "latitude")


def _differs(a: dict, b: dict, cols) -> bool:
    return any(a.get(c) != b.get(c) for c in cols if c in a and c in b)


CONFLICT_RULES = ("only_prod_ok", "only_local_ok", "both_ok_prod_newer", "both_ok_local_newer_or_same", "both_failed")


def _ok(r: dict) -> bool:
    return str(r.get("status") or "").strip().lower() == "ok"


def resolve_conflict(prod: dict, local: dict) -> tuple[str, str]:
    """같은 키에 값이 다를 때 어느 쪽을 쓸지 → ("prod"|"local", 규칙 이름).
    한쪽만 ok → ok 쪽 · 둘 다 ok → geocoded_at 더 최근(같거나 운영 쪽이 없으면 로컬) · 둘 다 실패(ok 아님) → 로컬."""
    po, lo = _ok(prod), _ok(local)
    if po and not lo:
        return "prod", "only_prod_ok"
    if lo and not po:
        return "local", "only_local_ok"
    if po and lo:
        gp, gl = prod.get("geocoded_at"), local.get("geocoded_at")
        if gp is not None and (gl is None or gp > gl):
            return "prod", "both_ok_prod_newer"
        return "local", "both_ok_local_newer_or_same"
    return "local", "both_failed"


def plan_geocodes(src_rows: list[dict], keycol: str, rules: dict, local_keys) -> tuple[list[dict], list[dict], dict]:
    """원본 행 → (넣을 행, 운영 값으로 바꿀 행, 단계별 건수).
    local_keys 가 {키: 로컬 행} 이면 같은 키에 값이 다른 경우(충돌)를 resolve_conflict 규칙으로 처리한다.
      conflict = 시각 열(updated_at·geocoded_at)을 뺀 값이 하나라도 다름 · conflict_coords = 좌표가 다름 ·
      rule_<규칙> = 규칙별 건수 · update = 운영 쪽이 이겨 바꿀 행 · kept_local = 로컬이 이겨 그대로 둔 충돌."""
    cnt = Counter(src=len(src_rows))
    updates: list[dict] = []
    picked: dict[str, dict] = {}
    for r in src_rows:
        k = str(r[keycol]).strip()
        rule, new = rules.get(k, (KEEP, None))
        if rule in (DROP_C01, DROP_C2):
            cnt[rule] += 1
            continue
        if rule == REKEY:
            cnt["rekeyed"] += 1
            r = {**r, keycol: new}
            k = new
        else:
            cnt["unchanged"] += 1
        old = picked.get(k)
        if old is not None:
            cnt["rekey_overlap"] += 1
            if _ts(r) <= _ts(old):
                continue
        picked[k] = r
    ins = [r for k, r in picked.items() if k not in local_keys]
    cnt["exists_local"] = len(picked) - len(ins)
    if isinstance(local_keys, dict):
        for k, r in picked.items():
            loc = local_keys.get(k)
            if loc is None:
                continue
            vcols = [c for c in r if c != keycol and c not in TS_COLS]
            if _differs(r, loc, vcols):
                cnt["conflict"] += 1
                win, rule = resolve_conflict(r, loc)
                cnt[f"rule_{rule}"] += 1
                if win == "prod":
                    updates.append(r)
            elif any(r.get(c) != loc.get(c) for c in TS_COLS if c in r and c in loc):
                cnt["same_value_other_time"] += 1
            else:
                cnt["identical"] += 1
            if _differs(r, loc, COORD_COLS):
                cnt["conflict_coords"] += 1
    cnt["insert"] = len(ins)
    cnt["update"] = len(updates)
    cnt["kept_local"] = cnt["conflict"] - len(updates)
    keys = ("src", "unchanged", "rekeyed", DROP_C01, DROP_C2, "rekey_overlap", "exists_local", "identical",
            "same_value_other_time", "conflict", "conflict_coords", *(f"rule_{r}" for r in CONFLICT_RULES),
            "update", "kept_local", "insert")
    return ins, updates, {k: int(cnt.get(k, 0)) for k in keys}


def _c2_bases(c: Connection) -> set[str]:
    if not _exists(c, C2_TABLE):
        return set()
    return {str(r[0]).strip() for r in c.execute(text(f"SELECT DISTINCT base_key FROM {C2_TABLE} WHERE decision='split'"))}


def merge_geocode(src: Connection, dst: Connection, table: str, keycol: str, map_table: str, use_c2: bool,
                  *, apply: bool) -> dict:
    if not _exists(src, table):
        return {"table": table, "status": "원본에 표 없음"}
    if not _exists(dst, table):
        raise MergeError(f"대상에 {table} 표가 없음")
    if not _exists(dst, map_table):
        raise MergeError(f"대상에 연결표 {map_table} 가 없음 — 키 이전 뒤에 합친다")
    cols = [c for c, _ in _cols(dst, table)]
    scols = {c for c, _ in _cols(src, table)}
    cols = [c for c in cols if c in scols]
    src_rows = [dict(r._mapping) for r in src.execute(text(f"SELECT {', '.join(cols)} FROM {table}"))]
    maps = [tuple(r) for r in dst.execute(text(f"SELECT old_key, new_key, reason FROM {map_table}"))]
    rules = key_rules(maps, _c2_bases(dst) if use_c2 else set())
    local = {str(r[keycol]).strip(): r for r in (dict(x._mapping) for x in
                                                 dst.execute(text(f"SELECT {', '.join(cols)} FROM {table}")))}
    ins, upd, cnt = plan_geocodes(src_rows, keycol, rules, local)
    led_t, led_c = LEDGER.get(table, (None, None))
    if led_t and _exists(dst, led_t) and ins:
        led = {str(r[0]).strip() for r in dst.execute(text(f"SELECT DISTINCT {led_c} FROM {led_t} WHERE {led_c} IS NOT NULL"))}
        cnt["insert_not_in_ledger"] = sum(1 for r in ins if str(r[keycol]).strip() not in led)
    else:
        cnt["insert_not_in_ledger"] = 0
    out = {"table": table, **cnt, "dst_before": len(local),
           "rule": "키 이전 적용(1:1 재키 · C-01 분할 옛 키·C-2 옛 키 버림) → 로컬에 없는 키 추가 · 같은 키 값 다름은 "
                   "한쪽만 ok→ok 쪽 / 둘 다 ok→geocoded_at 최근(같으면 로컬) / 둘 다 실패→로컬 (운영 쪽이면 값 그대로 UPDATE)"}
    if apply and upd:
        set_cols = [c for c in cols if c != keycol]
        sql = text(f"UPDATE {table} SET {', '.join(f'{c} = :{c}' for c in set_cols)} WHERE {keycol} = :{keycol}")
        done = sum(dst.execute(sql, r).rowcount or 0 for r in upd)
        if done != len(upd):
            raise MergeError(f"{table}: 바꾼 행 {done} ≠ 계획 {len(upd)} — 되돌림")
    if apply and ins:
        sql = text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)}) "
                   f"ON CONFLICT ({keycol}) DO NOTHING")
        done = 0
        for i in range(0, len(ins), 1000):
            done += dst.execute(sql, ins[i:i + 1000]).rowcount or 0
        if done != len(ins):
            raise MergeError(f"{table}: 넣은 행 {done} ≠ 계획 {len(ins)} — 되돌림")
    if apply:
        after = int(dst.execute(text(f"SELECT count(*) FROM {table}")).scalar() or 0)
        if after != len(local) + len(ins):
            raise MergeError(f"{table}: 합친 뒤 행 수 {after} ≠ {len(local)} + {len(ins)} — 되돌림")
        out["dst_after"] = after
    return out


# --- QA 기록 --------------------------------------------------------------------

def _norm(v):
    if isinstance(v, str):
        try:
            return json.loads(v) if v[:1] in "[{" else v
        except ValueError:
            return v
    return v


def merge_qa(src: Connection, dst: Connection, *, apply: bool, remap_out: Path | None) -> dict:
    if not _exists(src, QA):
        return {"table": QA, "status": "원본에 표 없음"}
    n_src = int(src.execute(text(f"SELECT count(*) FROM {QA}")).scalar() or 0)
    if not _exists(dst, QA):
        if n_src:
            raise MergeError(f"대상에 {QA} 표가 없는데 원본에 {n_src}행")
        return {"table": QA, "status": "양쪽 비었음"}
    types = dict(_cols(dst, QA))
    scols = {c for c, _ in _cols(src, QA)}
    cols = [c for c in types if c in scols and c != "id"]
    src_rows = [dict(r._mapping) for r in src.execute(text(f"SELECT id, {', '.join(cols)} FROM {QA} ORDER BY id"))]
    dst_rows = {int(r["id"]): r for r in (dict(x._mapping) for x in
                                          dst.execute(text(f"SELECT id, {', '.join(cols)} FROM {QA}")))}
    src_max = max((int(r["id"]) for r in src_rows), default=0)
    dst_max = max(dst_rows, default=0)
    def sig(r):
        return tuple(json.dumps(_norm(r[c]), sort_keys=True, ensure_ascii=False, default=str) for c in cols)

    dst_sigs = {sig(r) for r in dst_rows.values()}
    same_id_new, same, merged, diff = [], 0, 0, []
    for r in src_rows:
        d = dst_rows.get(int(r["id"]))
        if d is None:
            same_id_new.append(r)
        elif all(_norm(r[c]) == _norm(d[c]) for c in cols):
            same += 1
        elif sig(r) in dst_sigs:          # 지난 합치기에서 새 id 로 이미 들어간 같은 기록(다시 돌려도 중복 없음)
            merged += 1
        else:
            diff.append(r)
    out = {"table": QA, "src": len(src_rows), "dst_before": len(dst_rows), "src_max_id": src_max, "dst_max_id": dst_max,
           "insert_same_id": len(same_id_new), "skip_identical": same, "skip_already_merged": merged,
           "insert_new_id": len(diff)}
    if not apply:
        return out
    seq = dst.execute(text(f"SELECT pg_get_serial_sequence('{QA}', 'id')")).scalar()
    if not seq:
        raise MergeError(f"{QA}.id 시퀀스를 찾을 수 없음")
    # 0) 넣기 전에 시퀀스를 양쪽 max 보다 크게
    dst.execute(text("SELECT setval(CAST(:s AS regclass), :v, false)"), {"s": seq, "v": max(src_max, dst_max) + 1})

    def val(c, v):
        return json.dumps(v, ensure_ascii=False) if types[c] in ("jsonb", "json") and v is not None and not isinstance(v, str) else v

    ph = ", ".join(f"CAST(:{c} AS {types[c]})" if types[c] in ("jsonb", "json") else f":{c}" for c in cols)
    for r in same_id_new:                                   # 1) 같은 id 로
        dst.execute(text(f"INSERT INTO {QA} (id, {', '.join(cols)}) VALUES (:id, {ph})"),
                    {"id": r["id"], **{c: val(c, r[c]) for c in cols}})
    remap = []
    for r in diff:                                          # 3) 새 id 로
        nid = dst.execute(text(f"INSERT INTO {QA} ({', '.join(cols)}) VALUES ({ph}) RETURNING id"),
                          {c: val(c, r[c]) for c in cols}).scalar()
        remap.append((int(r["id"]), int(nid)))
    last, mx = dst.execute(text(f"SELECT (SELECT last_value FROM {seq}), (SELECT coalesce(max(id), 0) FROM {QA})")).one()
    if int(last) < int(mx):                                 # 4) 시퀀스 ≥ max(id)
        raise MergeError(f"{QA} 시퀀스 {last} < max(id) {mx} — 되돌림")
    after = int(dst.execute(text(f"SELECT count(*) FROM {QA}")).scalar() or 0)
    if after != len(dst_rows) + len(same_id_new) + len(diff):
        raise MergeError(f"{QA}: 합친 뒤 행 수 {after} ≠ {len(dst_rows)} + {len(same_id_new)} + {len(diff)} — 되돌림")
    out.update({"dst_after": after, "seq_last_value": int(last), "max_id_after": int(mx), "remapped": len(remap)})
    if remap_out is not None and remap:
        remap_out.parent.mkdir(parents=True, exist_ok=True)
        with remap_out.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["prod_id", "new_id"])
            w.writerows(remap)
        out["remap_csv"] = remap_out.name
    return out


# --- 덤프 사전 확인(동결 뒤 새 덤프인지) ---------------------------------------------

MANIFEST_TS = "%Y%m%d_%H%M%S"
ARCHIVE_SIDE = {"collective_stats": "collective", "rent_stats": "rent"}
# manifest 에 있어야 하는 정확한 집합(Codex 재검수 2): DB 2개 · 표 4개. 누락·중복·모르는 DB/표·행 수 누락은 거절
REQUIRED_ARCHIVES: dict[str, frozenset[str]] = {
    "collective_stats": frozenset({"collective_building_geocodes", "collective_commercial_map_geocodes", "qa_audit_run"}),
    "rent_stats": frozenset({"rent_building_geocodes"}),
}


def validate_manifest_shape(m: dict) -> list[dict]:
    """manifest 구조 검사(파일을 읽기 전). 통과하면 archives 를 DB 이름 순으로 돌려준다. 어긋나면 MergeError."""
    if not isinstance(m, dict):
        raise MergeError("manifest 가 JSON 객체가 아님")
    arcs = m.get("archives")
    if not isinstance(arcs, list) or not arcs:
        raise MergeError("manifest 에 덤프 항목(archives)이 없음")
    seen: dict[str, dict] = {}
    for a in arcs:
        if not isinstance(a, dict):
            raise MergeError("manifest archives 항목이 객체가 아님")
        db = a.get("db")
        if db not in REQUIRED_ARCHIVES:
            raise MergeError(f"manifest 에 알 수 없는 DB: {db!r} (허용 {sorted(REQUIRED_ARCHIVES)})")
        if db in seen:
            raise MergeError(f"manifest 에 같은 DB 가 두 번: {db}")
        seen[db] = a
    missing = sorted(set(REQUIRED_ARCHIVES) - set(seen))
    if missing:
        raise MergeError(f"manifest 에 필요한 DB 가 없음: {missing}")
    for db, a in seen.items():
        rows = a.get("archive_rows")
        if not isinstance(rows, dict):
            raise MergeError(f"{db}: archive_rows(표별 행 수)가 없음")
        want = REQUIRED_ARCHIVES[db]
        if sorted(set(want) - set(rows)):
            raise MergeError(f"{db}: 필요한 표가 없음 {sorted(set(want) - set(rows))}")
        if sorted(set(rows) - set(want)):
            raise MergeError(f"{db}: 알 수 없는 표 {sorted(set(rows) - set(want))}")
        for t, n in rows.items():
            if isinstance(n, bool) or not isinstance(n, int) or n < 0:
                raise MergeError(f"{db}.{t}: 행 수가 없거나 정수가 아님({n!r})")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(a.get("sha256") or "")):
            raise MergeError(f"{db}: sha256 이 없거나 형식이 아님")
        if isinstance(a.get("bytes"), bool) or not isinstance(a.get("bytes"), int) or a["bytes"] < 0:
            raise MergeError(f"{db}: bytes(파일 크기)가 없거나 정수가 아님")
        if not str(a.get("file") or "").strip():
            raise MergeError(f"{db}: file(덤프 파일 이름)이 없음")
    return [seen[db] for db in sorted(seen)]


def parse_kst(s: str):
    """'YYYYMMDD_HHMMSS'(manifest created_kst) 또는 ISO('2026-11-17T03:00' — 시간대 없으면 KST)."""
    from datetime import datetime, timedelta, timezone

    kst = timezone(timedelta(hours=9))
    s = (s or "").strip()
    try:
        dt = datetime.strptime(s, MANIFEST_TS)
    except ValueError:
        try:
            dt = datetime.fromisoformat(s)
        except ValueError as ex:
            raise MergeError(f"시각 형식이 아님: {s!r} (YYYYMMDD_HHMMSS 또는 ISO)") from ex
    return dt.replace(tzinfo=kst) if dt.tzinfo is None else dt


def preflight(manifest: Path, freeze_at: str, src_counts: dict[str, dict[str, int]] | None = None) -> dict:
    """병합 전 확인(하나라도 어긋나면 MergeError — 아무것도 쓰기 전):
    ① manifest 의 각 덤프 파일 SHA-256·크기 = 실제 파일(파일은 manifest 와 같은 폴더에서 찾는다)
    ② manifest created_kst ≥ 동결 시각(--freeze-at) — 동결 전에 뜬(오래된) 덤프면 진행하지 않는다
    ③ production_read_only = true
    ④ src_counts 를 주면 원본 임시 DB 의 표별 행 수 = manifest archive_rows(그 덤프를 복원한 DB 인지)."""
    import hashlib

    manifest = Path(manifest)
    if not manifest.is_file():
        raise MergeError(f"manifest 없음: {manifest.name}")
    try:
        m = json.loads(manifest.read_text(encoding="utf-8"))
    except ValueError as ex:
        raise MergeError("manifest 를 JSON 으로 읽을 수 없음") from ex
    archives = validate_manifest_shape(m)
    if m.get("production_read_only") is not True:
        raise MergeError("manifest 가 운영 읽기 전용 덤프로 표시되지 않음(production_read_only)")
    created, freeze = parse_kst(str(m.get("created_kst", ""))), parse_kst(freeze_at)
    if created < freeze:
        raise MergeError(f"덤프가 동결 시각보다 오래됨(덤프 {created:%Y-%m-%d %H:%M:%S} < 동결 {freeze:%Y-%m-%d %H:%M:%S} KST) — 새 덤프 필요")
    out = {"manifest": manifest.name, "created_kst": f"{created:%Y-%m-%d %H:%M:%S}", "freeze_at": f"{freeze:%Y-%m-%d %H:%M:%S}",
           "archives": []}
    for a in archives:
        f = manifest.parent / Path(str(a.get("file", "")).replace("\\", "/")).name
        if not f.is_file():
            raise MergeError(f"덤프 파일 없음: {f.name}")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        if sha != str(a.get("sha256", "")).lower():
            raise MergeError(f"덤프 SHA-256 이 manifest 와 다름: {f.name}")
        if int(a.get("bytes", -1)) != f.stat().st_size:
            raise MergeError(f"덤프 크기가 manifest 와 다름: {f.name}")
        side = ARCHIVE_SIDE.get(a.get("db"))
        rows = {k: int(v) for k, v in (a.get("archive_rows") or {}).items()}
        if src_counts is not None:
            if side not in src_counts:
                raise MergeError(f"{a.get('db')}: 이 덤프를 복원한 원본 임시 DB 가 실행 인자에 없음(--src-{side})")
            got = src_counts[side]
            bad = {t: (n, got.get(t)) for t, n in rows.items() if got.get(t) != n}
            if bad:
                raise MergeError(f"원본 임시 DB 행 수가 manifest 와 다름({a.get('db')}): " +
                                 ", ".join(f"{t} {g} ≠ {n}" for t, (n, g) in bad.items()))
        out["archives"].append({"db": a.get("db"), "file": f.name, "sha256_ok": True, "rows": rows})
    return out


def source_counts(eng: Engine, side: str) -> dict[str, int]:
    tabs = [t for sd, t, *_ in GEOCODES if sd == side] + ([QA] if side == "collective" else [])
    with eng.connect() as c:
        return {t: int(c.execute(text(f"SELECT count(*) FROM {t}")).scalar() or 0) for t in tabs if _exists(c, t)}


# --- 실행 -----------------------------------------------------------------------

def merge_side(src_eng: Engine, dst_eng: Engine, dst_name: str, side: str, *, apply: bool,
               remap_out: Path | None = None) -> list[dict]:
    """한 DB 쪽(collective·rent): 원본은 읽기 전용 세션, 대상은 한 트랜잭션(apply) 또는 읽기(드라이런)."""
    with src_eng.connect() as s, (dst_eng.begin() if apply else dst_eng.connect()) as d:
        if apply:
            assert_rehearsal_db(d, dst_name)
        res = [merge_geocode(s, d, t, k, m, c2, apply=apply) for sd, t, k, m, c2 in GEOCODES if sd == side]
        if side == "collective":
            res.append(merge_qa(s, d, apply=apply, remap_out=remap_out))
        return res


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src-collective", required=True, help="운영 collective 4표 덤프를 복원한 임시 DB(읽기만)")
    p.add_argument("--src-rent", default="", help="운영 rent_building_geocodes 덤프를 복원한 임시 DB(읽기만)")
    p.add_argument("--dst-collective", required=True)
    p.add_argument("--dst-rent", default="")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--base-url", default="", help="DB 서버 URL(기본 backend/.env)")
    p.add_argument("--remap-out", default=str(OUT / "qa_audit_id_remap.csv"))
    p.add_argument("--report-out", default=str(OUT / "merge_prod_only.json"))
    p.add_argument("--manifest", default="", help="Codex 덤프 manifest(JSON). --real-apply 필수")
    p.add_argument("--freeze-at", default="", help="동결 시각(KST, 'YYYY-MM-DDTHH:MM' 또는 YYYYMMDD_HHMMSS). 덤프가 이보다 오래되면 중단")
    add_real_apply_args(p)
    a = p.parse_args(argv)
    if a.real_apply:
        if not a.manifest or not a.freeze_at:
            raise GuardError("--real-apply 는 --manifest · --freeze-at 이 필요하다(동결 뒤 새 덤프 확인, 런북 6.1)")
        a.apply = True
    if bool(a.manifest) != bool(a.freeze_at):
        raise GuardError("--manifest 와 --freeze-at 은 같이 준다")
    if bool(a.src_rent) != bool(a.dst_rent):
        raise GuardError("--src-rent 와 --dst-rent 는 같이 준다")
    if a.real_apply and not a.dst_rent:
        raise GuardError("--real-apply 는 네 표(집합 3 + 임대 1)를 한 번에 합친다 — --src-rent · --dst-rent 필요")
    for s_, d_ in ((a.src_collective, a.dst_collective), (a.src_rent, a.dst_rent)):
        if s_ and s_ == d_:
            raise GuardError(f"원본과 대상이 같은 DB: {s_}")
    base = a.base_url or None
    dsts = [x for x in (a.dst_collective, a.dst_rent) if x]
    if a.apply:
        check_write_targets(dsts, a, base_url=base)
    report = {"apply": bool(a.apply), "real_apply": bool(a.real_apply), "applied": False, "sides": {}}
    if a.manifest:
        counts = {}
        for side, src in (("collective", a.src_collective), ("rent", a.src_rent)):
            if src:
                se = engine_for(src, read_only=True, base_url=base)
                try:
                    counts[side] = source_counts(se, side)
                finally:
                    se.dispose()
        report["preflight"] = preflight(Path(a.manifest), a.freeze_at, counts)
    for side, src, dst in (("collective", a.src_collective, a.dst_collective), ("rent", a.src_rent, a.dst_rent)):
        if not dst:
            continue
        se = engine_for(src, read_only=True, base_url=base)
        de = engine_for(dst, read_only=not a.apply, base_url=base)
        try:
            report["sides"][side] = {"src": src, "dst": dst,
                                     "tables": merge_side(se, de, dst, side, apply=a.apply,
                                                          remap_out=Path(a.remap_out) if side == "collective" else None)}
        finally:
            se.dispose()
            de.dispose()
    report["applied"] = bool(a.apply)          # 여기까지 오면 모든 쪽 트랜잭션이 커밋됨(드라이런은 False)
    txt = json.dumps(report, ensure_ascii=False, indent=1, default=str)
    Path(a.report_out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report_out).write_text(txt, encoding="utf-8")
    print(txt)
    if not a.apply:
        print("드라이런 — 쓰지 않았다. 쓰려면 --apply (리허설 DB) 또는 --real-apply (실제 로컬 반영본, 런북 6.1).")
    return 0


def cli(argv: list[str] | None = None) -> int:
    """종료 코드: 0 성공 · 2 가드·사전 확인·병합 검사 실패(쓰기 전 거절 또는 되돌림)."""
    try:
        return main(argv)
    except (GuardError, MergeError) as ex:
        print(f"중단: {ex}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
