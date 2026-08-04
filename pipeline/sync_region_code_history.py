# -*- coding: utf-8 -*-
"""Sync region_code_history (+ affected region_codes) from land SSOT → built/collective.

Design (interim → target):
  - Today: land_stats.region_code_history is the operational source of truth.
  - Sync copies the same rows into built_stats / collective_stats so each DB can
    JOIN locally (no cross-DB SQL in mart builders / API).
  - Do NOT invent per-DB mapping rules — only replicate land history.
  - Long-term: promote region_codes + region_code_history to a CH2 Macro shared
    region master (not Land-owned). Sync then becomes pull-from-master.

Excludes: unresolved / split (no history rows). Ledger beopjungri never updated.

Usage:
  cd backend
  .venv/Scripts/python.exe ../pipeline/sync_region_code_history.py
  .venv/Scripts/python.exe ../pipeline/sync_region_code_history.py --dry-run
  .venv/Scripts/python.exe ../pipeline/sync_region_code_history.py --targets built,collective
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env", override=True)
load_dotenv(ROOT / "pipeline" / ".env.built")
load_dotenv()

DDL_PATH = ROOT / "db" / "046_region_code_history_shared.sql"
OUT_MD = ROOT / "docs" / "reports" / "REGION_CODE_HISTORY_SYNC_VERIFY.md"


def _ensure_ddl(engine: Engine) -> None:
    ddl = DDL_PATH.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _fetch_land_history(land: Engine) -> list[dict]:
    with land.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT from_code, to_code, change_type,
                       effective_from, effective_to, source_note, created_at
                FROM region_code_history
                WHERE change_type IN ('code_reissue', 'merge', 'rename')
                ORDER BY id
                """
            )
        ).mappings().all()
    return [dict(r) for r in rows]


def _sync_history(dst: Engine, rows: list[dict], *, dry_run: bool) -> dict:
    with dst.connect() as conn:
        before = int(conn.execute(text("SELECT COUNT(*) FROM region_code_history")).scalar() or 0)
    if dry_run:
        return {"before": before, "after": before, "upserted": 0, "dry_run": True}

    with dst.begin() as conn:
        # Replace allowed-type rows with SSOT snapshot (avoid divergent forks)
        conn.execute(
            text(
                """
                DELETE FROM region_code_history
                WHERE change_type IN ('code_reissue', 'merge', 'rename')
                """
            )
        )
        for r in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO region_code_history (
                        from_code, to_code, change_type,
                        effective_from, effective_to, source_note, created_at
                    ) VALUES (
                        :from_code, :to_code, :change_type,
                        :effective_from, :effective_to, :source_note,
                        COALESCE(:created_at, NOW())
                    )
                    """
                ),
                r,
            )
        after = int(conn.execute(text("SELECT COUNT(*) FROM region_code_history")).scalar() or 0)
    return {"before": before, "after": after, "upserted": len(rows), "dry_run": False}


def _sync_region_codes_for_pairs(land: Engine, dst: Engine, rows: list[dict], *, dry_run: bool) -> dict:
    """Upsert to_code rows + deactivate from_code rows from land region_codes."""
    from_codes = sorted({str(r["from_code"]).strip() for r in rows})
    to_codes = sorted({str(r["to_code"]).strip() for r in rows})
    codes = sorted(set(from_codes) | set(to_codes))
    with land.connect() as conn:
        src = conn.execute(
            text(
                """
                SELECT sido_code, sido_name, sigungu_code, sigungu_name,
                       eupmyeondong_code, eupmyeondong_name,
                       beopjungri_code, beopjungri_name, is_active, updated_at
                FROM region_codes
                WHERE btrim(beopjungri_code::text) = ANY(:c)
                """
            ),
            {"c": codes},
        ).mappings().all()
    src_rows = [dict(r) for r in src]
    if dry_run:
        return {"land_rows": len(src_rows), "written": 0, "dry_run": True}

    n = 0
    with dst.begin() as conn:
        for r in src_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO region_codes (
                        sido_code, sido_name, sigungu_code, sigungu_name,
                        eupmyeondong_code, eupmyeondong_name,
                        beopjungri_code, beopjungri_name, is_active, updated_at
                    ) VALUES (
                        :sido_code, :sido_name, :sigungu_code, :sigungu_name,
                        :eupmyeondong_code, :eupmyeondong_name,
                        :beopjungri_code, :beopjungri_name, :is_active,
                        COALESCE(:updated_at, NOW())
                    )
                    ON CONFLICT (beopjungri_code) DO UPDATE SET
                        sido_code = EXCLUDED.sido_code,
                        sido_name = EXCLUDED.sido_name,
                        sigungu_code = EXCLUDED.sigungu_code,
                        sigungu_name = EXCLUDED.sigungu_name,
                        eupmyeondong_code = EXCLUDED.eupmyeondong_code,
                        eupmyeondong_name = EXCLUDED.eupmyeondong_name,
                        beopjungri_name = EXCLUDED.beopjungri_name,
                        is_active = EXCLUDED.is_active,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                r,
            )
            n += 1
    return {"land_rows": len(src_rows), "written": n, "dry_run": False}


def _integrity(land: Engine, targets: dict[str, Engine], rows: list[dict]) -> dict:
    land_set = {(str(r["from_code"]).strip(), str(r["to_code"]).strip(), str(r["change_type"])) for r in rows}
    out: dict = {"land_n": len(land_set), "targets": {}}
    for name, eng in targets.items():
        with eng.connect() as conn:
            n = int(conn.execute(text("SELECT COUNT(*) FROM region_code_history")).scalar() or 0)
            dst_rows = conn.execute(
                text(
                    """
                    SELECT from_code, to_code, change_type
                    FROM region_code_history
                    WHERE change_type IN ('code_reissue', 'merge', 'rename')
                    """
                )
            ).fetchall()
            dst_set = {
                (str(a).strip(), str(b).strip(), str(t).strip()) for a, b, t in dst_rows
            }
            # sample resolve
            sample = conn.execute(
                text(
                    """
                    SELECT COALESCE(
                      (SELECT h.to_code FROM region_code_history h
                       WHERE h.from_code = '4377034026'
                         AND h.change_type IN ('code_reissue','merge','rename')
                       ORDER BY h.effective_from DESC, h.id DESC LIMIT 1),
                      '4377034026'
                    ) AS canon
                    """
                )
            ).scalar()
            # sute may be absent in built/collective txs but mapping must exist
            hw = conn.execute(
                text(
                    """
                    SELECT COALESCE(
                      (SELECT h.to_code FROM region_code_history h
                       WHERE h.from_code = '4159025321'
                         AND h.change_type IN ('code_reissue','merge','rename')
                       ORDER BY h.effective_from DESC, h.id DESC LIMIT 1),
                      'MISSING'
                    )
                    """
                )
            ).scalar()
        missing = land_set - dst_set
        extra = dst_set - land_set
        out["targets"][name] = {
            "history_n": n,
            "missing_vs_land": len(missing),
            "extra_vs_land": len(extra),
            "sample_sute_canon": str(sample).strip() if sample else None,
            "sample_hwaseong_canon": str(hw).strip() if hw else None,
            "ok": len(missing) == 0 and len(extra) == 0,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--targets",
        default="built,collective",
        help="comma: built,collective",
    )
    ap.add_argument("--skip-region-codes", action="store_true")
    args = ap.parse_args()

    from built.db_utils import get_built_engine
    from collective.db_utils import get_collective_engine
    from db_utils import get_engine as get_land_engine

    land = get_land_engine()
    rows = _fetch_land_history(land)
    print(f"land history rows (allowed types)={len(rows)}")

    engines: dict[str, Engine] = {}
    for t in [x.strip() for x in args.targets.split(",") if x.strip()]:
        if t == "built":
            engines["built_stats"] = get_built_engine()
        elif t == "collective":
            engines["collective_stats"] = get_collective_engine()
        else:
            raise SystemExit(f"unknown target: {t}")

    sync_stats: dict = {}
    for name, eng in engines.items():
        print(f"[{name}] ensure DDL…")
        if not args.dry_run:
            _ensure_ddl(eng)
        h = _sync_history(eng, rows, dry_run=args.dry_run)
        rc = {"skipped": True}
        if not args.skip_region_codes:
            rc = _sync_region_codes_for_pairs(land, eng, rows, dry_run=args.dry_run)
        sync_stats[name] = {"history": h, "region_codes": rc}
        print(f"[{name}] history={h} region_codes={rc}")

    integ = _integrity(land, engines, rows)
    lines = [
        "# region_code_history sync verify",
        "",
        "## Design",
        "",
        "- **Interim SSOT:** `land_stats.region_code_history` (replicate, do not fork).",
        "- **Targets:** `built_stats`, `collective_stats` local copies for JOIN/API.",
        "- **Long-term:** CH2 Macro shared region master (`region_codes` + `history`), not Land-owned.",
        "- **Excluded:** unresolved / `split` (no auto rows).",
        "- **Ledger:** never UPDATE `beopjungri_code`.",
        "",
        f"- dry_run={args.dry_run}",
        f"- land allowed-type rows: **{len(rows)}**",
        "",
        "## Sync stats",
        "",
        "```json",
        __import__("json").dumps(sync_stats, ensure_ascii=False, indent=2, default=str),
        "```",
        "",
        "## Integrity",
        "",
        "```json",
        __import__("json").dumps(integ, ensure_ascii=False, indent=2, default=str),
        "```",
        "",
    ]
    all_ok = all(t.get("ok") for t in integ["targets"].values()) if not args.dry_run else False
    lines.append(f"- integrity_ok: **{all_ok if not args.dry_run else 'n/a (dry-run)'}**")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_MD}")
    if not args.dry_run and not all_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
