"""ledger_snapshot UPSERT."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def ensure_ledger_snapshot_kind(engine: Engine) -> None:
    """기존 PK (source, snapshot, sido_code) → kind 컬럼 추가."""
    with engine.begin() as conn:
        cols = {
            str(r[0])
            for r in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'ledger_snapshot'"
                )
            )
        }
        if "kind" in cols:
            return
        conn.execute(text("ALTER TABLE ledger_snapshot DROP CONSTRAINT IF EXISTS ledger_snapshot_pkey"))
        conn.execute(text("ALTER TABLE ledger_snapshot ADD COLUMN kind TEXT NOT NULL DEFAULT ''"))
        conn.execute(
            text(
                "ALTER TABLE ledger_snapshot ADD PRIMARY KEY (source, snapshot, sido_code, kind)"
            )
        )


def upsert_ledger_snapshot(
    engine: Engine,
    *,
    source: str,
    snapshot: str,
    sido_code: str,
    row_count: int | None,
    kind: str = "",
) -> None:
    ensure_ledger_snapshot_kind(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ledger_snapshot (source, snapshot, sido_code, kind, loaded_at, row_count)
                VALUES (:source, :snapshot, :sido_code, :kind, NOW(), :row_count)
                ON CONFLICT (source, snapshot, sido_code, kind)
                DO UPDATE SET loaded_at = EXCLUDED.loaded_at, row_count = EXCLUDED.row_count
                """
            ),
            {
                "source": source,
                "snapshot": snapshot,
                "sido_code": sido_code,
                "kind": kind,
                "row_count": row_count,
            },
        )


def record_building_snapshots(engine: Engine, ledger_kind: str) -> None:
    """표제부 적재 후 스냅샷×시도 건수를 레지스트리에 남긴다."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT snapshot, sido_code, COUNT(*) AS n
                FROM building
                WHERE ledger_kind = :kind
                GROUP BY snapshot, sido_code
                """
            ),
            {"kind": ledger_kind},
        ).all()
    for snap, sido, n in rows:
        upsert_ledger_snapshot(
            engine,
            source="title",
            snapshot=str(snap),
            sido_code=str(sido),
            row_count=int(n),
            kind=ledger_kind,
        )
