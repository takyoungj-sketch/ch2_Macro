# -*- coding: utf-8 -*-
"""Canonical region code resolve via region_code_history (D-028).

- Does NOT mutate land_transactions.beopjungri_code (historical preserved).
- split / unresolved: never auto-mapped (no history row, or excluded types).
- Allowed remap types: code_reissue, merge, rename.

Public contract (stateless — no Resolver object, no session cache):
  resolve_to_canonical(codes)     — any code → canonical
  expand_to_ledger_codes(codes)   — canonical → ledger lookup set (canonical ∪ historical)
  normalize_result_codes(...)     — ledger/API rows → canonical codes (idempotent)
  is_canonical(code)              — True when code already equals its canonical form

DB-facing wrappers load a history snapshot per call, then delegate to pure core.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence, TypeVar

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

# 1:N split 제외 — 자동 canonical 치환 금지
RESOLVE_CHANGE_TYPES: tuple[str, ...] = ("code_reissue", "merge", "rename")

# Verify·배포 리포트에 기록 — resolver 계약 변경 시 갱신
RESOLVER_VERSION = "2026.08"

_TYPES_SQL = ",".join(f"'{t}'" for t in RESOLVE_CHANGE_TYPES)

_ADMIN_PREFIX_LENGTHS: tuple[int, ...] = (2, 5, 8)

T = TypeVar("T")


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


@dataclass(frozen=True)
class RegionCodeHistorySnapshot:
    """Explicit history map for pure (DB-free) resolver functions."""

    forward: dict[str, str]
    reverse: dict[str, tuple[str, ...]]
    prefix_forward: dict[tuple[int, str], str]


def build_history_snapshot(
    rows: Iterable[tuple[str, str, str]],
) -> RegionCodeHistorySnapshot:
    """Build snapshot from (from_code, to_code, change_type) tuples."""
    forward: dict[str, str] = {}
    reverse_sets: dict[str, set[str]] = {}
    prefix_forward: dict[tuple[int, str], str] = {}

    for raw_from, raw_to, change_type in rows:
        if change_type not in RESOLVE_CHANGE_TYPES:
            continue
        src = str(raw_from).strip()
        dst = str(raw_to).strip()
        if not src or not dst:
            continue
        forward[src] = dst
        reverse_sets.setdefault(dst, set()).add(src)
        for n in _ADMIN_PREFIX_LENGTHS:
            if len(src) >= n and len(dst) >= n:
                old_p = src[:n]
                new_p = dst[:n]
                if old_p != new_p:
                    prefix_forward[(n, old_p)] = new_p

    reverse = {k: tuple(sorted(v)) for k, v in reverse_sets.items()}
    return RegionCodeHistorySnapshot(
        forward=forward,
        reverse=reverse,
        prefix_forward=prefix_forward,
    )


def load_history_snapshot(conn: Connection | Session) -> RegionCodeHistorySnapshot:
    """DB adapter: load region_code_history into an explicit snapshot."""
    rows = conn.execute(
        text(
            f"""
            SELECT DISTINCT ON (from_code)
                   from_code, to_code, change_type
            FROM region_code_history
            WHERE change_type IN ({_TYPES_SQL})
            ORDER BY from_code, effective_from DESC, id DESC
            """
        )
    ).fetchall()
    return build_history_snapshot(
        (str(r.from_code).strip(), str(r.to_code).strip(), str(r.change_type).strip())
        for r in rows
    )


def _resolve_one_pure(snapshot: RegionCodeHistorySnapshot, code: str) -> str:
    cc = str(code).strip()
    if not cc:
        return cc
    if cc in snapshot.forward:
        return snapshot.forward[cc]
    n = len(cc)
    if n in _ADMIN_PREFIX_LENGTHS:
        mapped = snapshot.prefix_forward.get((n, cc))
        if mapped:
            return mapped
    return cc


def resolve_to_canonical_pure(
    snapshot: RegionCodeHistorySnapshot,
    codes: Sequence[str] | None,
) -> list[str]:
    """Pure: map codes through history (identity when unmapped)."""
    cleaned = _norm_codes(codes)
    out: list[str] = []
    seen: set[str] = set()
    for c in cleaned:
        canon = _resolve_one_pure(snapshot, c)
        if canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out


def expand_to_ledger_codes_pure(
    snapshot: RegionCodeHistorySnapshot,
    codes: Sequence[str] | None,
) -> list[str]:
    """Pure: canonical input → ledger lookup set (input ∪ matching historical from_codes)."""
    cleaned = _norm_codes(codes)
    if not cleaned:
        return []
    result: set[str] = set(cleaned)
    for code in cleaned:
        for hist_from in snapshot.reverse.get(code, ()):
            result.add(hist_from)
        n = len(code)
        if n in _ADMIN_PREFIX_LENGTHS:
            for hist_from, hist_to in snapshot.forward.items():
                if len(hist_to) >= n and hist_to[:n] == code:
                    result.add(hist_from)
                    if len(hist_from) >= n:
                        result.add(hist_from[:n])
    return _norm_codes(result)


def is_canonical_pure(snapshot: RegionCodeHistorySnapshot, code: str) -> bool:
    """Pure: True when code equals its canonical resolution."""
    cc = str(code).strip()
    if not cc:
        return False
    return _resolve_one_pure(snapshot, cc) == cc


def normalize_result_codes_pure(
    snapshot: RegionCodeHistorySnapshot,
    records_or_codes: Sequence[str] | Sequence[Mapping[str, Any]] | None,
    *,
    code_key: str = "code",
    code_keys: Sequence[str] | None = None,
) -> list[str] | list[dict[str, Any]]:
    """Pure: normalize codes to canonical; dedupe code lists; shallow-copy record dicts."""
    if records_or_codes is None:
        return []
    if not records_or_codes:
        return []

    first = records_or_codes[0]
    if isinstance(first, str):
        return resolve_to_canonical_pure(snapshot, records_or_codes)  # type: ignore[arg-type]

    keys = tuple(code_keys) if code_keys else (code_key,)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rec in records_or_codes:
        if not isinstance(rec, Mapping):
            continue
        item = dict(rec)
        primary: str | None = None
        for k in keys:
            raw = item.get(k)
            if raw is None or str(raw).strip() == "":
                continue
            canon = _resolve_one_pure(snapshot, str(raw))
            item[k] = canon
            if primary is None and k == code_key:
                primary = canon
        if primary is not None:
            if primary in seen:
                continue
            seen.add(primary)
        out.append(item)
    return out


def resolve_to_canonical(
    conn: Connection | Session,
    codes: Sequence[str] | None,
) -> list[str]:
    """Map each code through region_code_history.from→to (identity if no row)."""
    cleaned = _norm_codes(codes)
    if not cleaned:
        return []
    snapshot = load_history_snapshot(conn)
    return resolve_to_canonical_pure(snapshot, cleaned)


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
    snapshot = load_history_snapshot(conn)
    return expand_to_ledger_codes_pure(snapshot, cleaned)


def is_canonical(conn: Connection | Session, code: str) -> bool:
    """True when code already equals its canonical resolution."""
    snapshot = load_history_snapshot(conn)
    return is_canonical_pure(snapshot, code)


def normalize_result_codes(
    conn: Connection | Session,
    records_or_codes: Sequence[str] | Sequence[Mapping[str, Any]] | None,
    *,
    code_key: str = "code",
    code_keys: Sequence[str] | None = None,
) -> list[str] | list[dict[str, Any]]:
    """Normalize user-facing codes to canonical (idempotent). Does not mutate ledger rows."""
    snapshot = load_history_snapshot(conn)
    return normalize_result_codes_pure(
        snapshot,
        records_or_codes,
        code_key=code_key,
        code_keys=code_keys,
    )


def normalize_code(conn: Connection | Session, code: str | None) -> str | None:
    """Single-code helper: ledger/historical → canonical for API responses."""
    cc = (code or "").strip()
    if not cc:
        return None
    resolved = resolve_to_canonical(conn, [cc])
    return resolved[0] if resolved else None


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


def canonical_prefix_coalesce_sql(
    beop_expr: str,
    eup_expr: str,
    sigungu_expr: str,
    sido_expr: str,
    n: int,
) -> str:
    """Canonical admin prefix from arbitrary SQL column expressions (t/rc COALESCE)."""
    if n not in (2, 5, 8):
        raise ValueError(f"canonical_prefix_coalesce_sql n must be 2|5|8, got {n}")
    if n == 8:
        raw = (
            f"COALESCE(NULLIF(btrim(({beop_expr})::text), ''), "
            f"NULLIF(btrim(({eup_expr})::text), ''), '')"
        )
    elif n == 5:
        raw = (
            f"COALESCE(NULLIF(btrim(({beop_expr})::text), ''), "
            f"NULLIF(btrim(({sigungu_expr})::text), ''), '')"
        )
    else:
        raw = (
            f"COALESCE(NULLIF(btrim(({beop_expr})::text), ''), "
            f"NULLIF(btrim(({sido_expr})::text), ''), '')"
        )
    return f"""COALESCE(
      (
        SELECT left(h.to_code, {n})
        FROM region_code_history h
        WHERE left(h.from_code, {n}) = left({raw}, {n})
          AND length(btrim({raw})) >= {n}
          AND h.change_type IN ({_TYPES_SQL})
        ORDER BY h.effective_from DESC, h.id DESC
        LIMIT 1
      ),
      CASE WHEN length(btrim({raw})) >= {n} THEN left(btrim({raw}), {n}) ELSE NULL END
    )"""


def canonical_prefix_expr(alias: str = "lt", n: int = 8) -> str:
    """Canonical admin prefix (2/5/8) for map/mart grain.

    Prefer remapping via beopjungri history; if beopjungri is NULL (common on
    Built/Collective addr-only rows), remap eupmyeondong/sigungu/sido code through
    history using left(from_code, n) → left(to_code, n).
    """
    a = alias
    return canonical_prefix_coalesce_sql(
        f"{a}.beopjungri_code",
        f"{a}.eupmyeondong_code",
        f"{a}.sigungu_code",
        f"{a}.sido_code",
        n,
    )


def lookup_active_admin_codes_by_name(
    conn: Connection,
    *,
    level: str,
    sido_name: str,
    sigungu_name: str | None = None,
    names: Sequence[str] | None = None,
) -> list[str]:
    """Active region_codes lookup by address names (NULL admin-code rows on Built/Collective).

    level: eupmyeondong | sigungu
    """
    a1 = (sido_name or "").strip()
    if not a1:
        return []
    a2 = (sigungu_name or "").strip() or None
    labels = _norm_codes(names) if names else []

    if level == "eupmyeondong":
        if not a2 or not labels:
            return []
        if a2 == "__FLAT_SIDO__":
            # 세종 등: 행정 읍·면·동명이 sigungu_name
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT btrim(eupmyeondong_code::text) AS code
                    FROM region_codes
                    WHERE COALESCE(is_active, TRUE)
                      AND btrim(sido_name::text) = :a1
                      AND btrim(sigungu_name::text) = ANY(:names)
                      AND eupmyeondong_code IS NOT NULL
                      AND btrim(eupmyeondong_code::text) <> ''
                    ORDER BY 1
                    """
                ),
                {"a1": a1, "names": labels},
            ).fetchall()
        else:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT btrim(eupmyeondong_code::text) AS code
                    FROM region_codes
                    WHERE COALESCE(is_active, TRUE)
                      AND btrim(sido_name::text) = :a1
                      AND btrim(sigungu_name::text) = :a2
                      AND btrim(eupmyeondong_name::text) = ANY(:names)
                      AND eupmyeondong_code IS NOT NULL
                      AND btrim(eupmyeondong_code::text) <> ''
                    ORDER BY 1
                    """
                ),
                {"a1": a1, "a2": a2, "names": labels},
            ).fetchall()
    elif level == "sigungu":
        if labels:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT btrim(sigungu_code::text) AS code
                    FROM region_codes
                    WHERE COALESCE(is_active, TRUE)
                      AND btrim(sido_name::text) = :a1
                      AND btrim(sigungu_name::text) = ANY(:names)
                      AND sigungu_code IS NOT NULL
                      AND btrim(sigungu_code::text) <> ''
                    ORDER BY 1
                    """
                ),
                {"a1": a1, "names": labels},
            ).fetchall()
        elif a2:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT btrim(sigungu_code::text) AS code
                    FROM region_codes
                    WHERE COALESCE(is_active, TRUE)
                      AND btrim(sido_name::text) = :a1
                      AND btrim(sigungu_name::text) = :a2
                      AND sigungu_code IS NOT NULL
                      AND btrim(sigungu_code::text) <> ''
                    ORDER BY 1
                    """
                ),
                {"a1": a1, "a2": a2},
            ).fetchall()
        else:
            return []
    else:
        return []
    return _norm_codes(str(r[0]) for r in rows)


def lookup_active_beopjungri_by_ri_picks(
    conn: Connection,
    *,
    sido_name: str,
    sigungu_name: str | None,
    picks: Sequence[tuple[str, str]],
) -> list[tuple[str, str]]:
    """(canonical_code, 'eup ri') for active region_codes matching (eup, ri) picks.

    Built ledger often has addr5=리 with NULL beopjungri_code — map resolve still
    needs a user-facing canonical code.
    """
    a1 = (sido_name or "").strip()
    a2 = (sigungu_name or "").strip()
    if not a1 or not a2:
        return []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for eup, ri in picks:
        e = (eup or "").strip()
        r = (ri or "").strip()
        if not e or not r:
            continue
        if a2 == "__FLAT_SIDO__":
            row = conn.execute(
                text(
                    """
                    SELECT btrim(beopjungri_code::text) AS code
                    FROM region_codes
                    WHERE COALESCE(is_active, TRUE)
                      AND btrim(sido_name::text) = :a1
                      AND btrim(sigungu_name::text) = :eup
                      AND btrim(beopjungri_name::text) = :ri
                      AND beopjungri_code IS NOT NULL
                      AND btrim(beopjungri_code::text) <> ''
                    ORDER BY beopjungri_code
                    LIMIT 1
                    """
                ),
                {"a1": a1, "eup": e, "ri": r},
            ).first()
        else:
            row = conn.execute(
                text(
                    """
                    SELECT btrim(beopjungri_code::text) AS code
                    FROM region_codes
                    WHERE COALESCE(is_active, TRUE)
                      AND btrim(sido_name::text) = :a1
                      AND btrim(sigungu_name::text) = :a2
                      AND btrim(eupmyeondong_name::text) = :eup
                      AND btrim(beopjungri_name::text) = :ri
                      AND beopjungri_code IS NOT NULL
                      AND btrim(beopjungri_code::text) <> ''
                    ORDER BY beopjungri_code
                    LIMIT 1
                    """
                ),
                {"a1": a1, "a2": a2, "eup": e, "ri": r},
            ).first()
        if not row or not row[0]:
            continue
        code = str(row[0]).strip()
        if code in seen:
            continue
        seen.add(code)
        out.append((code, f"{e} {r}"))
    return out


def region_codes_join_on_canonical(
    tx_alias: str = "lt",
    rc_alias: str = "r",
    *,
    active_only: bool = True,
) -> str:
    """INNER JOIN region_codes … ON canonical(beopjungri) = rc.beopjungri_code.

    Uses a small DISTINCT ON history map (not a per-row correlated subquery)
    so sido-wide upper/annual rebuilds stay tractable.
    Hierarchy (sido/sigungu/eup) comes from the *canonical* region_codes row.
    """
    a = tx_alias
    active = f" AND COALESCE({rc_alias}.is_active, TRUE)" if active_only else ""
    return f"""
LEFT JOIN (
  SELECT DISTINCT ON (from_code) from_code, to_code
  FROM region_code_history
  WHERE change_type IN ({_TYPES_SQL})
  ORDER BY from_code, effective_from DESC, id DESC
) _rch ON _rch.from_code = btrim({a}.beopjungri_code::text)
INNER JOIN region_codes {rc_alias}
  ON btrim({rc_alias}.beopjungri_code::text) = COALESCE(
       _rch.to_code, btrim({a}.beopjungri_code::text)
     ){active}
"""


def canonical_beopjungri_sql(alias: str = "lt") -> str:
    """Prefer join-friendly form when history map alias `_rch` is already present.

    Fallback: correlated COALESCE (same as canonical_select_expr).
    """
    return (
        f"COALESCE(_rch.to_code, btrim({alias}.beopjungri_code::text))"
    )


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
