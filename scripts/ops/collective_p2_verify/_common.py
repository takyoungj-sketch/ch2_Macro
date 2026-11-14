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


def ro_engine(url: str) -> Engine:
    u = make_url(url)
    if u.drivername == "postgresql":
        u = u.set(drivername="postgresql+psycopg2")
    return create_engine(u, poolclass=NullPool,
                         connect_args={"options": f"-c default_transaction_read_only=on -c statement_timeout={LIGHT_MS}",
                                       "connect_timeout": 10})


@contextmanager
def ro_conn(url: str) -> Iterator[Connection]:
    eng = ro_engine(url)
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


def write_result(path: Path, *, kind: str, status: str, left_db: str, right_db: str, detail: dict) -> None:
    """compare 결과 파일. 실제 적용 모드(migrate_p2_keys --real-apply --sync-result)가 이 파일의 status=pass 를 요구한다."""
    import datetime as _dt

    write_json(path, {"kind": kind, "status": status, "left_db": left_db, "right_db": right_db,
                      "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(), **detail})


def md_table(rows, headers) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(v) for v in r) + " |" for r in rows]
    return "\n".join(out)
