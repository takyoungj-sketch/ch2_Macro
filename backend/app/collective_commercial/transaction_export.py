"""집합상가·공장 거래목록 CSV — 목록 API와 동일 필터."""

from __future__ import annotations

import csv
import io
from typing import Any

from app.collective.transaction_export import format_contract_date_csv


def _road_width_cell(row: dict[str, Any]) -> str:
    label = row.get("road_width_label")
    if label:
        return str(label)
    code = row.get("road_code")
    if code is not None:
        return f"{code}m"
    return ""


def _dong_cell(row: dict[str, Any]) -> str:
    parts = [row.get("addr3"), row.get("addr4")]
    return " ".join(str(p).strip() for p in parts if p and str(p).strip())


def commercial_transactions_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "계약일",
            "동",
            "번지",
            "용도지역",
            "도로폭",
            "건축물용도",
            "준공",
            "층",
            "연면적(㎡)",
            "금액(만원)",
            "단가(만원/㎡)",
            "매수",
            "매도",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                format_contract_date_csv(r),
                _dong_cell(r),
                r.get("lot_number") or "",
                r.get("zone_type") or "",
                _road_width_cell(r),
                r.get("building_use") or "",
                "" if r.get("building_year") is None else r["building_year"],
                "" if r.get("floor") is None else r["floor"],
                "" if r.get("gross_area") is None else r["gross_area"],
                "" if r.get("price") is None else r["price"],
                "" if r.get("unit_price") is None else r["unit_price"],
                r.get("buyer_type") or "",
                r.get("seller_type") or "",
            ]
        )
    return buf.getvalue().encode("utf-8")
