"""토지 거래목록에 붙이는 특성대장 연결.

원장(land_transactions)은 수정하지 않는다. 결과는 land_transaction_trait_link 에만 있고,
목록은 요청이 있을 때만 LEFT JOIN 한다. 공시지가는 필지가 하나이고 금액이 하나일 때만 채워져 있다.
"""

from __future__ import annotations

TABLE = "land_transaction_trait_link"

NOTICE: tuple[str, ...] = (
    "이 버튼은 거래 목록에 토지특성 대장의 공시지가와 특성 기준일을 붙입니다. 실거래 원장의 값은 바꾸지 않습니다.",
    "필지가 하나로 정해진 거래만 공시지가를 채웁니다. 후보가 여러 개이거나, 계약일 이전 관측이 없거나, 같은 해 공시지가가 서로 다르면 금액을 채우지 않고 상태만 보여 줍니다.",
)
MATCH_NOTE = (
    "전국 연결 시험(2019년 이후, 비교 가능 거래)에서 필지가 하나로 정해진 비율은 71.4%입니다. "
    "연결은 검증 전입니다."
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

TRAIT_ITEM_KEYS = (
    "trait_link_status",
    "trait_link_label",
    "trait_price_status",
    "official_price_won",
    "official_price_year",
    "trait_asof",
    "trait_unverified",
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
    return {
        "trait_link_status": status,
        "trait_link_label": label,
        "trait_price_status": price_status,
        "official_price_won": None if amount is None else float(amount),
        "official_price_year": None if year is None else int(year),
        "trait_asof": row.get("trait_asof"),
        "trait_unverified": None if status is None else bool(row.get("trait_unverified")),
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
