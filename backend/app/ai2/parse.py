"""문장에서 분석 맥락만 고른다. 카탈로그에 없는 분석은 만들지 않는다."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai2.case_tools import UNAVAILABLE_ANALYSIS
from app.ai2.catalog import get_spec

_ANALYSIS = (
    ("공장 층별효용", "factory_floor"),
    ("공장층별효용", "factory_floor"),
    ("집합공장", "factory_floor"),
    ("창고", "factory_floor"),
    ("공장", "factory_floor"),
    ("층별 효용", "floor_utility"),
    ("층별효용", "floor_utility"),
    ("층 효용", "floor_utility"),
    ("산식", "floor_utility_method"),
    ("쌍둥이", "twin_region"),
    ("예측", "built_predict"),
    ("가치", "built_value"),
    ("회귀", "land_regression"),
)
_PROPERTY = (
    ("아파트", "apartment"),
    ("토지", "land"),
    ("복합", "built"),
)
_STOP = {"알려줘", "해줘", "좀", "은", "는", "이", "가", "을", "를", "에", "의", "에서"}
_REGION = re.compile(r"^[가-힣]{1,12}(?:동|구|읍|면|리|시|도)$")
_RANGE = re.compile(r"(\d{4}-\d{2}~\d{4}-\d{2})")
_YEAR = re.compile(r"(?<!\d)(\d{4})년")


@dataclass
class ParsedSentence:
    region: str | None = None
    property_type: str | None = None
    analysis_type: str | None = None
    target: str | None = None
    period: str | None = None
    measure: str | None = None
    claim: str | None = None
    ambiguous_property: bool = False
    ambiguous_analysis: bool = False
    ambiguous_target: bool = False


def parse_sentence(sentence: str) -> ParsedSentence:
    text = " ".join(sentence.split())
    parsed = ParsedSentence()
    if not text:
        return parsed
    ranged = _RANGE.search(text)
    if ranged:
        parsed.period = ranged.group(1)
        text = text.replace(ranged.group(1), " ")
    else:
        year = _YEAR.search(text)
        if year:
            value = year.group(1)
            parsed.period = f"{value}-01~{value}-12"
            text = text.replace(year.group(0), " ")
    if "㎡당" in text:
        parsed.measure = "unit_price"
        text = text.replace("㎡당", " ")
    elif "총액" in text:
        parsed.measure = "total"
        text = text.replace("총액", " ")
    if "적정가" in text or "적정" in text:
        parsed.claim = "appraisal"
        text = text.replace("적정가", " ").replace("적정", " ")
    text, analyses = _take(text, _ANALYSIS)
    known = [name for name in analyses if get_spec(name) is not None or name in UNAVAILABLE_ANALYSIS]
    if len(known) > 1:
        parsed.ambiguous_analysis = True
    elif len(known) == 1:
        parsed.analysis_type = known[0]
    text, properties = _take(text, _PROPERTY)
    if len(properties) > 1:
        parsed.ambiguous_property = True
    elif len(properties) == 1:
        parsed.property_type = properties[0]
    text = text.replace("지역 전체", " ").replace("전체", " ")
    wants_region = "전체" in sentence
    tokens = [token for token in text.split() if token not in _STOP]
    regions = [token for token in tokens if _REGION.match(token)]
    names = [token for token in tokens if token not in regions]
    if len(regions) > 1 or len(names) > 1:
        parsed.ambiguous_target = True
    elif len(regions) == 1:
        parsed.region = regions[0]
    if wants_region:
        parsed.target = "region"
    elif len(names) == 1:
        parsed.target = names[0]
    return parsed


def _take(text: str, aliases: tuple[tuple[str, str], ...]) -> tuple[str, list[str]]:
    found: list[str] = []
    for phrase, value in sorted(aliases, key=lambda item: len(item[0]), reverse=True):
        if phrase in text:
            found.append(value)
            text = text.replace(phrase, " ")
    return text, list(dict.fromkeys(found))
