"""beopjungri_code 매칭 품질 리포트 — attach_beopjungri_codes() 회귀 검증."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


DEFAULT_MIN_MAPPED_PCT = 99.7
DEFAULT_MAX_DROP_PP = 0.5  # 전월 대비 mapped_pct 하락 경고 (percentage points)


@dataclass
class SliceStats:
    valid: int = 0
    mapped: int = 0
    needs_review: int = 0

    @property
    def unmapped(self) -> int:
        return max(0, self.valid - self.mapped)

    @property
    def mapped_pct(self) -> float:
        return round(100.0 * self.mapped / self.valid, 4) if self.valid else 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "mapped": self.mapped,
            "unmapped": self.unmapped,
            "mapped_pct": self.mapped_pct,
            "needs_review": self.needs_review,
        }


@dataclass
class ProductReport:
    product: str
    table: str
    overall: SliceStats = field(default_factory=SliceStats)
    by_asset: dict[str, SliceStats] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "product": self.product,
            "table": self.table,
            **self.overall.to_dict(),
        }
        if self.by_asset:
            out["by_asset"] = {k: v.to_dict() for k, v in sorted(self.by_asset.items())}
        if self.notes:
            out["notes"] = self.notes
        return out


def _mapped_clause(col: str = "beopjungri_code") -> str:
    return f"({col} IS NOT NULL AND btrim({col}::text) <> '')"


def _collect_table_stats(
    conn: Connection,
    *,
    table: str,
    valid_sql: str = "is_valid = true",
    asset_col: str | None = None,
) -> ProductReport:
    rep = ProductReport(product="", table=table)
    mapped = _mapped_clause()
    if asset_col:
        rows = conn.execute(
            text(
                f"""
                SELECT COALESCE({asset_col}, '(all)') AS asset,
                       COUNT(*) FILTER (WHERE {valid_sql})::bigint AS valid_n,
                       COUNT(*) FILTER (WHERE {valid_sql} AND {mapped})::bigint AS mapped_n,
                       COUNT(*) FILTER (WHERE COALESCE(needs_review, false))::bigint AS review_n
                FROM {table}
                GROUP BY ROLLUP({asset_col})
                ORDER BY asset NULLS FIRST
                """
            )
        ).mappings().all()
        for r in rows:
            stats = SliceStats(
                valid=int(r["valid_n"]),
                mapped=int(r["mapped_n"]),
                needs_review=int(r["review_n"]),
            )
            if r["asset"] == "(all)":
                rep.overall = stats
            else:
                rep.by_asset[str(r["asset"])] = stats
    else:
        row = conn.execute(
            text(
                f"""
                SELECT COUNT(*) FILTER (WHERE {valid_sql})::bigint AS valid_n,
                       COUNT(*) FILTER (WHERE {valid_sql} AND {mapped})::bigint AS mapped_n,
                       COUNT(*) FILTER (WHERE COALESCE(needs_review, false))::bigint AS review_n
                FROM {table}
                """
            )
        ).one()
        rep.overall = SliceStats(
            valid=int(row.valid_n),
            mapped=int(row.mapped_n),
            needs_review=int(row.review_n),
        )
    return rep


def _addr_key(addr1: str, addr2: str, addr3: str, addr4: str, addr5: str) -> str:
    return "|".join(x.strip() for x in (addr1, addr2, addr3, addr4, addr5))


def _fetch_unmapped_groups(
    conn: Connection,
    *,
    table: str,
    product: str,
    valid_sql: str = "is_valid = true",
    asset_filter: str | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    mapped = _mapped_clause()
    clauses = [valid_sql, f"NOT {mapped}"]
    params: dict[str, Any] = {}
    if asset_filter:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_filter
    where = " AND ".join(clauses)
    rows = conn.execute(
        text(
            f"""
            SELECT addr1, addr2, addr3, addr4, addr5, COUNT(*)::bigint AS n
            FROM {table}
            WHERE {where}
            GROUP BY addr1, addr2, addr3, addr4, addr5
            ORDER BY n DESC
            LIMIT :lim
            """
        ),
        {**params, "lim": limit},
    ).mappings().all()
    out: list[dict[str, Any]] = []
    for r in rows:
        a1 = str(r["addr1"] or "").strip()
        a2 = str(r["addr2"] or "").strip()
        a3 = str(r["addr3"] or "").strip()
        a4 = str(r["addr4"] or "").strip()
        a5 = str(r["addr5"] or "").strip()
        key = _addr_key(a1, a2, a3, a4, a5)
        label = " ".join(p for p in (a1, a2, a3, a4, a5) if p)
        out.append(
            {
                "product": product,
                "address_key": key,
                "count": int(r["n"]),
                "sample_label": label,
            }
        )
    return out


def collect_collective_commercial_report(conn: Connection) -> ProductReport:
    """집합상가·집합공장 — attach_beopjungri_codes DB 컬럼 기준."""
    rep = _collect_table_stats(
        conn,
        table="collective_commercial_transactions",
        asset_col="asset_type",
    )
    rep.product = "collective_commercial"
    return rep


def collect_land_report(conn: Connection) -> ProductReport:
    rep = _collect_table_stats(conn, table="land_transactions")
    rep.product = "land"
    return rep


def collect_collective_report(conn: Connection) -> ProductReport:
    rep = _collect_table_stats(
        conn,
        table="collective_transactions",
        asset_col="asset_type",
    )
    rep.product = "collective"
    return rep


def collect_built_report(conn: Connection) -> ProductReport:
    rep = _collect_table_stats(
        conn,
        table="built_transactions",
        asset_col="asset_type",
    )
    rep.product = "built"
    return rep


def aggregate_overall(products: list[ProductReport]) -> SliceStats:
    """attach_beopjungri_codes 대상(토지·집합·복합·집합상업) 가중 합산."""
    core = [p for p in products if p.product in ("land", "collective", "built", "collective_commercial")]
    total = SliceStats()
    for p in core:
        total.valid += p.overall.valid
        total.mapped += p.overall.mapped
        total.needs_review += p.overall.needs_review
    return total


def compare_with_previous(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    max_drop_pp: float = DEFAULT_MAX_DROP_PP,
) -> dict[str, Any]:
    if not previous:
        return {"previous_available": False}

    prev_overall = previous.get("overall") or {}
    cur_overall = current.get("overall") or {}
    prev_pct = float(prev_overall.get("mapped_pct") or 0)
    cur_pct = float(cur_overall.get("mapped_pct") or 0)
    delta_pp = round(cur_pct - prev_pct, 4)

    by_product: dict[str, Any] = {}
    prev_products = {p["product"]: p for p in previous.get("products") or [] if p.get("product")}
    for p in current.get("products") or []:
        key = p.get("product")
        if not key or key not in prev_products:
            continue
        pp = float(prev_products[key].get("mapped_pct") or 0)
        cp = float(p.get("mapped_pct") or 0)
        by_product[key] = {
            "previous_mapped_pct": pp,
            "current_mapped_pct": cp,
            "change_pp": round(cp - pp, 4),
        }

    return {
        "previous_available": True,
        "previous_cycle_id": previous.get("cycle_id"),
        "previous_generated_at_utc": previous.get("generated_at_utc"),
        "overall_mapped_pct_change_pp": delta_pp,
        "by_product": by_product,
        "warn_on_drop_pp": max_drop_pp,
    }


def find_newly_unmapped(
    current_groups: list[dict[str, Any]],
    previous_report: dict[str, Any] | None,
    *,
    top_n: int = 100,
) -> list[dict[str, Any]]:
    prev_keys: set[str] = set()
    if previous_report:
        for item in previous_report.get("unmapped_fingerprints") or []:
            prev_keys.add(f"{item.get('product')}|{item.get('address_key')}")

    new_items: list[dict[str, Any]] = []
    for g in current_groups:
        fk = f"{g['product']}|{g['address_key']}"
        if fk not in prev_keys:
            new_items.append(g)
    new_items.sort(key=lambda x: x["count"], reverse=True)
    return new_items[:top_n]


def evaluate_gates(
    report: dict[str, Any],
    *,
    min_mapped_pct: float = DEFAULT_MIN_MAPPED_PCT,
    max_drop_pp: float = DEFAULT_MAX_DROP_PP,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    overall = report.get("overall") or {}
    pct = float(overall.get("mapped_pct") or 0)
    if pct < min_mapped_pct:
        errors.append(
            f"전체 매칭률 {pct:.2f}% < 목표 {min_mapped_pct:.1f}% "
            f"(valid={overall.get('valid')}, unmapped={overall.get('unmapped')})"
        )

    for p in report.get("products") or []:
        if p.get("product") not in ("land", "collective", "built", "collective_commercial"):
            continue
        pp = float(p.get("mapped_pct") or 0)
        if pp < min_mapped_pct:
            errors.append(
                f"{p['product']} 매칭률 {pp:.2f}% < 목표 {min_mapped_pct:.1f}% "
                f"(unmapped={p.get('unmapped')})"
            )

    delta = report.get("delta_vs_previous") or {}
    if delta.get("previous_available"):
        ch = float(delta.get("overall_mapped_pct_change_pp") or 0)
        if ch < -max_drop_pp:
            warnings.append(
                f"전월 대비 전체 매칭률 {ch:+.2f}%p (임계 -{max_drop_pp}%p)"
            )
        for prod, info in (delta.get("by_product") or {}).items():
            d = float(info.get("change_pp") or 0)
            if d < -max_drop_pp:
                warnings.append(f"전월 대비 {prod} 매칭률 {d:+.2f}%p")

    return {
        "passed": len(errors) == 0,
        "min_mapped_pct": min_mapped_pct,
        "errors": errors,
        "warnings": warnings,
    }


def build_report(
    *,
    land_conn: Connection | None,
    collective_conn: Connection | None,
    built_conn: Connection | None,
    cycle_id: str | None = None,
    previous_report: dict[str, Any] | None = None,
    min_mapped_pct: float = DEFAULT_MIN_MAPPED_PCT,
    max_drop_pp: float = DEFAULT_MAX_DROP_PP,
    top_unmapped: int = 100,
) -> dict[str, Any]:
    products: list[ProductReport] = []
    unmapped_groups: list[dict[str, Any]] = []

    if land_conn is not None:
        products.append(collect_land_report(land_conn))
    if collective_conn is not None:
        products.append(collect_collective_report(collective_conn))
        products.append(collect_collective_commercial_report(collective_conn))
        unmapped_groups.extend(
            _fetch_unmapped_groups(
                collective_conn,
                table="collective_transactions",
                product="collective",
            )
        )
        unmapped_groups.extend(
            _fetch_unmapped_groups(
                collective_conn,
                table="collective_commercial_transactions",
                product="collective_commercial",
            )
        )
    if built_conn is not None:
        products.append(collect_built_report(built_conn))
        unmapped_groups.extend(
            _fetch_unmapped_groups(built_conn, table="built_transactions", product="built")
        )

    overall = aggregate_overall(products)
    product_dicts = [p.to_dict() for p in products]

    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_mapped_pct": min_mapped_pct,
        "overall": overall.to_dict(),
        "products": product_dicts,
        "unmapped_fingerprints": [
            {"product": g["product"], "address_key": g["address_key"]} for g in unmapped_groups
        ],
    }
    if cycle_id:
        report["cycle_id"] = cycle_id.strip()

    report["delta_vs_previous"] = compare_with_previous(report, previous_report, max_drop_pp=max_drop_pp)
    report["newly_unmapped_top100"] = find_newly_unmapped(
        unmapped_groups, previous_report, top_n=top_unmapped
    )
    report["gate"] = evaluate_gates(report, min_mapped_pct=min_mapped_pct, max_drop_pp=max_drop_pp)
    return report


def load_previous_report(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def find_previous_report(repo: Path, cycle_id: str) -> Path | None:
    """clean_snapshots/{YYYYMM}/beopjungri_mapping_report.json 중 cycle_id 미만 최신."""
    snap_root = repo / "clean_snapshots"
    if not snap_root.is_dir():
        return None
    try:
        current = int(cycle_id.strip())
    except ValueError:
        return None
    candidates: list[tuple[int, Path]] = []
    for d in snap_root.iterdir():
        if not d.is_dir():
            continue
        try:
            cid = int(d.name)
        except ValueError:
            continue
        p = d / "beopjungri_mapping_report.json"
        if cid < current and p.is_file():
            candidates.append((cid, p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def save_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def format_summary_lines(report: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    ov = report.get("overall") or {}
    lines.append(
        f"overall: mapped={ov.get('mapped_pct')}% "
        f"(valid={int(ov.get('valid') or 0):,}, unmapped={int(ov.get('unmapped') or 0):,}, "
        f"needs_review={int(ov.get('needs_review') or 0):,})"
    )
    for p in report.get("products") or []:
        lines.append(
            f"  {p.get('product')}: {p.get('mapped_pct')}% "
            f"(unmapped={p.get('unmapped'):,}, needs_review={p.get('needs_review'):,})"
        )
        for asset, st in (p.get("by_asset") or {}).items():
            lines.append(
                f"    - {asset}: {st.get('mapped_pct')}% (unmapped={st.get('unmapped'):,})"
            )
    gate = report.get("gate") or {}
    lines.append(f"gate: {'PASS' if gate.get('passed') else 'FAIL'}")
    for e in gate.get("errors") or []:
        lines.append(f"  [ERR] {e}")
    for w in gate.get("warnings") or []:
        lines.append(f"  [WARN] {w}")
    delta = report.get("delta_vs_previous") or {}
    if delta.get("previous_available"):
        lines.append(
            f"vs previous ({delta.get('previous_cycle_id')}): "
            f"{delta.get('overall_mapped_pct_change_pp'):+.2f}%p"
        )
    new = report.get("newly_unmapped_top100") or []
    if new:
        lines.append(f"newly unmapped addresses (top {min(5, len(new))} of {len(new)}):")
        for item in new[:5]:
            lines.append(f"  [{item.get('product')}] n={item.get('count')} {item.get('sample_label')}")
    return lines
