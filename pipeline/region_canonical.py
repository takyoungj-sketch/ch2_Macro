# -*- coding: utf-8 -*-
"""Canonical region code resolve via region_code_history (D-028).

- Does NOT mutate land_transactions.beopjungri_code (historical preserved).
- split / unresolved: never auto-mapped (no history row, or excluded types).
- Allowed remap types: code_reissue, merge, rename.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

# 1:N split 제외 — 자동 canonical 치환 금지
RESOLVE_CHANGE_TYPES: tuple[str, ...] = ("code_reissue", "merge", "rename")

_TYPES_SQL = ",".join(f"'{t}'" for t in RESOLVE_CHANGE_TYPES)


def _norm_codes(codes: Iterable[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for c in codes or []:
        cc = str(c).strip()
        if not cc or cc in seen:
            continue
        seen.add(cc)
        out.append(cc)
    return out


def resolve_to_canonical(
    conn: Connection | Session,
    codes: Sequence[str] | None,
) -> list[str]:
    """Map each code through region_code_history.from→to (identity if no row)."""
    cleaned = _norm_codes(codes)
    if not cleaned:
        return []
    rows = conn.execute(
        text(
            f"""
            SELECT c.code AS input_code,
                   COALESCE(
                     (
                       SELECT h.to_code
                       FROM region_code_history h
                       WHERE h.from_code = c.code
                         AND h.change_type IN ({_TYPES_SQL})
                       ORDER BY h.effective_from DESC, h.id DESC
                       LIMIT 1
                     ),
                     c.code
                   ) AS canonical_code
            FROM unnest(CAST(:codes AS text[])) AS c(code)
            """
        ),
        {"codes": cleaned},
    ).fetchall()
    # preserve first-seen order of canonicals
    out: list[str] = []
    seen: set[str] = set()
    by_in = {str(r.input_code).strip(): str(r.canonical_code).strip() for r in rows}
    for c in cleaned:
        canon = by_in.get(c, c)
        if canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out


def expand_to_ledger_codes(
    conn: Connection | Session,
    codes: Sequence[str] | None,
) -> list[str]:
    """Codes to filter Master ledger: input ∪ historical from_codes that map into them.

    After resolve_to_canonical, pass canonical list here so txs still stored under
    from_code are included in re-aggregation.
    """
    cleaned = _norm_codes(codes)
    if not cleaned:
        return []
    rows = conn.execute(
        text(
            f"""
            SELECT DISTINCT x.code
            FROM (
              SELECT unnest(CAST(:codes AS text[])) AS code
              UNION
              SELECT h.from_code
              FROM region_code_history h
              WHERE h.to_code = ANY(:codes)
                AND h.change_type IN ({_TYPES_SQL})
            ) x
            WHERE x.code IS NOT NULL AND btrim(x.code) <> ''
            """
        ),
        {"codes": cleaned},
    ).fetchall()
    return _norm_codes(str(r[0]) for r in rows)


def canonical_select_expr(alias: str = "lt") -> str:
    """SQL expression: COALESCE(history.to_code, beopjungri_code) for SELECT list."""
    a = alias
    return f"""COALESCE(
      (
        SELECT h.to_code
        FROM region_code_history h
        WHERE h.from_code = btrim({a}.beopjungri_code::text)
          AND h.change_type IN ({_TYPES_SQL})
        ORDER BY h.effective_from DESC, h.id DESC
        LIMIT 1
      ),
      btrim({a}.beopjungri_code::text)
    )"""


def load_code_reissue_pairs_from_csv(csv_path) -> list[tuple[str, str]]:
    """Return (from_code, to_code) for Phase 1a code_reissue rows."""
    import csv
    from pathlib import Path

    path = Path(csv_path)
    pairs: list[tuple[str, str]] = []
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("change_type") != "code_reissue":
                continue
            a = (r.get("historical_code") or "").strip()
            b = (r.get("canonical_code") or "").strip()
            if len(a) == 10 and len(b) == 10:
                pairs.append((a, b))
    return pairs


def upsert_canonical_region_codes_from_master(
    engine: Engine,
    to_codes: Sequence[str],
    master_path,
) -> int:
    """Ensure canonical codes exist in region_codes (from 법정동 마스터 존재 rows)."""
    from pathlib import Path

    want = set(_norm_codes(to_codes))
    if not want:
        return 0
    text_ko = Path(master_path).read_bytes().decode("cp949", errors="replace")
    records: list[dict] = []
    for line in text_ko.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        code, name, status = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if code not in want or status != "존재":
            continue
        toks = name.split()
        sido_name = toks[0] if toks else ""
        # crude but matches seed_region_codes leaf naming
        if len(toks) >= 3 and (
            toks[2].endswith("구")
            or (toks[2].endswith("군") and not toks[2].endswith("면"))
        ):
            sigungu_name = f"{toks[1]} {toks[2]}"
            rest = toks[3:]
        elif len(toks) >= 2:
            sigungu_name = toks[1]
            rest = toks[2:]
        else:
            sigungu_name = ""
            rest = []
        eup = rest[0] if rest else ""
        leaf = rest[1] if len(rest) >= 2 else eup
        records.append(
            {
                "sido_code": code[:2],
                "sido_name": sido_name,
                "sigungu_code": code[:5],
                "sigungu_name": sigungu_name,
                "eupmyeondong_code": code[:8],
                "eupmyeondong_name": eup,
                "beopjungri_code": code,
                "beopjungri_name": leaf,
            }
        )

    if not records:
        return 0

    n = 0
    with engine.begin() as conn:
        for rec in records:
            conn.execute(
                text(
                    """
                    INSERT INTO region_codes (
                        sido_code, sido_name,
                        sigungu_code, sigungu_name,
                        eupmyeondong_code, eupmyeondong_name,
                        beopjungri_code, beopjungri_name,
                        is_active, updated_at
                    ) VALUES (
                        :sido_code, :sido_name,
                        :sigungu_code, :sigungu_name,
                        :eupmyeondong_code, :eupmyeondong_name,
                        :beopjungri_code, :beopjungri_name,
                        TRUE, NOW()
                    )
                    ON CONFLICT (beopjungri_code) DO UPDATE SET
                        sido_name = EXCLUDED.sido_name,
                        sigungu_name = EXCLUDED.sigungu_name,
                        eupmyeondong_code = EXCLUDED.eupmyeondong_code,
                        eupmyeondong_name = EXCLUDED.eupmyeondong_name,
                        beopjungri_name = EXCLUDED.beopjungri_name,
                        is_active = TRUE,
                        updated_at = NOW()
                    """
                ),
                rec,
            )
            n += 1
    return n


def deactivate_historical_codes(engine: Engine, from_codes: Sequence[str]) -> int:
    codes = _norm_codes(from_codes)
    if not codes:
        return 0
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                UPDATE region_codes
                SET is_active = FALSE, updated_at = NOW()
                WHERE beopjungri_code = ANY(:codes)
                """
            ),
            {"codes": codes},
        )
        return int(res.rowcount or 0)
