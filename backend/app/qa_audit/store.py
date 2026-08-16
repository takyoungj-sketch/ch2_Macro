"""qa_audit_run 저장. 원장·마트는 변경하지 않는다."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.qa_audit.sql_pred import execute_sql


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def log_dir() -> Path:
    d = _repo_root() / "logs" / "qa_audit"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_json_log(run: dict[str, Any]) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    code = str(run.get("region_code") or "unknown")
    year = str(run.get("period_key") or "")
    path = log_dir() / f"{ts}_{code}_{year}_{run.get('verdict')}.json"
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def ensure_table(conn) -> None:
    """CREATE IF NOT EXISTS. 원장·마트 테이블은 건드리지 않는다."""
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS qa_audit_run (
                id              BIGSERIAL PRIMARY KEY,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                trigger         VARCHAR(16) NOT NULL,
                domain          VARCHAR(32) NOT NULL,
                region_level    VARCHAR(16) NOT NULL,
                region_code     VARCHAR(10) NOT NULL,
                region_name     TEXT,
                period_kind     VARCHAR(24) NOT NULL,
                period_key      VARCHAR(32) NOT NULL,
                asset_type      VARCHAR(32) NOT NULL,
                engine_version  VARCHAR(32) NOT NULL,
                builder_version TEXT,
                as_of           TEXT,
                l1_json         JSONB NOT NULL,
                l2_json         JSONB NOT NULL,
                l3_json         JSONB NOT NULL,
                mart_json       JSONB NOT NULL,
                diffs_json      JSONB NOT NULL,
                verdict         VARCHAR(16) NOT NULL,
                ai_report       TEXT,
                operator_note   TEXT
            )
            """
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_qa_audit_run_created "
            "ON qa_audit_run (created_at DESC)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_qa_audit_run_verdict "
            "ON qa_audit_run (verdict, created_at DESC)"
        )
    )


def insert_run(conn, run: dict[str, Any]) -> int | None:
    row = execute_sql(
        conn,
        """
        INSERT INTO qa_audit_run (
            trigger, domain, region_level, region_code, region_name,
            period_kind, period_key, asset_type,
            engine_version, builder_version, as_of,
            l1_json, l2_json, l3_json, mart_json, diffs_json,
            verdict, ai_report, operator_note
        ) VALUES (
            :trigger, :domain, :region_level, :region_code, :region_name,
            :period_kind, :period_key, :asset_type,
            :engine_version, :builder_version, :as_of,
            CAST(:l1_json AS jsonb), CAST(:l2_json AS jsonb),
            CAST(:l3_json AS jsonb), CAST(:mart_json AS jsonb),
            CAST(:diffs_json AS jsonb),
            :verdict, :ai_report, :operator_note
        )
        RETURNING id
        """,
        {
            "trigger": run.get("trigger"),
            "domain": run.get("domain"),
            "region_level": run.get("region_level"),
            "region_code": run.get("region_code"),
            "region_name": run.get("region_name"),
            "period_kind": run.get("period_kind"),
            "period_key": run.get("period_key"),
            "asset_type": run.get("asset_type"),
            "engine_version": run.get("engine_version"),
            "builder_version": run.get("builder_version"),
            "as_of": run.get("as_of"),
            "l1_json": json.dumps(run.get("l1") or {}, ensure_ascii=False, default=str),
            "l2_json": json.dumps(run.get("l2") or {}, ensure_ascii=False, default=str),
            "l3_json": json.dumps(run.get("l3") or {}, ensure_ascii=False, default=str),
            "mart_json": json.dumps(run.get("mart") or {}, ensure_ascii=False, default=str),
            "diffs_json": json.dumps(run.get("diffs") or {}, ensure_ascii=False, default=str),
            "verdict": run.get("verdict"),
            "ai_report": run.get("ai_report"),
            "operator_note": run.get("operator_note"),
        },
    ).scalar()
    return int(row) if row is not None else None


def list_runs(conn, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = execute_sql(
        conn,
        """
        SELECT id, created_at, trigger, domain, region_level, region_code,
               region_name, period_key, asset_type, verdict
        FROM qa_audit_run
        ORDER BY created_at DESC
        LIMIT :lim
        """,
        {"lim": int(limit)},
    ).mappings().all()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        if d.get("created_at") is not None:
            d["created_at"] = str(d["created_at"])
        out.append(d)
    return out
