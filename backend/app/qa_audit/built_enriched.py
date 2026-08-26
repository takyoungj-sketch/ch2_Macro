"""복합 거래 보강 QA — 원장·enrichment 조인 대조. WRITE 없음.

D-047: 채운 용도지역이 대분류 라벨이면 0건 실패. 커버리지는 리포트.
마트 재계산이 아니라 원장 SQL × 조인 SQL × enrichment 테이블 세 칸.
"""

from __future__ import annotations

import random
from typing import Any

from app.built.enrichment_join import ZONE_COARSE_LABELS
from app.qa_audit import ENGINE_VERSION
from app.qa_audit.report import format_report
from app.qa_audit.sql_pred import execute_sql, ledger_admin_predicate
from app.qa_audit.store import insert_run, write_json_log
from app.qa_audit.verdict import worst

DOMAIN = "built_enriched"
ASSET_TYPE = "commercial"
MIN_YEAR = 2019
MAX_RANDOM_RETRIES = 8
RANDOM_ASSET_TYPES = ("commercial", "factory", "detached")
ASSET_LABEL: dict[str, str] = {
    "commercial": "상업",
    "factory": "공장",
    "detached": "단독",
}


def normalize_asset_type(asset_type: str | None) -> str:
    raw = (asset_type or ASSET_TYPE).strip().lower()
    aliases = {
        "상업": "commercial",
        "상가": "commercial",
        "공장": "factory",
        "단독": "detached",
        "단독다가구": "detached",
    }
    raw = aliases.get(raw, raw)
    if raw not in ASSET_LABEL:
        raise ValueError(
            f"지원 유형: commercial / factory / detached (받은 값: {asset_type})"
        )
    return raw


def asset_label(asset_type: str) -> str:
    return ASSET_LABEL.get(normalize_asset_type(asset_type), asset_type)


def infer_region_level(code: str) -> str:
    n = len(str(code).strip())
    if n <= 2:
        return "sido"
    if n <= 5:
        return "sigungu"
    return "eupmyeondong"


def _coarse_sql() -> str:
    return ", ".join("'" + x.replace("'", "''") + "'" for x in sorted(ZONE_COARSE_LABELS))


def _qualify_pred(pred: str, alias: str) -> str:
    out = pred
    for col in (
        "eupmyeondong_code",
        "sigungu_code",
        "beopjungri_code",
        "sido_code",
    ):
        out = out.replace(col, f"{alias}.{col}")
    return out


def _admin_pred(
    codes: list[str],
    *,
    region_level: str,
    alias: str = "t",
) -> tuple[str, dict[str, Any]]:
    pred, params = ledger_admin_predicate(codes, region_level=region_level)
    return _qualify_pred(pred, alias), params


def _eligible_sql(pred: str) -> str:
    return f"""
        t.is_valid = true
        AND t.gross_area IS NOT NULL
        AND t.gross_area > 0
        AND t.asset_type = :asset_type
        AND t.contract_year = :calendar_year
        AND {pred}
    """


def _table_exists(conn, name: str) -> bool:
    row = execute_sql(
        conn,
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = :n
        """,
        {"n": name},
    ).first()
    return row is not None


def lookup_region(
    conn,
    *,
    region_code: str | None = None,
    region_name: str | None = None,
    region_level: str | None = None,
) -> dict[str, Any]:
    if _table_exists(conn, "region_codes"):
        from app.qa_audit.collective_apt import lookup_region as _lookup

        return _lookup(
            conn,
            region_code=region_code,
            region_name=region_name,
            region_level=region_level,
        )
    return _lookup_from_ledger(
        conn,
        region_code=region_code,
        region_name=region_name,
        region_level=region_level,
    )


def _lookup_from_ledger(
    conn,
    *,
    region_code: str | None,
    region_name: str | None,
    region_level: str | None,
) -> dict[str, Any]:
    if region_code and str(region_code).strip().isdigit():
        code = str(region_code).strip()
        level = region_level or infer_region_level(code)
        if level == "beopjungri":
            level = "eupmyeondong"
            code = code[:8]
        name = _name_for_code(conn, code, level)
        return {
            "region_code": code,
            "region_level": level,
            "region_name": name or code,
            "sido_code": code[:2],
            "sido_name": None,
            "addr1": None,
            "ledger_codes": [code],
        }

    name = (region_name or "").strip()
    if not name:
        raise ValueError("region_code 또는 region_name 이 필요합니다")
    tokens = name.split()
    eup_token = tokens[-1]
    sido_token = tokens[0] if len(tokens) >= 2 else None
    rows = execute_sql(
        conn,
        """
        SELECT
            btrim(eupmyeondong_code::text) AS eup,
            MAX(btrim(addr1::text)) AS sido_name,
            MAX(btrim(addr2::text)) AS sg_name,
            MAX(COALESCE(NULLIF(btrim(addr4::text), ''), btrim(addr3::text))) AS eup_name
        FROM built_transactions
        WHERE is_valid = true
          AND eupmyeondong_code IS NOT NULL
          AND length(btrim(eupmyeondong_code::text)) = 8
          AND (
            btrim(addr3::text) = :eup
            OR btrim(addr4::text) = :eup
            OR btrim(addr2::text) = :eup
          )
        GROUP BY 1
        """,
        {"eup": eup_token},
    ).mappings().all()
    if sido_token:
        filtered = [
            r
            for r in rows
            if sido_token in " ".join(
                str(x or "") for x in (r.get("sido_name"), r.get("sg_name"), r.get("eup_name"))
            )
        ]
        if filtered:
            rows = filtered
    if not rows:
        raise ValueError(f"지역을 찾지 못함: {name}")
    if len(rows) > 1:
        raise ValueError(
            "동명 지역이 여러 개입니다. 시도·시군구를 붙이거나 region_code 를 쓰세요: "
            + ", ".join(str(r["eup"]) for r in rows[:8])
        )
    row = dict(rows[0])
    code = str(row["eup"]).strip()
    display = " ".join(
        x for x in (row.get("sido_name"), row.get("sg_name"), row.get("eup_name")) if x
    )
    return {
        "region_code": code,
        "region_level": "eupmyeondong",
        "region_name": display or name,
        "sido_code": code[:2],
        "sido_name": row.get("sido_name"),
        "addr1": row.get("sido_name"),
        "ledger_codes": [code],
    }


def _name_for_code(conn, code: str, level: str) -> str | None:
    pred, params = _admin_pred([code], region_level=level, alias="t")
    row = execute_sql(
        conn,
        f"""
        SELECT
            MAX(btrim(t.addr1::text)) AS a1,
            MAX(btrim(t.addr2::text)) AS a2,
            MAX(COALESCE(NULLIF(btrim(t.addr4::text), ''), btrim(t.addr3::text))) AS a3
        FROM built_transactions t
        WHERE {pred}
        """,
        params,
    ).mappings().first()
    if not row:
        return None
    return " ".join(x for x in (row.get("a1"), row.get("a2"), row.get("a3")) if x) or None


def run_l1(
    conn,
    *,
    ledger_codes: list[str],
    region_level: str,
    calendar_year: int,
    asset_type: str = ASSET_TYPE,
) -> dict[str, Any]:
    asset = normalize_asset_type(asset_type)
    pred, params = _admin_pred(ledger_codes, region_level=region_level)
    params = {**params, "asset_type": asset, "calendar_year": int(calendar_year)}
    n = execute_sql(
        conn,
        f"SELECT COUNT(*)::int FROM built_transactions t WHERE {_eligible_sql(pred)}",
        params,
    ).scalar()
    return {
        "n": int(n or 0),
        "asset_type": asset,
        "calendar_year": int(calendar_year),
    }


def run_l2(
    conn,
    *,
    ledger_codes: list[str],
    region_level: str,
    calendar_year: int,
    asset_type: str = ASSET_TYPE,
) -> dict[str, Any]:
    asset = normalize_asset_type(asset_type)
    pred, params = _admin_pred(ledger_codes, region_level=region_level)
    params = {**params, "asset_type": asset, "calendar_year": int(calendar_year)}
    elig = _eligible_sql(pred)
    coarse = _coarse_sql()
    n_all = execute_sql(
        conn,
        f"""
        SELECT COUNT(*)::int FROM built_transactions t
        WHERE t.asset_type = :asset_type
          AND t.contract_year = :calendar_year
          AND {pred}
        """,
        params,
    ).scalar()
    n_invalid = execute_sql(
        conn,
        f"""
        SELECT COUNT(*)::int FROM built_transactions t
        WHERE t.asset_type = :asset_type
          AND t.contract_year = :calendar_year
          AND {pred}
          AND t.is_valid IS NOT TRUE
        """,
        params,
    ).scalar()
    n_eligible = execute_sql(
        conn,
        f"SELECT COUNT(*)::int FROM built_transactions t WHERE {elig}",
        params,
    ).scalar()
    n_enriched = 0
    n_coarse_first = 0
    n_invalid_tier = 0
    n_orphan = 0
    if _table_exists(conn, "built_transaction_enrichment"):
        n_enriched = execute_sql(
            conn,
            f"""
            SELECT COUNT(*)::int
            FROM built_transactions t
            JOIN built_transaction_enrichment e
              ON e.transaction_hash = t.transaction_hash
            WHERE {elig}
            """,
            params,
        ).scalar()
        n_coarse_first = execute_sql(
            conn,
            f"""
            SELECT COUNT(*)::int
            FROM built_transactions t
            JOIN built_transaction_enrichment e
              ON e.transaction_hash = t.transaction_hash
            WHERE {elig}
              AND (
                SELECT btrim(p.part)
                FROM unnest(COALESCE(e.zone_labels, ARRAY[]::text[]))
                     WITH ORDINALITY AS u(x, ord)
                CROSS JOIN LATERAL unnest(string_to_array(COALESCE(u.x::text, ''), ','))
                     WITH ORDINALITY AS p(part, pord)
                WHERE btrim(COALESCE(p.part, '')) <> ''
                ORDER BY u.ord, p.pord
                LIMIT 1
              ) IN ({coarse})
              AND EXISTS (
                SELECT 1
                FROM unnest(COALESCE(e.zone_labels, ARRAY[]::text[])) u(x)
                CROSS JOIN LATERAL unnest(string_to_array(COALESCE(u.x::text, ''), ',')) AS p(part)
                WHERE btrim(p.part) <> ''
                  AND lower(btrim(p.part)) <> 'nan'
                  AND btrim(p.part) NOT IN ({coarse})
              )
            """,
            params,
        ).scalar()
        n_invalid_tier = execute_sql(
            conn,
            f"""
            SELECT COUNT(*)::int
            FROM built_transactions t
            JOIN built_transaction_enrichment e
              ON e.transaction_hash = t.transaction_hash
            WHERE {elig}
              AND e.match_tier IS DISTINCT FROM 'A1'
              AND e.match_tier IS DISTINCT FROM 'A2'
            """,
            params,
        ).scalar()
        n_orphan = execute_sql(
            conn,
            """
            SELECT COUNT(*)::int
            FROM built_transaction_enrichment e
            WHERE NOT EXISTS (
                SELECT 1 FROM built_transactions t
                WHERE t.transaction_hash = e.transaction_hash
            )
            """,
        ).scalar()
    n_all_i = int(n_all or 0)
    n_elig_i = int(n_eligible or 0)
    n_enr_i = int(n_enriched or 0)
    return {
        "n_all": n_all_i,
        "n_invalid": int(n_invalid or 0),
        "n_l1_eligible": n_elig_i,
        "n_enriched": n_enr_i,
        "n_unmatched": max(n_elig_i - n_enr_i, 0),
        "n_coarse_pollution": int(n_coarse_first or 0),
        "n_invalid_tier": int(n_invalid_tier or 0),
        "n_orphan": int(n_orphan or 0),
        "drop_chain": {
            "n_all": n_all_i,
            "n_invalid": int(n_invalid or 0),
            "n_excluded_unit_price": 0,
            "n_l1_eligible": n_elig_i,
        },
        "n_needs_review": int(n_coarse_first or 0) + int(n_invalid_tier or 0),
    }


def run_l3(
    conn,
    *,
    ledger_codes: list[str],
    region_level: str,
    calendar_year: int,
    asset_type: str = ASSET_TYPE,
) -> dict[str, Any]:
    """원장 해시 유일 건수 + 조인 건수. 빌더 재실행 없음."""
    asset = normalize_asset_type(asset_type)
    pred, params = _admin_pred(ledger_codes, region_level=region_level)
    params = {**params, "asset_type": asset, "calendar_year": int(calendar_year)}
    elig = _eligible_sql(pred)
    n_eligible = execute_sql(
        conn,
        f"""
        SELECT COUNT(*)::int FROM (
            SELECT t.transaction_hash
            FROM built_transactions t
            WHERE {elig}
            GROUP BY t.transaction_hash
        ) u
        """,
        params,
    ).scalar()
    n_enriched = 0
    available = _table_exists(conn, "built_transaction_enrichment")
    error = None if available else "built_transaction_enrichment 테이블 없음"
    if available:
        n_enriched = execute_sql(
            conn,
            f"""
            SELECT COUNT(*)::int
            FROM built_transactions t
            INNER JOIN built_transaction_enrichment e
              ON e.transaction_hash = t.transaction_hash
            WHERE {elig}
            """,
            params,
        ).scalar()
    return {
        "n": int(n_eligible or 0),
        "n_eligible": int(n_eligible or 0),
        "n_enriched": int(n_enriched or 0),
        "available": available,
        "error": error,
        "asset_type": asset,
    }


def fetch_mart(
    conn,
    *,
    ledger_codes: list[str],
    region_level: str,
    calendar_year: int,
    asset_type: str = ASSET_TYPE,
) -> dict[str, Any]:
    """저장 enrichment 를 EXISTS 로 다시 센다. 원장 UPDATE 없음."""
    asset = normalize_asset_type(asset_type)
    if not _table_exists(conn, "built_transaction_enrichment"):
        return {"n": 0, "missing": True, "batch_id": None, "computed_at": None}
    pred, params = _admin_pred(ledger_codes, region_level=region_level)
    params = {**params, "asset_type": asset, "calendar_year": int(calendar_year)}
    elig = _eligible_sql(pred)
    n = execute_sql(
        conn,
        f"""
        SELECT COUNT(*)::int
        FROM built_transaction_enrichment e
        WHERE EXISTS (
            SELECT 1 FROM built_transactions t
            WHERE t.transaction_hash = e.transaction_hash
              AND {elig}
        )
        """,
        params,
    ).scalar()
    return {
        "n": int(n or 0),
        "missing": False,
        "batch_id": None,
        "computed_at": None,
        "asset_type": asset,
    }


def compare_enrichment(
    l1: dict[str, Any],
    l2: dict[str, Any],
    l3: dict[str, Any],
    mart: dict[str, Any],
) -> dict[str, Any]:
    n_l1 = int(l1.get("n") or 0)
    n_l3 = int(l3.get("n") or 0)
    n_enr_l3 = int(l3.get("n_enriched") or 0)
    n_enr_mart = None if mart.get("missing") else int(mart.get("n") or 0)
    n_coarse = int(l2.get("n_coarse_pollution") or 0)
    n_bad_tier = int(l2.get("n_invalid_tier") or 0)
    n_orphan = int(l2.get("n_orphan") or 0)

    if n_l1 == 0 and n_l3 == 0:
        skip = {
            "id": "eligible",
            "label": "원장 유효 건수",
            "grade": "SKIP",
            "detail": "대상 기간 유효 거래 0건",
        }
        return {
            "verdict": "SKIP",
            "verdict_ui": "SKIP",
            "metrics": {
                "n": {"grade": "SKIP", "reason": skip["detail"], "l1": 0, "l3": 0, "mart": None},
            },
            "checks": [skip],
            "cause_candidates": ["대상 기간 유효 거래 0건"],
        }

    if n_l1 != n_l3:
        elig_grade, elig_reason = "ERROR", "원장 COUNT 와 해시 유일 재집계가 다름"
    else:
        elig_grade, elig_reason = "PASS", "원장 유효 건수 일치"

    if l3.get("error"):
        join_grade, join_reason = "ERROR", str(l3.get("error"))
    elif mart.get("missing"):
        join_grade, join_reason = "ERROR", "enrichment 테이블 없음"
    elif n_enr_mart is None or n_enr_l3 != n_enr_mart:
        join_grade, join_reason = "ERROR", "조인 재집계와 enrichment 테이블 건수 불일치"
    else:
        join_grade, join_reason = "PASS", f"보강 조인 {n_enr_l3}건"

    coarse_grade = "BLOCK" if n_coarse else "PASS"
    coarse_detail = f"대분류를 대표로 쓴 행 {n_coarse}건 (0건 조건)"
    tier_grade = "BLOCK" if n_bad_tier else "PASS"
    tier_detail = f"A1/A2 아닌 등급 {n_bad_tier}건"
    orphan_grade = "REVIEW" if n_orphan else "PASS"
    orphan_detail = f"원장에 없는 enrichment {n_orphan}건 (리포트)"

    if n_l1 == 0:
        cov_grade, cov_detail = "SKIP", "유효 거래 0건"
    elif n_enr_l3 == 0:
        cov_grade, cov_detail = "REVIEW", "보강 0건 — 운영 미적재이거나 미상만 있는 표본"
    else:
        pct = 100.0 * n_enr_l3 / n_l1
        cov_grade, cov_detail = "PASS", f"{n_enr_l3}/{n_l1} = {pct:.1f}%"

    checks = [
        {
            "id": "eligible",
            "label": "원장 유효 건수",
            "grade": "ERROR" if elig_grade == "BLOCK" else elig_grade,
            "detail": elig_reason,
        },
        {
            "id": "join_count",
            "label": "보강 조인 건수",
            "grade": "ERROR" if join_grade == "BLOCK" else join_grade,
            "detail": join_reason,
        },
        {
            "id": "coarse_zone",
            "label": "대분류 용도지역 0건",
            "grade": "ERROR" if coarse_grade == "BLOCK" else coarse_grade,
            "detail": coarse_detail,
        },
        {
            "id": "match_tier",
            "label": "확정 등급 A1/A2",
            "grade": "ERROR" if tier_grade == "BLOCK" else tier_grade,
            "detail": tier_detail,
        },
        {
            "id": "orphan",
            "label": "고아 보강",
            "grade": orphan_grade,
            "detail": orphan_detail,
        },
        {
            "id": "coverage",
            "label": "보강 커버리지",
            "grade": cov_grade,
            "detail": cov_detail,
        },
    ]
    verdict = worst(elig_grade, join_grade, coarse_grade, tier_grade, orphan_grade, cov_grade)
    causes: list[str] = []
    if n_coarse:
        causes.append("zone_labels 첫 칸이 대분류인데 세부가 있음 — D-047 채움 오염")
    if n_enr_l3 == 0 and n_l1 > 0:
        causes.append("해당 지역·연도에 enrichment 행이 없음 (운영 dump 전이면 정상)")
    if n_l1 != n_l3:
        causes.append("transaction_hash 중복 가능")
    return {
        "verdict": verdict,
        "verdict_ui": "ERROR" if verdict == "BLOCK" else verdict,
        "metrics": {
            "n": {
                "grade": elig_grade,
                "reason": elig_reason,
                "l1": n_l1,
                "l3": n_l3,
                "mart": None,
                "delta_l1_mart": None,
            },
            "n_enriched": {
                "grade": join_grade,
                "reason": join_reason,
                "l1": int(l2.get("n_enriched") or 0),
                "l3": n_enr_l3,
                "mart": n_enr_mart,
                "delta_l1_mart": None
                if n_enr_mart is None
                else int(l2.get("n_enriched") or 0) - n_enr_mart,
            },
        },
        "checks": checks,
        "cause_candidates": causes,
    }


def _years_with_tx(conn) -> list[int]:
    rows = execute_sql(
        conn,
        """
        SELECT DISTINCT contract_year
        FROM built_transactions
        WHERE is_valid = true
          AND gross_area IS NOT NULL AND gross_area > 0
          AND contract_year >= :min_year
        ORDER BY 1
        """,
        {"min_year": MIN_YEAR},
    ).fetchall()
    return [int(r[0]) for r in rows if r[0] is not None]


def _assets_in_year(conn, calendar_year: int) -> list[str]:
    rows = execute_sql(
        conn,
        """
        SELECT DISTINCT asset_type
        FROM built_transactions
        WHERE is_valid = true
          AND gross_area IS NOT NULL AND gross_area > 0
          AND contract_year = :y
        """,
        {"y": int(calendar_year)},
    ).fetchall()
    found = {str(r[0]).strip() for r in rows if r[0]}
    return [a for a in RANDOM_ASSET_TYPES if a in found]


def pick_random_targets(
    conn,
    *,
    calendar_year: int | None = None,
    asset_type: str | None = None,
    n: int = 1,
    rng: random.Random | None = None,
) -> list[dict[str, Any]]:
    rng = rng or random.Random()
    out: list[dict[str, Any]] = []
    used: set[tuple[str, str, int]] = set()
    attempts = 0
    while len(out) < n and attempts < MAX_RANDOM_RETRIES * max(n, 1):
        attempts += 1
        year = int(calendar_year) if calendar_year else None
        if year is None:
            years = _years_with_tx(conn)
            if not years:
                return []
            year = rng.choice(years)
        if year < MIN_YEAR:
            continue
        asset = normalize_asset_type(asset_type) if asset_type else None
        if asset is None:
            assets = _assets_in_year(conn, year)
            if not assets:
                continue
            asset = rng.choice(assets)
        sidos = [
            str(r[0]).strip()
            for r in execute_sql(
                conn,
                """
                SELECT DISTINCT btrim(sido_code::text)
                FROM built_transactions
                WHERE is_valid = true
                  AND asset_type = :asset_type
                  AND contract_year = :y
                  AND gross_area IS NOT NULL AND gross_area > 0
                  AND sido_code IS NOT NULL
                  AND btrim(sido_code::text) <> ''
                """,
                {"asset_type": asset, "y": year},
            ).fetchall()
            if r[0]
        ]
        if not sidos:
            continue
        sido = rng.choice(sidos)
        eups = execute_sql(
            conn,
            """
            SELECT btrim(eupmyeondong_code::text) AS eup, COUNT(*)::int AS n
            FROM built_transactions
            WHERE is_valid = true
              AND asset_type = :asset_type
              AND contract_year = :y
              AND gross_area IS NOT NULL AND gross_area > 0
              AND btrim(sido_code::text) = :sido
              AND eupmyeondong_code IS NOT NULL
              AND length(btrim(eupmyeondong_code::text)) = 8
            GROUP BY 1
            HAVING COUNT(*) > 0
            """,
            {"asset_type": asset, "y": year, "sido": sido},
        ).mappings().all()
        candidates = [r for r in eups if r["eup"] and (r["eup"], asset, year) not in used]
        if not candidates:
            continue
        pick = rng.choice(candidates)
        used.add((pick["eup"], asset, year))
        try:
            target = lookup_region(conn, region_code=pick["eup"], region_level="eupmyeondong")
        except ValueError:
            continue
        target["asset_type"] = asset
        target["calendar_year"] = year
        target["asset_label"] = asset_label(asset)
        out.append(target)
    return out


def run_specified(
    engine,
    *,
    calendar_year: int,
    region_code: str | None = None,
    region_name: str | None = None,
    region_level: str | None = None,
    asset_type: str | None = None,
    save_db: bool = False,
) -> dict[str, Any]:
    asset = normalize_asset_type(asset_type)
    with engine.connect() as conn:
        target = lookup_region(
            conn,
            region_code=region_code,
            region_name=region_name,
            region_level=region_level,
        )
    target["asset_type"] = asset
    target["asset_label"] = asset_label(asset)
    run = _audit_one(engine, target=target, calendar_year=calendar_year, trigger="specified")
    return _persist(engine, run, save_db=save_db)


def run_random(
    engine,
    *,
    calendar_year: int | None = None,
    asset_type: str | None = None,
    n: int = 1,
    save_db: bool = False,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    n = max(1, min(int(n), 3))
    rng = random.Random(seed)
    with engine.connect() as conn:
        targets = pick_random_targets(
            conn,
            calendar_year=calendar_year,
            asset_type=asset_type,
            n=n,
            rng=rng,
        )
    if not targets:
        empty = {
            "trigger": "random",
            "domain": DOMAIN,
            "verdict": "SKIP",
            "verdict_ui": "SKIP",
            "period_kind": "calendar_year",
            "period_key": str(calendar_year) if calendar_year else "",
            "asset_type": asset_type or ASSET_TYPE,
            "engine_version": ENGINE_VERSION,
            "diffs": {
                "verdict": "SKIP",
                "metrics": {},
                "checks": [],
                "cause_candidates": ["유효 거래가 있는 지역·유형·연도 표본을 찾지 못함"],
            },
        }
        empty["ai_report"] = format_report(empty)
        write_json_log(empty)
        return [empty]

    runs: list[dict[str, Any]] = []
    for target in targets:
        run = _audit_one(
            engine,
            target=target,
            calendar_year=int(target.get("calendar_year") or calendar_year or 0),
            trigger="random",
        )
        if run.get("verdict") == "SKIP":
            continue
        runs.append(_persist(engine, run, save_db=save_db))
    if not runs:
        run = _audit_one(
            engine,
            target=targets[0],
            calendar_year=int(targets[0].get("calendar_year") or calendar_year or 0),
            trigger="random",
        )
        runs.append(_persist(engine, run, save_db=save_db))
    return runs


def _audit_one(
    engine,
    *,
    target: dict[str, Any],
    calendar_year: int,
    trigger: str,
) -> dict[str, Any]:
    level = target.get("region_level") or "eupmyeondong"
    code = str(target["region_code"]).strip()
    ledger = list(target.get("ledger_codes") or [code])
    asset = normalize_asset_type(target.get("asset_type") or ASSET_TYPE)

    if int(calendar_year) < MIN_YEAR:
        run = {
            "trigger": trigger,
            "domain": DOMAIN,
            "region_level": level,
            "region_code": code,
            "region_name": target.get("region_name"),
            "period_kind": "calendar_year",
            "period_key": str(calendar_year),
            "asset_type": asset,
            "asset_label": target.get("asset_label") or asset_label(asset),
            "verdict": "SKIP",
            "verdict_ui": "SKIP",
            "engine_version": ENGINE_VERSION,
            "l1": {"n": 0},
            "l2": {},
            "l3": {"n": 0, "available": False, "reason": "2019년 이전은 보강 대상 아님"},
            "mart": {"missing": True},
            "diffs": {
                "verdict": "SKIP",
                "metrics": {},
                "checks": [],
                "cause_candidates": ["계약 2019년 이전은 enrichment 를 두지 않음"],
            },
            "ai_report": None,
            "wrote_ledger_or_mart": False,
        }
        run["ai_report"] = format_report(run)
        return run

    with engine.connect() as conn:
        l1 = run_l1(
            conn,
            ledger_codes=ledger,
            region_level=level,
            calendar_year=calendar_year,
            asset_type=asset,
        )
        l2 = run_l2(
            conn,
            ledger_codes=ledger,
            region_level=level,
            calendar_year=calendar_year,
            asset_type=asset,
        )
        l3 = run_l3(
            conn,
            ledger_codes=ledger,
            region_level=level,
            calendar_year=calendar_year,
            asset_type=asset,
        )
        mart = fetch_mart(
            conn,
            ledger_codes=ledger,
            region_level=level,
            calendar_year=calendar_year,
            asset_type=asset,
        )
    diffs = compare_enrichment(l1, l2, l3, mart)
    run = {
        "trigger": trigger,
        "domain": DOMAIN,
        "region_level": level,
        "region_code": code,
        "region_name": target.get("region_name"),
        "period_kind": "calendar_year",
        "period_key": str(calendar_year),
        "asset_type": asset,
        "asset_label": target.get("asset_label") or asset_label(asset),
        "verdict_ui": diffs.get("verdict_ui") or diffs.get("verdict"),
        "engine_version": ENGINE_VERSION,
        "builder_version": mart.get("batch_id"),
        "as_of": mart.get("computed_at"),
        "l1": l1,
        "l2": l2,
        "l3": l3,
        "mart": mart,
        "diffs": diffs,
        "verdict": diffs.get("verdict"),
        "ai_report": None,
        "operator_note": None,
        "wrote_ledger_or_mart": False,
    }
    run["ai_report"] = format_report(run)
    return run


def _persist(engine, run: dict[str, Any], *, save_db: bool) -> dict[str, Any]:
    path = write_json_log(run)
    run["log_path"] = str(path)
    if save_db:
        from app.qa_audit.store import ensure_table

        with engine.begin() as conn:
            ensure_table(conn)
            run_id = insert_run(conn, run)
        run["id"] = run_id
    return run
