"""복합부동산 거래목록 CSV 내보내기 — 목록 API와 동일 필터."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from typing import Any

from starlette.responses import Response

from app.collective.transaction_export import csv_attachment_response, safe_filename_part

MAX_BUILT_TX_EXPORT = 50_000

ASSET_TYPE_LABELS = {
    "commercial": "상업",
    "factory": "공장",
    "detached": "단독",
}


def format_contract_date_csv(row: dict[str, Any]) -> str:
    cd = row.get("contract_date")
    if cd is not None:
        if isinstance(cd, date):
            return cd.isoformat()
        return str(cd)[:10]
    cy = row.get("contract_year")
    cm = row.get("contract_month")
    if cy is not None and cm is not None:
        return f"{int(cy)}-{int(cm):02d}"
    if cy is not None:
        return str(int(cy))
    return str(row.get("trade_year_label") or "")


def export_filename(*, scope_label: str = "built") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    base = safe_filename_part(scope_label)
    if base == "export":
        base = "built"
    return f"{base}_transactions_{ts}.csv"


def built_transactions_csv_bytes(
    rows: list[dict[str, Any]],
    *,
    asset_type: str | None,
) -> bytes:
    show_asset = asset_type == "all" or asset_type is None
    show_zone = asset_type != "detached"
    use_label = "주택유형" if asset_type == "detached" else "건축물용도"

    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf, lineterminator="\n")
    header = [
        *(["유형"] if show_asset else []),
        "주소",
        "계약일",
        *(["용도지역"] if show_zone else []),
        use_label,
        "금액(만원)",
        "연면적(㎡)",
        "대지면적(㎡)",
        "연식",
        "도로조건",
    ]
    writer.writerow(header)
    for r in rows:
        row_asset = str(r.get("asset_type") or "")
        zone_val = "" if row_asset == "detached" else (r.get("zone_type") or "")
        line = [
            *( [ASSET_TYPE_LABELS.get(row_asset, row_asset)] if show_asset else [] ),
            r.get("display_address") or "",
            format_contract_date_csv(r),
            *( [zone_val] if show_zone else [] ),
            r.get("building_use") or "",
            "" if r.get("price") is None else r["price"],
            "" if r.get("gross_area") is None else r["gross_area"],
            "" if r.get("land_area") is None else r["land_area"],
            "" if r.get("building_age") is None else r["building_age"],
            r.get("road_width_label") or "",
        ]
        writer.writerow(line)
    return buf.getvalue().encode("utf-8")


def built_csv_response(payload: bytes, filename: str) -> Response:
    return csv_attachment_response(payload, filename)
