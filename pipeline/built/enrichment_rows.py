# -*- coding: utf-8 -*-
"""복원 확정 행 → built_transaction_enrichment.

마스킹 해제·건축구조는 표제부 조인. 미상은 행을 만들지 않는다.
확정 해시는 ON CONFLICT DO NOTHING 으로 동결한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

LAND_SRC_OK = {"title", "summary", "land_ledger"}

MATCH_RULE = {
    "A1": "gross_exact",
    "A2": "gross_exact_land_tiebreak",
}


def structure_group(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.replace(" ", "")
    if "철골철근" in s or "SRC" in s.upper():
        return "SRC"
    if "철근콘크리트" in s or s.upper() == "RC":
        return "RC"
    if "철골" in s or "강파이프" in s or "H빔" in s:
        return "철골"
    if "블록" in s:
        return "블록"
    if "벽돌" in s or "조적" in s:
        return "벽돌"
    if "목" in s:
        return "목"
    return "기타"


def _as_int(v: Any) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _road_contains(tx: Any, reg: Any) -> bool | None:
    if not isinstance(tx, str) or not tx:
        return None
    if not isinstance(reg, str) or not reg:
        return None
    return tx in reg or reg in tx


def to_enrichment_records(
    res: pd.DataFrame,
    zone_labels: list[list[str]] | None,
    *,
    coverage_scope: str,
    matched_cycle: str,
) -> list[dict[str, Any]]:
    """확정(A1/A2) 행만. transaction_hash 없는 행은 건너뛴다."""
    n = len(res)
    labels = zone_labels if zone_labels is not None else [[] for _ in range(n)]
    if len(labels) != n:
        raise ValueError("zone_labels length must match res")

    out: list[dict[str, Any]] = []
    for i, (_, row) in enumerate(res.iterrows()):
        tier = row.get("tier")
        parcel = row.get("parcel")
        if not isinstance(parcel, str) or not parcel:
            continue
        if tier not in MATCH_RULE:
            continue
        h = row.get("transaction_hash")
        if h is None or (isinstance(h, float) and pd.isna(h)):
            continue
        hx = str(h).strip()
        if len(hx) != 64:
            continue
        z = [x for x in labels[i] if x]
        src = row.get("land_src") if tier == "A2" else None
        if src not in LAND_SRC_OK:
            src = None
        used = row.get("snapshot_used")
        snaps = [used] if isinstance(used, str) and used else []
        tx_road = row.get("tx_road")
        reg_road = row.get("reg_road")
        out.append(
            {
                "transaction_hash": hx,
                "recovered_lot": parcel,
                "bldrgst_pk": None,
                "structure_raw": row.get("struct") if pd.notna(row.get("struct")) else None,
                "structure_group": structure_group(row.get("struct")),
                "max_floor": _as_int(row.get("floors")),
                "approve_year": _as_int(row.get("approve")),
                "zone_labels": z,
                "zone_source": "al_d155" if z else None,
                "zone_multi": len(z) > 1,
                "match_tier": tier,
                "match_rule": MATCH_RULE[str(tier)],
                "land_area_source": src if isinstance(src, str) and src else None,
                "n_range": _as_int(row.get("n_range")) or 0,
                "n_exact": _as_int(row.get("n_exact")) or 0,
                "snapshots_matched": snaps,
                "coverage_scope": coverage_scope,
                "matched_cycle": matched_cycle,
                "evidence": {
                    "tx_road": tx_road if isinstance(tx_road, str) else None,
                    "reg_road": reg_road if isinstance(reg_road, str) else None,
                    "road_contains": _road_contains(tx_road, reg_road),
                    "snapshot_used": used if isinstance(used, str) else None,
                    "snapshot_via": row.get("snapshot_via")
                    if isinstance(row.get("snapshot_via"), str)
                    else None,
                },
            }
        )
    return out


DDL_068 = Path(__file__).resolve().parents[2] / "db" / "068_built_transaction_enrichment.sql"


def _sql_statements(sql: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                parts.append(stmt)
            buf = []
    rest = "\n".join(buf).strip()
    if rest:
        parts.append(rest)
    return parts


def ensure_enrichment_table(engine: Engine) -> None:
    sql = DDL_068.read_text(encoding="utf-8")
    with engine.begin() as conn:
        for stmt in _sql_statements(sql):
            conn.execute(text(stmt))


def apply_enrichment_rows(engine: Engine, recs: list[dict[str, Any]]) -> dict[str, int]:
    """확정 행만 INSERT. 이미 있는 해시는 동결(덮지 않음)."""
    ensure_enrichment_table(engine)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in recs:
        h = r.get("transaction_hash")
        if not isinstance(h, str) or h in seen:
            continue
        seen.add(h)
        unique.append(r)
    recs = unique
    if not recs:
        return {"attempted": 0, "inserted": 0, "already": 0}

    insert_sql = text(
        """
        INSERT INTO built_transaction_enrichment (
            transaction_hash, recovered_lot, bldrgst_pk, structure_raw, structure_group,
            max_floor, approve_year, zone_labels, zone_source, zone_multi,
            match_tier, match_rule, land_area_source, n_range, n_exact,
            snapshots_matched, coverage_scope, matched_cycle, evidence
        ) VALUES (
            :transaction_hash, :recovered_lot, :bldrgst_pk, :structure_raw, :structure_group,
            :max_floor, :approve_year, CAST(:zone_labels AS text[]), :zone_source, :zone_multi,
            :match_tier, :match_rule, :land_area_source, :n_range, :n_exact,
            CAST(:snapshots_matched AS text[]), :coverage_scope, :matched_cycle,
            CAST(:evidence AS jsonb)
        )
        ON CONFLICT (transaction_hash) DO NOTHING
        """
    )

    def _pg_arr(xs: list[str] | None) -> str:
        if not xs:
            return "{}"
        escaped = [str(x).replace("\\", "\\\\").replace('"', '\\"') for x in xs]
        return "{" + ",".join('"' + e + '"' for e in escaped) + "}"

    params = []
    for r in recs:
        src = r.get("land_area_source")
        if src not in LAND_SRC_OK:
            src = None
        params.append(
            {
                "transaction_hash": r["transaction_hash"],
                "recovered_lot": r["recovered_lot"],
                "bldrgst_pk": r.get("bldrgst_pk"),
                "structure_raw": r.get("structure_raw"),
                "structure_group": r.get("structure_group"),
                "max_floor": r.get("max_floor"),
                "approve_year": r.get("approve_year"),
                "zone_labels": _pg_arr(r.get("zone_labels") or []),
                "zone_source": r.get("zone_source"),
                "zone_multi": bool(r.get("zone_multi")),
                "match_tier": r["match_tier"],
                "match_rule": r["match_rule"],
                "land_area_source": src,
                "n_range": r.get("n_range"),
                "n_exact": r.get("n_exact"),
                "snapshots_matched": _pg_arr(r.get("snapshots_matched") or []),
                "coverage_scope": r["coverage_scope"],
                "matched_cycle": r["matched_cycle"],
                "evidence": json.dumps(r.get("evidence") or {}, ensure_ascii=False),
            }
        )

    with engine.connect() as conn:
        before = int(conn.execute(text("SELECT COUNT(*) FROM built_transaction_enrichment")).scalar() or 0)
    with engine.begin() as conn:
        for i in range(0, len(params), 400):
            conn.execute(insert_sql, params[i : i + 400])
    with engine.connect() as conn:
        after = int(conn.execute(text("SELECT COUNT(*) FROM built_transaction_enrichment")).scalar() or 0)
    inserted = after - before
    return {"attempted": len(recs), "inserted": inserted, "already": len(recs) - inserted}
