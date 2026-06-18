"""건물 목록·상세용 주소 표시 문자열."""

from __future__ import annotations


def _strip(value: str | None) -> str:
    return (value or "").strip()


def _is_gu(name: str) -> bool:
    return bool(name) and name.endswith("구")


def format_jibun_address(
    *,
    addr3: str | None,
    addr4: str | None,
    addr5: str | None = None,
    lot_number: str | None,
) -> str:
    """읍·면·동 + 리 + 번지 (구·시군구 제외)."""
    a3 = _strip(addr3)
    a4 = _strip(addr4)
    a5 = _strip(addr5)
    lot = _strip(lot_number)

    if _is_gu(a3):
        eup = a4
        ri = a5
    else:
        eup = a3
        ri = a5 or (a4 if a4.endswith("리") else "")

    parts = [p for p in (eup, ri, lot) if p]
    return " ".join(parts) if parts else "—"


def format_road_address(*, road_name: str | None) -> str:
    road = _strip(road_name)
    return road or "—"


def format_building_address(
    *,
    addr3: str | None,
    addr4: str | None,
    lot_number: str | None,
    road_name: str | None,
    addr5: str | None = None,
) -> str:
    """하위 호환 — 지번 + (도로명)."""
    jibun = format_jibun_address(addr3=addr3, addr4=addr4, addr5=addr5, lot_number=lot_number)
    road = format_road_address(road_name=road_name)
    if jibun != "—" and road != "—" and road not in jibun:
        return f"{jibun} ({road})"
    if jibun != "—":
        return jibun
    return road


def split_building_addresses(
    *,
    addr3: str | None,
    addr4: str | None,
    addr5: str | None,
    lot_number: str | None,
    road_name: str | None,
) -> tuple[str, str, str]:
    """(jibun_address, road_address, legacy address)."""
    jibun = format_jibun_address(addr3=addr3, addr4=addr4, addr5=addr5, lot_number=lot_number)
    road = format_road_address(road_name=road_name)
    legacy = format_building_address(
        addr3=addr3,
        addr4=addr4,
        addr5=addr5,
        lot_number=lot_number,
        road_name=road_name,
    )
    return jibun, road, legacy
