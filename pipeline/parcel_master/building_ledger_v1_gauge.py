"""Gauge the national building title ledger before building it (plan step 3).

Reads the three title and summary snapshots. Writes counts only; no management key
or parcel number is written. Checks file hashes against the earlier Cheongju evidence.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from parcel_master.paths import SNAPSHOTS, bldrgst_dir, title_path  # noqa: E402

EVIDENCE = ROOT / "docs" / "lab" / "cheongju_relation_source_evidence.json"
OUT = ROOT / "docs" / "lab" / "building_ledger_v1_gauge_20261017.json"


def summary_path(snapshot: str) -> Path:
    tag = SNAPSHOTS[snapshot]
    return bldrgst_dir() / f"국토교통부_건축물대장_총괄표제부+({tag})" / "mart_djy_02.txt"


def identity_status(sg: str, bd: str, gb: str, bun: str, ji: str) -> str:
    sg, bd, gb, bun, ji = (v.strip() for v in (sg, bd, gb, bun, ji))
    if len(bd) == 10 and bd.isdigit():
        bjd = bd
    elif len(sg) == 5 and sg.isdigit() and bd.isdigit() and len(bd) <= 5:
        bjd = sg + bd.zfill(5)
    else:
        return "invalid_bjd"
    if len(bjd) != 10:
        return "invalid_bjd"
    if gb not in ("0", "1"):
        return "unknown_land_type"
    if not (bun.isdigit() and len(bun) <= 4):
        return "invalid_main_lot"
    if not (ji.isdigit() and len(ji) <= 4):
        return "invalid_sub_lot"
    if bun.lstrip("0") == "":
        return "zero_main_lot"
    return "canonical_address"


def scan(
    path: Path, kind: str, previous: dict[str, int] | None, prev_sample: dict[str, list[bytes]] | None
) -> tuple[dict, dict[str, int], dict[str, list[bytes]]]:
    sha = hashlib.sha256()
    rows = 0
    cols = Counter()
    status = Counter()
    ledger_kind = Counter()
    sido = Counter()
    pk_seen: dict[str, int] = {}
    dup_rows = 0
    same_as_prev = 0
    changed_vs_prev = 0
    new_vs_prev = 0
    changed_cols = Counter()
    raw_bytes = 0
    start = 8 if kind == "title" else 10
    sample: dict[str, list[bytes]] = {}
    with path.open("rb") as stream:
        for line in stream:
            rows += 1
            sha.update(line)
            body = line.rstrip(b"\r\n")
            raw_bytes += len(body)
            parts = body.split(b"|")
            cols[len(parts)] += 1
            pk = parts[0].decode("ascii", "replace").strip()
            digest = int.from_bytes(hashlib.blake2b(body, digest_size=8).digest(), "big")
            if pk in pk_seen:
                dup_rows += 1
            pk_seen[pk] = digest
            if len(parts) > start + 4:
                ident = [p.decode("ascii", "replace") for p in parts[start:start + 5]]
                status[identity_status(*ident)] += 1
                sido[ident[0].strip()[:2]] += 1
                if ident[0].strip().startswith("4311"):
                    sample[pk] = parts
                    old_parts = (prev_sample or {}).get(pk)
                    if old_parts is not None and old_parts != parts and len(old_parts) == len(parts):
                        for i, (a, b) in enumerate(zip(old_parts, parts)):
                            if a != b:
                                changed_cols[i] += 1
            if kind == "title" and len(parts) > 2:
                ledger_kind[parts[2].decode("utf-8", "replace").strip()] += 1
            if previous is not None:
                old = previous.get(pk)
                if old is None:
                    new_vs_prev += 1
                elif old == digest:
                    same_as_prev += 1
                else:
                    changed_vs_prev += 1
            if rows % 2_000_000 == 0:
                print(f"{path.parent.name} rows={rows}", flush=True)
    info = {
        "file": f"{path.parent.name}/{path.name}",
        "bytes": path.stat().st_size,
        "sha256": sha.hexdigest(),
        "rows": rows,
        "raw_bytes_without_newline": raw_bytes,
        "column_counts": dict(cols),
        "unique_pk": len(pk_seen),
        "duplicate_pk_rows": dup_rows,
        "identity_status": dict(status.most_common()),
        "sido_prefix": dict(sorted(sido.items())),
    }
    if kind == "title":
        info["ledger_kind"] = dict(ledger_kind.most_common())
    if previous is not None:
        info["vs_previous_snapshot"] = {
            "same_line": same_as_prev,
            "changed_line": changed_vs_prev,
            "new_pk": new_vs_prev,
            "gone_pk": len(set(previous) - set(pk_seen)),
            "cheongju_changed_column_index": dict(changed_cols.most_common(20)),
        }
    return info, pk_seen, sample


def main() -> None:
    started = time.time()
    evidence = {
        (r["source"], r["snapshot"]): r
        for r in json.loads(EVIDENCE.read_text(encoding="utf-8"))["raw_inventory"]
        if r["source"] in ("title", "summary")
    }
    report: dict = {"run_date": "2026-10-17", "title": {}, "summary": {}}
    for kind, path_of in (("title", title_path), ("summary", summary_path)):
        previous = None
        prev_sample = None
        for snapshot in sorted(SNAPSHOTS):
            info, seen, prev_sample = scan(path_of(snapshot), kind, previous, prev_sample)
            prior = evidence.get((kind, snapshot))
            info["matches_cheongju_evidence"] = bool(
                prior and prior["sha256"] == info["sha256"] and prior["rows"] == info["rows"]
            )
            report[kind][snapshot] = info
            previous = seen
            print(f"{kind} {snapshot} rows={info['rows']} unique_pk={info['unique_pk']}", flush=True)
        del previous
    report["elapsed_seconds"] = round(time.time() - started, 1)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
