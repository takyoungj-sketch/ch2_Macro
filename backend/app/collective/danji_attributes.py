"""집합(주거) 단지 속성 조회 — K-apt 매칭 결과 노출 (P2.5).

설계 SSOT: `docs/COLLECTIVE_TWO_STAGE_HEDONIC_DESIGN.md` §0.1 · §3.1 · §3.1.1.

값만 내려보내지 않는다 — 출처(`source_label`)·매칭 신뢰도(`match`)·원본 이상값
사유(`quality_flags`)·회귀 표본 제외 사유(`notes`)를 함께 반환한다. 판정 임계값은
`pipeline/collective/apply_danji_dictionary.py` 상단 상수가 SSOT이며 여기서는
그 결과 코드(`attr_quality_flags`)를 사람이 읽는 문장으로만 옮긴다.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.schemas import BuildingStatsRow

ATTRIBUTES_TABLE = "collective_building_attributes"
BUILDER_MASTER_TABLE = "builder_master"
LAND_PRICE_TABLE = "collective_building_assessed_land_price"
_JOINT_SPLIT_RE = re.compile(r"[,/·]|\s+및\s+")
_HH_LIST_FLAGS = frozenset({"hh_zero", "scale_inconsistent"})

# match_tier → 라벨·신뢰도·회귀 사용 가능 여부 (아파트 hard: A·B·C·D·F)
TIER_META: dict[str, dict[str, Any]] = {
    "A": {"label": "단지명 완전일치", "reliability": "높음", "usable": True},
    "B": {"label": "단지명 핵심어 일치", "reliability": "높음", "usable": True},
    "C": {"label": "법정동+지번 완전일치", "reliability": "높음", "usable": True},
    "D": {"label": "지번 복수 단지(세대 합산)", "reliability": "중간", "usable": True},
    "E": {"label": "단지명 부분일치(단일후보)", "reliability": "낮음", "usable": False},
    "F": {"label": "단지명 복수 후보(세대 합산)", "reliability": "중간", "usable": True},
    "P": {"label": "필지고유번호 유일", "reliability": "중간", "usable": False},
    "T": {"label": "표제부 동 합산", "reliability": "중간", "usable": False},
    "Z": {"label": "미매칭", "reliability": "없음", "usable": False},
}

# attr_quality_flags 코드 → 사람이 읽는 라벨·사유·해당 필드
QUALITY_FLAG_META: dict[str, dict[str, Any]] = {
    "hh_zero": {
        "label": "세대수 0",
        "detail": "원본 세대수가 0으로 기록됐습니다.",
        "affected_fields": ["households"],
    },
    "floor_implausible": {
        "label": "최고층수 이상값",
        "detail": (
            "최고층수가 3층 미만이거나 101층을 초과합니다 — "
            "원본에 자리표시자(1)가 들어간 경우가 많습니다."
        ),
        "affected_fields": ["max_floor"],
    },
    "parking_implausible": {
        "label": "세대당 주차 이상값",
        "detail": (
            "세대당 주차가 5대를 초과합니다 — 세대수가 일부만 기록된 신호입니다."
        ),
        "affected_fields": ["parking_total", "parking_per_household"],
    },
    "scale_inconsistent": {
        "label": "세대수·동수·층수 불일치",
        "detail": (
            "층당 세대수가 20세대를 넘습니다 — 세대수·동수·최고층수 중 하나가 "
            "원본에서 잘못 기록됐으며, 어느 값이 틀렸는지는 특정할 수 없습니다."
        ),
        "affected_fields": ["households", "dong_count", "max_floor"],
    },
}

NOTE_NOT_USABLE = "매칭 신뢰도가 낮아 이 단지는 브랜드·규모 회귀 표본에서 제외됩니다."
NOTE_QUALITY_FLAGGED = (
    "원본 이상값이 있어 해당 변수는 회귀에서 결측으로 처리됩니다. "
    "값 자체는 원본 그대로 표시합니다."
)
NOTE_JOINT_BUILDER = (
    "공동시공 단지입니다. 기업집단은 원문 첫 번째 시공사를 기준으로 표시했습니다."
)
NOTE_BUILDER_GROUP_MISSING = (
    "원문이 시공사가 아니거나(조합·신탁 등) 실체를 특정할 수 없어 "
    "기업집단은 비워 뒀습니다."
)
NOTE_PUBLIC_SUPPLIER = (
    "공공 공급주체(LH 등)로, 민간 브랜드 프리미엄과는 성격이 다릅니다."
)
NOTE_BRAND_NOT_DETECTED = (
    "브랜드 사전에서 검출되지 않았습니다 — 「브랜드 없음」이 확정된 것은 아닙니다."
)
NOTE_BRAND_LOW_CONFIDENCE = "브랜드-시공사 대응이 확인 필요 수준(low)입니다."
NOTE_BRAND_WITHOUT_MATCH = (
    "브랜드는 K-apt 매칭과 무관하게 실거래 단지명에서 추출하므로, "
    "K-apt 단지 정보가 없어도 표시됩니다."
)
NOTE_YEAR_DIFF = (
    "K-apt 사용승인연도와 실거래 건축연도가 {n}년 차이 납니다 — "
    "매칭 오류 가능성을 감안하세요."
)
NOTE_NON_APARTMENT = (
    "K-apt는 아파트 위주로 등록되어 이 자산유형은 정보가 없을 수 있습니다."
)

MATCH_NOTE_YEAR_EXACT = "K-apt 사용승인연도와 실거래 건축연도가 일치합니다."
MATCH_NOTE_NO_MATCH = (
    "K-apt 단지와 연결되지 않았습니다. K-apt는 의무관리대상(150세대 이상 등) "
    "공동주택만 등록되므로 소규모 단지는 정보가 없습니다."
)
MATCH_NOTE_PNU_UNIQUE = (
    "주소 규칙으로는 못 붙였고, K-apt 필지고유번호가 이 지번에 하나뿐입니다. "
    "목록 세대수·시공사는 채우지만 지역회귀 hard 표본(A·B·C)에는 넣지 않습니다."
)
MATCH_NOTE_TITLE_PNU = (
    "K-apt에 없는 필지입니다. 세대수·층·구조는 표제부에서 같은 용도 동을 합친 값이고, "
    "시공사는 표제부에 없습니다. 지역회귀 hard 표본(A·B·C)에는 넣지 않습니다."
)
MATCH_NOTE_MULTI = (
    "같은 지번 또는 단지명에 K-apt 단지가 둘 이상입니다. "
    "세대수·동수·주차는 합산하고, 시공사는 첫 단지 기준에 「외」를 붙입니다. "
    "후보는 아래 표에 모두 보여 줍니다."
)

# 브랜드는 K-apt가 아니라 실거래 단지명에서 추출한다
# (`pipeline/collective/apply_danji_dictionary.py::_load_display_names`).
BRAND_DETECTED_FROM = "실거래 단지명"

_ATTR_COLUMNS = """
    a.snapshot_ym, a.asset_type, a.match_tier, a.match_rule, a.danji_code,
    a.approved_year, a.building_year, a.year_diff,
    a.builder_raw, a.builder_norm, a.builder_group,
    a.builder_is_joint, a.builder_is_public, a.developer_raw,
    a.brand, a.brand_confidence, a.brand_is_public,
    a.structure_raw, a.structure_group,
    a.households, a.households_sale, a.households_rent,
    a.dong_count, a.max_floor, a.parking_total, a.parking_per_household,
    a.danji_class, a.supply_type,
    a.attr_quality_flags, a.dictionary_version, a.n_tx
"""


def _table_exists(conn: Connection, table: str) -> bool:
    return (
        conn.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar()
        is not None
    )


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    return (
        conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :t AND column_name = :c
                """
            ),
            {"t": table, "c": column},
        ).scalar()
        is not None
    )


def source_label(snapshot_ym: str | None, *, tier: str | None = None) -> str:
    """출처 문구 — 어느 스냅샷을 본 결과인지 항상 함께 노출한다."""
    if tier == "T":
        return "건축물대장 표제부 (집합)"
    base = "국토교통부 공동주택관리정보시스템(K-apt)"
    if snapshot_ym and len(snapshot_ym) >= 6 and snapshot_ym[:6].isdigit():
        return f"{base} {snapshot_ym[:4]}년 {snapshot_ym[4:6]}월 스냅샷"
    return f"{base} 스냅샷"


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _tier_meta(tier: str) -> dict[str, Any]:
    return TIER_META.get(tier) or {"label": tier, "reliability": "없음", "usable": False}


def _quality_flags(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    for code in [c.strip() for c in str(raw).split(",") if c.strip()]:
        meta = QUALITY_FLAG_META.get(code)
        if meta is None:
            # 사전에 없는 코드는 문구를 만들지 않고 코드만 그대로 노출한다.
            out.append({"code": code, "label": code, "detail": None, "affected_fields": []})
            continue
        out.append(
            {
                "code": code,
                "label": meta["label"],
                "detail": meta["detail"],
                "affected_fields": list(meta["affected_fields"]),
            }
        )
    return out


def _non_apartment_notes(asset_type: str | None) -> list[str]:
    """자산유형을 아는 경우에만 안내한다 — 모르는 키에는 사유를 만들지 않는다."""
    if asset_type and asset_type != "apartment":
        return [NOTE_NON_APARTMENT]
    return []


def _ledger_meta(conn: Connection, building_key: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT MAX(asset_type) AS asset_type,
                   MAX(building_year) AS building_year
            FROM collective_transactions
            WHERE building_key = :bk
            """
        ),
        {"bk": building_key},
    ).mappings().first()
    if not row or row["asset_type"] is None:
        return None
    return dict(row)


def _fetch_assessed_land_price(
    conn: Connection,
    building_key: str,
    asset_type: str | None,
) -> dict[str, Any] | None:
    """대표 필지 최신 개별공시지가를 단지정보 탭용으로 조회한다."""
    if not _table_exists(conn, LAND_PRICE_TABLE):
        return None
    where = ["building_key = :bk"]
    params: dict[str, Any] = {"bk": building_key}
    if asset_type:
        where.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    row = conn.execute(
        text(
            f"""
            SELECT assessed_land_price, assessed_land_price_year,
                   representative_pnu, source
            FROM {LAND_PRICE_TABLE}
            WHERE {' AND '.join(where)}
            ORDER BY assessed_land_price_year DESC
            LIMIT 1
            """
        ),
        params,
    ).mappings().first()
    if not row:
        return None
    return {
        "assessed_land_price": _to_float(row["assessed_land_price"]),
        "assessed_land_price_year": _to_int(row["assessed_land_price_year"]),
        "representative_pnu": str(row["representative_pnu"]).strip()
        if row["representative_pnu"]
        else None,
        "source": str(row["source"]).strip() if row["source"] else None,
    }


def _latest_snapshot_ym(conn: Connection) -> str | None:
    value = conn.execute(
        text(f"SELECT MAX(snapshot_ym) FROM {ATTRIBUTES_TABLE}")
    ).scalar()
    return str(value).strip() if value else None


def _fetch_row(
    conn: Connection,
    building_key: str,
    snapshot_ym: str | None,
) -> dict[str, Any] | None:
    join_sql = ""
    select_name = "NULL::varchar AS danji_name"
    select_codes = "NULL::text AS match_danji_codes"
    if _table_exists(conn, BUILDER_MASTER_TABLE):
        join_sql = f"""
            LEFT JOIN {BUILDER_MASTER_TABLE} m
                   ON m.danji_code = a.danji_code
                  AND m.snapshot_ym = a.snapshot_ym
        """
        select_name = "m.danji_name AS danji_name"
    if _column_exists(conn, ATTRIBUTES_TABLE, "match_danji_codes"):
        select_codes = "a.match_danji_codes AS match_danji_codes"
    where = ["a.building_key = :bk"]
    params: dict[str, Any] = {"bk": building_key}
    if snapshot_ym:
        where.append("a.snapshot_ym = :ym")
        params["ym"] = snapshot_ym
    row = conn.execute(
        text(
            f"""
            SELECT {_ATTR_COLUMNS}, {select_name}, {select_codes}
            FROM {ATTRIBUTES_TABLE} a
            {join_sql}
            WHERE {" AND ".join(where)}
            ORDER BY a.snapshot_ym DESC
            LIMIT 1
            """
        ),
        params,
    ).mappings().first()
    return dict(row) if row else None


def _parse_danji_codes(danji_code: Any, match_danji_codes: Any) -> list[str]:
    if match_danji_codes:
        parts = [p.strip() for p in str(match_danji_codes).split(",") if p.strip()]
        if parts:
            return parts
    if danji_code:
        code = str(danji_code).strip()
        if code:
            return [code]
    return []


def _fetch_candidates(
    conn: Connection,
    snapshot_ym: str | None,
    codes: list[str],
) -> list[dict[str, Any]]:
    if not codes or not snapshot_ym or not _table_exists(conn, BUILDER_MASTER_TABLE):
        return []
    rows = conn.execute(
        text(
            f"""
            SELECT danji_code, danji_name, households, builder_raw
            FROM {BUILDER_MASTER_TABLE}
            WHERE snapshot_ym = :ym
              AND danji_code = ANY(:codes)
            """
        ),
        {"ym": snapshot_ym, "codes": codes},
    ).mappings().all()
    by_code = {str(r["danji_code"]): dict(r) for r in rows}
    out: list[dict[str, Any]] = []
    for code in codes:
        r = by_code.get(code)
        if r is None:
            out.append(
                {
                    "danji_code": code,
                    "danji_name": None,
                    "households": None,
                    "builder_raw": None,
                }
            )
            continue
        out.append(
            {
                "danji_code": str(r["danji_code"]),
                "danji_name": r.get("danji_name"),
                "households": _to_int(r.get("households")),
                "builder_raw": r.get("builder_raw"),
            }
        )
    return out


def _unmatched_payload(
    *,
    building_key: str,
    snapshot_ym: str | None,
    building_year: int | None,
    tier: str,
    rule: str,
    match_note: str | None,
    notes: list[str],
    brand: dict[str, Any] | None = None,
    dictionary_version: str | None = None,
    land_price: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = _tier_meta(tier)
    return {
        "building_key": building_key,
        "snapshot_ym": snapshot_ym,
        "source_label": source_label(snapshot_ym, tier=tier),
        "dictionary_version": dictionary_version,
        "matched": False,
        "match": {
            "tier": tier,
            "tier_label": meta["label"],
            "rule": rule,
            "reliability": meta["reliability"],
            "usable_for_regression": bool(meta["usable"]),
            "danji_code": None,
            "danji_name": None,
            "approved_year": None,
            "building_year": building_year,
            "year_diff": None,
            "note": match_note,
            "candidates": [],
        },
        "builder": None,
        "brand": brand,
        "scale": None,
        "structure": None,
        "classification": None,
        "land_price": land_price,
        "quality_flags": [],
        "notes": notes,
    }


def fetch_danji_attributes(
    conn: Connection,
    building_key: str,
    *,
    snapshot_ym: str | None = None,
) -> dict[str, Any]:
    """단지 속성 1건 조회. 행이 없어도 404가 아니라 미매칭 사유를 담아 반환한다."""
    ledger = _ledger_meta(conn, building_key)
    ledger_asset_type = str(ledger["asset_type"]) if ledger else None
    ledger_building_year = _to_int(ledger["building_year"]) if ledger else None
    land_price = _fetch_assessed_land_price(conn, building_key, ledger_asset_type)

    if not _table_exists(conn, ATTRIBUTES_TABLE):
        return _unmatched_payload(
            building_key=building_key,
            snapshot_ym=snapshot_ym,
            building_year=ledger_building_year,
            tier="Z",
            rule="no_match",
            match_note=MATCH_NOTE_NO_MATCH,
            notes=_non_apartment_notes(ledger_asset_type),
            land_price=land_price,
        )

    row = _fetch_row(conn, building_key, snapshot_ym)

    if row is None:
        return _unmatched_payload(
            building_key=building_key,
            snapshot_ym=snapshot_ym or _latest_snapshot_ym(conn),
            building_year=ledger_building_year,
            tier="Z",
            rule="no_match",
            match_note=MATCH_NOTE_NO_MATCH,
            notes=_non_apartment_notes(ledger_asset_type),
            land_price=land_price,
        )

    ym = str(row["snapshot_ym"]).strip() if row["snapshot_ym"] else None
    tier = str(row["match_tier"] or "").strip() or "Z"
    rule = str(row["match_rule"] or "").strip() or "no_match"
    meta = _tier_meta(tier)
    asset_type = str(row["asset_type"] or "") or ledger_asset_type
    building_year = _to_int(row["building_year"])
    if building_year is None:
        building_year = ledger_building_year
    year_diff = _to_int(row["year_diff"])
    # D·F는 후보를 합산해 danji_code(첫 코드)와 세대·시공사를 채운다.
    matched = row["danji_code"] is not None or tier == "T"
    flags = _quality_flags(row["attr_quality_flags"])
    brand_name = row["brand"]
    brand_confidence = row["brand_confidence"]
    builder_group = row["builder_group"]
    builder_raw = row["builder_raw"]
    builder_is_joint = row["builder_is_joint"]
    is_public = bool(row["builder_is_public"]) or bool(row["brand_is_public"])
    is_multi = tier in {"D", "F"}
    codes = _parse_danji_codes(row.get("danji_code"), row.get("match_danji_codes"))
    candidates = _fetch_candidates(conn, ym, codes) if is_multi else []

    notes: list[str] = []
    if not meta["usable"] and tier != "Z":
        notes.append(NOTE_NOT_USABLE)
    if flags:
        notes.append(NOTE_QUALITY_FLAGGED)
    if builder_is_joint and not is_multi:
        notes.append(NOTE_JOINT_BUILDER)
    if builder_group is None and builder_raw:
        notes.append(NOTE_BUILDER_GROUP_MISSING)
    if is_public:
        notes.append(NOTE_PUBLIC_SUPPLIER)
    if brand_name is None:
        notes.append(NOTE_BRAND_NOT_DETECTED)
    if brand_confidence == "low":
        notes.append(NOTE_BRAND_LOW_CONFIDENCE)
    if year_diff is not None and abs(year_diff) >= 2:
        notes.append(NOTE_YEAR_DIFF.format(n=abs(year_diff)))
    if not matched:
        notes.extend(_non_apartment_notes(asset_type))

    brand_payload = {
        "name": brand_name,
        "confidence": brand_confidence,
        "is_public": bool(row["brand_is_public"]),
        "detected_from": BRAND_DETECTED_FROM if brand_name else None,
    }

    if not matched:
        # 브랜드는 실거래 단지명에서 추출하므로 K-apt 미매칭 단지에도 존재한다
        # (실측 653단지). 숨기면 브랜드 커버리지가 매칭 tier에 종속돼버린다.
        if brand_name:
            notes.append(NOTE_BRAND_WITHOUT_MATCH)
        return _unmatched_payload(
            building_key=building_key,
            snapshot_ym=ym,
            building_year=building_year,
            tier=tier,
            rule=rule,
            match_note=MATCH_NOTE_NO_MATCH if tier == "Z" else None,
            notes=notes,
            brand=brand_payload if brand_name else None,
            dictionary_version=row["dictionary_version"],
            land_price=land_price,
        )

    match_note = MATCH_NOTE_YEAR_EXACT if year_diff == 0 else None
    if rule == "pnu_unique":
        match_note = MATCH_NOTE_PNU_UNIQUE if match_note is None else f"{MATCH_NOTE_PNU_UNIQUE} {match_note}"
    if rule == "title_pnu":
        match_note = MATCH_NOTE_TITLE_PNU if match_note is None else f"{MATCH_NOTE_TITLE_PNU} {match_note}"
    if is_multi:
        match_note = MATCH_NOTE_MULTI if match_note is None else f"{MATCH_NOTE_MULTI} {match_note}"
    return {
        "building_key": building_key,
        "snapshot_ym": ym,
        "source_label": source_label(ym, tier=tier),
        "dictionary_version": row["dictionary_version"],
        "matched": True,
        "match": {
            "tier": tier,
            "tier_label": meta["label"],
            "rule": rule,
            "reliability": meta["reliability"],
            "usable_for_regression": bool(meta["usable"]),
            "danji_code": row["danji_code"],
            "danji_name": row["danji_name"],
            "approved_year": _to_int(row["approved_year"]),
            "building_year": building_year,
            "year_diff": year_diff,
            "note": match_note,
            "candidates": candidates,
        },
        "builder": {
            "raw": builder_raw,
            "norm": row["builder_norm"],
            "group": builder_group,
            "is_joint": bool(builder_is_joint),
            "is_public": bool(row["builder_is_public"]),
            "developer_raw": row["developer_raw"],
        },
        "brand": brand_payload,
        "scale": {
            "households": _to_int(row["households"]),
            "households_sale": _to_int(row["households_sale"]),
            "households_rent": _to_int(row["households_rent"]),
            "dong_count": _to_int(row["dong_count"]),
            "max_floor": _to_int(row["max_floor"]),
            "parking_total": _to_int(row["parking_total"]),
            "parking_per_household": _to_float(row["parking_per_household"]),
        },
        "structure": {"raw": row["structure_raw"], "group": row["structure_group"]},
        "classification": {
            "danji_class": row["danji_class"],
            "supply_type": row["supply_type"],
        },
        "land_price": land_price,
        "quality_flags": flags,
        "notes": notes,
    }


def list_builder_label(norm: Any, raw: Any, is_joint: Any) -> str | None:
    """목록용 시공사: 대표 1곳. 공동시공은 첫 회사 + '외'."""
    text = ""
    if norm is not None:
        text = str(norm).strip()
        if text.lower() in {"", "none", "nan"}:
            text = ""
    if not text and raw is not None:
        text = str(raw).strip()
        if text.lower() in {"", "none", "nan"}:
            text = ""
    if not text:
        return None
    if not is_joint:
        return text
    parts = [p.strip() for p in _JOINT_SPLIT_RE.split(text) if p.strip()]
    first = parts[0] if parts else text
    if first.endswith(" 외"):
        return first
    return f"{first} 외"


def _households_flagged(raw: Any) -> bool:
    if raw is None:
        return False
    flags = {p.strip() for p in str(raw).split(",") if p.strip()}
    return bool(flags & _HH_LIST_FLAGS)


def attach_danji_list_fields(conn: Connection, items: list[BuildingStatsRow]) -> None:
    """기본통계 목록에 세대수·시공사·개별공시지가를 붙인다. 없으면 그대로 둔다."""
    if not items:
        return
    _attach_list_attr_fields(conn, items)
    _attach_list_land_prices(conn, items)


def _attach_list_attr_fields(conn: Connection, items: list[BuildingStatsRow]) -> None:
    if not _table_exists(conn, ATTRIBUTES_TABLE):
        return
    snap = _latest_snapshot_ym(conn)
    if not snap:
        return
    keys = list({it.building_key for it in items if it.building_key})
    if not keys:
        return
    rows = conn.execute(
        text(
            f"""
            SELECT building_key, asset_type, households, builder_norm, builder_raw,
                   builder_is_joint, attr_quality_flags, match_tier
            FROM {ATTRIBUTES_TABLE}
            WHERE snapshot_ym = :snap
              AND building_key = ANY(:keys)
            """
        ),
        {"snap": snap, "keys": keys},
    ).mappings().all()
    by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    by_key: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        bk = str(d["building_key"])
        at = str(d.get("asset_type") or "")
        by_pair[(bk, at)] = d
        by_key.setdefault(bk, d)
    for i, it in enumerate(items):
        row = by_pair.get((it.building_key, it.asset_type)) or by_key.get(it.building_key)
        if not row:
            continue
        items[i] = it.model_copy(
            update={
                "households": _to_int(row.get("households")),
                "households_flagged": _households_flagged(row.get("attr_quality_flags")),
                "builder_label": list_builder_label(
                    row.get("builder_norm"),
                    row.get("builder_raw"),
                    row.get("builder_is_joint"),
                ),
                "builder_is_joint": bool(row.get("builder_is_joint")),
                "match_tier": (str(row.get("match_tier") or "").strip() or None),
            }
        )


def _attach_list_land_prices(conn: Connection, items: list[BuildingStatsRow]) -> None:
    if not _table_exists(conn, LAND_PRICE_TABLE):
        return
    keys = list({it.building_key for it in items if it.building_key})
    if not keys:
        return
    rows = conn.execute(
        text(
            f"""
            SELECT DISTINCT ON (building_key, asset_type)
                   building_key, asset_type, assessed_land_price, assessed_land_price_year
            FROM {LAND_PRICE_TABLE}
            WHERE building_key = ANY(:keys)
            ORDER BY building_key, asset_type, assessed_land_price_year DESC NULLS LAST
            """
        ),
        {"keys": keys},
    ).mappings().all()
    by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    by_key: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        bk = str(d["building_key"])
        at = str(d.get("asset_type") or "")
        by_pair[(bk, at)] = d
        by_key.setdefault(bk, d)
    for i, it in enumerate(items):
        row = by_pair.get((it.building_key, it.asset_type)) or by_key.get(it.building_key)
        if not row:
            continue
        items[i] = it.model_copy(
            update={
                "assessed_land_price": _to_float(row.get("assessed_land_price")),
                "assessed_land_price_year": _to_int(row.get("assessed_land_price_year")),
            }
        )
