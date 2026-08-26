"""복합 enrichment 동결 검증 (P3.3).

확정 행의 recovered_lot · structure_group · zone_labels 지문 비교.
고아·2019+ 커버리지·상위 용도지역은 리포트. 값 변경이 있으면 실패.

  py scripts/monthly/verify_built_enrichment_freeze.py --dump logs/enr_before.jsonl
  py scripts/monthly/verify_built_enrichment_freeze.py --before logs/enr_before.jsonl --output logs/enr_freeze.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "pipeline" / "built"))

from db_utils import get_built_engine  # noqa: E402

GATE_N = 498_568
GATE_TX = 665_030
GATE_PCT = 75.0
COARSE = ("도시지역", "도시지역기타", "비도시지역", "관리지역", "도시관리계획 입안중")

UNIVERSE_SQL = """
SELECT COUNT(*) FROM built_transactions
WHERE is_valid AND gross_area > 0 AND contract_year >= :min_year
"""
ENR_2019_SQL = """
SELECT COUNT(*) FROM built_transaction_enrichment e
JOIN built_transactions t ON t.transaction_hash = e.transaction_hash
WHERE t.contract_year >= :min_year
"""
ORPHAN_SQL = """
SELECT COUNT(*) FROM built_transaction_enrichment e
WHERE NOT EXISTS (
    SELECT 1 FROM built_transactions t WHERE t.transaction_hash = e.transaction_hash
)
"""
COARSE_SQL = """
SELECT COUNT(*) FROM built_transaction_enrichment
WHERE zone_labels[1] = ANY(:coarse)
"""
DUMP_SQL = """
SELECT transaction_hash,
       COALESCE(recovered_lot, ''),
       COALESCE(structure_group, ''),
       COALESCE(array_to_string(zone_labels, '|'), '')
FROM built_transaction_enrichment
"""


def fingerprint(lot: str, structure_group: str, zones: str) -> str:
    raw = f"{lot}|{structure_group}|{zones}".encode("utf-8")
    return hashlib.md5(raw, usedforsecurity=False).hexdigest()


def dump_fingerprints(path: Path) -> int:
    eng = get_built_engine()
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with eng.connect() as conn, path.open("w", encoding="utf-8") as fh:
        for h, lot, sg, z in conn.execute(text(DUMP_SQL)):
            fh.write(f"{h}\t{fingerprint(str(lot), str(sg), str(z))}\n")
            n += 1
    return n


def load_fingerprints(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        h, fp = line.split("\t", 1)
        h, fp = h.strip(), fp.strip()
        if h and fp:
            out[h] = fp
    return out


def current_fingerprints() -> dict[str, str]:
    eng = get_built_engine()
    out: dict[str, str] = {}
    with eng.connect() as conn:
        for h, lot, sg, z in conn.execute(text(DUMP_SQL)):
            out[str(h)] = fingerprint(str(lot), str(sg), str(z))
    return out


def compare_fingerprints(before: dict[str, str], after: dict[str, str]) -> dict[str, int]:
    both = set(before) & set(after)
    changed = sum(1 for h in both if before[h] != after[h])
    disappeared = len(set(before) - set(after))
    inserted = len(set(after) - set(before))
    return {
        "n_before": len(before),
        "n_after": len(after),
        "changed": changed,
        "disappeared": disappeared,
        "inserted": inserted,
    }


def collect_report(*, min_year: int = 2019) -> dict[str, Any]:
    eng = get_built_engine()
    with eng.connect() as conn:
        n_tx = int(conn.execute(text(UNIVERSE_SQL), {"min_year": min_year}).scalar() or 0)
        n_enr = int(conn.execute(text(ENR_2019_SQL), {"min_year": min_year}).scalar() or 0)
        orphans = int(conn.execute(text(ORPHAN_SQL)).scalar() or 0)
        coarse = int(conn.execute(text(COARSE_SQL), {"coarse": list(COARSE)}).scalar() or 0)
    pct = round(100.0 * n_enr / n_tx, 1) if n_tx else 0.0
    return {
        "n_tx_2019": n_tx,
        "n_enr_2019": n_enr,
        "confirmed_pct": pct,
        "gate_n": GATE_N,
        "gate_tx": GATE_TX,
        "gate_pct": GATE_PCT,
        "orphans": orphans,
        "coarse_primary": coarse,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="built_transaction_enrichment 동결 검증")
    p.add_argument("--dump", type=Path, help="현재 지문을 JSONL(탭)로 저장하고 종료")
    p.add_argument("--before", type=Path, help="cycle 시작 지문")
    p.add_argument("--output", type=Path)
    p.add_argument("--min-year", type=int, default=2019)
    p.add_argument("--fail-on-change", action="store_true", default=True)
    p.add_argument("--no-fail-on-change", action="store_false", dest="fail_on_change")
    p.add_argument("--fail-on-orphan", action="store_true")
    p.add_argument("--fail-on-coarse", action="store_true")
    args = p.parse_args()

    if args.dump:
        n = dump_fingerprints(args.dump)
        print(f"dumped {n:,} fingerprints → {args.dump}")
        return

    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        **collect_report(min_year=args.min_year),
    }
    if args.before and args.before.is_file():
        cmp = compare_fingerprints(load_fingerprints(args.before), current_fingerprints())
        report["freeze"] = cmp
    else:
        report["freeze"] = None
        print("warn: --before 없음. 값 변경 비교 생략", flush=True)

    print(
        f"[동결] enr_2019={report['n_enr_2019']:,}/{report['n_tx_2019']:,} "
        f"{report['confirmed_pct']}% (gate {GATE_PCT}%) "
        f"orphans={report['orphans']:,} coarse_primary={report['coarse_primary']:,}",
        flush=True,
    )
    if report["freeze"]:
        fz = report["freeze"]
        print(
            f"[동결] changed={fz['changed']:,} disappeared={fz['disappeared']:,} "
            f"inserted={fz['inserted']:,}",
            flush=True,
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.output}", flush=True)

    fail = False
    if args.fail_on_change and report["freeze"] and report["freeze"]["changed"]:
        print(f"FAIL: 확정 행 값 변경 {report['freeze']['changed']:,}", flush=True)
        fail = True
    if args.fail_on_change and report["freeze"] and report["freeze"]["disappeared"]:
        print(f"FAIL: 확정 행 삭제 {report['freeze']['disappeared']:,}", flush=True)
        fail = True
    if args.fail_on_orphan and report["orphans"]:
        print(f"FAIL: 고아 enrichment {report['orphans']:,}", flush=True)
        fail = True
    if args.fail_on_coarse and report["coarse_primary"]:
        print(f"FAIL: 상위 용도지역 대표 {report['coarse_primary']:,}", flush=True)
        fail = True
    if fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
