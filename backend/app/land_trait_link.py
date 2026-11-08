"""토지 거래목록에 붙이는 특성대장 연결.

원장(land_transactions)은 수정하지 않는다. 결과는 land_transaction_trait_link 에만 있고,
목록은 요청이 있을 때만 LEFT JOIN 한다. 공시지가는 필지가 하나이고 금액이 하나일 때만 채워져 있다.
"""

from __future__ import annotations

TABLE = "land_transaction_trait_link"

NOTICE: tuple[str, ...] = (
    "CH2 Macro는 실거래자료의 소재지와 필지정보 등을 토지특성 및 개별공시지가 자료와 연결하여 공시지가를 표시합니다.",
    "공시지가는 거래연도 자료를 우선 사용하며, 없는 경우 전년도 자료를 사용할 수 있습니다. 표시된 기준연도를 함께 확인해 주세요. 자료의 관측일과 공시지가 기준시점은 다를 수 있습니다.",
)
MATCH_NOTE = (
    "공시지가는 실거래가격과 별개의 공적 자료이며, 개별 부동산의 적정가격을 의미하지 않습니다."
)

LINK_STATUS_LABELS: dict[str, str] = {
    "exact": "일치",
    "label_normalized": "표기 정규화",
    "multiple_candidates": "복수 후보",
    "other_unmatched": "미연결",
    "clean_precontract_traits_differ": "특성 불일치",
    "label_normalized_traits_differ": "표기 불일치",
    "post_contract_only": "계약 이후만",
    "no_precontract_observation": "계약 전 없음",
    "true_conflict": "충돌",
}

PRICE_STATUS_LABELS: dict[str, str] = {
    "same_year": "해당연도",
    "previous_year": "전년",
    "price_conflict": "충돌",
    "price_missing": "없음",
    "none": "",
}

UNIQUE_LINK_STATUSES = frozenset({"exact", "label_normalized"})

TRAIT_ITEM_KEYS = (
    "trait_link_status",
    "trait_link_label",
    "trait_price_status",
    "official_price_won",
    "official_price_year",
    "trait_asof",
    "trait_unverified",
    "recovered_lot",
)

TRAIT_CSV_HEADER = ["연결상태", "공시지가(원/㎡)", "공시기준연도", "공시지가구분", "특성기준일"]


def table_ready(db) -> bool:
    from sqlalchemy import text

    ready = db.execute(
        text("SELECT to_regclass('public.land_transaction_trait_link') IS NOT NULL")
    ).scalar()
    return bool(ready)


def item_fields(row: dict) -> dict:
    """Join 행을 목록 응답 필드로 바꾼다. 행이 없으면 상태만 비운다."""
    raw_status = row.get("trait_link_status")
    status = str(raw_status).strip() if raw_status is not None else ""
    status = status or None
    raw_price = row.get("trait_price_status")
    price_status = str(raw_price).strip() if raw_price is not None else ""
    price_status = price_status or None
    amount = row.get("official_price_won")
    year = row.get("official_price_year")
    label = None
    if status:
        label = LINK_STATUS_LABELS.get(status, status)
    raw_lot = row.get("recovered_lot")
    lot = str(raw_lot).strip() if raw_lot is not None else ""
    if status not in UNIQUE_LINK_STATUSES:
        lot = ""
    return {
        "trait_link_status": status,
        "trait_link_label": label,
        "trait_price_status": price_status,
        "official_price_won": None if amount is None else float(amount),
        "official_price_year": None if year is None else int(year),
        "trait_asof": row.get("trait_asof"),
        "trait_unverified": None if status is None else bool(row.get("trait_unverified")),
        "recovered_lot": lot or None,
    }


def csv_cells(row: dict) -> list:
    status = row.get("trait_link_status")
    if not status:
        return ["미계산", "미계산", "", "", ""]
    price_status = row.get("trait_price_status") or ""
    amount = row.get("official_price_won")
    if price_status in ("same_year", "previous_year") and amount is not None:
        price_cell: object = amount
    elif price_status == "price_conflict":
        price_cell = "충돌"
    elif price_status == "price_missing":
        price_cell = "없음"
    else:
        price_cell = ""
    year = row.get("official_price_year")
    asof = row.get("trait_asof")
    if hasattr(asof, "isoformat"):
        asof_text = asof.isoformat()
    elif asof:
        asof_text = str(asof)[:10]
    else:
        asof_text = ""
    kind = PRICE_STATUS_LABELS.get(price_status, "") if price_status and price_status != "none" else ""
    return [
        row.get("trait_link_label") or LINK_STATUS_LABELS.get(status, status),
        price_cell,
        "" if year is None else int(year),
        kind,
        asof_text,
    ]
