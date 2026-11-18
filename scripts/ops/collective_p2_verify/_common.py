"""집합 2단계 운영 확인 공통 — 읽기 전용 접속·쿼리 시간 제한·결과 기록. (Claude Code 작성, Codex 검토·실행)

- 접속 URL 은 환경변수(없으면 --env-file 의 KEY=VALUE)에서 읽고 **출력하지 않는다.** 결과에는 DB 이름만 남긴다.
- 세션은 `default_transaction_read_only=on` 으로 열고, 첫 쿼리 전에 `SHOW transaction_read_only` 가 on 인지 확인한다.
- 쿼리마다 `statement_timeout` 을 건다(기본 10초). 무거운 쿼리는 호출하는 쪽이 따로 시간과 승인 여부를 정한다.
- 운영 서버에는 pipeline 전체가 배포되지 않으므로 이 폴더는 pipeline 을 import 하지 않는다(SQL 은 sql_copies.py 에 복사,
  테스트가 원본과 같은지 확인).
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.pool import NullPool

LIGHT_MS = 10_000


def read_env_file(path: Path | None) -> dict[str, str]:
    if not path or not path.is_file():
        return {}
    out: dict[str, str] = {}
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def db_url(env_name: str, env_file: Path | None = None) -> str:
    """환경변수 → env 파일 순서. 없으면 이름만 밝히고 멈춘다(값은 출력하지 않음)."""
    v = os.environ.get(env_name) or read_env_file(env_file).get(env_name)
    if not v:
        raise SystemExit(f"접속 정보 없음: 환경변수 {env_name} (값은 출력하지 않음)")
    return v


def ro_engine(url: str, *, timezone: str | None = None) -> Engine:
    u = make_url(url)
    if u.drivername == "postgresql":
        u = u.set(drivername="postgresql+psycopg2")
    opts = f"-c default_transaction_read_only=on -c statement_timeout={LIGHT_MS}"
    if timezone is not None:
        if not all(ch.isalnum() or ch in "/_+-" for ch in timezone):
            raise SystemExit("TimeZone 값 거부")
        opts += f" -c TimeZone={timezone}"
    return create_engine(u, poolclass=NullPool,
                         connect_args={"options": opts, "connect_timeout": 10})


@contextmanager
def ro_conn(url: str, *, timezone: str | None = None) -> Iterator[Connection]:
    eng = ro_engine(url, timezone=timezone)
    try:
        with eng.connect() as c:
            if c.execute(text("SHOW transaction_read_only")).scalar() != "on":
                raise SystemExit("읽기 전용 세션이 아님 — 중단")
            yield c
    finally:
        eng.dispose()


class Timed:
    """쿼리마다 시간 제한을 걸고 걸린 시간을 남긴다. 시간 초과는 예외 대신 None 과 기록으로 돌려준다."""

    def __init__(self) -> None:
        self.log: list[dict[str, Any]] = []

    def run(self, conn: Connection, label: str, sql: str, params: dict | None = None, *, timeout_ms: int = LIGHT_MS,
            fetch: str = "all"):
        conn.execute(text(f"SET statement_timeout = {int(timeout_ms)}"))
        t0 = time.time()
        try:
            r = conn.execute(text(sql), params or {})
            out = r.all() if fetch == "all" else r.scalar() if fetch == "scalar" else r.one()
            self.log.append({"query": label, "sec": round(time.time() - t0, 2), "timeout_ms": timeout_ms, "ok": True})
            return out
        except Exception as ex:  # noqa: BLE001
            conn.rollback()
            msg = "시간 초과" if "statement timeout" in str(ex) else type(ex).__name__
            self.log.append({"query": label, "sec": round(time.time() - t0, 2), "timeout_ms": timeout_ms, "ok": False,
                             "error": msg})
            return None


def db_name(conn: Connection) -> str:
    return str(conn.execute(text("SELECT current_database()")).scalar())


def table_columns(conn: Connection, table: str) -> list[str]:
    return [r[0] for r in conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:t "
        "ORDER BY ordinal_position"), {"t": table})]


def table_exists(conn: Connection, table: str) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{table}"}).scalar())


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# 비교 결과 세 가지와 종료 코드(T·Codex: 「검증 못 함」은 통과로 세지 않는다)
PASS, DIFF, UNVERIFIED = "pass", "diff", "unverified"
EXIT = {PASS: 0, DIFF: 1, UNVERIFIED: 2}
STATUS_KO = {PASS: "통과", DIFF: "차이", UNVERIFIED: "검증 못 함"}


def now_iso() -> str:
    """이 프로세스가 도는 기계의 시계를 UTC 로. 순서 판정에 쓰는 값은 로컬 PC 에서 끝난 뒤에만 local 로 둔다."""
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).isoformat()


STAMP_MAX_SKEW_S = 600


class StampError(RuntimeError):
    pass


def _parse_utc(s):
    import datetime as _dt

    try:
        d = _dt.datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else None


def stamp_local(obj: dict, *fields: str, now=None) -> dict:
    """로컬 PC 시계(UTC)로 순서 판정 시각을 찍고 출처를 local 로 둔다.

    server_now(출처 server)가 없거나, 찍는 시각과 10분을 넘기면 StampError.
    오래된 파일을 나중에 가져와 오늘 시각이 찍히는 것을 막는다. server_now 값은 바꾸지 않고, 순서 판정도 쓰지 않는다.
    """
    import datetime as _dt

    if not isinstance(obj, dict) or obj.get("server_now_source") != "server" or not obj.get("server_now"):
        raise StampError("server_now 가 없거나 출처가 server 가 아님")
    server = _parse_utc(obj.get("server_now"))
    if server is None:
        raise StampError("server_now 시각을 읽을 수 없음")
    stamped = now or _dt.datetime.now(_dt.timezone.utc)
    if abs((stamped - server).total_seconds()) > STAMP_MAX_SKEW_S:
        raise StampError("server_now 와 로컬 시각 차이가 10분을 넘음")
    out = dict(obj)
    iso = stamped.isoformat()
    for f in fields:
        out[f] = iso
        out[f + "_source"] = "local"
    return out


def oldest_measured(*snaps: dict) -> tuple[str | None, list[str]]:
    """입력 스냅샷들의 measured_at 중 가장 오래된 값. 없거나 형식이 틀린 스냅샷은 사유로 돌려준다."""
    import datetime as _dt

    times, why = [], []
    for s in snaps:
        v = (s or {}).get("measured_at")
        try:
            t = _dt.datetime.fromisoformat(str(v))
            if t.tzinfo is None:
                raise ValueError
            times.append(t)
        except (TypeError, ValueError):
            why.append(f"{(s or {}).get('db')}: 스냅샷 측정 시각(measured_at) 없음·형식 오류")
    return (min(times).isoformat() if times and not why else None), why


def make_result(*, kind: str, status: str, left_db: str, right_db: str, diff: int, unverified: list,
                failures: list, detail: dict | None = None, snapshots: tuple = ()) -> dict:
    """compare 결과(파일로 쓰기 전). ops_guards.validate_result 가 요구하는 필드를 모두 담는다.
    created_at = 입력 스냅샷 중 **가장 오래된 measured_at**(비교한 시각이 아니라 자료를 잰 시각). 48시간 검사는 이 값으로 한다.
    스냅샷 없이 부르면(이전 호출 호환) 지금 시각. 측정 시각을 알 수 없는 스냅샷이 있으면 검증 못 함 항목에 넣는다."""
    unv = list(unverified)
    created = now_iso()
    if snapshots:
        oldest, why = oldest_measured(*snapshots)
        unv += why
        created = oldest or created
    return {"kind": kind, "status": status, "left_db": left_db, "right_db": right_db,
            "targets": sorted({x for x in (left_db, right_db) if x}),
            "created_at": created, "compared_at": now_iso(),
            "diff": int(diff), "unverified": unv, "failures": list(failures), **(detail or {})}


def finalize_result(obj: dict, expected_targets) -> dict:
    """결과를 내기 전에 validate_result 를 거친다. 검증이 통과가 아니면 status 를 그 판정으로 낮춘다(사유 기록)."""
    from ops_guards import validate_result

    st, why = validate_result(obj, expected_targets, kind=obj.get("kind"))
    out = dict(obj)
    if st != obj.get("status") or why:
        out["status"] = st
        out["validation"] = why
    return out


def snapshot_failures(*snaps: dict) -> list[str]:
    """스냅샷 안의 쿼리 실패(시간 초과 등) 기록."""
    out = []
    for s in snaps:
        for x in (s or {}).get("_timings", []):
            if not x.get("ok"):
                out.append(f"{s.get('db')}: {x.get('query')} ({x.get('error')})")
    return out


def write_result(path: Path, *, kind: str, status: str, left_db: str, right_db: str, detail: dict) -> None:
    """(이전 호출 호환) 결과 파일. 실제 적용 모드는 make_result→finalize_result 를 거친 파일만 통과로 받는다."""
    obj = make_result(kind=kind, status=status, left_db=left_db, right_db=right_db,
                      diff=int(detail.get("diff", 0)), unverified=list(detail.get("unverified", [])),
                      failures=list(detail.get("failures", [])),
                      detail={k: v for k, v in detail.items() if k not in ("diff", "unverified", "failures")})
    write_json(path, finalize_result(obj, [left_db]))


def md_table(rows, headers) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(v) for v in r) + " |" for r in rows]
    return "\n".join(out)
