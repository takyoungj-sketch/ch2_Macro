"""표제부 단지명으로 필지 집합을 만들고 K-apt를 그 위에 붙인다.

K-apt 대표지번과 실거래·표제부 지번이 달라도, 같은 법정동의 표제부 건물명이
같은 동이면 한 단지다. 시공사는 계속 K-apt.

    python -m parcel_master.apply_pnu_unique
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from build_collective_building_attributes import (  # noqa: E402
    _compact_region,
    norm_name,
    region_name_prefixes,
)
from parcel_master.title_fill import is_housing_dong

log = logging.getLogger(__name__)

_APT_TAIL = re.compile(r"(아파트|공동주택)$")
STEM_MIN = 6
_SKIP_NAMES = frozenset(
    {
        "상가",
        "상가동",
        "주차장",
        "지하주차장",
        "관리사무소",
        "경비실",
        "경로당",
        "주민공동시설",
    }
)

TITLE_CLUSTER_SQL = """
SELECT beopjungri_code, btrim(building_name) AS building_name, pnu,
       main_purpose, purpose_detail
FROM building
WHERE snapshot = (SELECT MAX(snapshot) FROM building)
  AND ledger_kind = '집합'
  AND building_name IS NOT NULL
  AND btrim(building_name) <> ''
"""


def name_stem(name: object) -> str:
    t = norm_name(name)
    return _APT_TAIL.sub("", t)


def stems_align(
    title_name: object,
    kapt_name: object,
    *,
    sido: object = "",
    sigungu: object = "",
) -> bool:
    """표제부 건물명과 K-apt 단지명이 같은 단지인지. 시도·시 접두와 '아파트' 접미만 허용."""
    a = name_stem(title_name)
    b = name_stem(kapt_name)
    if not a or not b:
        return False
    if a == b and len(a) >= STEM_MIN:
        return True
    longer, shorter = (a, b) if len(a) >= len(b) else (b, a)
    if len(shorter) >= STEM_MIN and longer.endswith(shorter):
        prefix = longer[: -len(shorter)]
        if not prefix:
            return True
        prefixes = set(region_name_prefixes(sido, sigungu))
        sgg = _compact_region(sigungu)
        sido_c = _compact_region(sido)
        if prefix in prefixes or (sgg and sgg.startswith(prefix)) or (
            sido_c and sido_c.startswith(prefix)
        ):
            return True
    return False


def _usable_title_name(name: object) -> str:
    key = norm_name(name)
    if not key or key in _SKIP_NAMES or len(key) < 4:
        return ""
    return key


def clusters_from_title_rows(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str], set[str]]:
    """(beopjungri_code, name_key) → PNU 집합. 공동주택 동만."""
    out: dict[tuple[str, str], set[str]] = defaultdict(set)
    for rec in rows:
        if not is_housing_dong(rec.get("main_purpose"), rec.get("purpose_detail")):
            continue
        bj = str(rec.get("beopjungri_code") or "").strip()
        pnu = str(rec.get("pnu") or "").strip()
        key = _usable_title_name(rec.get("building_name"))
        if len(bj) != 10 or len(pnu) != 19 or not key:
            continue
        out[(bj, key)].add(pnu)
    return dict(out)


def load_title_clusters(conn: Connection) -> dict[tuple[str, str], set[str]]:
    rows = conn.execute(text(TITLE_CLUSTER_SQL)).mappings().all()
    clusters = clusters_from_title_rows(rows)
    log.info("title clusters=%s  pnus=%s", len(clusters), sum(len(v) for v in clusters.values()))
    return clusters


def _attr_str(row: Any, name: str) -> str:
    v = getattr(row, name, None)
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in {"nan", "none"} else s


def _beopjungri_of(row: Any) -> str:
    bj = _attr_str(row, "beopjungri_code")
    if len(bj) == 10:
        return bj
    pnu = _attr_str(row, "pnu")
    return pnu[:10] if len(pnu) == 19 else ""


def expand_kapt_pnu_map(
    unique_by_pnu: dict[str, Any],
    clusters: dict[tuple[str, str], set[str]],
) -> tuple[dict[str, Any], dict[str, str]]:
    """유일 PNU K-apt에 표제부 단지 필지를 별칭으로 붙인다.

    같은 클러스터에 K-apt가 둘이면 별칭을 넣지 않는다(묶음).
    """
    out = dict(unique_by_pnu)
    rules: dict[str, str] = {p: "pnu_unique" for p in unique_by_pnu}
    by_code: dict[str, Any] = {}
    for row in unique_by_pnu.values():
        code = _attr_str(row, "danji_code")
        if code:
            by_code[code] = row
    if not clusters or not by_code:
        return out, rules

    clusters_in_bj: dict[str, list[tuple[str, set[str]]]] = defaultdict(list)
    for (bj, nm), pnus in clusters.items():
        clusters_in_bj[bj].append((nm, pnus))

    cluster_kapt: dict[tuple[str, str], set[str]] = defaultdict(set)
    for code, row in by_code.items():
        bj = _beopjungri_of(row)
        if len(bj) != 10:
            continue
        sido = _attr_str(row, "sido_name")
        sgg = _attr_str(row, "sigungu_name")
        kname = _attr_str(row, "danji_name")
        for nm, _pnus in clusters_in_bj.get(bj, []):
            if stems_align(nm, kname, sido=sido, sigungu=sgg):
                cluster_kapt[(bj, nm)].add(code)

    aliased = 0
    for key, codes in cluster_kapt.items():
        if len(codes) != 1:
            continue
        row = by_code[next(iter(codes))]
        own = _attr_str(row, "pnu")
        for pnu in clusters[key]:
            if pnu == own:
                continue
            existing = out.get(pnu)
            if existing is None:
                out[pnu] = row
                rules[pnu] = "title_cluster"
                aliased += 1
            elif _attr_str(existing, "danji_code") != _attr_str(row, "danji_code"):
                out.pop(pnu, None)
                rules.pop(pnu, None)
    log.info("title_cluster aliased_pnus=%s  map=%s", aliased, len(out))
    return out, rules


def persist_title_clusters(
    conn: Connection, snapshot: str, clusters: dict[tuple[str, str], set[str]]
) -> None:
    conn.execute(text("DELETE FROM title_cluster_pnu WHERE snapshot = :s"), {"s": snapshot})
    sql = text(
        """
        INSERT INTO title_cluster_pnu (snapshot, beopjungri_code, name_key, pnu)
        VALUES (:snapshot, :beopjungri_code, :name_key, :pnu)
        """
    )
    rows: list[dict[str, str]] = []
    for (bj, nm), pnus in clusters.items():
        for pnu in pnus:
            rows.append(
                {
                    "snapshot": snapshot,
                    "beopjungri_code": bj,
                    "name_key": nm[:200],
                    "pnu": pnu,
                }
            )
    if not rows:
        log.info("persisted title_cluster_pnu rows=0 snapshot=%s", snapshot)
        return
    for start in range(0, len(rows), 2000):
        conn.execute(sql, rows[start : start + 2000])
    log.info("persisted title_cluster_pnu rows=%s snapshot=%s", len(rows), snapshot)
