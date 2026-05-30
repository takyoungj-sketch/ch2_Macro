"""land_transactions.transaction_hash 생성 (clean·dedupe·rehash 공용)."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping


def transaction_hash_key(
    *,
    beopjungri_code: str | None = None,
    sigungu_code: str | None = None,
    sigungu_name: str | None = None,
    contract_year: Any = "",
    contract_month: Any = "",
    contract_day: Any = "",
    lot_number: str | None = None,
    main_number: str | None = None,
    sub_number: str | None = None,
    lot_display: str | None = None,
    area_sqm: Any = "",
    total_price_10k: Any = "",
    cancel_date: str | None = None,
    cancel_type: str | None = None,
    cancel_flag_raw: str | None = None,
    is_cancelled: bool | None = None,
) -> str:
    """
    거래 1건의 논리 키 문자열.

    Excel 순번·raw_id 는 **포함하지 않는다** — 재적재·다른 엑셀 export 에서
    동일 거래가 다른 hash 로 쌓이는 것을 막기 위함 (2026-06 dedupe).
    """
    region_key = (
        _s(beopjungri_code) or _s(sigungu_code) or _s(sigungu_name) or ""
    )
    lot_key = _s(lot_number)
    if not lot_key:
        lot_key = "|".join(_s(c) for c in (main_number, sub_number))
    if not lot_key:
        lot_key = _s(lot_display) or ""

    cancel_flag = _s(cancel_flag_raw)
    if not cancel_flag and is_cancelled:
        cancel_flag = "1"

    return "|".join(
        str(v)
        for v in [
            region_key,
            contract_year,
            contract_month,
            contract_day,
            lot_key,
            area_sqm,
            total_price_10k,
            _s(cancel_date),
            _s(cancel_type),
            cancel_flag,
        ]
    )


def make_transaction_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def hash_from_series(row: Mapping[str, Any]) -> str:
    """clean.py DataFrame 행 → SHA-256 hex."""
    day = row.get("contract_day")
    if day is None or (isinstance(day, float) and str(day) == "nan"):
        cd = row.get("contract_date")
        if cd is not None and hasattr(cd, "day"):
            day = cd.day
    return make_transaction_hash(
        transaction_hash_key(
            beopjungri_code=row.get("beopjungri_code"),
            sigungu_code=row.get("sigungu_code"),
            sigungu_name=row.get("sigungu_name"),
            contract_year=row.get("contract_year", ""),
            contract_month=row.get("contract_month", ""),
            contract_day=day if day is not None else "",
            lot_number=row.get("lot_number"),
            main_number=row.get("main_number"),
            sub_number=row.get("sub_number"),
            lot_display=row.get("lot_display"),
            area_sqm=row.get("area_sqm", ""),
            total_price_10k=row.get("total_price_10k", ""),
            cancel_date=row.get("cancel_date"),
            cancel_type=row.get("cancel_type"),
            cancel_flag_raw=row.get("cancel_flag_raw"),
        )
    )


def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and str(v) == "nan":
        return ""
    return str(v).strip()
