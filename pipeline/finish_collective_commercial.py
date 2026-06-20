#!/usr/bin/env python3
"""
비주거 집합(상가·공장) 재구축 마무리 — DB·mart 스모크 검증.

실행:
    cd pipeline
    python finish_collective_commercial.py

    # mart 재빌드 포함
    python finish_collective_commercial.py --rebuild

    # API 스모크 (백엔드 :8000 기동 중일 때)
    python finish_collective_commercial.py --api-base http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
PIPE = REPO / "pipeline"
LOG_DIR = REPO / "logs"
SNAP_DIR = PIPE / "clean_snapshots" / "collective_commercial"
PY = sys.executable

sys.path.insert(0, str(PIPE / "collective"))
from db_utils import get_collective_engine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MIN_TX = 250_000
MIN_CLUSTERS = 15_000
MIN_ANNUAL_PRE2021 = 50_000
MIN_ANNUAL_POST2020 = 10_000


def _run(cmd: list[str]) -> None:
    log.info("RUN %s", " ".join(cmd))
    subprocess.run(cmd, cwd=str(PIPE), check=True)


def _counts(engine) -> dict:
    with engine.connect() as conn:
        tx = conn.execute(text("SELECT COUNT(*) FROM collective_commercial_transactions")).scalar()
        clusters = conn.execute(text("SELECT COUNT(*) FROM commercial_clusters")).scalar()
        ccs = conn.execute(
            text("SELECT to_regclass('public.collective_cluster_stats') IS NOT NULL")
        ).scalar()
        ccr = conn.execute(
            text("SELECT to_regclass('public.collective_cluster_rolling_stats') IS NOT NULL")
        ).scalar()
        cca = conn.execute(
            text("SELECT to_regclass('public.collective_cluster_annual_stats') IS NOT NULL")
        ).scalar()
        mart_n = conn.execute(text("SELECT COUNT(*) FROM collective_cluster_stats")).scalar() if ccs else 0
        rolling_n = (
            conn.execute(text("SELECT COUNT(*) FROM collective_cluster_rolling_stats")).scalar() if ccr else 0
        )
        annual_n = (
            conn.execute(text("SELECT COUNT(*) FROM collective_cluster_annual_stats")).scalar() if cca else 0
        )
        annual_pre = (
            conn.execute(
                text("SELECT COUNT(*) FROM collective_cluster_annual_stats WHERE contract_year < 2021")
            ).scalar()
            if cca
            else 0
        )
        annual_post = (
            conn.execute(
                text("SELECT COUNT(*) FROM collective_cluster_annual_stats WHERE contract_year >= 2021")
            ).scalar()
            if cca
            else 0
        )
        year_range = (
            conn.execute(
                text(
                    """
                    SELECT MIN(contract_year)::int, MAX(contract_year)::int
                    FROM collective_cluster_annual_stats
                    """
                )
            ).first()
            if cca and annual_n
            else (None, None)
        )
        sample = (
            conn.execute(
                text(
                    """
                    SELECT cluster_key, COUNT(*)::int AS n_years,
                           MIN(contract_year)::int AS y_min,
                           MAX(contract_year)::int AS y_max
                    FROM collective_cluster_annual_stats
                    GROUP BY cluster_key
                    HAVING COUNT(*) >= 10 AND MIN(contract_year) <= 2012
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                    """
                )
            ).mappings().first()
            if cca
            else None
        )
        snap = (
            conn.execute(
                text(
                    """
                    SELECT as_of_month, window_years, COUNT(*)::int AS n
                    FROM collective_cluster_stats
                    GROUP BY 1, 2
                    ORDER BY 1 DESC, 2 DESC
                    LIMIT 4
                    """
                )
            ).mappings().all()
            if ccs and mart_n
            else []
        )
    return {
        "transactions": int(tx or 0),
        "clusters": int(clusters or 0),
        "cluster_stats_rows": int(mart_n or 0),
        "cluster_rolling_rows": int(rolling_n or 0),
        "cluster_annual_rows": int(annual_n or 0),
        "annual_pre2021": int(annual_pre or 0),
        "annual_post2020": int(annual_post or 0),
        "annual_year_min": year_range[0],
        "annual_year_max": year_range[1],
        "sample_cluster": dict(sample) if sample else None,
        "mart_snapshots": [
            {
                "as_of_month": r["as_of_month"].isoformat() if r["as_of_month"] else None,
                "window_years": int(r["window_years"]),
                "n": int(r["n"]),
            }
            for r in snap
        ],
    }


def _api_smoke(base: str, cluster_key: str | None) -> dict:
    out: dict = {}
    health_url = f"{base.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(health_url, timeout=8) as resp:
            out["health"] = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        out["health_error"] = str(exc)
        return out

    if not cluster_key:
        return out

    by_year_url = (
        f"{base.rstrip('/')}/api/collective/commercial/clusters/{cluster_key}/stats/by-year"
    )
    try:
        with urllib.request.urlopen(by_year_url, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            pts = data.get("points") or []
            out["by_year"] = {
                "data_source": data.get("data_source"),
                "n_points": len(pts),
                "year_min": min(p["year"] for p in pts) if pts else None,
                "year_max": max(p["year"] for p in pts) if pts else None,
            }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        out["by_year_error"] = str(exc)
    return out


def _assert_ok(summary: dict) -> list[str]:
    errors: list[str] = []
    if summary["transactions"] < MIN_TX:
        errors.append(f"transactions={summary['transactions']:,} < {MIN_TX:,}")
    if summary["clusters"] < MIN_CLUSTERS:
        errors.append(f"clusters={summary['clusters']:,} < {MIN_CLUSTERS:,}")
    if summary["cluster_stats_rows"] <= 0:
        errors.append("collective_cluster_stats empty")
    if summary["cluster_rolling_rows"] <= 0:
        errors.append("collective_cluster_rolling_stats empty")
    if summary["cluster_annual_rows"] <= 0:
        errors.append("collective_cluster_annual_stats empty")
    if summary["annual_pre2021"] < MIN_ANNUAL_PRE2021:
        errors.append(f"annual pre-2021={summary['annual_pre2021']:,} < {MIN_ANNUAL_PRE2021:,}")
    if summary["annual_post2020"] < MIN_ANNUAL_POST2020:
        errors.append(f"annual 2021+={summary['annual_post2020']:,} < {MIN_ANNUAL_POST2020:,}")
    if summary["annual_year_min"] is None or summary["annual_year_min"] > 2010:
        errors.append(f"annual year_min={summary['annual_year_min']} (expected 2010)")
    if summary["sample_cluster"] is None:
        errors.append("no sample cluster with 10+ years including 2010~2012")
    return errors


def main() -> None:
    p = argparse.ArgumentParser(description="비주거 집합 재구축 finish 검증")
    p.add_argument("--rebuild", action="store_true", help="rebuild_collective_commercial.py 실행 후 검증")
    p.add_argument("--skip-long-term", action="store_true")
    p.add_argument("--api-base", default=None, help="예: http://127.0.0.1:8000")
    args = p.parse_args()

    if args.rebuild:
        cmd = [PY, "rebuild_collective_commercial.py"]
        if args.skip_long_term:
            cmd.append("--skip-long-term")
        _run(cmd)

    engine = get_collective_engine()
    summary = _counts(engine)
    summary["finished_at"] = datetime.now().isoformat()

    if args.api_base:
        ck = (summary.get("sample_cluster") or {}).get("cluster_key")
        summary["api"] = _api_smoke(args.api_base, ck)

    errors = _assert_ok(summary)
    if args.api_base and summary.get("api", {}).get("by_year"):
        by = summary["api"]["by_year"]
        if by.get("data_source") != "mart":
            errors.append(f"API by-year data_source={by.get('data_source')} (expected mart)")
        if (by.get("year_min") or 9999) > 2010:
            errors.append(f"API by-year year_min={by.get('year_min')} (expected 2010)")

    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out = SNAP_DIR / "finish_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("summary: %s", out)
    log.info(
        "tx=%s clusters=%s mart=%s rolling=%s annual=%s (%s~%s, pre2021=%s post2020=%s)",
        f"{summary['transactions']:,}",
        f"{summary['clusters']:,}",
        f"{summary['cluster_stats_rows']:,}",
        f"{summary['cluster_rolling_rows']:,}",
        f"{summary['cluster_annual_rows']:,}",
        summary["annual_year_min"],
        summary["annual_year_max"],
        f"{summary['annual_pre2021']:,}",
        f"{summary['annual_post2020']:,}",
    )
    if summary.get("sample_cluster"):
        log.info("sample_cluster: %s", summary["sample_cluster"])

    if errors:
        for e in errors:
            log.error("FAIL: %s", e)
        sys.exit(1)
    log.info("commercial rebuild finish OK — Promote 전 UI 스모크 권장")


if __name__ == "__main__":
    main()
