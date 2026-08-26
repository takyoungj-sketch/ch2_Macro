"""D-051 속성 보강 노출 — 동의 문장 · 표시=필터.

원장 zone_type 은 UPDATE 하지 않는다. 조인은 wrap_tx_enrichment(enrich=True).
"""

from __future__ import annotations

NOTICE: tuple[str, ...] = (
    "계약 2019년 이후 거래의 75.0%만 건축물대장과 연결됩니다.",
    "표제부는 계약 시점이 아닌 이후 대장(2024-09·2025-07·2026-07) 기준이며, 최대 7년 6개월 차이가 날 수 있습니다.",
    "필지에 용도지역이 여럿이면 빈도 최다 대표 1개만 씁니다(2019년 이후 거래 기준 49.4%).",
    "매칭 정확도 인증은 서울·충북뿐입니다. 다른 시도는 같은 규칙을 씁니다.",
)

LIST_BADGE = "건축물대장 확인"
MATCH_TIERS_CONFIRMED = frozenset({"A1", "A2"})
MATCH_RULE_LABELS: dict[str, str] = {
    "gross_exact": "법정동·연면적 일치",
    "gross_exact_land_tiebreak": "법정동·연면적 일치, 대지면적으로 동률 해소",
}


def split_zone_filter(
    *,
    enrich: bool,
    zone_types: list[str] | None,
) -> tuple[list[str] | None, list[str] | None]:
    """표시=필터: enrich 켜면 용도지역은 조인 뒤 표시값으로 거른다."""
    zones = [z for z in (zone_types or []) if str(z).strip()] or None
    if enrich:
        return None, zones
    return zones, None


def is_confirmed_match(tier: str | None) -> bool:
    t = (tier or "").strip()
    return t in MATCH_TIERS_CONFIRMED


def match_rule_label(rule: str | None) -> str | None:
    raw = (rule or "").strip()
    if not raw:
        return None
    return MATCH_RULE_LABELS.get(raw, raw)
