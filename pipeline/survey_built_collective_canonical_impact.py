# -*- coding: utf-8 -*-
"""Built/Collective canonical impact survey — read-only, no rebuild."""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

CSV_1A = ROOT / "docs" / "reports" / "REGION_CODE_PHASE1A_CLASSIFICATION.csv"
OUT = ROOT / "docs" / "reports" / "REGION_CODE_BUILT_COLLECTIVE_IMPACT.md"
OUT_JSON = ROOT / "docs" / "reports" / "REGION_CODE_BUILT_COLLECTIVE_IMPACT.json"


def load_pairs() -> list[tuple[str, str]]:
    pairs = []
    with CSV_1A.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("change_type") != "code_reissue":
                continue
            a = (r.get("historical_code") or "").strip()
            b = (r.get("canonical_code") or "").strip()
            if len(a) == 10 and len(b) == 10:
                pairs.append((a, b))
    return pairs


def table_exists(conn, name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name=:t
                """
            ),
            {"t": name},
        ).scalar()
    )


def col_exists(conn, table: str, col: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name=:t AND column_name=:c
                """
            ),
            {"t": table, "c": col},
        ).scalar()
    )


def count_in(conn, table: str, col: str, codes: list[str]) -> dict:
    if not table_exists(conn, table) or not col_exists(conn, table, col):
        return {"exists": False}
    n_rows = int(
        conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE btrim({col}::text) = ANY(:c)"),
            {"c": codes},
        ).scalar()
        or 0
    )
    n_codes = int(
        conn.execute(
            text(
                f"SELECT COUNT(DISTINCT btrim({col}::text)) FROM {table} "
                f"WHERE btrim({col}::text) = ANY(:c)"
            ),
            {"c": codes},
        ).scalar()
        or 0
    )
    return {"exists": True, "rows": n_rows, "distinct_codes": n_codes}


def prefix8_count(conn, table: str, col: str, prefixes: list[str]) -> dict:
    if not table_exists(conn, table) or not col_exists(conn, table, col):
        return {"exists": False}
    n_rows = int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*) FROM {table}
                WHERE LEFT(btrim({col}::text), 8) = ANY(:p)
                """
            ),
            {"p": prefixes},
        ).scalar()
        or 0
    )
    return {"exists": True, "rows": n_rows}


def survey_db(label: str, engine, from_codes: list[str], to_codes: list[str], stale_eup: list[str]) -> dict:
    out: dict = {"db": label, "tables": {}, "history": {}}
    with engine.connect() as conn:
        out["history"]["region_code_history"] = table_exists(conn, "region_code_history")
        out["history"]["region_codes"] = table_exists(conn, "region_codes")
        if out["history"]["region_code_history"]:
            out["history"]["history_rows"] = int(
                conn.execute(text("SELECT COUNT(*) FROM region_code_history")).scalar() or 0
            )
        # candidate tables / columns
        candidates = [
            ("built_transactions", "beopjungri_code"),
            ("collective_transactions", "beopjungri_code"),
            ("collective_commercial_transactions", "beopjungri_code"),
            ("market_stats", "region_code"),
            ("market_annual_stats", "region_code"),
            ("built_annual_stats", "region_code"),
            ("built_annual_stats", "beopjungri_code"),
            ("collective_commercial_region_annual_stats", "region_code"),
            ("collective_building_annual_stats", "beopjungri_code"),
            ("collective_building_annual_stats", "sigungu_code"),
            ("collective_presale_lifetime_stats", "beopjungri_code"),
            ("collective_cluster_annual_stats", "beopjungri_code"),
            ("collective_commercial_cluster_annual_stats", "beopjungri_code"),
        ]
        for table, col in candidates:
            key = f"{table}.{col}"
            hist = count_in(conn, table, col, from_codes)
            canon = count_in(conn, table, col, to_codes)
            out["tables"][key] = {"historical": hist, "canonical": canon}
            # also eup prefix for market_stats style 8-digit grains
            if hist.get("exists") and col in ("region_code", "eupmyeondong_code"):
                out["tables"][f"{table}.{col}__stale_eup8"] = {
                    "historical_eup_prefix": prefix8_count(conn, table, col, stale_eup)
                }

        # top historical codes by tx if built/collective tx exist
        for table in (
            "built_transactions",
            "collective_transactions",
            "collective_commercial_transactions",
        ):
            if not table_exists(conn, table) or not col_exists(conn, table, "beopjungri_code"):
                continue
            rows = conn.execute(
                text(
                    f"""
                    SELECT btrim(beopjungri_code::text) AS code, COUNT(*)::int AS n
                    FROM {table}
                    WHERE btrim(beopjungri_code::text) = ANY(:c)
                    GROUP BY 1
                    ORDER BY n DESC
                    LIMIT 15
                    """
                ),
                {"c": from_codes},
            ).fetchall()
            out[f"top_hist_{table}"] = [{"code": r.code, "n": r.n} for r in rows]

            # sido breakdown of hist txs
            if col_exists(conn, table, "sido_code"):
                sido = conn.execute(
                    text(
                        f"""
                        SELECT LEFT(btrim(beopjungri_code::text), 2) AS sido, COUNT(*)::int AS n
                        FROM {table}
                        WHERE btrim(beopjungri_code::text) = ANY(:c)
                        GROUP BY 1 ORDER BY n DESC
                        """
                    ),
                    {"c": from_codes},
                ).fetchall()
                out[f"sido_hist_{table}"] = [{"sido": r.sido, "n": r.n} for r in sido]
    return out


def main() -> int:
    from built.db_utils import get_built_engine
    from collective.db_utils import get_collective_engine
    from db_utils import get_engine as get_land_engine

    pairs = load_pairs()
    from_codes = sorted({a for a, _ in pairs})
    to_codes = sorted({b for _, b in pairs})
    stale_eup = sorted({a[:8] for a, b in pairs if a[:8] != b[:8]})

    report = {
        "pairs": len(pairs),
        "from_codes": len(from_codes),
        "to_codes": len(to_codes),
        "stale_eup_prefixes": len(stale_eup),
        "unresolved_excluded": 2,
        "dbs": {},
    }

    # land: history SSOT presence
    with get_land_engine().connect() as conn:
        report["land_history_rows"] = int(
            conn.execute(text("SELECT COUNT(*) FROM region_code_history")).scalar() or 0
        )

    report["dbs"]["built_stats"] = survey_db(
        "built_stats", get_built_engine(), from_codes, to_codes, stale_eup
    )
    report["dbs"]["collective_stats"] = survey_db(
        "collective_stats", get_collective_engine(), from_codes, to_codes, stale_eup
    )

    # markdown
    lines = [
        "# Built · Collective canonical 영향 조사 (재빌드 없음)",
        "",
        f"- Phase 1a `code_reissue` pairs: **{len(pairs)}** (historical {len(from_codes)} / canonical {len(to_codes)})",
        f"- stale eup 8자리 prefix (면→읍 등): **{len(stale_eup)}**",
        f"- unresolved: **2** (계속 제외)",
        f"- land `region_code_history` rows: **{report['land_history_rows']}**",
        "",
        "## DB별 history / region_codes 존재",
        "",
        "| DB | region_code_history | region_codes | history_rows |",
        "|----|---------------------|--------------|--------------|",
    ]
    for dbn, d in report["dbs"].items():
        h = d["history"]
        lines.append(
            f"| {dbn} | {h.get('region_code_history')} | {h.get('region_codes')} | {h.get('history_rows', '—')} |"
        )

    lines += ["", "## 원장·mart: historical / canonical 코드 건수", ""]
    lines.append("| DB | table.col | hist rows | hist codes | canon rows | canon codes |")
    lines.append("|----|-----------|-----------|------------|------------|-------------|")
    for dbn, d in report["dbs"].items():
        for key, v in sorted(d["tables"].items()):
            if key.endswith("__stale_eup8"):
                continue
            h, c = v.get("historical", {}), v.get("canonical", {})
            if not h.get("exists"):
                continue
            lines.append(
                f"| {dbn} | `{key}` | {h.get('rows', 0)} | {h.get('distinct_codes', 0)} "
                f"| {c.get('rows', 0)} | {c.get('distinct_codes', 0)} |"
            )

    lines += ["", "## historical 거래 top (원장)", ""]
    for dbn, d in report["dbs"].items():
        for k, rows in d.items():
            if not k.startswith("top_hist_"):
                continue
            lines.append(f"### {dbn} · {k.replace('top_hist_', '')}")
            if not rows:
                lines.append("- (0)")
            else:
                for r in rows[:10]:
                    lines.append(f"- `{r['code']}`: {r['n']}")
            sido = d.get(k.replace("top_hist_", "sido_hist_"), [])
            if sido:
                lines.append("시도 합계: " + ", ".join(f"{x['sido']}={x['n']}" for x in sido))
            lines.append("")

    lines += [
        "## 예비 재빌드 후보 (실행하지 않음)",
        "",
        "원장 historical rows > 0 인 자산의 mart만 부분 재빌드 대상.",
        "history 테이블이 Built/Collective DB에 없으면 land history를 복사하거나 cross-DB resolve 필요.",
        "",
    ]

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"wrote {OUT_JSON}")
    # console-safe summary
    for dbn, d in report["dbs"].items():
        print(f"=== {dbn} history={d['history']} ===")
        for key, v in sorted(d["tables"].items()):
            if key.endswith("__stale_eup8"):
                continue
            h = v.get("historical") or {}
            if h.get("exists") and (h.get("rows") or 0) > 0:
                print(f"  HIST {key}: rows={h['rows']} codes={h['distinct_codes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
