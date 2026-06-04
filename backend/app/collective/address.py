"""건물 목록·상세용 주소 표시 문자열."""

from __future__ import annotations


def format_building_address(
    *,
    addr3: str | None,
    addr4: str | None,
    lot_number: str | None,
    road_name: str | None,
) -> str:
    a3 = (addr3 or "").strip()
    a4 = (addr4 or "").strip()
    lot = (lot_number or "").strip()
    road = (road_name or "").strip()

    parts: list[str] = []
    if a3 and a4:
        parts.extend([a3, a4])
    elif a4:
        parts.append(a4)
    elif a3:
        parts.append(a3)
    if lot:
        parts.append(lot)
    if parts:
        return " ".join(parts)
    return road
