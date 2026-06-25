"""집합부동산 거래목록 CSV 내보내기 — 목록 API와 동일 필터."""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timezone
from typing import Any

from starlette.responses import Response

MAX_COLLECTIVE_TX_EXPORT = 50_000

TX_SELECT = """
    SELECT id, asset_type, building_key, display_name,
           contract_year, contract_month, contract_date,
           exclusive_area, price, unit_price, floor, dong, housing_subtype,
           buyer_type, seller_type, deal_type
    FROM collective_transactions
"""


def tx_row_dict(row: Any) -> dict[str, Any]:
    """SQLAlchemy Row → CollectiveTransactionRow kwargs (contract_date ISO)."""
    d = dict(row)
    cd = d.get("contract_date")
    if cd is not None and hasattr(cd, "isoformat"):
        d["contract_date"] = cd.isoformat()
    return d


def format_contract_date_csv(row: dict[str, Any]) -> str:
    cd = row.get("contract_date")
    if cd is not None:
        if isinstance(cd, date):
            return cd.isoformat()
        return str(cd)[:10]
    cy = row.get("contract_year")
    cm = row.get("contract_month")
    if cy is not None and cm is not None:
        return f"{int(cy)}-{int(cm):02d}-01"
    if cy is not None:
        return str(int(cy))
    return ""


def dong_cell(row: dict[str, Any], asset_type: str) -> str:
    if asset_type == "presale":
        return str(row.get("housing_subtype") or "")
    return str(row.get("dong") or "")


def dong_header(asset_type: str) -> str:
    return "권리" if asset_type == "presale" else "동"


def safe_filename_part(label: str, *, max_len: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9\-_]+", "_", (label or "export").strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:max_len] or "export")


def export_filename(
    *,
    display_name: str,
    prefix: str = "transactions",
    fallback_key: str | None = None,
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    base = safe_filename_part(display_name)
    if base == "export" and fallback_key:
        base = safe_filename_part(fallback_key[:16])
    if base == "export":
        base = "collective"
    return f"{base}_{prefix}_{ts}.csv"


def csv_attachment_response(payload: bytes, filename: str) -> Response:
    safe = safe_filename_part(filename.replace(".csv", "")) + ".csv"
    if safe == ".csv" or safe == "export.csv":
        safe = "collective_transactions.csv"
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


def transactions_csv_bytes(
    rows: list[dict[str, Any]],
    *,
    asset_type: str,
    include_building: bool = False,
) -> bytes:
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf, lineterminator="\n")
    header = [
        *(["단지"] if include_building else []),
        "계약일",
        dong_header(asset_type),
        "층",
        "면적(㎡)",
        "금액(만원)",
        "단가(만원/㎡)",
        "매수",
        "매도",
        "거래유형",
    ]
    writer.writerow(header)
    for r in rows:
        line = [
            *( [r.get("display_name") or ""] if include_building else [] ),
            format_contract_date_csv(r),
            dong_cell(r, asset_type),
            "" if r.get("floor") is None else r["floor"],
            "" if r.get("exclusive_area") is None else r["exclusive_area"],
            "" if r.get("price") is None else r["price"],
            "" if r.get("unit_price") is None else r["unit_price"],
            r.get("buyer_type") or "",
            r.get("seller_type") or "",
            r.get("deal_type") or "",
        ]
        writer.writerow(line)
    return buf.getvalue().encode("utf-8")
