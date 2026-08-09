# -*- coding: utf-8 -*-
"""단지 속성 사전 — 시공사 표기 정규화·기업집단·브랜드 추출.

설계 SSOT: `docs/COLLECTIVE_TWO_STAGE_HEDONIC_DESIGN.md` §3,
근거 실측: `docs/COLLECTIVE_RESIDENTIAL_VALUATION_EXPANSION_REVIEW.md` §1.3.

3단 분리 원칙(원자료 보존):

- `builder_raw`   K-apt 원문 그대로. 절대 덮어쓰지 않는다.
- `builder_norm`  표기만 정규화(법인형태·공백·영문 케이스). **회사 병합 판단 없음.**
- `builder_group` 사명 변경·계열 통합을 반영한 분석 단위. **판단이 들어간 값.**

`builder_norm`과 `builder_group`을 분리하는 이유는 "현대건설과 현대엔지니어링을
합칠 것인가"처럼 분석 목적에 따라 답이 달라지는 판단을 데이터에 박아넣지 않기
위해서다. 사용자는 두 축 중 하나를 골라 회귀를 돌릴 수 있어야 한다.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------- 시공사 정규화

_CORP_FORMS = (
    "주식회사",
    "(주)",
    "㈜",
    "(유)",
    "(합)",
    "(재)",
    "(사)",
)

_WS_RE = re.compile(r"\s+")
_JOINT_SPLIT_RE = re.compile(r"[,/·]|\s+및\s+")
# pandas 결측(float nan)은 truthy라서 `not raw`로 걸러지지 않는다 — str(nan)="nan"이
# 시공사명으로 오인되는 것을 막는다.
_NULLISH = frozenset({"", "nan", "none", "null", "na", "-", "미상", "없음"})
# 「1/3공구:삼성물산, 2공구 : 동부」처럼 공구·구간 표기가 섞인 원문에서 구간 라벨을
# 떼어낸다. 떼지 않으면 분리 결과의 첫 토큰이 「1」이 되어 기업집단이 오염된다.
_SECTION_MARK_RE = re.compile(r"\d+(\s*/\s*\d+)*\s*(공구|구간|블럭|블록|BL)\s*[:：]?")
# 회사명은 최소 2자이고 한글 또는 라틴 문자를 포함한다 — 「0」·「1」 같은 자리표시자 배제.
_HAS_LETTER_RE = re.compile(r"[가-힣A-Za-z]")
_COMPANY_TAIL_RE = re.compile(
    r"(건설산업|종합건설|건설|산업개발|개발|기업|토건|공영|주택|물산|중공업|엔지니어링|이앤씨|E&C)$"
)


def normalize_builder(raw: str | None) -> str:
    """표기 정규화만 수행한다(회사 병합 없음).

    - 유니코드 NFC, 앞뒤 공백 제거
    - 법인형태 표기 제거: `(주)`, `㈜`, `주식회사`, `(합)` 등
    - ASCII 대문자 통일: `sk건설` → `SK건설`
    - 내부 공백 축소

    `건설`·`산업개발` 같은 접미어는 **남긴다** — 이것이 현대건설과
    현대산업개발을 구분하는 유일한 단서다.
    """
    if raw is None or raw != raw:  # noqa: PLR0124 — NaN 판정
        return ""
    text = unicodedata.normalize("NFC", str(raw)).strip()
    if text.lower() in _NULLISH:
        return ""
    for form in _CORP_FORMS:
        text = text.replace(form, " ")
    text = _SECTION_MARK_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip(" ,.-:/")
    if len(text) < 2 or not _HAS_LETTER_RE.search(text):
        return ""
    return "".join(ch.upper() if ch.isascii() and ch.isalpha() else ch for ch in text)


def split_joint_builders(raw: str | None) -> list[str]:
    """공동시공 원문을 개별 시공사로 분리한다."""
    if not normalize_builder(raw):
        return []
    parts = [p.strip() for p in _JOINT_SPLIT_RE.split(str(raw)) if p.strip()]
    if len(parts) > 1:
        return [normalize_builder(p) for p in parts if normalize_builder(p)]

    # 구분자 없이 공백으로만 나열된 경우: 회사 접미어가 2개 이상이면 공동시공
    tokens = [t for t in _WS_RE.split(normalize_builder(raw)) if t]
    if len(tokens) >= 2 and sum(1 for t in tokens if _COMPANY_TAIL_RE.search(t)) >= 2:
        return tokens
    return [normalize_builder(raw)] if normalize_builder(raw) else []


def is_joint_construction(raw: str | None) -> bool:
    return len(split_joint_builders(raw)) > 1


# ------------------------------------------------------- 기업집단(판단 포함) 매핑
#
# 이 표에는 **명확한 근거가 있는 병합만** 넣는다. 표에 없는 시공사는
# `builder_norm`이 그대로 group이 된다(임의 병합 금지).
#
# 병합 근거 분류:
#   [사명]   동일 법인의 사명 변경 (LG건설 → GS건설)
#   [계열]   건설 브랜드를 공유하는 계열 통합 (현대건설 + 현대엔지니어링)
#   [표기]   같은 회사의 표기 흔들림 (부영 / 부영주택)
#   [공공]   공공 공급주체 (대한주택공사 → LH)

_BUILDER_GROUP: dict[str, str] = {
    # [사명] LG건설 → GS건설 (2005년 사명 변경, 동일 법인)
    "LG건설": "GS건설",
    "GS건설": "GS건설",
    # [계열] 힐스테이트 브랜드 공유 — 현대산업개발과 혼동 금지
    "현대건설": "현대건설",
    "현대엔지니어링": "현대건설",
    # [사명] 현대산업개발 → HDC현대산업개발 (아이파크). 현대건설과 별개 회사
    "현대산업개발": "HDC현대산업개발",
    "HDC현대산업개발": "HDC현대산업개발",
    # [사명] 대림산업 → DL이앤씨 / 대림건설 → DL건설 (분할 후 별개 법인)
    "대림산업": "DL이앤씨",
    "대림": "DL이앤씨",
    "대림건설": "DL건설",
    "삼호": "DL건설",
    # [사명] 포스코건설 → 포스코이앤씨
    "포스코건설": "포스코이앤씨",
    "포스코": "포스코이앤씨",
    # [사명] 코오롱건설 → 코오롱글로벌
    "코오롱건설": "코오롱글로벌",
    "코오롱글로벌": "코오롱글로벌",
    # [사명] SK건설 → SK에코플랜트
    "SK건설": "SK에코플랜트",
    "SK에코플랜트": "SK에코플랜트",
    # [계열] 금호산업 건설부문 → 금호건설
    "금호건설": "금호건설",
    "금호산업": "금호건설",
    # [사명] 한라건설 → HL디앤아이한라
    "한라건설": "HL디앤아이한라",
    "한라": "HL디앤아이한라",
    # [계열] 삼성건설 = 삼성물산 건설부문. 삼성중공업은 별개로 둔다
    "삼성물산": "삼성물산",
    "삼성건설": "삼성물산",
    # [표기] 부영 계열 표기 흔들림
    "부영": "부영주택",
    "부영주택": "부영주택",
    "부영건설": "부영주택",
    # [표기] 중흥 계열
    "중흥건설": "중흥건설",
    "중흥건설산업": "중흥건설",
    "중흥토건": "중흥건설",
    "중흥주택": "중흥건설",
    # [표기] 우미 계열
    "우미건설": "우미건설",
    "우미산업개발": "우미건설",
    # [표기] 동아건설산업 = 동아건설
    "동아건설": "동아건설",
    "동아건설산업": "동아건설",
    # [표기] 계룡건설산업
    "계룡건설": "계룡건설산업",
    "계룡건설산업": "계룡건설산업",
    # [표기] 한양
    "한양": "한양",
    "한양건설": "한양",
    # [공공] LH 계열 — 공공 공급주체
    "대한주택공사": "LH",
    "한국토지주택공사": "LH",
    "대한토지주택공사": "LH",
    "한국주택공사": "LH",
    "LH": "LH",
    "LH공사": "LH",
    "LH주택공사": "LH",
    "주택공사": "LH",
    "주공": "LH",
}

# 공공 공급주체 — 민간 브랜드 프리미엄과 성격이 다르므로 분석에서 분리한다.
_PUBLIC_GROUPS: frozenset[str] = frozenset({"LH", "지방도시개발공사", "SH공사"})

_PUBLIC_HINT_RE = re.compile(r"도시개발공사|도시공사|주택공사|LH|SH공사|지방공사")

# 시공사가 아닌 값 — 재건축조합·신탁사·발주처가 시공사 칸에 들어온 경우.
# group을 비워 회귀에서 결측 처리되게 한다(임의 추정 금지).
_NON_BUILDER_RE = re.compile(r"조합|신탁|공단|시청|군청|도청|교육청|재건축|재개발")

# 접미어가 없어 실체 특정이 불가한 표기(예: 「현대」는 현대건설/현대산업개발 불명).
# 억지로 배정하면 브랜드 프리미엄이 오염되므로 결측으로 둔다.
_AMBIGUOUS_BUILDERS: frozenset[str] = frozenset(
    {"현대", "삼성", "대우", "금호", "한신", "청구", "우방", "경남", "진로", "라인"}
)


def builder_group(raw: str | None) -> str | None:
    """분석용 기업집단. 판단이 불가능하면 None(결측)."""
    norm = normalize_builder(raw)
    if not norm:
        return None
    if _NON_BUILDER_RE.search(norm):
        return None
    # 「현대」처럼 접미어가 없어 어느 회사인지 특정할 수 없는 표기는 결측 처리
    if norm in _AMBIGUOUS_BUILDERS:
        return None
    if is_joint_construction(raw):
        head = split_joint_builders(raw)[0]
        return _BUILDER_GROUP.get(head, head)
    if norm in _BUILDER_GROUP:
        return _BUILDER_GROUP[norm]
    if _PUBLIC_HINT_RE.search(norm):
        return "지방도시개발공사"
    return norm


def is_public_builder(group: str | None) -> bool:
    return bool(group) and group in _PUBLIC_GROUPS


# ------------------------------------------------------------------- 브랜드 사전
#
# K-apt에는 브랜드 컬럼이 없다 — 단지명에서 추출한다.
# `builder_hint`는 참고용 메타데이터이며 **계산에 쓰지 않는다**(오탐 시 회귀 오염 방지).
# confidence: high=널리 확인된 매핑, low=확인 필요.

_BRANDS: tuple[tuple[str, tuple[str, ...], str | None, str], ...] = (
    # (브랜드, 단지명 패턴, builder_hint, confidence)
    ("래미안", ("래미안",), "삼성물산", "high"),
    ("자이", ("자이",), "GS건설", "high"),
    ("힐스테이트", ("힐스테이트",), "현대건설", "high"),
    ("푸르지오", ("푸르지오",), "대우건설", "high"),
    ("e편한세상", ("e편한세상", "이편한세상", "편한세상"), "DL이앤씨", "high"),
    # 「아크로」 단독 패턴은 무관한 소형 단지명(아크로빌·아크로타워 등)까지 잡아
    # 단지당 거래수가 비정상적으로 낮게 나왔다 — 알려진 단지명으로 한정한다.
    (
        "아크로",
        ("아크로리버", "아크로포레", "아크로힐스", "아크로서울", "아크로원"),
        "DL이앤씨",
        "high",
    ),
    ("아이파크", ("아이파크", "IPARK", "I-PARK", "I PARK"), "HDC현대산업개발", "high"),
    ("롯데캐슬", ("롯데캐슬",), "롯데건설", "high"),
    ("더샵", ("더샵", "더 샵"), "포스코이앤씨", "high"),
    ("위브", ("위브",), "두산건설", "high"),
    ("SK뷰", ("SKVIEW", "SK뷰", "SK-VIEW"), "SK에코플랜트", "high"),
    ("센트레빌", ("센트레빌",), "동부건설", "high"),
    ("하늘채", ("하늘채",), "코오롱글로벌", "high"),
    ("한라비발디", ("비발디",), "HL디앤아이한라", "high"),
    ("베르디움", ("베르디움",), "호반건설", "high"),
    ("우미린", ("우미린",), "우미건설", "high"),
    ("데시앙", ("데시앙",), "태영건설", "high"),
    ("리슈빌", ("리슈빌",), "계룡건설산업", "high"),
    ("스위첸", ("스위첸",), "KCC건설", "high"),
    ("어울림", ("어울림",), "금호건설", "high"),
    ("포레나", ("포레나",), "한화건설", "high"),
    ("꿈에그린", ("꿈에그린",), "한화건설", "high"),
    ("유보라", ("유보라",), "반도건설", "high"),
    ("노블랜드", ("노블랜드",), "대방건설", "high"),
    ("디에트르", ("디에트르",), "대방건설", "high"),
    ("스타힐스", ("스타힐스",), "서희건설", "high"),
    ("S클래스", ("S-클래스", "S클래스", "에스클래스"), "중흥건설", "high"),
    ("사랑으로", ("사랑으로",), "부영주택", "high"),
    ("더휴", ("더휴",), "한신공영", "high"),
    ("해모로", ("해모로",), "한진중공업", "high"),
    ("파라곤", ("파라곤",), "동양건설산업", "high"),
    ("브라운스톤", ("브라운스톤",), "이수건설", "high"),
    ("굿모닝힐", ("굿모닝힐",), "동문건설", "high"),
    ("휴포레", ("휴포레",), "협성건설", "high"),
    # 「하이빌」은 일반명사처럼 쓰여 과매칭(191단지·단지당 43건) — 접두어 고정
    ("동일하이빌", ("동일하이빌",), "동일", "high"),
    ("중앙하이츠", ("중앙하이츠",), "중앙건설", "high"),
    ("풍경채", ("풍경채",), "제일건설", "high"),
    ("모아엘가", ("모아엘가",), "모아건설", "high"),
    ("루첸", ("루첸",), "대명건설", "low"),
    ("이다음", ("이다음",), "서한", "low"),
    ("예다음", ("예다음",), "영무토건", "low"),
    ("로제비앙", ("로제비앙",), "대광건영", "high"),
    ("그랑블", ("그랑블",), "서해종합건설", "low"),
    ("유앤아이", ("유앤아이", "유엔아이"), "한일건설", "low"),
    ("센트리움", ("센트리움",), "동도건설", "low"),
    ("칸타빌", ("칸타빌",), "대원", "high"),
    ("리엔파크", ("리엔파크",), "라인건설", "low"),
    ("아이유쉘", ("아이유쉘",), "우방", "low"),
    # 「아너스」도 여러 업체가 혼용 — 태왕 브랜드로 한정
    ("태왕아너스", ("태왕아너스",), "태왕", "high"),
    ("코아루", ("코아루",), None, "low"),
    ("퍼스트빌", ("퍼스트빌",), "우남건설", "low"),
    ("라온프라이빗", ("라온프라이빗",), "라온건설", "low"),
    ("베라체", ("베라체",), "금강주택", "high"),
    ("엘리프", ("엘리프",), "계룡건설산업", "low"),
    # 공공 브랜드 — 민간 브랜드와 성격이 다르므로 별도 식별
    ("휴먼시아", ("휴먼시아",), "LH", "high"),
    ("안단테", ("안단테",), "LH", "high"),
    ("뜨란채", ("뜨란채",), "LH", "high"),
)

_PUBLIC_BRANDS: frozenset[str] = frozenset({"휴먼시아", "안단테", "뜨란채"})

_BRAND_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (
        brand,
        re.compile(
            "|".join(re.escape(unicodedata.normalize("NFC", k)) for k in keys),
            re.IGNORECASE,
        ),
    )
    for brand, keys, _hint, _conf in _BRANDS
)

BRAND_META: dict[str, dict[str, str | None]] = {
    brand: {"builder_hint": hint, "confidence": conf} for brand, _k, hint, conf in _BRANDS
}


def detect_brand(danji_name: str | None) -> str | None:
    """단지명에서 브랜드를 추출한다. 사전에 없으면 None.

    None은 「브랜드 없음」이 아니라 **「사전 미검출」**이다 — 회귀 기준범주
    라벨에도 이 구분을 반영해야 한다(§3.2 기준범주 표기).
    """
    if danji_name is None or danji_name != danji_name:  # noqa: PLR0124 — NaN 판정
        return None
    text = unicodedata.normalize("NFC", str(danji_name)).strip()
    if not text or text.lower() in _NULLISH:
        return None
    for brand, pattern in _BRAND_PATTERNS:
        if pattern.search(text):
            return brand
    return None


def is_public_brand(brand: str | None) -> bool:
    return bool(brand) and brand in _PUBLIC_BRANDS


BRAND_REFERENCE_LABEL = "브랜드 미검출(무브랜드 포함)"

__all__ = [
    "BRAND_META",
    "BRAND_REFERENCE_LABEL",
    "builder_group",
    "detect_brand",
    "is_joint_construction",
    "is_public_brand",
    "is_public_builder",
    "normalize_builder",
    "split_joint_builders",
]
