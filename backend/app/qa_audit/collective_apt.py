"""집합 아파트 × 행정구역 × 달력 연도 — L1 / L2 / L3 / 저장 마트."""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

from app.qa_audit.sql_pred import execute_sql, ledger_admin_predicate

DOMAIN = "collective_apt"
ASSET_TYPE = "apartment"
MARKET_DOMAIN = "apartment_market"
MAX_RANDOM_RETRIES = 8
RANDOM_ASSET_TYPES = ("apartment", "rowhouse", "officetel")
ASSET_MARKET: dict[str, str] = {
    "apartment": "apartment_market",
    "rowhouse": "rowhouse_market",
    "officetel": "officetel_market",
}
ASSET_LABEL: dict[str, str] = {
    "apartment": "아파트",
    "rowhouse": "연립다세대",
    "officetel": "오피스텔",
}


def normalize_asset_type(asset_type: str | None) -> str:
    raw = (asset_type or ASSET_TYPE).strip().lower()
    aliases = {
        "아파트": "apartment",
        "연립": "rowhouse",
        "연립다세대": "rowhouse",
        "오피스텔": "officetel",
    }
    raw = aliases.get(raw, raw)
    if raw not in ASSET_MARKET:
        raise ValueError(f"지원 유형: apartment / rowhouse / officetel (받은 값: {asset_type})")
    return raw


def market_domain_for(asset_type: str) -> str:
    return ASSET_MARKET[normalize_asset_type(asset_type)]


def asset_label(asset_type: str) -> str:
    return ASSET_LABEL.get(normalize_asset_type(asset_type), asset_type)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ensure_pipeline_path() -> Path:
    pipe = _repo_root() / "pipeline"
    s = str(pipe)
    if s not in sys.path:
        sys.path.insert(0, s)
    return pipe


def _compute_stats(prices: list[float]) -> dict[str, Any]:
    _ensure_pipeline_path()
    from stats import compute_stats  # type: ignore[import-not-found]

    return compute_stats(prices)


def _canon_and_ledger(conn, codes: list[str]) -> tuple[str, list[str]]:
    raw = [str(c).strip() for c in codes if str(c).strip()]
    if not raw:
        raise ValueError("region code required")
    seed = raw[0]
    try:
        from app.region_canonical import expand_to_ledger_codes, resolve_to_canonical

        resolved = resolve_to_canonical(conn, raw) or raw
        canon = str(resolved[0]).strip()
        expanded = expand_to_ledger_codes(conn, [canon]) or [canon]
        return canon, _uniq(expanded)
    except Exception:
        return seed, _uniq(raw)


def _uniq(xs: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in xs:
        c = str(x).strip()
        if not c or c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def infer_region_level(code: str) -> str:
    n = len(str(code).strip())
    if n <= 2:
        return "sido"
    if n <= 5:
        return "sigungu"
    if n <= 8:
        return "eupmyeondong"
    return "beopjungri"


def lookup_region(
    conn,
    *,
    region_code: str | None = None,
    region_name: str | None = None,
    region_level: str | None = None,
) -> dict[str, Any]:
    """region_codes 에서 대상 1건. 동명이면 ValueError."""
    if region_code and str(region_code).strip().isdigit():
        code = str(region_code).strip()
        level = region_level or infer_region_level(code)
        if level == "beopjungri":
            level = "eupmyeondong"
            code = code[:8]
        row = _region_row_by_code(conn, code, level)
        if row:
            canon, ledger = _canon_and_ledger(conn, [code])
            row["region_code"] = canon
            row["ledger_codes"] = ledger
            row["region_level"] = level
            return row
        canon, ledger = _canon_and_ledger(conn, [code])
        return {
            "region_code": canon,
            "region_level": level,
            "region_name": code,
            "sido_code": canon[:2],
            "sido_name": None,
            "addr1": None,
            "ledger_codes": ledger,
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
        SELECT DISTINCT
            btrim(eupmyeondong_code::text) AS eup,
            btrim(eupmyeondong_name::text) AS eup_name,
            btrim(sigungu_code::text) AS sg,
            btrim(sigungu_name::text) AS sg_name,
            btrim(sido_code::text) AS sido,
            btrim(sido_name::text) AS sido_name
        FROM region_codes
        WHERE COALESCE(is_active, TRUE)
          AND (
                eupmyeondong_name = :q
             OR sigungu_name = :q
             OR eupmyeondong_name LIKE :q_suf
             OR sigungu_name LIKE :q_suf
          )
        """,
        {"q": eup_token, "q_suf": f"%{eup_token}%"},
    ).mappings().all()
    picked = [dict(r) for r in rows]
    if sido_token:
        filtered = [
            r
            for r in picked
            if (r.get("sido_name") or "").startswith(sido_token)
            or sido_token in (r.get("sido_name") or "")
        ]
        if filtered:
            picked = filtered
    eups = _uniq([r["eup"] for r in picked if r.get("eup")])
    if not eups:
        raise ValueError(f"지역을 찾지 못했습니다: {name}")
    if len(eups) > 1:
        labels = sorted(
            {
                f"{r.get('sido_name')} {r.get('sg_name')} {r.get('eup_name')} ({r.get('eup')})"
                for r in picked
                if r.get("eup")
            }
        )
        raise ValueError("동명 지역이 여러 개입니다. --region-code 로 지정하세요: " + "; ".join(labels[:8]))
    eup = eups[0]
    row0 = next(r for r in picked if r.get("eup") == eup)
    canon, ledger = _canon_and_ledger(conn, [eup])
    display = " ".join(
        x
        for x in (row0.get("sido_name"), row0.get("sg_name"), row0.get("eup_name"))
        if x
    )
    return {
        "region_code": canon,
        "region_level": region_level or "eupmyeondong",
        "region_name": display or name,
        "sido_code": row0.get("sido"),
        "sido_name": row0.get("sido_name"),
        "addr1": row0.get("sido_name"),
        "ledger_codes": ledger,
    }


def _region_row_by_code(conn, code: str, level: str) -> dict[str, Any] | None:
    if level == "eupmyeondong":
        sql = """
            SELECT
                btrim(eupmyeondong_code::text) AS region_code,
                btrim(sido_code::text) AS sido_code,
                btrim(sido_name::text) AS sido_name,
                concat_ws(' ', btrim(sido_name::text), btrim(sigungu_name::text),
                          btrim(eupmyeondong_name::text)) AS region_name
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND btrim(eupmyeondong_code::text) = :c
            LIMIT 1
        """
    elif level == "sigungu":
        sql = """
            SELECT
                btrim(sigungu_code::text) AS region_code,
                btrim(sido_code::text) AS sido_code,
                btrim(sido_name::text) AS sido_name,
                concat_ws(' ', btrim(sido_name::text), btrim(sigungu_name::text)) AS region_name
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND btrim(sigungu_code::text) = :c
            LIMIT 1
        """
    else:
        sql = """
            SELECT
                btrim(sido_code::text) AS region_code,
                btrim(sido_code::text) AS sido_code,
                btrim(sido_name::text) AS sido_name,
                btrim(sido_name::text) AS region_name
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND btrim(sido_code::text) = :c
            LIMIT 1
        """
    row = execute_sql(conn, sql, {"c": code}).mappings().first()
    if not row:
        return None
    d = dict(row)
    d["addr1"] = d.get("sido_name")
    d["region_name"] = " ".join(str(d.get("region_name") or "").split())
    return d


def _eligible_where(pred_sql: str) -> str:
    return f"""
        asset_type = :asset_type
        AND contract_year = :calendar_year
        AND is_valid = true
        AND unit_price IS NOT NULL
        AND unit_price > 0
        AND {pred_sql}
    """


def run_l1(
    conn,
    *,
    ledger_codes: list[str],
    region_level: str,
    calendar_year: int,
    asset_type: str = ASSET_TYPE,
) -> dict[str, Any]:
    asset_type = normalize_asset_type(asset_type)
    pred, params = ledger_admin_predicate(ledger_codes, region_level=region_level)
    params = {**params, "asset_type": asset_type, "calendar_year": int(calendar_year)}
    rows = execute_sql(
        conn,
        f"""
        SELECT unit_price, price
        FROM collective_transactions
        WHERE {_eligible_where(pred)}
        """,
        params,
    ).fetchall()
    prices = [float(r[0]) for r in rows if r[0] is not None]
    amounts = [float(r[1]) for r in rows if r[1] is not None]
    st = _compute_stats(prices) if prices else {"count": 0, "mean": None, "median": None}
    samples = execute_sql(
        conn,
        f"""
        SELECT contract_date, eupmyeondong_code, beopjungri_code,
               exclusive_area, price, unit_price
        FROM collective_transactions
        WHERE {_eligible_where(pred)}
        ORDER BY contract_date
        LIMIT 5
        """,
        params,
    ).mappings().all()
    return {
        "n": int(st["count"]),
        "sum_price": round(sum(amounts), 2) if amounts else 0.0,
        "mean_price": st.get("mean"),
        "median_price": st.get("median"),
        "unit": "만원(합) / 만원/㎡(평균·중위)",
        "asset_type": asset_type,
        "filter": f"is_valid AND unit_price > 0 AND asset_type={asset_type}",
        "ledger_codes": ledger_codes,
        "samples": [
            {k: (str(v) if v is not None else None) for k, v in dict(s).items()}
            for s in samples
        ],
    }


def run_l2(
    conn,
    *,
    ledger_codes: list[str],
    region_level: str,
    calendar_year: int,
    asset_type: str = ASSET_TYPE,
) -> dict[str, Any]:
    asset_type = normalize_asset_type(asset_type)
    pred, params = ledger_admin_predicate(ledger_codes, region_level=region_level)
    params = {**params, "asset_type": asset_type, "calendar_year": int(calendar_year)}
    row = execute_sql(
        conn,
        f"""
        SELECT
            COUNT(*)::int AS n_all,
            COUNT(*) FILTER (WHERE is_valid)::int AS n_valid,
            COUNT(*) FILTER (WHERE NOT is_valid)::int AS n_invalid,
            COUNT(*) FILTER (WHERE COALESCE(needs_review, FALSE))::int AS n_needs_review,
            COUNT(*) FILTER (
                WHERE is_valid
                  AND (unit_price IS NULL OR unit_price <= 0)
            )::int AS n_excluded_unit_price,
            COUNT(*) FILTER (
                WHERE beopjungri_code IS NULL
                   OR length(btrim(beopjungri_code::text)) <> 10
            )::int AS n_bad_beop,
            COUNT(*) FILTER (
                WHERE eupmyeondong_code IS NULL
                   OR length(btrim(eupmyeondong_code::text)) <> 8
            )::int AS n_bad_eup
        FROM collective_transactions
        WHERE asset_type = :asset_type
          AND contract_year = :calendar_year
          AND {pred}
        """,
        params,
    ).mappings().first()
    d = dict(row or {})
    d["n_bad_region_code"] = int(d.get("n_bad_beop") or 0) + int(d.get("n_bad_eup") or 0)
    d["n_l1_eligible"] = int(d.get("n_valid") or 0) - int(d.get("n_excluded_unit_price") or 0)
    dup = execute_sql(
        conn,
        f"""
        SELECT COUNT(*)::int AS n_groups
        FROM (
            SELECT transaction_hash
            FROM collective_transactions
            WHERE asset_type = :asset_type
              AND contract_year = :calendar_year
              AND transaction_hash IS NOT NULL
              AND {pred}
            GROUP BY transaction_hash
            HAVING COUNT(*) > 1
        ) s
        """,
        params,
    ).scalar()
    d["n_hash_dup_groups"] = int(dup or 0)
    d["drop_chain"] = {
        "n_all": d.get("n_all"),
        "n_invalid": d.get("n_invalid"),
        "n_needs_review": d.get("n_needs_review"),
        "n_excluded_unit_price": d.get("n_excluded_unit_price"),
        "n_l1_eligible": d.get("n_l1_eligible"),
    }
    d["notes"] = [
        "해제(취소) 거래는 ingest 단계에서 원장에 들어오지 않음",
        "집합 원장은 semantic hash 중복 제거를 하지 않음",
    ]
    return d


def fetch_mart(
    conn,
    *,
    region_level: str,
    region_code: str,
    calendar_year: int,
    asset_type: str = ASSET_TYPE,
) -> dict[str, Any]:
    md = market_domain_for(asset_type)
    row = execute_sql(
        conn,
        """
        SELECT count, mean, median, amount_sum, batch_id, computed_at
        FROM market_annual_stats
        WHERE market_domain = :md
          AND region_level = :rl
          AND region_code = :rc
          AND calendar_year = :y
        """,
        {
            "md": md,
            "rl": region_level,
            "rc": region_code,
            "y": int(calendar_year),
        },
    ).mappings().first()
    if not row:
        return {
            "missing": True,
            "n": None,
            "sum_price": None,
            "mean_price": None,
            "median_price": None,
            "market_domain": md,
        }
    return {
        "missing": False,
        "n": int(row["count"]) if row["count"] is not None else None,
        "sum_price": float(row["amount_sum"]) if row["amount_sum"] is not None else None,
        "mean_price": float(row["mean"]) if row["mean"] is not None else None,
        "median_price": float(row["median"]) if row["median"] is not None else None,
        "batch_id": row["batch_id"],
        "computed_at": str(row["computed_at"]) if row["computed_at"] is not None else None,
        "market_domain": md,
    }


def run_l3(
    engine,
    *,
    addr1: str | None,
    region_level: str,
    region_code: str,
    calendar_year: int,
    asset_type: str = ASSET_TYPE,
) -> dict[str, Any]:
    md = market_domain_for(asset_type)
    if not addr1:
        return {
            "available": False,
            "reason": "addr1(시도명) 없음 — L3 생략",
            "n": None,
            "sum_price": None,
            "mean_price": None,
            "median_price": None,
        }
    _ensure_pipeline_path()
    from build_collective_market_stats import compute_annual_records  # type: ignore[import-not-found]

    try:
        records = compute_annual_records(
            engine,
            addr1_filter=addr1,
            calendar_year=int(calendar_year),
            batch_id="qa-readonly",
        )
    except Exception as exc:  # noqa: BLE001 — L3 실패는 BLOCK
        return {
            "available": False,
            "error": str(exc),
            "n": None,
            "sum_price": None,
            "mean_price": None,
            "median_price": None,
        }
    hit = next(
        (
            r
            for r in records
            if r.get("market_domain") == md
            and r.get("region_level") == region_level
            and str(r.get("region_code") or "").strip() == str(region_code).strip()
            and int(r.get("calendar_year") or 0) == int(calendar_year)
        ),
        None,
    )
    if not hit:
        return {
            "available": True,
            "missing": True,
            "n": 0,
            "sum_price": 0.0,
            "mean_price": None,
            "median_price": None,
            "note": "빌더 재실행 결과에 해당 지역 행 없음",
        }
    return {
        "available": True,
        "missing": False,
        "n": int(hit.get("count") or 0),
        "sum_price": float(hit["amount_sum"]) if hit.get("amount_sum") is not None else None,
        "mean_price": float(hit["mean"]) if hit.get("mean") is not None else None,
        "median_price": float(hit["median"]) if hit.get("median") is not None else None,
        "wrote_mart": False,
        "market_domain": md,
    }


def _years_with_tx(conn, asset_type: str | None = None) -> list[int]:
    extra = ""
    params: dict[str, Any] = {}
    if asset_type:
        extra = "AND asset_type = :asset_type"
        params["asset_type"] = asset_type
    rows = execute_sql(
        conn,
        f"""
        SELECT DISTINCT contract_year
        FROM collective_transactions
        WHERE is_valid = true
          AND unit_price IS NOT NULL AND unit_price > 0
          AND contract_year IS NOT NULL
          {extra}
        ORDER BY 1
        """,
        params,
    ).fetchall()
    return [int(r[0]) for r in rows if r[0] is not None]


def _assets_in_year(conn, calendar_year: int) -> list[str]:
    rows = execute_sql(
        conn,
        """
        SELECT DISTINCT asset_type
        FROM collective_transactions
        WHERE is_valid = true
          AND unit_price IS NOT NULL AND unit_price > 0
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
    """층화: (연도) → (유형) → 시도 → 읍면동(n>0). 표본마다 연도·유형을 다시 뽑을 수 있다."""
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
                FROM collective_transactions
                WHERE is_valid = true
                  AND asset_type = :asset_type
                  AND contract_year = :y
                  AND unit_price IS NOT NULL AND unit_price > 0
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
            FROM collective_transactions
            WHERE is_valid = true
              AND asset_type = :asset_type
              AND contract_year = :y
              AND unit_price IS NOT NULL AND unit_price > 0
              AND btrim(sido_code::text) = :sido
              AND eupmyeondong_code IS NOT NULL
              AND length(btrim(eupmyeondong_code::text)) = 8
            GROUP BY 1
            HAVING COUNT(*) > 0
            """,
            {"asset_type": asset, "y": year, "sido": sido},
        ).mappings().all()
        candidates = [
            r
            for r in eups
            if r["eup"] and (r["eup"], asset, year) not in used
        ]
        if not candidates:
            continue
        pick = rng.choice(candidates)
        used.add((pick["eup"], asset, year))
        try:
            target = lookup_region(conn, region_code=pick["eup"], region_level="eupmyeondong")
        except ValueError:
            continue
        if not target.get("addr1"):
            addr1 = execute_sql(
                conn,
                """
                SELECT addr1 FROM collective_transactions
                WHERE btrim(sido_code::text) = :sido
                  AND addr1 IS NOT NULL AND btrim(addr1::text) <> ''
                LIMIT 1
                """,
                {"sido": sido},
            ).scalar()
            target["addr1"] = addr1
        target["asset_type"] = asset
        target["calendar_year"] = year
        target["asset_label"] = asset_label(asset)
        out.append(target)
    return out
