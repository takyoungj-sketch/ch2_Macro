#!/usr/bin/env python3
"""집합 2단계 — 단지 키 이전(호남 행정명 표준화 + 다른 단지 이름 키 분할). D-084 · Phase A 결정.

기본은 드라이런(읽기 전용 접속, 건수만 출력). 쓰기는 --apply, 되돌리기는 --rollback.
쓰기 접속은 매번 current_database()가 지정한 리허설 DB 이름(…_p2r)과 같은지 확인한 뒤에만 진행한다.

하는 일 (--apply)
  1. 원장 addr1 옛 시도명 → 개편 후 이름: collective_transactions · collective_commercial_transactions · built_transactions
  2. building_key 재계산: 호남 표준화 키 → 분할 목록(pipeline/collective/data/p2_split_units.csv) 키는 동 단위 새 키
     임대 원장(rent_transactions)도 같은 분할(Phase A 결정 3)
  3. 비주거 cluster_key 재계산·commercial_clusters 병합(거래 cluster_id 이동)
  4. 연결표: collective_building_key_map · collective_cluster_key_map · rent_building_key_map (old_key, new_key, reason, split_part)
  5. 보존: 원장은 *_p2_before(id, 바뀌기 전 값), 부속 표는 행 전체 사본(*_p2_before) — 원장 행 삭제 0
  6. 부속 표: 단지 속성·공시지가·지오코드·실험 표의 영향 키 행은 보존 후 재키(1:1) 또는 제거(재생성 대상)
     rent_sale_building_map 은 전체 사본만 남긴다(Phase C에서 빌더로 재생성)
mart(building_stats·rolling·annual·presale·market·cluster)는 건드리지 않는다 → 이전 뒤 빌더로 재생성.

멱등: 두 번 돌려도 같은 상태(이미 바뀐 행은 다시 선택되지 않고, 보존·연결표는 ON CONFLICT DO NOTHING).

사용
  python pipeline/collective/migrate_p2_keys.py --collective-db collective_stats_p2r --built-db built_stats_p2r --rent-db rent_stats_p2r            # 드라이런
  ... --apply      # 쓰기(리허설 DB만)
  ... --verify     # 이전 후 검증(읽기)
  ... --rollback   # 보존 표·연결표로 원상태(리허설 DB만)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "pipeline" / "collective"))

from admin_names import LEGACY_SIDO_TO_CURRENT  # noqa: E402
from collective.building_keys import (  # noqa: E402
    SPLIT_UNITS_PATH,
    building_key_raw_series,
    load_split_units,
    resolve_split_unit,
    split_key_from_raw,
)
from collective_commercial.cluster_keys import make_road_cluster_key  # noqa: E402

log = logging.getLogger("migrate_p2_keys")

REHEARSAL_RE = re.compile(r"^[a-z0-9_]+_p2r(_[a-z0-9]+)?$")
PROTECTED = {"collective_stats", "built_stats", "rent_stats", "land_stats", "macro_ts", "platform"}
LEGACY = sorted(LEGACY_SIDO_TO_CURRENT)
CHUNK = 5000


class GuardError(RuntimeError):
    pass


# 실제 적용 모드(--real-apply): 로컬 실제 DB 에 쓰는 유일한 길. 조건 셋을 모두 통과한 이름만 이 집합에 들어간다.
REAL_TARGETS = {"collective_stats", "built_stats", "rent_stats"}
SYNC_RESULT_KIND = "prod_sync_check"
SYNC_RESULT_MAX_AGE_H = 48
_REAL_ALLOWED: set[str] = set()


def _ops_guards():
    """공통 가드 모듈(scripts/ops/collective_p2_verify/ops_guards.py — 운영 확인 스크립트와 같은 파일)."""
    import sys as _sys

    d = str(REPO / "scripts" / "ops" / "collective_p2_verify")
    if d not in _sys.path:
        _sys.path.insert(0, d)
    import ops_guards

    return ops_guards


def enable_real_apply(targets: list[str], confirm: list[str], sync_results: list[Path], *,
                      max_age_h: float = SYNC_RESULT_MAX_AGE_H, now=None) -> set[str]:
    """실제 적용 허가. ① 대상이 실제 DB 이름(REAL_TARGETS)일 것 ② --confirm-db 로 다시 입력한 이름 목록이 대상과 같을 것
    ③ 대상 DB 마다 시작 전 동기화 확인 결과 파일이 ops_guards.validate_result 로 「통과」일 것
       (필수 필드·형식·측정 시각(미래 금지, max_age_h 이내)·대상 목록 일치·실패 기록 없음·diff·unverified 0).
    통과하면 그 이름만 assert_rehearsal_db 에서 허용한다(리허설 가드는 그대로). 로컬 호스트 확인은 check_write_targets."""
    og = _ops_guards()
    targets = [t for t in targets if t]
    if not targets:
        raise GuardError("실제 적용 대상 DB 가 없음")
    bad = [t for t in targets if t not in REAL_TARGETS]
    if bad:
        raise GuardError(f"실제 적용 대상이 아닌 DB 이름: {bad} (허용: {sorted(REAL_TARGETS)})")
    if sorted(c for c in confirm if c) != sorted(targets):
        raise GuardError("--confirm-db 로 다시 입력한 DB 이름이 대상과 다름")
    passed: set[str] = set()
    for p in sync_results:
        p = Path(p)
        if not p.is_file():
            raise GuardError(f"동기화 확인 결과 파일 없음: {p}")
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as ex:
            raise GuardError(f"동기화 확인 결과 파일을 읽을 수 없음: {p}") from ex
        if not isinstance(d, dict) or d.get("kind") != SYNC_RESULT_KIND:
            raise GuardError(f"동기화 확인 결과 파일이 아님: {p}")
        db = d.get("left_db")
        if db not in targets:
            raise GuardError(f"동기화 확인 결과의 DB({db})가 실제 적용 대상이 아님: {p}")
        st, why = og.validate_result(d, [db], kind=SYNC_RESULT_KIND, now=now, max_age_h=max_age_h)
        if st != og.PASS:
            raise GuardError(f"동기화 확인이 통과가 아님({st}): {p} — {'; '.join(why)}")
        passed.add(db)
    missing = [t for t in targets if t not in passed]
    if missing:
        raise GuardError(f"동기화 확인 통과 결과가 없는 대상: {missing}")
    _REAL_ALLOWED.update(targets)
    return set(targets)


def assert_rehearsal_db(conn: Connection, expected: str) -> str:
    """쓰기 전 확인: 접속 DB 이름 = 지정 이름, 리허설 패턴, 보호 목록 밖.
    실제 적용 모드에서 enable_real_apply 를 통과한 실제 DB 이름만 예외로 허용한다."""
    cur = conn.execute(text("SELECT current_database()")).scalar()
    if cur != expected:
        raise GuardError(f"접속 DB({cur}) ≠ 지정 DB({expected})")
    if cur in _REAL_ALLOWED:
        return cur
    if cur in PROTECTED or not REHEARSAL_RE.match(cur or ""):
        raise GuardError(f"리허설 DB 이름이 아님: {cur} — 쓰기 거부")
    return cur


def add_real_apply_args(p) -> None:
    p.add_argument("--real-apply", action="store_true",
                   help="실제 로컬 DB 에 적용(런북 5절). --confirm-db·--sync-result 필요")
    p.add_argument("--confirm-db", action="append", default=[], help="실제 적용 대상 DB 이름을 다시 입력(대상마다 한 번)")
    p.add_argument("--sync-result", action="append", default=[], help="prod_sync_check compare --result-out 결과(통과) 파일")


def check_write_targets(names: list[str], a, *, base_url: str | None = None) -> None:
    """쓰기 전 이름 확인: --real-apply 면 접속 대상이 로컬 루프백인지(ops_guards.assert_local_target, libpq 최종 인자·
    PGHOST/PGHOSTADDR/PGSERVICE 포함) 먼저 보고 실제 적용 허가, 아니면 리허설 이름만."""
    if getattr(a, "real_apply", False):
        og = _ops_guards()
        for n in [x for x in names if x]:
            try:
                og.assert_local_target(engine_for(n, read_only=True, base_url=base_url))
            except og.TargetError as ex:
                raise GuardError(f"실제 적용 거부: {ex}") from ex
        enable_real_apply(names, a.confirm_db, [Path(x) for x in a.sync_result])
        return
    for n in names:
        if n and (n in PROTECTED or not REHEARSAL_RE.match(n)):
            raise GuardError(f"쓰기 대상 DB 이름이 리허설 이름(…_p2r)이 아님: {n}")


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------------
# 연결
# --------------------------------------------------------------------------------------------

def server_url_from_env() -> str:
    env = dotenv_values(REPO / "backend" / ".env")
    url = str(env.get("COLLECTIVE_DATABASE_URL") or env.get("DATABASE_URL") or "")
    if not url:
        raise RuntimeError("backend/.env 에 COLLECTIVE_DATABASE_URL 없음")
    return url


def engine_for(dbname: str, *, read_only: bool, base_url: str | None = None) -> Engine:
    url = make_url(base_url or server_url_from_env()).set(database=dbname)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    opts = "-c statement_timeout=0"
    if read_only:
        opts += " -c default_transaction_read_only=on"
    return create_engine(url, pool_pre_ping=True, connect_args={"options": opts})


# --------------------------------------------------------------------------------------------
# 계획(읽기만)
# --------------------------------------------------------------------------------------------

@dataclass
class Plan:
    ledger: pd.DataFrame = field(default_factory=pd.DataFrame)          # 집합 주거 원장 바뀌는 행
    keymap: pd.DataFrame = field(default_factory=pd.DataFrame)          # old_key,new_key,asset_type,reason,split_part
    commercial: pd.DataFrame = field(default_factory=pd.DataFrame)      # id,old_cluster_key,new_cluster_key,old_addr1,cluster_id,new_cluster_id
    cluster_actions: pd.DataFrame = field(default_factory=pd.DataFrame) # cluster id, action(rekey|delete), new_key
    clustermap: pd.DataFrame = field(default_factory=pd.DataFrame)
    built_ids: list[int] = field(default_factory=list)
    rent: pd.DataFrame = field(default_factory=pd.DataFrame)
    rentmap: pd.DataFrame = field(default_factory=pd.DataFrame)
    counts: dict = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


LEDGER_COLS = "id, asset_type, building_key, addr1, addr2, addr3, addr4, building_name, lot_number, road_name, beopjungri_code"


def _split_part_lookup(path: Path = SPLIT_UNITS_PATH) -> dict[tuple[str, str], int]:
    if not path.is_file():
        return {}
    df = pd.read_csv(path, dtype=str)
    df = df[df["decision"] == "split"]
    return {(b, u): int(p) for b, u, p in zip(df["base_key"], df["unit_emd8"], df["part"])}


def compute_new_keys(df: pd.DataFrame, units: dict, parts: dict) -> pd.DataFrame:
    """원장 행 → (std addr1, new_key, reason, split_part). 원문 재현이 안 되는 행은 problem 표시."""
    out = df.copy()
    out["new_addr1"] = out["addr1"].map(lambda a: LEGACY_SIDO_TO_CURRENT.get(a, a) if isinstance(a, str) else a)
    out["ok"] = True
    out["new_key"] = out["building_key"]
    out["reason"] = ""
    out["split_part"] = 0
    for asset, idx in out.groupby("asset_type").groups.items():
        sub = out.loc[idx]
        raw_old = building_key_raw_series(sub, asset)
        ok = raw_old.map(_sha) == sub["building_key"]
        std = sub.assign(addr1=sub["new_addr1"])
        raw_std = building_key_raw_series(std, asset)
        key_std = raw_std.map(_sha)
        new, reason, part = [], [], []
        for r, ks, ko, a_old, a_new, code in zip(raw_std, key_std, sub["building_key"], sub["addr1"], sub["new_addr1"],
                                                sub["beopjungri_code"]):
            rs = []
            if a_old != a_new:
                rs.append("honam_sido")
            nk = ks
            sp = 0
            if ks in units:
                unit = resolve_split_unit(units[ks], "" if code is None or code != code else str(code))
                nk = split_key_from_raw(r, unit)
                sp = parts.get((ks, unit), 0)
                rs.append("split")
            new.append(nk)
            reason.append("+".join(rs))
            part.append(sp)
        out.loc[idx, "ok"] = ok.values
        out.loc[idx, "new_key"] = new
        out.loc[idx, "reason"] = reason
        out.loc[idx, "split_part"] = part
    return out


def plan_collective(conn: Connection, units: dict, parts: dict, plan: Plan) -> None:
    base = list(units)
    df = pd.read_sql(
        text(f"SELECT {LEDGER_COLS} FROM collective_transactions WHERE addr1 = ANY(:leg) OR building_key = ANY(:base)"),
        conn, params={"leg": LEGACY, "base": base})
    # 호남 표준화 후 분할 목록에 드는 키(옛 이름 원 키)도 위 OR 의 addr1 조건으로 이미 포함된다
    df = compute_new_keys(df, units, parts) if len(df) else df.assign(new_addr1=None, ok=True, new_key=None, reason="", split_part=0)
    bad = df[~df["ok"]] if len(df) else df
    if len(bad):
        plan.problems.append(f"collective_transactions 원문 재현 불일치 {len(bad)}행 — 그 행은 키 유지(addr1만 표준화)")
        df.loc[~df["ok"], "new_key"] = df.loc[~df["ok"], "building_key"]
    ch = df[(df["new_key"] != df["building_key"]) | (df["new_addr1"] != df["addr1"])].copy() if len(df) else df
    plan.ledger = ch
    km = (ch[ch["new_key"] != ch["building_key"]]
          .groupby(["building_key", "new_key", "asset_type"], as_index=False)
          .agg(reason=("reason", "first"), split_part=("split_part", "max"), n=("id", "count"))
          .rename(columns={"building_key": "old_key"})) if len(ch) else pd.DataFrame(
        columns=["old_key", "new_key", "asset_type", "reason", "split_part", "n"])
    plan.keymap = km
    # 충돌: 분할로 생기는 새 키가 이전 전에 이미 다른 행의 키로 있으면 안 된다
    split_new = sorted(set(km.loc[km["reason"].str.contains("split"), "new_key"]))
    coll = 0
    if split_new:
        coll = int(conn.execute(text(
            "SELECT count(*) FROM collective_transactions WHERE building_key = ANY(:k)"), {"k": split_new}).scalar() or 0)
    dup_new = int(km[km["reason"].str.contains("split")].groupby("new_key")["old_key"].nunique().gt(1).sum()) if len(km) else 0
    honam_new = sorted(set(km.loc[km["reason"] == "honam_sido", "new_key"]))
    merged = 0
    if honam_new:
        merged = int(conn.execute(text(
            "SELECT count(DISTINCT building_key) FROM collective_transactions WHERE building_key = ANY(:k)"),
            {"k": honam_new}).scalar() or 0)
    plan.counts["collective"] = dict(
        rows_changed=len(ch), rows_addr1=int((ch["new_addr1"] != ch["addr1"]).sum()) if len(ch) else 0,
        rows_rekey=int((ch["new_key"] != ch["building_key"]).sum()) if len(ch) else 0,
        old_keys=int(km["old_key"].nunique()) if len(km) else 0, new_keys=int(km["new_key"].nunique()) if len(km) else 0,
        keymap_rows=len(km), honam_old_keys=int(km.loc[km.reason == "honam_sido", "old_key"].nunique()) if len(km) else 0,
        honam_merged_into_existing=merged, split_base_keys=int(km.loc[km.reason.str.contains("split"), "old_key"].nunique()) if len(km) else 0,
        split_new_keys=len(split_new), new_key_collision=coll, split_new_key_shared=dup_new,
    )
    if coll or dup_new:
        plan.problems.append(f"새 키 충돌: 기존 키와 {coll}행, 여러 옛 키가 같은 새 키 {dup_new}")


def plan_commercial(conn: Connection, plan: Plan) -> None:
    df = pd.read_sql(text("""SELECT id, asset_type, cluster_key, cluster_id, addr1, addr2, addr3, addr4, addr5, road_name
                             FROM collective_commercial_transactions WHERE addr1 = ANY(:leg)"""), conn, params={"leg": LEGACY})
    if df.empty:
        plan.commercial = df
        plan.counts["commercial"] = dict(rows=0)
        return
    new_keys, bad = [], 0
    for r in df.itertuples(index=False):
        a4 = r.addr4
        if make_road_cluster_key(asset_type=r.asset_type, addr1=r.addr1, addr2=r.addr2, addr3=r.addr3, addr4=a4,
                                 road_name=r.road_name) != r.cluster_key:
            a4 = r.addr5  # 옛 적재: 리가 addr4 칸에 있던 시점의 키(범위 밖 — 규칙은 그대로 재현만)
            if make_road_cluster_key(asset_type=r.asset_type, addr1=r.addr1, addr2=r.addr2, addr3=r.addr3, addr4=a4,
                                     road_name=r.road_name) != r.cluster_key:
                bad += 1
                new_keys.append(None)
                continue
        new_keys.append(make_road_cluster_key(asset_type=r.asset_type, addr1=LEGACY_SIDO_TO_CURRENT[r.addr1],
                                              addr2=r.addr2, addr3=r.addr3, addr4=a4, road_name=r.road_name))
    df["new_cluster_key"] = new_keys
    if bad:
        plan.problems.append(f"비주거 cluster 원문 재현 불일치 {bad}행 — cluster 유지(addr1만 표준화)")
        df.loc[df["new_cluster_key"].isna(), "new_cluster_key"] = df.loc[df["new_cluster_key"].isna(), "cluster_key"]
    df["new_addr1"] = df["addr1"].map(LEGACY_SIDO_TO_CURRENT)
    targets = sorted(set(df["new_cluster_key"]))
    ex = dict(conn.execute(text("SELECT cluster_key, id FROM commercial_clusters WHERE cluster_key = ANY(:k)"), {"k": targets}).all())
    # 대상 cluster id: 새 키 cluster가 이미 있으면 그것, 없으면 옛 cluster 중 가장 작은 id를 재키
    actions = []
    tgt_id: dict[str, int] = {}
    for nk, g in df.groupby("new_cluster_key"):
        olds = sorted(set(int(x) for x in g["cluster_id"]))
        if nk in ex and int(ex[nk]) not in olds:
            tgt_id[nk] = int(ex[nk])
            actions += [(cid, "delete", nk) for cid in olds]
        else:
            keep = int(ex[nk]) if nk in ex else olds[0]
            tgt_id[nk] = keep
            actions += [(keep, "rekey", nk)] + [(cid, "delete", nk) for cid in olds if cid != keep]
    df["new_cluster_id"] = df["new_cluster_key"].map(tgt_id)
    plan.commercial = df
    plan.cluster_actions = pd.DataFrame(actions, columns=["id", "action", "new_key"]).drop_duplicates("id")
    cm = df[df["new_cluster_key"] != df["cluster_key"]].groupby(["cluster_key", "new_cluster_key", "asset_type"], as_index=False).size()
    plan.clustermap = cm.rename(columns={"cluster_key": "old_key", "new_cluster_key": "new_key", "size": "n"})
    plan.counts["commercial"] = dict(
        rows=len(df), old_cluster_keys=int(df["cluster_key"].nunique()), new_cluster_keys=len(targets),
        merged_into_existing=int(sum(1 for k in targets if k in ex)),
        clusters_rekey=int((plan.cluster_actions.action == "rekey").sum()),
        clusters_delete=int((plan.cluster_actions.action == "delete").sum()))


def plan_built(conn: Connection, plan: Plan) -> None:
    ids = [int(r[0]) for r in conn.execute(text("SELECT id FROM built_transactions WHERE addr1 = ANY(:leg)"), {"leg": LEGACY})]
    plan.built_ids = ids
    plan.counts["built"] = dict(rows_addr1=len(ids))


def plan_rent(conn: Connection, units: dict, parts: dict, plan: Plan) -> None:
    base = list(units)
    df = pd.read_sql(text(f"SELECT {LEDGER_COLS} FROM rent_transactions WHERE building_key = ANY(:base)"), conn,
                     params={"base": base})
    leg = int(conn.execute(text("SELECT count(*) FROM rent_transactions WHERE addr1 = ANY(:leg)"), {"leg": LEGACY}).scalar() or 0)
    if df.empty:
        plan.rent = df
        plan.counts["rent"] = dict(rows_rekey=0, legacy_addr1_rows_untouched=leg)
        return
    df = df.assign(addr1_orig=df["addr1"])
    df = compute_new_keys(df, units, parts)
    df["new_addr1"] = df["addr1_orig"]  # 임대 원장 addr1 은 바꾸지 않는다(범위: 분할만)
    bad = int((~df["ok"]).sum())
    if bad:
        plan.problems.append(f"rent_transactions 원문 재현 불일치 {bad}행 — 키 유지")
        df.loc[~df["ok"], "new_key"] = df.loc[~df["ok"], "building_key"]
    ch = df[df["new_key"] != df["building_key"]].copy()
    plan.rent = ch
    plan.rentmap = (ch.groupby(["building_key", "new_key", "asset_type"], as_index=False)
                    .agg(split_part=("split_part", "max"), n=("id", "count")).rename(columns={"building_key": "old_key"}))
    plan.rentmap["reason"] = "split"
    coll = 0
    if len(ch):
        coll = int(conn.execute(text("SELECT count(*) FROM rent_transactions WHERE building_key = ANY(:k)"),
                                {"k": sorted(set(ch["new_key"]))}).scalar() or 0)
    plan.counts["rent"] = dict(rows_rekey=len(ch), old_keys=int(ch["building_key"].nunique()),
                               new_keys=int(ch["new_key"].nunique()), new_key_collision=coll,
                               legacy_addr1_rows_untouched=leg)
    if coll:
        plan.problems.append(f"임대 새 키 충돌 {coll}행")


# 부속 표: (표, PK 열들, 키 열, 1:1 재키 허용)
SIDE_TABLES_COLLECTIVE = [
    ("collective_building_attributes", ("id",), "building_key", True),
    ("collective_building_geocodes", ("building_key",), "building_key", True),
    ("collective_building_assessed_land_price", ("building_key", "asset_type"), "building_key", True),
    ("new_apartment_complex_year", ("id",), "building_key", False),
]
SIDE_TABLES_RENT = [
    ("rent_building_geocodes", ("building_key",), "building_key", False),
]


def side_actions(conn: Connection, table: str, pk: tuple[str, ...], keycol: str, allow_rekey: bool,
                 keymap: pd.DataFrame) -> pd.DataFrame:
    """영향 키 행별 행동: honam 1:1 이고 새 키 행이 없으면 rekey, 그 밖(새 키 이미 있음·분할)은 delete."""
    if keymap is None or keymap.empty:
        return pd.DataFrame(columns=["pk", "action", "new_key"])
    olds = sorted(set(keymap["old_key"]))
    rows = pd.read_sql(text(f"SELECT {', '.join(dict.fromkeys(pk + (keycol, 'asset_type')))} FROM {table} WHERE {keycol} = ANY(:k)")
                       if "asset_type" in _cols(conn, table) else
                       text(f"SELECT {', '.join(dict.fromkeys(pk + (keycol,)))} FROM {table} WHERE {keycol} = ANY(:k)"),
                       conn, params={"k": olds})
    if rows.empty:
        return pd.DataFrame(columns=["pk", "action", "new_key"])
    one = keymap.groupby("old_key")["new_key"].nunique()
    one_new = keymap.drop_duplicates("old_key").set_index("old_key")["new_key"]
    targets = sorted(set(one_new[one[one == 1].index]))
    have = set()
    if targets:
        have = {r[0] for r in conn.execute(text(f"SELECT DISTINCT {keycol} FROM {table} WHERE {keycol} = ANY(:k)"), {"k": targets})}
    out = []
    for r in rows.to_dict("records"):
        ok_ = r[keycol]
        if allow_rekey and one.get(ok_, 0) == 1 and one_new[ok_] not in have:
            out.append((json.dumps([r[c] for c in pk], default=str), "rekey", one_new[ok_]))
        else:
            out.append((json.dumps([r[c] for c in pk], default=str), "delete", None))
    return pd.DataFrame(out, columns=["pk", "action", "new_key"])


_COLS_CACHE: dict[tuple[int, str], list[str]] = {}


def _cols(conn: Connection, table: str) -> list[str]:
    k = (id(conn.engine), table)
    if k not in _COLS_CACHE:
        _COLS_CACHE[k] = [r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:t "
            "ORDER BY ordinal_position"), {"t": table})]
    return _COLS_CACHE[k]


def _table_exists(conn: Connection, table: str) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{table}"}).scalar())


# --------------------------------------------------------------------------------------------
# 쓰기
# --------------------------------------------------------------------------------------------

DDL_COLLECTIVE = """
CREATE TABLE IF NOT EXISTS collective_building_key_map (
    old_key varchar(64) NOT NULL, new_key varchar(64) NOT NULL, asset_type varchar(32) NOT NULL,
    reason varchar(32) NOT NULL, split_part int NOT NULL DEFAULT 0, n_tx int,
    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (old_key, new_key));
CREATE INDEX IF NOT EXISTS ix_collective_building_key_map_new ON collective_building_key_map (new_key);
CREATE TABLE IF NOT EXISTS collective_cluster_key_map (
    old_key varchar(64) NOT NULL, new_key varchar(64) NOT NULL, asset_type varchar(32) NOT NULL,
    reason varchar(32) NOT NULL, n_tx int, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (old_key, new_key));
CREATE TABLE IF NOT EXISTS collective_transactions_p2_before (
    id bigint PRIMARY KEY, addr1 text, building_key text, migrated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS collective_commercial_transactions_p2_before (
    id bigint PRIMARY KEY, addr1 text, cluster_key text, cluster_id bigint, migrated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS p2_migration_log (
    id serial PRIMARY KEY, run_at timestamptz NOT NULL DEFAULT now(), step text NOT NULL, detail jsonb);
"""
DDL_BUILT = """
CREATE TABLE IF NOT EXISTS built_transactions_p2_before (
    id bigint PRIMARY KEY, addr1 text, migrated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS p2_migration_log (
    id serial PRIMARY KEY, run_at timestamptz NOT NULL DEFAULT now(), step text NOT NULL, detail jsonb);
"""
DDL_RENT = """
CREATE TABLE IF NOT EXISTS rent_building_key_map (
    old_key varchar(64) NOT NULL, new_key varchar(64) NOT NULL, asset_type varchar(32) NOT NULL,
    reason varchar(32) NOT NULL, split_part int NOT NULL DEFAULT 0, n_tx int,
    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (old_key, new_key));
CREATE TABLE IF NOT EXISTS rent_transactions_p2_before (
    id bigint PRIMARY KEY, building_key text, migrated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS p2_migration_log (
    id serial PRIMARY KEY, run_at timestamptz NOT NULL DEFAULT now(), step text NOT NULL, detail jsonb);
"""


def _exec_script(conn: Connection, ddl: str) -> None:
    for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
        conn.execute(text(stmt))


def _ensure_side_before(conn: Connection, table: str) -> str:
    b = f"{table}_p2_before"
    if not _table_exists(conn, b):
        conn.execute(text(f"CREATE TABLE {b} (LIKE {table})"))
        conn.execute(text(f"ALTER TABLE {b} ADD COLUMN p2_action text, ADD COLUMN p2_new_key text, "
                          f"ADD COLUMN p2_saved_at timestamptz NOT NULL DEFAULT now()"))
    return b


def _log(conn: Connection, step: str, detail: dict) -> None:
    conn.execute(text("INSERT INTO p2_migration_log (step, detail) VALUES (:s, CAST(:d AS jsonb))"),
                 {"s": step, "d": json.dumps(detail, ensure_ascii=False, default=str)})


def _bulk(conn: Connection, sql: str, rows: list[dict]) -> None:
    for i in range(0, len(rows), CHUNK):
        conn.execute(text(sql), rows[i:i + CHUNK])


def _baseline(conn: Connection, step: str, tables: list[str]) -> None:
    """첫 실행 때만 행 수·hash 중복 수를 남긴다(검증 기준)."""
    if conn.execute(text("SELECT 1 FROM p2_migration_log WHERE step = :s LIMIT 1"), {"s": step}).first():
        return
    d = {}
    for t in tables:
        d[t] = int(conn.execute(text(f"SELECT count(*) FROM {t}")).scalar() or 0)
        if "transaction_hash" in _cols(conn, t):
            d[t + ":hash_dup"] = int(conn.execute(text(
                f"SELECT count(*) FROM (SELECT transaction_hash FROM {t} GROUP BY 1 HAVING count(*) > 1) x")).scalar() or 0)
    _log(conn, step, d)


def _apply_side(conn: Connection, table: str, pk: tuple[str, ...], keycol: str, acts: pd.DataFrame) -> dict:
    if acts.empty or not _table_exists(conn, table):
        return {"rekey": 0, "delete": 0}
    b = _ensure_side_before(conn, table)
    cols = _cols(conn, table)
    collist = ", ".join(cols)
    where = " AND ".join(f"t.{c}::text = (CAST(:pk AS jsonb) ->> {i})" for i, c in enumerate(pk))
    n = {"rekey": 0, "delete": 0}
    for a in acts.to_dict("records"):
        prm = {"pk": a["pk"], "nk": a["new_key"], "act": a["action"]}
        conn.execute(text(f"""INSERT INTO {b} ({collist}, p2_action, p2_new_key)
                              SELECT {', '.join('t.' + c for c in cols)}, :act, :nk FROM {table} t WHERE {where}"""), prm)
        if a["action"] == "rekey":
            conn.execute(text(f"UPDATE {table} t SET {keycol} = :nk WHERE {where}"), prm)
        else:
            conn.execute(text(f"DELETE FROM {table} t WHERE {where}"), prm)
        n[a["action"]] += 1
    return n


def apply_collective(eng: Engine, dbname: str, plan: Plan) -> dict:
    res = {}
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        _exec_script(conn, DDL_COLLECTIVE)
        _baseline(conn, "baseline_collective", ["collective_transactions", "collective_commercial_transactions",
                                                 "commercial_clusters"])
        # 부속 표 행동은 원장 바꾸기 전에 계산(새 키 존재 여부를 이전 전 상태로 판단)
        side = {t: side_actions(conn, t, pk, kc, rk, plan.keymap) for t, pk, kc, rk in SIDE_TABLES_COLLECTIVE
                if _table_exists(conn, t)}
        ch = plan.ledger
        if len(ch):
            rows = [{"id": int(i), "a": a, "k": k} for i, a, k in zip(ch["id"], ch["addr1"], ch["building_key"])]
            _bulk(conn, "INSERT INTO collective_transactions_p2_before (id, addr1, building_key) VALUES (:id, :a, :k) "
                        "ON CONFLICT (id) DO NOTHING", rows)
            conn.execute(text("CREATE TEMP TABLE _p2_upd (id bigint PRIMARY KEY, addr1 text, building_key text) ON COMMIT DROP"))
            _bulk(conn, "INSERT INTO _p2_upd VALUES (:id, :a, :k)",
                  [{"id": int(i), "a": a, "k": k} for i, a, k in zip(ch["id"], ch["new_addr1"], ch["new_key"])])
            r = conn.execute(text("""UPDATE collective_transactions t SET addr1 = u.addr1, building_key = u.building_key
                                     FROM _p2_upd u WHERE t.id = u.id"""))
            res["collective_transactions_updated"] = int(r.rowcount or 0)
        if len(plan.keymap):
            _bulk(conn, """INSERT INTO collective_building_key_map (old_key, new_key, asset_type, reason, split_part, n_tx)
                           VALUES (:old_key, :new_key, :asset_type, :reason, :split_part, :n) ON CONFLICT DO NOTHING""",
                  [{k: (int(v) if k in ("split_part", "n") else v) for k, v in r.items()}
                   for r in plan.keymap[["old_key", "new_key", "asset_type", "reason", "split_part", "n"]].to_dict("records")])
        for t, pk, kc, _rk in SIDE_TABLES_COLLECTIVE:
            if t in side:
                res[t] = _apply_side(conn, t, pk, kc, side[t])
        # 비주거
        cdf = plan.commercial
        if len(cdf):
            cl = plan.cluster_actions
            b = _ensure_side_before(conn, "commercial_clusters")
            cols = _cols(conn, "commercial_clusters")
            for a in cl.to_dict("records"):
                conn.execute(text(f"""INSERT INTO {b} ({', '.join(cols)}, p2_action, p2_new_key)
                                      SELECT {', '.join(cols)}, :act, :nk FROM commercial_clusters WHERE id = :id"""),
                             {"id": int(a["id"]), "act": a["action"], "nk": a["new_key"]})
            _bulk(conn, """INSERT INTO collective_commercial_transactions_p2_before (id, addr1, cluster_key, cluster_id)
                           VALUES (:id, :a, :k, :c) ON CONFLICT (id) DO NOTHING""",
                  [{"id": int(i), "a": a, "k": k, "c": int(c)} for i, a, k, c in
                   zip(cdf["id"], cdf["addr1"], cdf["cluster_key"], cdf["cluster_id"])])
            case = " ".join(f"WHEN '{o}' THEN '{n}'" for o, n in LEGACY_SIDO_TO_CURRENT.items())
            for a in cl[cl.action == "rekey"].to_dict("records"):
                conn.execute(text(f"UPDATE commercial_clusters SET cluster_key = :nk, addr1 = CASE addr1 {case} ELSE addr1 END "
                                  "WHERE id = :id"), {"nk": a["new_key"], "id": int(a["id"])})
            conn.execute(text("CREATE TEMP TABLE _p2_cupd (id bigint PRIMARY KEY, addr1 text, cluster_key text, cluster_id bigint) ON COMMIT DROP"))
            _bulk(conn, "INSERT INTO _p2_cupd VALUES (:id, :a, :k, :c)",
                  [{"id": int(i), "a": a, "k": k, "c": int(c)} for i, a, k, c in
                   zip(cdf["id"], cdf["new_addr1"], cdf["new_cluster_key"], cdf["new_cluster_id"])])
            r = conn.execute(text("""UPDATE collective_commercial_transactions t
                                     SET addr1 = u.addr1, cluster_key = u.cluster_key, cluster_id = u.cluster_id
                                     FROM _p2_cupd u WHERE t.id = u.id"""))
            res["commercial_updated"] = int(r.rowcount or 0)
            dels = [int(x) for x in cl.loc[cl.action == "delete", "id"]]
            if dels:
                left = conn.execute(text("SELECT count(*) FROM collective_commercial_transactions WHERE cluster_id = ANY(:i)"),
                                    {"i": dels}).scalar()
                if left:
                    raise RuntimeError(f"병합 cluster 삭제 전 참조 거래 {left}행 남음 — 중단")
                conn.execute(text("DELETE FROM commercial_clusters WHERE id = ANY(:i)"), {"i": dels})
            res["clusters_deleted"] = len(dels)
            if len(plan.clustermap):
                _bulk(conn, """INSERT INTO collective_cluster_key_map (old_key, new_key, asset_type, reason, n_tx)
                               VALUES (:old_key, :new_key, :asset_type, 'honam_sido', :n) ON CONFLICT DO NOTHING""",
                      [{**r, "n": int(r["n"])} for r in plan.clustermap.to_dict("records")])
            for t in ("collective_commercial_map_geocodes",):
                if _table_exists(conn, t) and len(plan.clustermap):
                    km = plan.clustermap.rename(columns={})
                    acts = side_actions(conn, t, ("cluster_key",), "cluster_key", True, km)
                    res[t] = _apply_side(conn, t, ("cluster_key",), "cluster_key", acts)
        _log(conn, "apply_collective", {**plan.counts.get("collective", {}), **res})
    return res


def apply_built(eng: Engine, dbname: str, plan: Plan) -> dict:
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        _exec_script(conn, DDL_BUILT)
        _baseline(conn, "baseline_built", ["built_transactions"])
        n = 0
        if plan.built_ids:
            conn.execute(text("""INSERT INTO built_transactions_p2_before (id, addr1)
                                 SELECT id, addr1 FROM built_transactions WHERE id = ANY(:i) ON CONFLICT (id) DO NOTHING"""),
                         {"i": plan.built_ids})
            for old, new in LEGACY_SIDO_TO_CURRENT.items():
                r = conn.execute(text("UPDATE built_transactions SET addr1 = :n WHERE id = ANY(:i) AND addr1 = :o"),
                                 {"n": new, "o": old, "i": plan.built_ids})
                n += int(r.rowcount or 0)
        _log(conn, "apply_built", {"rows_addr1": n})
    return {"built_updated": n}


def apply_rent(eng: Engine, dbname: str, plan: Plan) -> dict:
    res = {}
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        _exec_script(conn, DDL_RENT)
        _baseline(conn, "baseline_rent", ["rent_transactions"])
        # 매매·임대 연결 표는 전체 사본(첫 실행만) — Phase C에서 빌더로 재생성
        if _table_exists(conn, "rent_sale_building_map") and not _table_exists(conn, "rent_sale_building_map_p2_before"):
            conn.execute(text("CREATE TABLE rent_sale_building_map_p2_before AS SELECT * FROM rent_sale_building_map"))
        side = {t: side_actions(conn, t, pk, kc, rk, plan.rentmap) for t, pk, kc, rk in SIDE_TABLES_RENT
                if _table_exists(conn, t)}
        ch = plan.rent
        if len(ch):
            _bulk(conn, "INSERT INTO rent_transactions_p2_before (id, building_key) VALUES (:id, :k) ON CONFLICT (id) DO NOTHING",
                  [{"id": int(i), "k": k} for i, k in zip(ch["id"], ch["building_key"])])
            conn.execute(text("CREATE TEMP TABLE _p2_rupd (id bigint PRIMARY KEY, building_key text) ON COMMIT DROP"))
            _bulk(conn, "INSERT INTO _p2_rupd VALUES (:id, :k)", [{"id": int(i), "k": k} for i, k in zip(ch["id"], ch["new_key"])])
            r = conn.execute(text("UPDATE rent_transactions t SET building_key = u.building_key FROM _p2_rupd u WHERE t.id = u.id"))
            res["rent_updated"] = int(r.rowcount or 0)
            _bulk(conn, """INSERT INTO rent_building_key_map (old_key, new_key, asset_type, reason, split_part, n_tx)
                           VALUES (:old_key, :new_key, :asset_type, :reason, :split_part, :n) ON CONFLICT DO NOTHING""",
                  [{**r, "split_part": int(r["split_part"]), "n": int(r["n"])} for r in plan.rentmap.to_dict("records")])
        for t, pk, kc, _rk in SIDE_TABLES_RENT:
            if t in side:
                res[t] = _apply_side(conn, t, pk, kc, side[t])
        _log(conn, "apply_rent", {**plan.counts.get("rent", {}), **res})
    return res


# --------------------------------------------------------------------------------------------
# 되돌리기
# --------------------------------------------------------------------------------------------

def _rollback_side(conn: Connection, table: str, pk: tuple[str, ...], keycol: str) -> int:
    b = f"{table}_p2_before"
    if not _table_exists(conn, b):
        return 0
    cols = _cols(conn, table)
    if pk == ("id",):
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "id")
        r = conn.execute(text(f"INSERT INTO {table} ({', '.join(cols)}) SELECT {', '.join(cols)} FROM {b} "
                              f"ON CONFLICT (id) DO UPDATE SET {sets}"))
    else:
        others = [c for c in pk if c != keycol]
        cond = " AND ".join([f"t.{keycol} = b.p2_new_key"] + [f"t.{c} = b.{c}" for c in others])
        conn.execute(text(f"DELETE FROM {table} t USING {b} b WHERE b.p2_action = 'rekey' AND {cond}"))
        r = conn.execute(text(f"INSERT INTO {table} ({', '.join(cols)}) SELECT {', '.join(cols)} FROM {b} ON CONFLICT DO NOTHING"))
    conn.execute(text(f"DROP TABLE {b}"))
    return int(r.rowcount or 0)


def rollback_collective(eng: Engine, dbname: str) -> dict:
    res = {}
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        if not _table_exists(conn, "collective_transactions_p2_before"):
            return {"skipped": "no before table"}
        # 비주거: cluster 먼저 복원(거래 cluster_id FK)
        res["clusters"] = _rollback_side(conn, "commercial_clusters", ("id",), "cluster_key")
        r = conn.execute(text("""UPDATE collective_commercial_transactions t SET addr1 = b.addr1, cluster_key = b.cluster_key,
                                 cluster_id = b.cluster_id FROM collective_commercial_transactions_p2_before b WHERE t.id = b.id"""))
        res["commercial"] = int(r.rowcount or 0)
        r = conn.execute(text("""UPDATE collective_transactions t SET addr1 = b.addr1, building_key = b.building_key
                                 FROM collective_transactions_p2_before b WHERE t.id = b.id"""))
        res["collective_transactions"] = int(r.rowcount or 0)
        for t, pk, kc, _rk in SIDE_TABLES_COLLECTIVE + [("collective_commercial_map_geocodes", ("cluster_key",), "cluster_key", True)]:
            if _table_exists(conn, t):
                res[t] = _rollback_side(conn, t, pk, kc)
        for t in ("collective_transactions_p2_before", "collective_commercial_transactions_p2_before"):
            conn.execute(text(f"DROP TABLE {t}"))
        conn.execute(text("DELETE FROM collective_building_key_map"))
        conn.execute(text("DELETE FROM collective_cluster_key_map"))
        _log(conn, "rollback_collective", res)
    return res


def rollback_built(eng: Engine, dbname: str) -> dict:
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        if not _table_exists(conn, "built_transactions_p2_before"):
            return {"skipped": "no before table"}
        r = conn.execute(text("UPDATE built_transactions t SET addr1 = b.addr1 FROM built_transactions_p2_before b WHERE t.id = b.id"))
        conn.execute(text("DROP TABLE built_transactions_p2_before"))
        _log(conn, "rollback_built", {"rows": int(r.rowcount or 0)})
        return {"built": int(r.rowcount or 0)}


def rollback_rent(eng: Engine, dbname: str) -> dict:
    res = {}
    with eng.begin() as conn:
        assert_rehearsal_db(conn, dbname)
        if not _table_exists(conn, "rent_transactions_p2_before"):
            return {"skipped": "no before table"}
        r = conn.execute(text("UPDATE rent_transactions t SET building_key = b.building_key FROM rent_transactions_p2_before b WHERE t.id = b.id"))
        res["rent_transactions"] = int(r.rowcount or 0)
        for t, pk, kc, _rk in SIDE_TABLES_RENT:
            if _table_exists(conn, t):
                res[t] = _rollback_side(conn, t, pk, kc)
        if _table_exists(conn, "rent_sale_building_map_p2_before"):
            conn.execute(text("DELETE FROM rent_sale_building_map"))
            conn.execute(text("INSERT INTO rent_sale_building_map SELECT * FROM rent_sale_building_map_p2_before"))
            conn.execute(text("DROP TABLE rent_sale_building_map_p2_before"))
            res["rent_sale_building_map"] = "restored"
        conn.execute(text("DROP TABLE rent_transactions_p2_before"))
        conn.execute(text("DELETE FROM rent_building_key_map"))
        _log(conn, "rollback_rent", res)
    return res


# --------------------------------------------------------------------------------------------
# 검증(읽기)
# --------------------------------------------------------------------------------------------

def verify(ceng: Engine, beng: Engine | None, reng: Engine | None, units: dict) -> list[tuple[str, object, object, bool]]:
    """(지표, 기대, 실제, 통과)."""
    out: list[tuple[str, object, object, bool]] = []
    base = list(units)
    with ceng.connect() as c:
        bl = c.execute(text("SELECT detail FROM p2_migration_log WHERE step='baseline_collective' ORDER BY id LIMIT 1")).scalar()
        bl = bl or {}
        for t in ("collective_transactions", "collective_commercial_transactions"):
            now = int(c.execute(text(f"SELECT count(*) FROM {t}")).scalar() or 0)
            out.append((f"{t} 행 수(삭제 0)", bl.get(t), now, bl.get(t) == now))
            dup = int(c.execute(text(f"SELECT count(*) FROM (SELECT transaction_hash FROM {t} GROUP BY 1 HAVING count(*)>1) x")).scalar() or 0)
            out.append((f"{t} hash 중복(이전 전과 같음)", bl.get(t + ":hash_dup"), dup, bl.get(t + ":hash_dup") == dup))
            leg = int(c.execute(text(f"SELECT count(*) FROM {t} WHERE addr1 = ANY(:l)"), {"l": LEGACY}).scalar() or 0)
            out.append((f"{t} 옛 시도명 행", 0, leg, leg == 0))
        rem = int(c.execute(text("SELECT count(*) FROM collective_transactions WHERE building_key = ANY(:k)"), {"k": base}).scalar() or 0)
        out.append(("분할 대상 옛 키 남은 행", 0, rem, rem == 0))
        # 분할 전후 거래 수 합계(누락·중복 0): 옛 키별 보존 행 수 = 연결표 새 키들의 그 보존 행 수
        q = """
        WITH b AS (SELECT p.id, p.building_key AS old_key, t.building_key AS cur_key
                   FROM collective_transactions_p2_before p JOIN collective_transactions t ON t.id = p.id),
             m AS (SELECT old_key, new_key FROM collective_building_key_map)
        SELECT
          (SELECT count(*) FROM b) AS before_rows,
          (SELECT count(*) FROM b JOIN m ON m.old_key = b.old_key AND m.new_key = b.cur_key) AS mapped_rows,
          (SELECT count(*) FROM b WHERE b.old_key = b.cur_key) AS unchanged_key_rows
        """
        br, mr, ur = c.execute(text(q)).one()
        out.append(("보존 행 = 연결표로 설명되는 행 + 키 유지 행", br, int(mr) + int(ur), br == int(mr) + int(ur)))
        # 새 키 충돌: 분할 새 키를 가진 행은 모두 그 키의 옛 키에서 온 행이어야 한다
        coll = int(c.execute(text("""
            SELECT count(*) FROM collective_transactions t
            JOIN (SELECT DISTINCT new_key FROM collective_building_key_map WHERE reason LIKE '%split%') s ON s.new_key = t.building_key
            LEFT JOIN collective_transactions_p2_before p ON p.id = t.id
            WHERE p.id IS NULL""")).scalar() or 0)
        out.append(("새 키 충돌(분할 새 키에 외부 행)", 0, coll, coll == 0))
        nm = int(c.execute(text("SELECT count(*) FROM collective_building_key_map")).scalar() or 0)
        nchg = int(c.execute(text("""SELECT count(*) FROM (SELECT DISTINCT p.building_key, t.building_key
                                     FROM collective_transactions_p2_before p JOIN collective_transactions t ON t.id=p.id
                                     WHERE p.building_key <> t.building_key) x""")).scalar() or 0)
        out.append(("연결표 행 수 = 바뀐 (옛,새) 키 쌍 수", nchg, nm, nchg == nm))
        orphan = int(c.execute(text("""SELECT count(*) FROM collective_commercial_transactions t
                                       LEFT JOIN commercial_clusters c ON c.id = t.cluster_id WHERE c.id IS NULL""")).scalar() or 0)
        out.append(("비주거 거래 cluster_id 고아", 0, orphan, orphan == 0))
        mis = int(c.execute(text("""SELECT count(*) FROM collective_commercial_transactions t JOIN commercial_clusters c
                                    ON c.id = t.cluster_id WHERE c.cluster_key <> t.cluster_key""")).scalar() or 0)
        out.append(("비주거 거래·cluster 키 불일치", 0, mis, mis == 0))
    if beng is not None:
        with beng.connect() as c:
            bl = c.execute(text("SELECT detail FROM p2_migration_log WHERE step='baseline_built' ORDER BY id LIMIT 1")).scalar() or {}
            now = int(c.execute(text("SELECT count(*) FROM built_transactions")).scalar() or 0)
            out.append(("built_transactions 행 수", bl.get("built_transactions"), now, bl.get("built_transactions") == now))
            leg = int(c.execute(text("SELECT count(*) FROM built_transactions WHERE addr1 = ANY(:l)"), {"l": LEGACY}).scalar() or 0)
            out.append(("built_transactions 옛 시도명 행", 0, leg, leg == 0))
    if reng is not None:
        with reng.connect() as c:
            bl = c.execute(text("SELECT detail FROM p2_migration_log WHERE step='baseline_rent' ORDER BY id LIMIT 1")).scalar() or {}
            now = int(c.execute(text("SELECT count(*) FROM rent_transactions")).scalar() or 0)
            out.append(("rent_transactions 행 수", bl.get("rent_transactions"), now, bl.get("rent_transactions") == now))
            rem = int(c.execute(text("SELECT count(*) FROM rent_transactions WHERE building_key = ANY(:k)"), {"k": base}).scalar() or 0)
            out.append(("임대 분할 대상 옛 키 남은 행", 0, rem, rem == 0))
    return out


# --------------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------------

def build_plan(ceng: Engine, beng: Engine | None, reng: Engine | None, units: dict,
               split_path: Path | None = None) -> Plan:
    parts = _split_part_lookup(split_path or SPLIT_UNITS_PATH)
    plan = Plan()
    with ceng.connect() as c:
        plan_collective(c, units, parts, plan)
        plan_commercial(c, plan)
    if beng is not None:
        with beng.connect() as c:
            plan_built(c, plan)
    if reng is not None:
        with reng.connect() as c:
            plan_rent(c, units, parts, plan)
    return plan


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--collective-db", required=True)
    p.add_argument("--built-db", default="")
    p.add_argument("--rent-db", default="")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true")
    g.add_argument("--rollback", action="store_true")
    g.add_argument("--verify", action="store_true")
    p.add_argument("--split-units", default="", help="분할 목록 CSV(기본 pipeline/collective/data/p2_split_units.csv)")
    p.add_argument("--base-url", default="", help="DB 서버 URL(기본 backend/.env). DB 이름은 위 인자로 바꾼다")
    add_real_apply_args(p)
    a = p.parse_args(argv)
    if a.real_apply and (a.rollback or a.verify):
        raise GuardError("--real-apply 는 적용만 한다(실제 DB 되돌리기는 런북의 로컬 덤프 복원)")
    if a.real_apply:
        a.apply = True
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    units = load_split_units(a.split_units or None)
    base = a.base_url or None
    write = a.apply or a.rollback
    if write:
        check_write_targets([a.collective_db, a.built_db, a.rent_db], a, base_url=base)
    ce = engine_for(a.collective_db, read_only=not write, base_url=base)
    be = engine_for(a.built_db, read_only=not write, base_url=base) if a.built_db else None
    re_ = engine_for(a.rent_db, read_only=not write, base_url=base) if a.rent_db else None

    if a.rollback:
        print(json.dumps({"collective": rollback_collective(ce, a.collective_db),
                          "built": rollback_built(be, a.built_db) if be else None,
                          "rent": rollback_rent(re_, a.rent_db) if re_ else None}, ensure_ascii=False, indent=1, default=str))
        return 0
    if a.verify:
        rows = verify(ce, be, re_, units)
        bad = [r for r in rows if not r[3]]
        for name, exp, got, ok in rows:
            print(f"{'OK ' if ok else 'NG '} {name}: 기대 {exp} / 실제 {got}")
        return 1 if bad else 0

    plan = build_plan(ce, be, re_, units, Path(a.split_units) if a.split_units else None)
    print(json.dumps({"split_base_keys": len(units), "counts": plan.counts, "problems": plan.problems},
                     ensure_ascii=False, indent=1, default=str))
    if not a.apply:
        print("드라이런 — 쓰지 않았다. 쓰려면 --apply (리허설 DB) 또는 --real-apply (실제 DB, 런북 5절).")
        return 0
    if any("충돌" in x for x in plan.problems):
        print("새 키 충돌이 있어 중단")
        return 2
    out = {"collective": apply_collective(ce, a.collective_db, plan)}
    if be is not None:
        out["built"] = apply_built(be, a.built_db, plan)
    if re_ is not None:
        out["rent"] = apply_rent(re_, a.rent_db, plan)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
