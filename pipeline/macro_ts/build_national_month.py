"""raw CSV → macro_ts_stats.national_month."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from macro_ts.csv_month import iter_source_files, parse_job  # noqa: E402
from macro_ts.gate_national_month import evaluate_gate  # noqa: E402

log = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS national_month (
    mix_type text NOT NULL,
    ym integer NOT NULL,
    n bigint NOT NULL,
    amount_10k double precision NOT NULL,
    source text NOT NULL,
    built_at timestamptz NOT NULL,
    PRIMARY KEY (mix_type, ym)
);
"""


def _default_url() -> str:
    try:
        sys.path.insert(0, str(REPO / "backend"))
        from app.config import settings  # noqa: WPS433

        url = (settings.macro_ts_database_url or "").strip()
        if url:
            return url
        base = settings.database_url
        if "/land_stats" in base:
            return base.replace("/land_stats", "/macro_ts_stats")
        return base.rsplit("/", 1)[0] + "/macro_ts_stats"
    except Exception:  # noqa: BLE001
        return "postgresql+psycopg2://postgres:password@localhost:5432/macro_ts_stats"


def _ensure_db(url: str) -> None:
    if "postgresql" not in url:
        return
    name = url.rsplit("/", 1)[-1]
    admin = url.rsplit("/", 1)[0] + "/postgres"
    eng = create_engine(admin, isolation_level="AUTOCOMMIT")
    with eng.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"),
            {"n": name},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
            log.info("created database %s", name)
    eng.dispose()


def build(*, repo: Path, url: str, workers: int, today: date | None = None) -> dict:
    today = today or date.today()
    cur = today.year * 100 + today.month
    jobs: list[tuple[str, str, str]] = []
    for path, mix, source in iter_source_files(repo):
        jobs.append((str(path), mix, source))
    log.info("csv files %s workers %s", len(jobs), workers)
    pipe = str(REPO / "pipeline")
    os.environ["PYTHONPATH"] = pipe + os.pathsep + os.environ.get("PYTHONPATH", "")
    acc: dict[tuple[str, int], list[float]] = defaultdict(lambda: [0.0, 0.0])
    src_of: dict[tuple[str, int], str] = {}
    errors: list[str] = []
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(parse_job, path): (path, mix, source) for path, mix, source in jobs}
        for fut in as_completed(futs):
            path, mix, source = futs[fut]
            _p, cells, err = fut.result()
            done += 1
            if done % 50 == 0 or done == len(jobs):
                log.info("parsed %s/%s", done, len(jobs))
            if err:
                errors.append(f"{path}: {err}")
                continue
            for ym, (n, amt) in cells.items():
                if ym >= cur:
                    continue
                key = (mix, ym)
                acc[key][0] += n
                acc[key][1] += amt
                src_of[key] = source
    _ensure_db(url)
    eng = create_engine(url)
    built_at = datetime.now(timezone.utc)
    rows = [
        {
            "mix_type": mix,
            "ym": ym,
            "n": int(n_amt[0]),
            "amount_10k": float(n_amt[1]),
            "source": src_of[(mix, ym)],
            "built_at": built_at,
        }
        for (mix, ym), n_amt in acc.items()
    ]
    with eng.begin() as conn:
        conn.execute(text(DDL))
        conn.execute(text("TRUNCATE national_month"))
        if rows:
            conn.execute(
                text(
                    """
                    INSERT INTO national_month (mix_type, ym, n, amount_10k, source, built_at)
                    VALUES (:mix_type, :ym, :n, :amount_10k, :source, :built_at)
                    """
                ),
                rows,
            )
    log.info("inserted %s rows errors %s", len(rows), len(errors))
    by_type: dict[str, dict[int, dict[str, float]]] = defaultdict(dict)
    for (mix, ym), n_amt in acc.items():
        by_type[mix][ym] = {"count": n_amt[0], "amount": n_amt[1]}
    gate = evaluate_gate(by_type)
    if errors:
        gate["errors"] = errors[:30]
        gate["error_n"] = len(errors)
    return {"rows": len(rows), "files": len(jobs), "gate": gate}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=REPO)
    p.add_argument("--url", default="")
    p.add_argument("--workers", type=int, default=6)
    args = p.parse_args()
    url = args.url or _default_url()
    out = build(repo=args.repo, url=url, workers=args.workers)
    gate = out["gate"]
    log.info("gate ok=%s fail=%s", gate.get("ok"), gate.get("failures"))
    if not gate.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
