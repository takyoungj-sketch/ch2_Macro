"""D-051 속성 보강 노출 — 동의 문장 · 표시=필터.

원장 zone_type 은 UPDATE 하지 않는다. 조인은 wrap_tx_enrichment(enrich=True).
"""

from __future__ import annotations

NOTICE: tuple[str, ...] = (
    "이 버튼은 국토부 실거래가 자료에 부족한 항목을 건축물대장으로 보강합니다. 상업용 건물은 구조를, 단독·다가구는 용도지역을 채웁니다.",
    "모든 거래를 완벽하게 맞추기는 어려울 수 있습니다. 오류를 줄이기 위해, 연결되지 않은 건은 보강하지 않고 실거래 자료를 그대로 보여 줍니다.",
)
MATCH_RATE = "현재 매칭률 75.0% (계약 2019년 이후)"

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
