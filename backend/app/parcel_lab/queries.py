"""대장DB 읽기 전용 조회. 상한 100행. ANY 없이 = / ILIKE."""

from __future__ import annotations

import re
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.parcel_lab.sido import sido_label

PAGE_MAX = 100
BUILDING_CAP = 200
ZONE_CAP = 40
QueryKind = Literal["pnu", "bjd", "name", "empty"]

_PNU_RE = re.compile(r"^\d{19}$")
_DIGITS = re.compile(r"\D")


def classify_query(q: str | None) -> tuple[QueryKind, str]:
    raw = (q or "").strip()
    if not raw:
        return "empty", ""
    digits = _DIGITS.sub("", raw)
    compact = raw.replace(" ", "")
    if len(digits) == 19 and digits.isdigit():
        return "pnu", digits
    if len(digits) == 10 and digits.isdigit() and compact == digits:
        return "bjd", digits
    if len(raw) < 2:
        return "empty", ""
    return "name", raw


def fetch_status(conn: Connection) -> dict[str, Any]:
    n_building = int(conn.execute(text("SELECT COUNT(*) FROM building")).scalar() or 0)
    n_parcel = int(conn.execute(text("SELECT COUNT(*) FROM parcel")).scalar() or 0)
    n_zone = 0
    n_zone_pnu = 0
    n_zone_fine = 0
    has_zone = conn.execute(
        text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'parcel_zone'")
    ).scalar()
    if has_zone:
        n_zone = int(conn.execute(text("SELECT COUNT(*) FROM parcel_zone")).scalar() or 0)
        n_zone_pnu = int(conn.execute(text("SELECT COUNT(DISTINCT pnu) FROM parcel_zone")).scalar() or 0)
        n_zone_fine = int(
            conn.execute(text("SELECT COUNT(*) FROM parcel_zone WHERE NOT is_coarse")).scalar() or 0
        )

    kinds = [
        {"kind": str(r[0]), "n": int(r[1])}
        for r in conn.execute(text("SELECT ledger_kind, COUNT(*) FROM building GROUP BY 1 ORDER BY 1"))
    ]
    snaps = [
        {"snapshot": str(r[0]), "n": int(r[1])}
        for r in conn.execute(text("SELECT snapshot, COUNT(*) FROM building GROUP BY 1 ORDER BY 1"))
    ]
    sido_rows = list(
        conn.execute(
            text(
                """
                SELECT p.sido_code,
                       COUNT(*) AS n_parcel,
                       COALESCE(SUM(p.n_buildings), 0) AS n_dong_keys
                FROM parcel p
                GROUP BY p.sido_code
                ORDER BY p.sido_code
                """
            )
        )
    )
    b_by_sido = {
        str(r[0]): int(r[1])
        for r in conn.execute(text("SELECT sido_code, COUNT(*) FROM building GROUP BY 1"))
    }
    sidos = [
        {
            "sido_code": str(code),
            "label": sido_label(str(code)),
            "n_parcel": int(n_p),
            "n_building": b_by_sido.get(str(code), 0),
        }
        for code, n_p, _n_keys in sido_rows
    ]
    return {
        "available": True,
        "n_building": n_building,
        "n_parcel": n_parcel,
        "n_zone": n_zone,
        "n_zone_pnu": n_zone_pnu,
        "n_zone_fine": n_zone_fine,
        "kinds": kinds,
        "snapshots": snaps,
        "sidos": sidos,
        "note": "표제부 집합 동에서 파생한 필지만. 토지만 있는 필지·「일반」 행은 없음.",
    }


def search_parcels(
    conn: Connection,
    *,
    q: str | None,
    sido: str | None,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    limit = min(max(limit, 1), PAGE_MAX)
    offset = max(offset, 0)
    kind, value = classify_query(q)
    sido_code = (sido or "").strip()
    if sido_code and (len(sido_code) != 2 or not sido_code.isdigit()):
        sido_code = ""

    if kind == "empty" and not sido_code:
        return {
            "items": [],
            "n": 0,
            "truncated": False,
            "kind": kind,
            "note": "시도를 고르거나 PNU·법정동코드·건물명을 넣으세요.",
        }

    where = ["1=1"]
    params: dict[str, Any] = {"lim": limit, "off": offset}
    if sido_code:
        where.append("p.sido_code = :sido")
        params["sido"] = sido_code

    join_building = False
    if kind == "pnu":
        where.append("p.pnu = :pnu")
        params["pnu"] = value
    elif kind == "bjd":
        where.append("p.beopjungri_code = :bjd")
        params["bjd"] = value
    elif kind == "name":
        join_building = True
        where.append("b.building_name ILIKE :pat")
        params["pat"] = f"%{value}%"

    where_sql = " AND ".join(where)
    from_sql = "parcel p"
    if join_building:
        from_sql = "building b JOIN parcel p ON p.pnu = b.pnu"

    count_sql = f"SELECT COUNT(DISTINCT p.pnu) FROM {from_sql} WHERE {where_sql}"
    n = int(conn.execute(text(count_sql), params).scalar() or 0)

    list_sql = f"""
        SELECT DISTINCT ON (p.pnu)
            p.pnu, p.sido_code, p.beopjungri_code, p.bun, p.ji,
            p.n_buildings, p.land_area, p.jimok_code, p.land_area_source,
            p.first_seen, p.last_seen,
            (SELECT b2.building_name FROM building b2
              WHERE b2.pnu = p.pnu AND b2.building_name IS NOT NULL
                AND b2.building_name <> ''
              ORDER BY b2.snapshot DESC LIMIT 1) AS building_name
        FROM {from_sql}
        WHERE {where_sql}
        ORDER BY p.pnu
        LIMIT :lim OFFSET :off
    """
    rows = conn.execute(text(list_sql), params).mappings().all()
    items = [_parcel_row(r) for r in rows]
    return {
        "items": items,
        "n": n,
        "truncated": n > offset + len(items) or (len(items) >= limit and n > limit),
        "kind": kind,
        "note": None,
    }


def fetch_parcel_detail(conn: Connection, pnu: str) -> dict[str, Any] | None:
    digits = _DIGITS.sub("", pnu or "")
    if not _PNU_RE.fullmatch(digits):
        return None
    prow = conn.execute(
        text(
            """
            SELECT pnu, sido_code, beopjungri_code, bun, ji, sigungu_code,
                   jimok_code, land_area, land_area_source, first_seen, last_seen, n_buildings
            FROM parcel WHERE pnu = :pnu
            """
        ),
        {"pnu": digits},
    ).mappings().first()
    if not prow:
        return None
    buildings = conn.execute(
        text(
            """
            SELECT mgmt_pk, snapshot, ledger_kind, building_name, dong_name,
                   structure_name, structure_group, main_purpose, purpose_detail,
                   households, floors_above, floors_below, gross_area, arch_area,
                   plat_area, approve_date
            FROM building
            WHERE pnu = :pnu
            ORDER BY snapshot DESC, mgmt_pk
            LIMIT :cap
            """
        ),
        {"pnu": digits, "cap": BUILDING_CAP},
    ).mappings().all()
    zones: list[dict[str, Any]] = []
    has_zone = conn.execute(
        text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'parcel_zone'")
    ).scalar()
    if has_zone:
        zones = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT zone_label, zone_family, is_coarse, source, snapshot
                    FROM parcel_zone
                    WHERE pnu = :pnu
                    ORDER BY is_coarse, zone_label
                    LIMIT :cap
                    """
                ),
                {"pnu": digits, "cap": ZONE_CAP},
            ).mappings()
        ]
    parcel = _parcel_row(prow)
    parcel["sigungu_code"] = prow.get("sigungu_code")
    return {
        "parcel": parcel,
        "buildings": [dict(r) for r in buildings],
        "zones": zones,
        "buildings_capped": len(buildings) >= BUILDING_CAP,
    }


def _parcel_row(r: Any) -> dict[str, Any]:
    pnu = str(r["pnu"])
    bun = str(r.get("bun") or "")
    ji = str(r.get("ji") or "")
    lot = f"{int(bun)}-{int(ji)}" if bun.isdigit() and ji.isdigit() else f"{bun}-{ji}"
    return {
        "pnu": pnu,
        "sido_code": r.get("sido_code"),
        "sido_label": sido_label(str(r.get("sido_code") or "")),
        "beopjungri_code": r.get("beopjungri_code"),
        "bun": bun,
        "ji": ji,
        "lot": lot,
        "n_buildings": r.get("n_buildings"),
        "land_area": float(r["land_area"]) if r.get("land_area") is not None else None,
        "jimok_code": r.get("jimok_code"),
        "land_area_source": r.get("land_area_source"),
        "first_seen": r.get("first_seen"),
        "last_seen": r.get("last_seen"),
        "building_name": r.get("building_name"),
    }
