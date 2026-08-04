# -*- coding: utf-8 -*-
"""Verify canonical resolver + mart migration readiness (D-028).

Exit 0 = PASS, 1 = FAIL (CI / pre-deploy gate).

Checks:
  1. Resolver meta (version, history snapshot row count)
  2. Resolver contract smoke (대소·양지 prefix pairs)
  3. Mart grain audit — historical rows in mart MUST be 0
  4. Mart stats: canonical / historical / orphan / duplicate counts
  5. region_code_history parity (land vs built/collective when configured)

Usage:
  cd backend
  .venv/Scripts/python.exe ../pipeline/verify_canonical_resolver_migration.py
  .venv/Scripts/python.exe ../pipeline/verify_canonical_resolver_migration.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "backend"))

OUT_JSON = ROOT / "docs" / "reports" / "REGION_CODE_CANONICAL_VERIFY.json"
OUT_MD = ROOT / "docs" / "reports" / "REGION_CODE_CANONICAL_VERIFY.md"

PILOT_CASES = (
    {"name": "daeso_eup", "hist_eup": "43770340", "canon_eup": "43770256", "hist_ri": "4377034026", "canon_ri": "4377025626"},
    {"name": "yangji_eup", "hist_eup": "41461360", "canon_eup": "41461262", "hist_ri": "4146136029", "canon_ri": "4146126229"},
)


def _engine_for_url(url: str | None):
    if not (url or "").strip():
        return None
    from sqlalchemy import create_engine

    return create_engine(url)


def _history_count(engine) -> int:
    from sqlalchemy import text

    with engine.connect() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM region_code_history")).scalar() or 0)


def _load_history_pairs(conn) -> tuple[list[str], list[str]]:
    from sqlalchemy import text

    from region_canonical import RESOLVE_CHANGE_TYPES

    types_sql = ",".join(f"'{t}'" for t in RESOLVE_CHANGE_TYPES)
    rows = conn.execute(
        text(
            f"""
            SELECT DISTINCT ON (from_code) from_code, to_code
            FROM region_code_history
            WHERE change_type IN ({types_sql})
            ORDER BY from_code, effective_from DESC, id DESC
            """
        )
    ).fetchall()
    from_codes = sorted({str(r.from_code).strip() for r in rows})
    to_codes = sorted({str(r.to_code).strip() for r in rows})
    return from_codes, to_codes


def _resolver_smoke(conn) -> dict:
    from region_canonical import RESOLVER_VERSION, expand_to_ledger_codes, is_canonical, resolve_to_canonical

    out: dict = {
        "resolver_version": RESOLVER_VERSION,
        "history_snapshot_rows": _history_count(conn.engine),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": [],
    }
    for case in PILOT_CASES:
        item = {"name": case["name"]}
        for label, hist, canon in (
            ("eup", case["hist_eup"], case["canon_eup"]),
            ("ri", case["hist_ri"], case["canon_ri"]),
        ):
            resolved = resolve_to_canonical(conn, [hist])
            item[f"{label}_resolve"] = resolved[0] if resolved else None
            item[f"{label}_ok"] = item[f"{label}_resolve"] == canon
            item[f"{label}_is_canonical_hist"] = is_canonical(conn, hist)
            item[f"{label}_is_canonical_canon"] = is_canonical(conn, canon)
            expanded = expand_to_ledger_codes(conn, [canon])
            item[f"{label}_expand_has_hist"] = hist in expanded or hist[:8] in expanded
            item[f"{label}_converted_codes"] = len(expanded)
        out["cases"].append(item)
    out["all_ok"] = all(
        c.get("eup_ok") and c.get("ri_ok") and c.get("eup_expand_has_hist") and c.get("ri_expand_has_hist")
        for c in out["cases"]
    )
    return out


def _mart_grain_audit(conn, as_of: date, from_codes: list[str], to_codes: list[str]) -> dict:
    """Mart must not contain historical from_codes; report grain statistics."""
    from sqlalchemy import text

    audit: dict = {
        "as_of": as_of.isoformat(),
        "tables": {},
        "gates": {},
        "pass": True,
        "failures": [],
    }

    def _gate(name: str, historical: int, *, allow_historical: bool = False) -> None:
        ok = allow_historical or historical == 0
        audit["gates"][name] = {"historical_rows": historical, "ok": ok}
        if not ok:
            audit["pass"] = False
            audit["failures"].append(f"{name}: historical_rows={historical} (expected 0)")

    if not from_codes:
        audit["note"] = "no history from_codes — mart grain gate skipped"
        return audit

    # land_upper_stats_v2 — eup/beop grain
    upper_hist = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)::int FROM land_upper_stats_v2
                WHERE region_code = ANY(:codes)
                  AND region_level IN ('eupmyeondong', 'beopjungri')
                  AND as_of_month = :a
                """
            ),
            {"codes": from_codes, "a": as_of},
        ).scalar()
        or 0
    )
    upper_canon = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)::int FROM land_upper_stats_v2
                WHERE region_code = ANY(:codes)
                  AND region_level IN ('eupmyeondong', 'beopjungri')
                  AND as_of_month = :a
                """
            ),
            {"codes": to_codes, "a": as_of},
        ).scalar()
        or 0
    )
    upper_dup = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)::int FROM (
                  SELECT region_level, region_code, as_of_month, window_years, col_axis,
                         zone_type, land_category
                  FROM land_upper_stats_v2
                  WHERE as_of_month = :a
                  GROUP BY 1,2,3,4,5,6,7
                  HAVING COUNT(*) > 1
                ) d
                """
            ),
            {"a": as_of},
        ).scalar()
        or 0
    )
    audit["tables"]["land_upper_stats_v2"] = {
        "canonical_rows": upper_canon,
        "historical_rows": upper_hist,
        "duplicated_grain_keys": upper_dup,
    }
    _gate("land_upper_stats_v2.historical", upper_hist)

    # land_annual_stats — beopjungri grain
    ann_hist = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)::int FROM land_annual_stats
                WHERE beopjungri_code = ANY(:codes)
                """
            ),
            {"codes": from_codes},
        ).scalar()
        or 0
    )
    ann_canon = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)::int FROM land_annual_stats
                WHERE beopjungri_code = ANY(:codes)
                """
            ),
            {"codes": to_codes},
        ).scalar()
        or 0
    )
    ann_dup = 0
    try:
        ann_dup = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int FROM (
                      SELECT beopjungri_code, calendar_year, col_axis, zone_type, land_category
                      FROM land_annual_stats
                      GROUP BY 1,2,3,4,5
                      HAVING COUNT(*) > 1
                    ) d
                    """
                )
            ).scalar()
            or 0
        )
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        audit.setdefault("warnings", []).append(f"land_annual_stats dup check: {exc}")
    audit["tables"]["land_annual_stats"] = {
        "canonical_rows": ann_canon,
        "historical_rows": ann_hist,
        "duplicated_grain_keys": ann_dup,
    }
    _gate("land_annual_stats.historical", ann_hist)

    # land_basic_stats_v2 — beopjungri grain (V2 basic)
    try:
        basic_hist = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int FROM land_basic_stats_v2
                    WHERE beopjungri_code = ANY(:codes) AND as_of_month = :a
                    """
                ),
                {"codes": from_codes, "a": as_of},
            ).scalar()
            or 0
        )
        basic_canon = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int FROM land_basic_stats_v2
                    WHERE beopjungri_code = ANY(:codes) AND as_of_month = :a
                    """
                ),
                {"codes": to_codes, "a": as_of},
            ).scalar()
            or 0
        )
        audit["tables"]["land_basic_stats_v2"] = {
            "canonical_rows": basic_canon,
            "historical_rows": basic_hist,
        }
        _gate("land_basic_stats_v2.historical", basic_hist)
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        audit["tables"]["land_basic_stats_v2"] = {"skipped": str(exc)}

    # orphan: to_code not in active region_codes
    try:
        orphan = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int
                    FROM unnest(CAST(:codes AS text[])) AS c(code)
                    WHERE NOT EXISTS (
                      SELECT 1 FROM region_codes rc
                      WHERE COALESCE(rc.is_active, TRUE)
                        AND btrim(rc.beopjungri_code::text) = c.code
                    )
                    """
                ),
                {"codes": to_codes[:500]},
            ).scalar()
            or 0
        )
        audit["orphan_canonical_codes"] = orphan
        if orphan:
            audit["pass"] = False
            audit["failures"].append(f"orphan_canonical_codes={orphan} (to_code missing in active region_codes)")
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        audit["orphan_canonical_codes"] = None
        audit.setdefault("warnings", []).append(f"orphan check skipped: {exc}")

    # pilot spot checks (readable summary)
    audit["pilot"] = {}
    for case in PILOT_CASES:
        canon_eup, hist_eup = case["canon_eup"], case["hist_eup"]
        canon_ri, hist_ri = case["canon_ri"], case["hist_ri"]
        u_can = conn.execute(
            text(
                """
                SELECT count FROM land_upper_stats_v2
                WHERE region_level='eupmyeondong' AND region_code=:c
                  AND as_of_month=:a AND window_years=3 AND col_axis='category'
                  AND zone_type='ALL' AND land_category='ALL'
                """
            ),
            {"c": canon_eup, "a": as_of},
        ).scalar()
        u_hist = conn.execute(
            text(
                """
                SELECT count FROM land_upper_stats_v2
                WHERE region_level='eupmyeondong' AND region_code=:c
                  AND as_of_month=:a AND window_years=3 AND col_axis='category'
                  AND zone_type='ALL' AND land_category='ALL'
                """
            ),
            {"c": hist_eup, "a": as_of},
        ).scalar()
        audit["pilot"][case["name"]] = {
            "upper_canonical_count": int(u_can or 0),
            "upper_historical_count": int(u_hist or 0),
        }
        if int(u_hist or 0) > 0:
            audit["pass"] = False
            audit["failures"].append(f"pilot {case['name']}: upper historical_count={int(u_hist or 0)}")

    return audit


def _stable_region_sample(conn, from_codes: list[str], to_codes: list[str], n: int = 10) -> list[str]:
    """Beopjungri codes with no history involvement — deploy regression anchors."""
    from sqlalchemy import text

    hist = set(from_codes) | set(to_codes)
    rows = conn.execute(
        text(
            """
            SELECT btrim(beopjungri_code::text) AS code
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND beopjungri_code IS NOT NULL
              AND btrim(beopjungri_code::text) <> ''
            ORDER BY random()
            LIMIT :lim
            """
        ),
        {"lim": n * 3},
    ).fetchall()
    out: list[str] = []
    for r in rows:
        c = str(r.code).strip()
        if c in hist or c in out:
            continue
        out.append(c)
        if len(out) >= n:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-06-01")
    ap.add_argument("--json", action="store_true", help="print JSON only")
    ap.add_argument(
        "--allow-historical-mart",
        action="store_true",
        help="warn only (do not fail) if historical mart rows exist — pre-migration use",
    )
    args = ap.parse_args()
    as_of = date.fromisoformat(args.as_of)

    from db_utils import get_engine
    from region_canonical import RESOLVER_VERSION

    land_eng = get_engine()
    built_url = os.environ.get("BUILT_DATABASE_URL", "")
    coll_url = os.environ.get("COLLECTIVE_DATABASE_URL", "")

    report: dict = {
        "status": "FAIL",
        "as_of": as_of.isoformat(),
        "resolver_version": RESOLVER_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "history_counts": {},
        "resolver": {},
        "mart_audit": {},
        "stable_region_sample": [],
    }

    report["history_counts"]["land"] = _history_count(land_eng)
    built_eng = _engine_for_url(built_url)
    coll_eng = _engine_for_url(coll_url)
    if built_eng is not None:
        report["history_counts"]["built"] = _history_count(built_eng)
    if coll_eng is not None:
        report["history_counts"]["collective"] = _history_count(coll_eng)

    hc = report["history_counts"]
    if "built" in hc:
        report["history_parity_ok"] = hc["land"] == hc["built"]
        if not report["history_parity_ok"]:
            report.setdefault("failures", []).append(
                f"history parity land={hc['land']} built={hc['built']}"
            )
    else:
        report["history_parity_ok"] = None

    with land_eng.connect() as conn:
        from_codes, to_codes = _load_history_pairs(conn)
        report["history_from_codes"] = len(from_codes)
        report["history_to_codes"] = len(to_codes)
        report["resolver"] = _resolver_smoke(conn)
        try:
            report["mart_audit"] = _mart_grain_audit(conn, as_of, from_codes, to_codes)
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            report["mart_audit"] = {"error": str(exc), "pass": False}
            report.setdefault("failures", []).append(f"mart_audit error: {exc}")
        try:
            report["stable_region_sample"] = _stable_region_sample(conn, from_codes, to_codes)
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            report["stable_region_sample"] = []
            report.setdefault("warnings", []).append(f"stable_region_sample: {exc}")

    failures: list[str] = list(report.get("failures", []))
    if not report["resolver"].get("all_ok"):
        failures.append("resolver smoke failed")
    mart = report.get("mart_audit") or {}
    if mart.get("error"):
        failures.append(f"mart_audit: {mart['error']}")
    elif not mart.get("pass") and not args.allow_historical_mart:
        failures.extend(mart.get("failures") or ["mart grain audit failed"])
    elif not mart.get("pass") and args.allow_historical_mart:
        report["mart_audit"]["gate_mode"] = "warn_only"

    if report.get("history_parity_ok") is False:
        failures.append("history parity land != built")

    report["failures"] = failures
    report["status"] = "PASS" if not failures else "FAIL"

    lines = [
        f"# Canonical resolver migration verify — **{report['status']}**",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- resolver_version: **{RESOLVER_VERSION}**",
        f"- as_of_month: {as_of.isoformat()}",
        f"- history land={hc.get('land')} built={hc.get('built', 'n/a')} collective={hc.get('collective', 'n/a')}",
        f"- history parity (land=built): **{report.get('history_parity_ok')}**",
        f"- resolver smoke: **{report['resolver'].get('all_ok')}**",
        "",
        "## Mart grain audit",
        "",
    ]
    for tbl, stats in (mart.get("tables") or {}).items():
        lines.append(f"- **{tbl}**: {stats}")
    if mart.get("orphan_canonical_codes") is not None:
        lines.append(f"- orphan_canonical_codes: **{mart.get('orphan_canonical_codes')}**")
    lines.extend(["", "## Pilot upper (canonical vs historical count)", ""])
    for name, p in (mart.get("pilot") or {}).items():
        lines.append(f"- {name}: {p}")
    if failures:
        lines.extend(["", "## Failures", ""])
        for f in failures:
            lines.append(f"- {f}")
    lines.extend(["", "## Stable region sample (no history)", ""])
    lines.append(", ".join(report.get("stable_region_sample") or []) or "(none)")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        text_out = "\n".join(lines) + "\n"
        try:
            print(text_out)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(text_out.encode("utf-8", errors="replace"))
        print(f"wrote {OUT_MD}")
        print(f"wrote {OUT_JSON}")

    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
