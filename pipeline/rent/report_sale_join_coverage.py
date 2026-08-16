#!/usr/bin/env python3
"""집합 매매 × 주거 임대 building 매칭률. 원장 저장된 building_key만 사용."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from collective.building_keys import normalize_name  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from rent.db_utils import get_rent_engine  # noqa: E402

ASSETS = ("apartment", "rowhouse", "officetel")
OUT = Path(__file__).resolve().parent / "_sale_join_coverage.json"

BUILDING_SQL = """
SELECT
  building_key,
  asset_type,
  MIN(NULLIF(btrim(building_name), '')) AS building_name,
  MIN(NULLIF(btrim(addr1), '')) AS addr1,
  MIN(NULLIF(btrim(addr2), '')) AS addr2,
  MIN(NULLIF(btrim(addr3), '')) AS addr3,
  MIN(NULLIF(btrim(beopjungri_code), '')) AS beopjungri_code
FROM {table}
WHERE is_valid = true
  AND asset_type IN ('apartment', 'rowhouse', 'officetel')
  AND NULLIF(btrim(building_key::text), '') IS NOT NULL
GROUP BY building_key, asset_type
"""


def _fetch(engine, table: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(BUILDING_SQL.format(table=table))).mappings().all()
    return [dict(r) for r in rows]


def _aux_key(row: dict) -> str | None:
    name = normalize_name(row.get("building_name"))
    if not name:
        return None
    at = row["asset_type"]
    code = (row.get("beopjungri_code") or "").strip()
    if code:
        return f"{at}|{code}|{name}"
    a1 = normalize_name(row.get("addr1"))
    a2 = normalize_name(row.get("addr2"))
    a3 = normalize_name(row.get("addr3"))
    if not (a1 and a2 and a3):
        return None
    return f"{at}|{a1}|{a2}|{a3}|{name}"


def _empty_bucket() -> dict:
    return {
        "sale_n": 0,
        "rent_n": 0,
        "exact": 0,
        "aux_1to1": 0,
        "aux_ambiguous": 0,
        "sale_only": 0,
        "rent_only": 0,
        "sale_exact_pct": None,
        "sale_joined_pct": None,
    }


def _pct(n: int, d: int) -> float | None:
    if d <= 0:
        return None
    return round(100.0 * n / d, 1)


def main() -> None:
    sale_rows = _fetch(get_collective_engine(), "collective_transactions")
    rent_rows = _fetch(get_rent_engine(), "rent_transactions")

    sale_by_key: dict[tuple[str, str], dict] = {}
    rent_by_key: dict[tuple[str, str], dict] = {}
    for r in sale_rows:
        sale_by_key[(r["asset_type"], r["building_key"])] = r
    for r in rent_rows:
        rent_by_key[(r["asset_type"], r["building_key"])] = r

    exact_keys = set(sale_by_key) & set(rent_by_key)
    sale_left = {k: sale_by_key[k] for k in sale_by_key if k not in exact_keys}
    rent_left = {k: rent_by_key[k] for k in rent_by_key if k not in exact_keys}

    rent_aux: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for k, row in rent_left.items():
        aux = _aux_key(row)
        if aux:
            rent_aux[aux].append(k)

    aux_1to1: set[tuple[str, str]] = set()
    aux_amb: set[tuple[str, str]] = set()
    miss_examples: list[dict] = []

    for k, row in sale_left.items():
        aux = _aux_key(row)
        cands = rent_aux.get(aux or "", [])
        if len(cands) == 1:
            aux_1to1.add(k)
        elif len(cands) > 1:
            aux_amb.add(k)
        elif len(miss_examples) < 12:
            miss_examples.append(
                {
                    "asset_type": row["asset_type"],
                    "sale_key": row["building_key"],
                    "name": row.get("building_name"),
                    "addr": " ".join(x for x in (row.get("addr1"), row.get("addr2"), row.get("addr3")) if x),
                    "beopjungri_code": row.get("beopjungri_code"),
                }
            )

    joined_sale = {k[0] for k in exact_keys}  # placeholder unused
    del joined_sale

    by_asset: dict[str, dict] = {a: _empty_bucket() for a in ASSETS}
    by_asset["all"] = _empty_bucket()

    def add(asset: str, field: str, n: int = 1) -> None:
        by_asset[asset][field] += n
        by_asset["all"][field] += n

    for at, _bk in sale_by_key:
        add(at, "sale_n")
    for at, _bk in rent_by_key:
        add(at, "rent_n")
    for at, _bk in exact_keys:
        add(at, "exact")
    for at, _bk in aux_1to1:
        add(at, "aux_1to1")
    for at, _bk in aux_amb:
        add(at, "aux_ambiguous")

    exact_or_aux = exact_keys | aux_1to1
    for k in sale_by_key:
        if k not in exact_or_aux:
            add(k[0], "sale_only")
    rent_aux_used = set()
    for k in aux_1to1:
        aux = _aux_key(sale_left[k])
        if aux and rent_aux.get(aux):
            rent_aux_used.add(rent_aux[aux][0])
    for k in rent_by_key:
        if k in exact_keys or k in rent_aux_used:
            continue
        add(k[0], "rent_only")

    for b in by_asset.values():
        b["sale_exact_pct"] = _pct(b["exact"], b["sale_n"])
        b["sale_joined_pct"] = _pct(b["exact"] + b["aux_1to1"], b["sale_n"])

    report = {
        "as_of": date.today().isoformat(),
        "note": "저장된 building_key 정확 층 + 법정동(또는 시·시군구·동)+단지명 보조 1:1. SQL fallback 키 미사용.",
        "assets": list(ASSETS),
        "by_asset": by_asset,
        "sale_miss_examples": miss_examples,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["by_asset"], ensure_ascii=False, indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
