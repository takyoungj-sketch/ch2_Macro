"""지정·랜덤 검증 오케스트레이션. 원장/마트 WRITE 없음 (런 로그 INSERT만)."""

from __future__ import annotations

import random
from typing import Any

from app.qa_audit import ENGINE_VERSION
from app.qa_audit.collective_apt import (
    ASSET_TYPE,
    DOMAIN,
    asset_label,
    fetch_mart,
    lookup_region,
    normalize_asset_type,
    pick_random_targets,
    run_l1,
    run_l2,
    run_l3,
)
from app.qa_audit.report import format_report
from app.qa_audit.store import insert_run, write_json_log
from app.qa_audit.verdict import compare_metrics

DOMAINS = ("collective_apt", "built_enriched")


def _normalize_domain(domain: str | None) -> str:
    raw = (domain or DOMAIN).strip()
    aliases = {
        "collective": "collective_apt",
        "apt": "collective_apt",
        "built": "built_enriched",
        "built_enrichment": "built_enriched",
    }
    raw = aliases.get(raw, raw)
    if raw not in DOMAINS:
        raise ValueError(f"지원 domain: collective_apt / built_enriched (받은 값: {domain})")
    return raw


def run_specified(
    engine,
    *,
    calendar_year: int,
    region_code: str | None = None,
    region_name: str | None = None,
    region_level: str | None = None,
    asset_type: str | None = None,
    save_db: bool = False,
    domain: str | None = None,
) -> dict[str, Any]:
    if _normalize_domain(domain) == "built_enriched":
        from app.qa_audit.built_enriched import run_specified as _run

        return _run(
            engine,
            calendar_year=calendar_year,
            region_code=region_code,
            region_name=region_name,
            region_level=region_level,
            asset_type=asset_type,
            save_db=save_db,
        )
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
    run = _audit_one(
        engine,
        target=target,
        calendar_year=calendar_year,
        trigger="specified",
    )
    return _persist(engine, run, save_db=save_db)


def run_random(
    engine,
    *,
    calendar_year: int | None = None,
    asset_type: str | None = None,
    n: int = 1,
    save_db: bool = False,
    seed: int | None = None,
    domain: str | None = None,
) -> list[dict[str, Any]]:
    if _normalize_domain(domain) == "built_enriched":
        from app.qa_audit.built_enriched import run_random as _run

        return _run(
            engine,
            calendar_year=calendar_year,
            asset_type=asset_type,
            n=n,
            save_db=save_db,
            seed=seed,
        )
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
        # 모두 SKIP — 한 건이라도 남긴다
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
    addr1 = target.get("addr1") or target.get("sido_name")
    asset = normalize_asset_type(target.get("asset_type") or ASSET_TYPE)

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
        mart = fetch_mart(
            conn,
            region_level=level,
            region_code=code,
            calendar_year=calendar_year,
            asset_type=asset,
        )

    l3 = run_l3(
        engine,
        addr1=addr1,
        region_level=level,
        region_code=code,
        calendar_year=calendar_year,
        asset_type=asset,
    )
    l3_error = l3.get("error")
    diffs = compare_metrics(
        l1,
        l3,
        mart,
        l2=l2,
        specified=(trigger == "specified"),
        l3_error=l3_error,
    )
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
