"""CH2 제품·데이터 파이프라인 지식 (Product Knowledge Pack)."""

from __future__ import annotations

from typing import Any

PRODUCT_OVERVIEW = """
CH2 Macro는 부동산 거래통계를 정제·축적해 회귀·추세·매트릭스·추천·예측 화면으로 제공하는 시장통계 분석 시스템입니다.
감정평가·적정가·투자 판단을 하지 않습니다.
"""

APP_STRUCTURE = """
앱 구조:
- built(복합): 단독·상가·공장 등 개별 건물/토지 거래 — 회귀·상위 scope 비교·예측·모형 추천
- land(토지): 용도지역×지목 매트릭스·장기추세·유료 필지 회귀
- collective(집합): 아파트·오피스텔 등 단지/코호트 회귀 — 주거·비주거 UI는 동일 패턴
- profile: 지역 프로필·Twin 유사지역 (실험·조건부)
- rent(임대): 주거 전월세 건물 목록 · CH2 분석용 전환율(단순평균) · 전세/월세 환산 P50. 상권분석 모달은 한국부동산원 상업용부동산 임대동향조사(상권 공표) — 주거 원장·전환율과 섞지 않음
"""

DATA_PIPELINE = """
데이터 흐름(요약):
- 원천: 국토부 등 공개 거래 데이터 → 정제·지역코드·건물키 매칭
- 마트: scope·자산유형·기간별 집계·회귀 입력 테이블
- API: FastAPI — 화면 facts·회귀 결과·추천 stage JSON
- AI: 화면 Bundle(facts) + Explain layer만 인용 — 재계산·가격판단 금지
"""

REGRESSION_LOGIC = """
회귀·진단:
- complete-case fit_n: 선택 변수 결측 제외 후 적합
- Adj R²·MAPE·VIF·상관 — 화면 수치 그대로 인용
- 로그(금액) semi-log vs 선형(총액): 자산·분포에 따라 trade-off
- 기초 정의(Adj R²·VIF·p 등)는 UI 지표 옆 ? 팝업 — AI는 이번 결과 해석에 집중
"""

NESTED_ADMIN_SCOPE = """
복합 회귀의 행정 계층 (History 실행 순서와 다름):
- 초점(하위): 지금 고른 단위. 대개 읍·면·동. 기본 회귀·예측의 primary.
- 상위지역: 직계 상위 시·군·구 등 comparisons. 「상위지역 분석」에서 같은 변수식을 더 넓은 표본에 반복한다.
- 의도: 하위 단위에서 표본·변수가 얇을 때 범위를 넓혀 같은 회귀를 시도한다. 계수가 윗단계에서 같은 방향이면, 그 패턴이 더 넓은 규모에서도 읽힌다는 참고(유사 지역 범위 규모의 간접 힌트)가 된다. Twin 채택·적정가가 아니다.
- 사용자가 1차=시군구(상위), 2차=읍면동(하위)라고 부르면 이 계층을 가리킨다. 화면은 초점을 먼저 보여 준다.
- History의 「1차·2차」는 세션에서 성공한 회귀의 실행 순서다. 초점 vs 상위와 같지 않을 수 있다. 둘 다 같은 동이면 동/구 비교가 아니다.
"""

RECOMMEND_LOGIC = """
모형 추천·Twin:
- 기본: Local scope 회귀·CV-MAPE 기반 모형 탐색
- Twin(쌍둥이): 지역프로필 벡터(algo 21)로 닮은 행정단위를 고른다. 발견 UI는 /profile/ 만. 토지 레거시 모달 없음.
- 복합 모형추천 Stage2: Twin을 표본 pool로 쓸지 CV-MAPE로 판정. 유사도 ≠ 자동 채택.
- Twin Lab: 실험·벤치마크용 — 제품 기본 추천과 동일 선언 금지
- stage1/stage2: 표본·설명력·CV 적합도로 후보·권장 행동 제시
"""

RENT_CONVERSION = """
주거 전월세 전환율 (연구 종료, 2026-08-15, D-040):
- 공식 한국부동산원 전월세전환율·고정 5%가 아님. 같은 건물 전세(J)·반전세(D,M)로 r_b=12M/(J-D) 후 지역 단순평균.
- 목적: 반전세→전세환산 / 반전세→월세환산. 학술적 금리 추정 아님.
- r_selected = mean_simple 확정. 4열(단순평균·n가중·원점회귀·가중회귀)은 마트에만 보관.
- 서울 hold-out MAPE: 시군구·동 × 3·5·7년 여섯 칸 모두 단순평균 1위. 원점회귀 열위, 가중회귀 최하위.
- 연립 r_b 분산은 개별 건물 이질성. 유형별 산식·가중을 만들지 않음. 분포는 품질 확인용.
- 적용: 지역×유형×3/5/7년. 읍면동 우선, 게이트 미달 시 시군구. 사용자 문구: 「적용 전환율 5년 x.x%」.
- 환산 P50은 비교값. 시세·적정 전세 아님. SSOT: docs/RENT_CONVERSION_EXPERIMENT.md
"""

SANGKWON_REB = """
한국부동산원 상업용부동산 임대동향조사 (상권분석 모달). SSOT: docs/REB_COMMERCIAL_RENT_SURVEY.md
- 분기 표본조사. 공표 단위는 행정동이 아니라 상권(하위시장). CH2는 공표를 재계산하지 않고 싣는다.
- 주거 전월세(국토부 원장·mean_simple·3/5/7년)와 출처·단위·기간이 다르다. 한 표에 섞지 않는다.
- 유형: 오피스(동, 6층+), 중대형 상가(동, 3층+ 또는 연면적>330㎡), 소규모 상가(동, 2층 이하·연면적≤330㎡), 집합 상가(호). 빈 칸은 그 유형 표본·층이 없음.
- 화면 범위: 선택한 시군구(구) 경계와 기하 교차하는 상권만. 동으로 상권을 만들지 않는다.

임대료 ≠ 임대수입:
- 임대료: 시장 환산월세 (보증금×전환율/12 + 월세) / 임대면적. 관리비·부가세 제외. 공표는 월 단가(천원/㎡).
- 임대수입(NOI 쪽): 받은 월세 + 보증금 운용이익 + 실비·관리비. 공실로 못 받은 월세는 이미 금액에서 빠진다.
- 임대료 × 순영업소득% 로 NOI 금액을 역산하지 말 것.

CH2 표시:
- 상권 모달 기본표: 최신 공표 분기 기준 **4분기(1년) 롤링**. 추세선만 달력 연간.
- 임대료·층별임대료: 4분기 월단가 평균 × 12, 천원→만원 (만원/㎡·년). 4분기 없으면 빈칸.
- 순영업소득(금액): 분기 유량 4분기 합, 천원→만원.
- 순영업소득(%)·임대수입%·기타수입%·운영경비%·공실률·전환율·임대가격지수: 분기 산술평균.
- 소득·자본·투자수익률: 부동산원 연간식 ∏(1+r_q/100)−1. 4분기 필수. 분기 I+C=T 이나 연간 복리값은 더해서 같지 않음.
- 동수·호수·평균층수·평균면적: 창의 마지막 유효 분기.

지표 정의(설명자료):
- NOI = (임대수입+기타수입−대손1%) − 운영경비. 구성비 항등식: 임대수입%+기타수입%−운영경비% ≒ 순영업소득%.
- 공실률 = 공실면적/임대가능면적. 면적 통계. 유효 임대수입에 다시 (1−공실)을 곱하지 말 것. 환원법에 쓸 값은 공표 NOI(만원/㎡·년)와 소득수익률.
- 소득수익률 I=NOI/V0, 자본수익률 C=ΔV/V0, 투자수익률 T=I+C (당해 분기). 상권은 연면적 가중.
- 임대가격지수: 2024.2Q=100, 기준층 시장임대료 Dutot.
- 상권 전환율은 상업용 공표용. 주거 mean_simple과 다른 식·표본.
- 연간 투자수익률을 가치·매수 판단으로 쓰지 말 것. 감정·적정가 금지.
"""


LIMITATIONS = """
공통 한계:
- 거래신고 데이터 — 실제 체결·조건과 차이 가능
- scope·필터·기간에 민감 — 화면에 표시된 n·Adj R²·한계를 우선
- 회귀 계수는 조건부 연관이며 인과·적정가를 의미하지 않음
"""

# 유형별 수집·정제·통계 방식 (경로 제안·출처 질문에 사용). 화면 n은 Bundle만.
DOMAIN_BY_APP: dict[str, str] = {
    "land": """
토지:
- 수집: 국토부 토지 실거래 CSV → 원장 land_transactions (Master 필지는 고치지 않음. 예외는 큐·보정 규칙).
- 분석 단위: 선택 지역의 용도지역×지목 칸. 개별 건물 회귀가 아님.
- 통계: V2 as_of_month + 3·5·7년 창. 매트릭스·지목군·장기 연도 추세. 유료 필터는 원장 재집계.
- 바람직: 같은 용도·지목 칸의 단가·건수 추세. 칸이 얇으면 지목군 또는 상위 행정 단건을 본다.
- 한계: 거래액 합 ≠ 가격지수. 시군구에 M2·금리 r를 붙이지 않음. 여러 칸을 한 OLS에 억지로 넣지 않음.
""",
    "built": """
복합(단독·일반상가·일반공장):
- 수집: 국토부 상업업무·공장창고·단독다가구 CSV 중 유형=일반(단독은 전량). 집합 상가·집합공장은 여기 없음.
- 분석 단위: 개별 건물 거래. 유형을 2개 이상 고르면 통합 분석(is_unified). 이때 기본으로 「유형 더미」(asset_type_dummy)가 켜진다.
- 통계: OLS(선형 또는 로그 금액). 유형 더미 계수는 기준 유형(상업이 있으면 상업) 대비 조건부 가격수준.
- 바람직: 상가 vs 단독 가격수준은 두 유형을 함께 고르고 회귀를 실행한 뒤 계수 표의 유형 더미(예: 단독, 기준 상업 대비)를 읽는다. 면적·연식 등 통제 후의 연관이다.
- 유형 더미 ≠ 건축물용도 더미. 용도 더미는 같은 유형 안의 용도 구성(근생·숙박 등).
- 행정 계층: 초점(대개 읍면동)=하위 단위, 「상위지역 분석」=직계 상위 시군구. 하위 n·변수가 얇을 때 같은 식으로 범위를 넓혀 회귀를 시도한다. 계수가 윗단계에서 같은 방향이면 더 넓은 규모의 참고(유사지역 범위의 간접 힌트). Twin 채택·적정가가 아님.
- History 「1차·2차」는 세션 실행 순서. 초점 vs 상위와 같지 않을 수 있다.
- 한계: 통합 식의 R²·MAPE가 상업 단독 식보다 좋아 보여도, 유형 간 수준 차이를 더미가 흡수한 결과일 수 있다. 상업만의 적합도와 우열을 단정하지 말 것. 집합 코호트(아파트·오피스텔) 통합회귀와는 다른 화면이다.
""",
    "collective": """
집합 주거(아파트·오피스텔 등):
- 수집: 국토부 집합 주거. 분석 단위=단지(building_key). 코호트에 단지를 모아 통합회귀(유형 더미)로 아파트 vs 오피스텔 가격수준을 면적·연식 통제 비교.
- 통계: 단지 회귀·코호트 통합회귀·지역회귀·고정효과(FE). K-apt 세대수·주차는 주거 단지 전용.
- 바람직: 유형 격차는 두 유형이 코호트에 있을 때 유형 더미. 한 단지 안 동·면적은 단지 회귀.
- 한계: 유형이 하나면 유형 더미 비교가 안 됨. 소표본이면 계수 불안정. 유형이 층으로 갈리면 유형 더미에 층 구간이 섞임.

집합 비주거(집합상가·집합공장):
- 수집: 국토부 집합 상업·공장. 분석 단위=도로명 cluster (건물 key·K-apt 없음).
- 통계 UX는 주거와 같음. 아파트·오피스텔 통합회귀 플레이북을 여기에 그대로 쓰지 않음.
""",
    "rent": """
임대:
- 주거 전월세: 국토부 원장. 전환율은 단순평균(D-040, mean_simple). 부동산원 공식 전월세전환율이 아님.
- 적용: 지역×유형×3/5/7년. 읍면동 우선, 게이트 미달 시 시군구. 환산 P50은 비교값.
- 상권 모달: 한국부동산원 상업용 임대동향(상권 공표). 공표 단위는 행정동이 아니라 상권.
- 바람직: 주거 전월세 단가·전환은 임대 목록, 상업 임대료·공실은 상권 모달.
- 한계: 주거 원장과 상권 공표는 출처·단위·기간이 다름. 한 표에 섞지 않음. 환산 P50 ≠ 시세·적정 전세.
""",
    "profile": """
지역프로필:
- 토지·복합·집합 마트를 지역 grain으로 묶어 8유형 구성(연간 3년)·인구·Twin·전국 순위.
- 제품 창은 window_years=3만. 토지/집합 분석의 3·5·7년 창과 같지 않음.
- 상가·공장은 프로필 집계에서만 일반+집합을 합침. 복합/집합 앱의 분석 단위를 바꾸지 않음.
- Twin은 regional_profile 벡터를 소비. Feature를 여기서 다시 만들지 않음.
- 바람직: 「이 지역이 어떤 시장 구성인가」는 프로필. 개별 건물·단지 회귀는 복합·집합 앱.
- 한계: 리 아파트 분위는 해당 grain만. 읍 값을 리에 넣지 않음(proxy 금지). 표본이 얇으면 구성이 한두 건에 흔들림.
""",
}

# 앱마다 「아닌 것」. LLM·템플릿이 다른 화면을 꺼내지 않게 한다.
NEGATIVE_BY_APP: dict[str, str] = {
    "land": """
토지에서 하지 않는 것:
- 복합 건물 OLS·집합 단지/코호트 회귀가 아님.
- 여러 용도×지목 칸을 한 식에 UNION하지 않음.
- 거래액 합·건수 합으로 가격지수·시세를 말하지 않음.
- 시군구에 M2·금리·거시지표 r를 붙이지 않음.
- 프로필 Twin 점수와 매트릭스 단가를 한 문장으로 합치지 않음.
- 「이용」만 말하면 감정평가 이용상황과 혼동됨. 용도지역×지목으로 말함.
- 지분거래 제외는 유료 옵션(토지 기본은 포함). 몰래 뺀 표본처럼 말하지 않음.
""",
    "built": """
복합에서 하지 않는 것:
- 집합 아파트·오피스텔 코호트 통합회귀가 아님. 그 화면으로 보내지 않음.
- 집합상가·집합공장은 복합 원장에 없음.
- 유형 더미 ≠ 건축물용도 더미.
- History 1차·2차 ≠ 시군구 vs 읍면동. 실행 순서일 수 있음.
- Twin 유사도 ≠ 자동 pool 채택·적정가.
- 통합 식 R²·MAPE가 좋아져도 유형 수준 차이를 더미가 흡수한 결과일 수 있음.
- 예측 ŷ·PI ≠ 감정·투자 판단.
""",
    "collective": """
집합에서 하지 않는 것:
- 복합 상가·단독 「유형 더미」화면이 아님.
- 비주거(도로 cluster)에 아파트·오피스텔 코호트 플레이북을 그대로 쓰지 않음.
- K-apt 세대수·주차는 주거 단지 전용. 유형 전용 재고로 읽지 않음.
- 단지 FE와 단지 속성을 한 식에서 동시에 읽지 않음.
- Twin 채택 ≠ 시세. 인접 확대는 별도 실행.
- 유형이 층으로 갈리면 유형 더미를 순수 유형 효과로 읽지 않음.
""",
    "rent": """
임대에서 하지 않는 것:
- 주거 mean_simple ≠ 한국부동산원 주거 전월세전환율·고정 5%.
- 주거 원장과 상권 공표를 한 표·한 문장으로 섞지 않음.
- 환산 P50 ≠ 시세·적정 전세.
- 임대료 × 순영업소득% 로 NOI 금액을 역산하지 않음.
- 공실률을 유효 임대수입에 다시 곱하지 않음.
- 상권은 행정동이 아님. 동으로 상권을 만들지 않음.
- 연간 투자수익률을 매수·가치 판단으로 쓰지 않음.
""",
    "profile": """
지역프로필에서 하지 않는 것:
- Twin 점수 ≠ 매수·투자 추천. 회귀 pool 자동 채택이 아님.
- 거래 구성비 ≠ 개별 건물·단지 회귀 계수.
- 일반+집합 합산은 프로필 집계만. 복합/집합 앱 표본이 아님.
- 토지/집합 3·5·7년 창과 프로필 3년을 같은 창처럼 말하지 않음.
- 리 아파트 분위에 읍 값을 넣지 않음(proxy 금지).
- GDP·M2·뉴스와 구성 숫자를 한 문장으로 합치지 않음.
- Building stats와 Market stats를 섞지 않음.
""",
}


def format_domain_card(app: str) -> str:
    body = (DOMAIN_BY_APP.get(app) or DOMAIN_BY_APP["built"]).strip()
    return "[유형별 데이터·통계 방식]\n" + body


def format_negative_card(app: str) -> str:
    body = (NEGATIVE_BY_APP.get(app) or NEGATIVE_BY_APP["built"]).strip()
    return "[혼동 금지]\n" + body


def is_cross_app_question(message: str) -> bool:
    """다섯 앱을 견줘야 하는 질문인가. 기본 발췌는 현재 앱만."""
    m = message.strip()
    names = ("토지", "복합", "집합", "임대", "프로필", "지역프로필")
    if sum(1 for k in names if k in m) >= 2:
        return True
    return any(
        k in m
        for k in (
            "유형별 데이터",
            "앱 차이",
            "앱마다",
            "각 유형",
            "유형이 뭐가",
            "뭐가 다르",
            "앱 구조",
        )
    )


def format_all_domain_cards(*, with_negatives: bool = False) -> str:
    parts = ["[유형별 데이터·통계 방식 — 토지·복합·집합·임대·지역프로필]"]
    for key in ("land", "built", "collective", "rent", "profile"):
        parts.append(DOMAIN_BY_APP[key].strip())
        if with_negatives:
            parts.append(NEGATIVE_BY_APP[key].strip())
    return "\n\n".join(parts)


def format_knowledge_source_answer(*, app: str) -> str:
    return (
        "앞선 안내는 외부 웹이 아니라 **CH2에 넣어 둔 지식**을 쓴 것입니다. "
        "플레이북에 전용 이름이 없다고 출처를 숨기지 않습니다.\n\n"
        "1. **Product Knowledge** — 유형별 수집·정제·DB·통계 방식·한계 "
        "(토지, 복합, 집합 주거/비주거, 임대, 지역프로필).\n"
        "2. **Playbook** — 질문 의도에 맞는 CH2 화면 경로. "
        "집합 코호트 통합회귀는 주거 집합(아파트·오피스텔) 화면입니다. "
        "복합의 상가·단독 비교는 복합 앱에서 유형을 같이 고르고 「유형 더미」 계수를 봅니다.\n"
        "3. **화면 Bundle** — n·계수 등 숫자는 현재 화면에서 엔진이 낸 결과만.\n\n"
        f"{format_all_domain_cards(with_negatives=True)}\n\n"
        f"지금 화면 앱(`{app}`)에 맞춰 위 방식 안에서 경로를 고릅니다. "
        "없는 화면을 있는 것처럼 만들지 않습니다."
    )


def _scope_level_line(level: dict[str, Any]) -> str:
    label = str(level.get("scope_label") or "—")
    admin = str(level.get("admin_level") or "")
    n = level.get("n")
    adj = level.get("adj_r_squared") or level.get("adj_r2")
    bits = [label]
    if admin:
        bits.append(admin)
    if n is not None:
        bits.append(f"n={n}")
    if adj is not None:
        try:
            bits.append(f"Adj R²={float(adj):.4f}")
        except (TypeError, ValueError):
            bits.append(f"Adj R²={adj}")
    return " · ".join(bits)


def format_nested_scope_answer(
    *,
    facts: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
    message: str = "",
) -> str:
    """초점 vs 직계 상위 설계 의도. 숫자는 Bundle facts만."""
    facts = facts if isinstance(facts, dict) else {}
    want_compare = any(k in (message or "") for k in ("비교", "결과"))
    lines = [
        "복합 회귀에서 말하는 1차·2차는 **History 실행 순서**가 아니라, "
        "행정 계층을 넓혀 같은 회귀를 시도하는 설계입니다.",
        "",
        "**하위(초점)** 는 지금 고른 단위입니다. 대개 읍·면·동이고, 기본 회귀·예측의 primary입니다.",
        "**상위** 는 직계 상위 시·군·구입니다. 화면 「상위지역 분석」이 같은 변수식을 더 넓은 표본에 반복합니다.",
        "",
        "의도는 두 가지입니다. 하위 단위에서 표본·변수가 얇을 때 범위를 넓혀 회귀를 시도할 수 있게 하는 것, "
        "그리고 계수가 윗단계에서도 같은 방향이면 그 패턴이 더 넓은 규모에서도 읽힌다는 **참고**(유사 지역 범위 규모의 간접 힌트)를 얻는 것입니다. "
        "Twin 채택이나 적정가가 아닙니다.",
        "",
        "화면은 초점을 먼저 보여 줍니다. 1차=시군구, 2차=읍면동이라고 부르시면 이 계층과 같습니다.",
    ]
    primary = facts.get("primary") if isinstance(facts.get("primary"), dict) else None
    raw_cmp = facts.get("comparisons")
    comparisons = [c for c in raw_cmp if isinstance(c, dict)] if isinstance(raw_cmp, list) else []
    if primary or comparisons:
        lines.append("")
        lines.append("지금 화면:")
        if primary:
            lines.append(f"- 초점(하위): {_scope_level_line(primary)}")
        if comparisons:
            lines.append(f"- 직계 상위: {_scope_level_line(comparisons[0])}")
            if want_compare:
                n_p, n_u = primary.get("n") if primary else None, comparisons[0].get("n")
                if n_p is not None and n_u is not None:
                    lines.append(
                        f"  상위 n={n_u} · 초점 n={n_p} 입니다. "
                        "윗단계 표본이 더 많으면 하위 단위의 얇은 표본을 보완하려는 시도입니다."
                    )
        else:
            lines.append(
                "- 직계 상위 숫자(comparisons)는 아직 Bundle에 없습니다. "
                "「상위지역 분석」을 열면 초점과 같은 식을 윗단계에서 볼 수 있습니다."
            )
    elif want_compare:
        lines.append("")
        lines.append(
            "지금 화면에 초점 vs 직계 상위 숫자가 없습니다. "
            "「상위지역 분석」을 연 뒤 같은 질문을 하시면 그 값을 인용합니다."
        )

    hist = [s for s in (history or []) if isinstance(s, dict)]
    if len(hist) >= 2:
        a, b = hist[-2], hist[-1]
        la = str((a.get("scope") or {}).get("region_label") or "")
        lb = str((b.get("scope") or {}).get("region_label") or "")
        lines.append("")
        if la and lb and la.strip() == lb.strip():
            lines.append(
                f"세션 History의 1차·2차는 **실행 순서**입니다. "
                f"지금 기록된 두 번은 모두 `{la}` 이라 시군구 vs 읍면동 비교가 아닙니다."
            )
        else:
            lines.append(
                "세션 History의 1차·2차는 성공한 회귀의 **실행 순서**입니다. "
                "초점 vs 상위지역과 같지 않을 수 있습니다. 실행 순서를 보려면 「아까와 비교해 주세요」라고 물어 주세요."
            )
    return "\n".join(lines).strip()


# 화면 사용법 — 플레이북 기능 목록이 아니라 클릭 순서
UI_HOWTO = """
화면에서 숫자를 보는 순서 (사용자가 회귀·유형비교를 묻지 않으면 이것을 먼저 안내):

집합(아파트·오피스텔):
1. 단지가 있는 시·도 / 시·군·구를 고른다
2. 「통계분석」을 누른다
3. 목록에서 단지를 클릭한다
4. 모달의 「추세」「장기추세」에서 평균단가의 과거 흐름과 추세선을 본다
비주거는 단지가 아니라 도로(cluster)를 클릭한다. 회귀·코호트·유형 더미는 격차를 통제해 비교할 때 쓴다.

복합(단독·상가·공장): 유형·지역을 고르고 「통계분석」을 누르면 회귀·요약 카드가 나온다.
유형을 2개 이상 고르면 통합회귀가 되고, 「유형 더미」 계수가 기준 유형 대비 가격수준이다.
읍면동 표본이 얇으면 「상위지역 분석」에서 직계 상위(시군구)에 같은 식을 반복한다. History 1차·2차(실행 순서)와 혼동하지 않는다.
토지: 지역을 고른 뒤 용도지역×지목 매트릭스와 장기추세를 본다.
임대: 지역을 고르고 통계분석 후 건물을 연다.
"""


def is_howto_ui_question(message: str) -> bool:
    """어디를 눌러 결과를 보나 — 분석방법(격차·통합회귀) 질문과 구분."""
    from app.ai.knowledge.planner import (
        detect_intent,
        is_knowledge_source_question,
        is_nested_admin_scope_question,
    )

    m = message.strip()
    if is_knowledge_source_question(m):
        return False
    if is_nested_admin_scope_question(m):
        return False
    if detect_intent(m) in ("apartment_officetel_price_gap", "built_type_price_gap"):
        return False
    if any(
        k in m
        for k in (
            "분석 경로",
            "어떤 경로",
            "어떤 분석",
            "어떻게 분석",
            "통합회귀",
            "유형 효과",
            "가격격차",
            "가격 차이",
        )
    ):
        return False
    how = any(
        k in m
        for k in (
            "어떻게 하면",
            "어떻게 보",
            "어디서 보",
            "어떻게 확인",
            "어떻게 찾",
            "어떻게 알",
            "보려면",
            "보는 법",
            "사용법",
        )
    )
    topic = any(
        k in m
        for k in (
            "추세",
            "평균",
            "매매가",
            "실거래",
            "과거",
            "장기",
            "단지",
            "아파트",
            "오피스텔",
            "통계분석",
        )
    )
    return how or (topic and any(k in m for k in ("알고 싶", "보고 싶", "보고싶", "알고싶")))


def format_howto_answer(app: str, message: str) -> str:
    """LLM이 없을 때도 쓸 화면 안내. 회귀를 먼저 꺼내지 않는다."""
    m = message.strip()
    if app == "collective" or any(k in m for k in ("아파트", "오피스텔", "단지")):
        grain = "도로(cluster)" if any(k in m for k in ("상가", "공장", "cluster", "비주거")) else "단지"
        return (
            "해당 아파트(단지)가 있는 **행정구역(시·도 / 시·군·구)**을 선택한 뒤 "
            "**「통계분석」**을 누르세요. 목록에서 원하는 "
            f"**{grain}를 클릭**하면 모달에서 **과거 추세**와 **장기추세선**을 볼 수 있습니다.\n\n"
            "평균 매매가의 흐름만 보려면 이 네 단계면 됩니다. "
            "면적·연식을 통제해 유형 격차를 보려면 그다음에 회귀·코호트를 쓰면 됩니다."
        )
    if app == "built":
        return (
            "유형과 지역(행정구역)을 고른 뒤 **「통계분석」**을 누르면 "
            "선택한 범위의 거래 요약과 회귀 카드를 볼 수 있습니다."
        )
    if app == "land":
        return (
            "지역을 선택한 뒤 용도지역×지목 **매트릭스**와 **장기추세**에서 "
            "단가 흐름을 볼 수 있습니다."
        )
    if app == "rent":
        return (
            "지역을 고르고 **「통계분석」**을 누른 다음 목록에서 건물을 열면 "
            "전월세 흐름을 볼 수 있습니다."
        )
    if app == "profile":
        return (
            "지역을 검색해 열면 거래 구성·Twin 유사지역·전국 순위를 볼 수 있습니다. "
            "단지별 추세는 집합 앱에서 행정구역 → 통계분석 → 단지 클릭 순입니다."
        )
    return (
        "보고 싶은 자산 앱에서 행정구역을 고르고 「통계분석」을 누른 다음 "
        "목록의 대상(단지·건물·필지)을 클릭하면 됩니다."
    )


def skip_llm_for_quota(message: str) -> bool:
    """제품 설명·사용법·혼동 정정은 LLM 호출 없이 코드가 답한다. 한도(월 200) 보호."""
    from app.ai.knowledge.planner import (
        is_history_compare_question,
        is_knowledge_source_question,
        is_memo_request,
        is_nested_admin_scope_question,
        is_path_intent_question,
    )

    if is_nested_admin_scope_question(message):
        return True
    if is_knowledge_source_question(message):
        return True
    if is_howto_ui_question(message):
        return True
    if is_memo_request(message) or is_history_compare_question(message):
        return True
    if is_path_intent_question(message):
        return True
    return False


# Planner 판단 자료. 한 단지 실측 n·계수는 넣지 않는다.
FUNCTION_CARDS: list[dict[str, Any]] = [
    {
        "id": "regional_profile",
        "name": "지역 프로필",
        "apps": ("profile",),
        "purpose": "한 지역의 거래 구성·유형 상관·전국 순위·닮은 지역(Twin)을 본다",
        "good_questions": [
            "이 지역의 거래 구성을 요약해 주세요",
            "Twin 유사지역은 무엇을 뜻하나요",
            "전국 순위는 어떻게 읽나요",
        ],
        "strengths": ["유형 간 구성·상관을 한 화면에서 본다"],
        "cautions": [
            "순위·Twin은 통계 유사성이지 투자 추천이 아님",
            "표본이 적은 지역은 구성이 한두 건에 흔들림",
        ],
    },
    {
        "id": "collective_integrated_regression",
        "name": "집합 통합회귀",
        "apps": ("collective",),
        "purpose": "서로 다른 유형의 집합부동산 가격수준 비교",
        "good_questions": [
            "아파트와 오피스텔 가격차이",
            "주거용과 비주거용 유형효과",
            "특정 유형의 상대가격",
        ],
        "strengths": ["면적, 연식 등 개별 특성을 통제 가능"],
        "cautions": [
            "유형별 표본 부족",
            "지역적 이질성이 큰 경우",
            "지나치게 넓은 지역을 하나로 묶는 경우",
            "유형이 층으로 갈리면 유형 더미에 층 구간이 섞임",
        ],
    },
    {
        "id": "collective_cohort",
        "name": "집합 코호트",
        "apps": ("collective",),
        "purpose": "같은 단지(주거) 또는 도로 cluster(비주거)를 묶어 동·면적·최근 변화를 본다",
        "good_questions": [
            "같은 단지 내 동일 전용면적의 최근 가격 변화",
            "이 단지와 인접 단지를 같이 보고 싶다",
        ],
        "strengths": ["단일 단지 표본 부족 시 통합 분석이 가능"],
        "cautions": [
            "주거는 단지 grain, 비주거는 도로 cluster grain — 섞지 않음",
            "코호트 조건을 AI가 임의로 바꾸지 않음 (사용자가 화면에서 구성)",
        ],
    },
    {
        "id": "collective_building_regression",
        "name": "집합 단일 단지 회귀",
        "apps": ("collective",),
        "purpose": "한 단지의 층·면적 등 거래 패턴",
        "good_questions": ["이 단지에서 층이 가격에 어떤 연관이 있나"],
        "strengths": ["단지 내부 구조 해석"],
        "cautions": ["표본이 얇으면 게이트 또는 참고용", "유형 간 비교용이 아님"],
    },
    {
        "id": "regional_regression",
        "name": "지역회귀",
        "apps": ("collective",),
        "purpose": "단지에 묶이지 않은 지역 단위에서 유형·규모 효과",
        "good_questions": ["이 동에서 아파트와 오피스텔 유형 효과", "인접 지역을 포함한 비교"],
        "strengths": ["코호트에 못 넣는 표본을 지역으로 볼 수 있음"],
        "cautions": ["지역이 넓으면 이질성", "n 과소 시 확대는 별도 실행"],
    },
    {
        "id": "built_type_compare",
        "name": "복합 통합회귀 (유형 더미)",
        "apps": ("built",),
        "purpose": "상업·단독·공장을 한 식에 넣고 유형 더미 계수로 기준 유형 대비 가격수준을 본다",
        "good_questions": ["상가와 단독 가격 차이", "복합에서 유형 비교", "유형 더미 계수는?"],
        "strengths": ["면적·연식 등을 통제한 뒤 유형 수준 차이를 한 표에서 읽음"],
        "cautions": [
            "집합 코호트(아파트·오피스텔) 통합회귀와는 다른 화면",
            "유형 더미 ≠ 건축물용도 더미",
            "통합 식 R²·MAPE가 좋아져도 유형 간 수준 차이를 더미가 흡수한 결과일 수 있음",
        ],
    },
    {
        "id": "built_regression",
        "name": "복합 회귀",
        "apps": ("built",),
        "purpose": "단독·상가·공장 등 개별 건물 거래의 규모·연식 패턴",
        "good_questions": ["연면적이 총액과 어떻게 연관되나"],
        "strengths": ["선택 변수·로그/선형 trade-off를 화면에서 실험"],
        "cautions": ["집합 유형 비교용이 아님", "예측값은 적정가가 아님"],
    },
    {
        "id": "built_upper_scope",
        "name": "복합 상위지역 비교",
        "apps": ("built",),
        "purpose": "초점(읍면동) 표본이 얇을 때 직계 상위(시군구)에 같은 회귀식을 반복해 패턴이 더 넓은 규모에서도 읽히는지 본다",
        "good_questions": [
            "1차와 2차가 의미하는 바는?",
            "상위와 하위 행정구역을 왜 같이 보나",
            "읍면동 n이 부족하면?",
        ],
        "strengths": ["같은 변수식으로 범위를 넓힘", "계수 방향이 윗단계에서 유지되면 규모 인사이트의 간접 힌트"],
        "cautions": [
            "History 1차·2차는 실행 순서이며 구 vs 동이 아닐 수 있음",
            "유사도·Twin 채택·적정가가 아님",
        ],
    },
    {
        "id": "land_matrix",
        "name": "토지 매트릭스·장기추세",
        "apps": ("land",),
        "purpose": "용도지역×지목 칸의 단가 수준과 추이",
        "good_questions": ["이 용도·지목의 단가는?", "장기 추세는?"],
        "strengths": ["칸별 n과 단가를 같이 봄"],
        "cautions": ["칸 n이 작으면 불안정", "전망이 아님", "여러 칸을 한 회귀에 넣지 않음", "거래액 합 ≠ 가격지수"],
    },
    {
        "id": "profile_twin",
        "name": "지역프로필 · Twin",
        "apps": ("built", "collective", "land"),
        "purpose": "구조가 닮은 지역을 찾아 비교 맥락을 만든다",
        "good_questions": ["이 지역과 비슷한 곳은?"],
        "strengths": ["회귀 변수가 아니라 지역 비교 엔진 (D-041)"],
        "cautions": ["Bundle 없이 Twin 지역 이름을 나열하지 않음", "유사도 ≠ 자동 채택"],
    },
    {
        "id": "rent_conversion",
        "name": "주거 전월세 전환율",
        "apps": ("rent",),
        "purpose": "반전세↔전세/월세 환산 비교",
        "good_questions": ["적용 전환율은 어떻게 쓰이나"],
        "strengths": ["mean_simple 확정 (D-040)"],
        "cautions": ["시세·적정 전세 아님", "상권 공표와 섞지 않음"],
    },
]


def format_function_cards(*, app: str = "", intent_hint: str = "") -> str:
    cards = FUNCTION_CARDS
    if app:
        cards = [c for c in FUNCTION_CARDS if app in c["apps"] or not c["apps"]]
    if intent_hint:
        h = intent_hint
        prefer = [
            c
            for c in cards
            if h in c["id"]
            or h in c["name"]
            or any(h in q for q in c["good_questions"])
        ]
        if prefer:
            cards = prefer + [c for c in cards if c not in prefer]
    lines = ["[기능 카드 — 목적 / 적합한 질문 / 장점 / 주의. 표본 숫자는 Bundle만]"]
    for c in cards[:6]:
        lines.append(f"## {c['name']}")
        lines.append(f"목적: {c['purpose']}")
        lines.append("적합한 질문: " + " · ".join(c["good_questions"]))
        if c.get("strengths"):
            lines.append("장점: " + " · ".join(c["strengths"]))
        lines.append("주의: " + " · ".join(c["cautions"]))
        lines.append("")
    return "\n".join(lines).strip()


def product_knowledge_pack(*, app: str = "built", panel: str = "") -> str:
    """현재 앱 지식. 다른 앱 전문은 넣지 않음."""
    key = app if app in DOMAIN_BY_APP else "built"
    parts = [
        PRODUCT_OVERVIEW.strip(),
        APP_STRUCTURE.strip(),
        format_domain_card(key),
        format_negative_card(key),
    ]
    if key == "built":
        parts.append(REGRESSION_LOGIC.strip())
        parts.append(NESTED_ADMIN_SCOPE.strip())
        if panel in ("RecommendationCard", "ModelSelectionCard"):
            parts.append(RECOMMEND_LOGIC.strip())
    elif key == "land":
        parts.append(
            "land: 용도지역×지목 매트릭스 셀 회귀·장기추세·유료 필지 분석. "
            "셀별 n·Adj R²·모델(log/선형)은 Bundle facts만 인용."
        )
    elif key == "collective":
        parts.append(format_function_cards(app="collective"))
        parts.append(
            "collective: 단지/코호트 회귀·고정효과(FE). "
            "주거·비주거는 분석 단위만 다르고 통계 UX는 동일. "
            "비주거 grain=도로 cluster. K-apt 세대수·주차는 주거 단지 전용."
        )
    elif key == "rent":
        parts.append(RENT_CONVERSION.strip())
        parts.append(SANGKWON_REB.strip())
        if panel == "SangkwonCard":
            parts.append(
                "지금 화면은 상권분석 모달이다. 주거 전환율·환산 P50이 아니라 "
                "부동산원 상업용 상권 공표(기본표 4분기 롤링, 추세는 연간)만 인용한다."
            )
    elif key == "profile":
        parts.append(format_function_cards(app="profile"))
        parts.append(RECOMMEND_LOGIC.strip())
        parts.append(
            "profile: 지역 프로필(거래 구성·Twin 유사지역·전국 순위). "
            "숫자는 화면 Bundle facts만 인용. 투자·매수 추천 금지."
        )
    parts.append(LIMITATIONS.strip())
    parts.append(UI_HOWTO.strip())
    if key in ("built", "land") and panel:
        extra = format_function_cards(app=key)
        if extra:
            parts.append(extra)
    return "\n\n".join(parts)


def product_knowledge_excerpt(*, app: str, panel: str, message: str) -> str:
    """LLM 컨텍스트용 — 기본은 현재 앱 + 네거티브. 전 앱은 유형 차이 질문만."""
    lower = message.lower()
    from app.ai.knowledge.planner import is_knowledge_source_question

    if is_knowledge_source_question(message) or is_cross_app_question(message):
        if is_knowledge_source_question(message):
            return format_knowledge_source_answer(app=app or "built")
        return "\n\n".join(
            [
                PRODUCT_OVERVIEW.strip(),
                APP_STRUCTURE.strip(),
                format_all_domain_cards(with_negatives=True),
                LIMITATIONS.strip(),
            ]
        )
    if any(k in lower or k in message for k in ("twin", "쌍둥이", "stage")) or (
        "모형" in message and any(k in message for k in ("추천", "탐색", "forward"))
    ):
        return product_knowledge_pack(app=app, panel=panel or "RecommendationCard")
    if any(k in message for k in ("데이터", "마트", "파이프", "원천", "정제", "수집", "원장")):
        return "\n\n".join(
            [
                PRODUCT_OVERVIEW.strip(),
                DATA_PIPELINE.strip(),
                format_domain_card(app or "built"),
                format_negative_card(app or "built"),
                LIMITATIONS.strip(),
            ]
        )
    sangkwon_keys = (
        "상권",
        "상업용",
        "순영업",
        "noi",
        "공실",
        "소득수익",
        "자본수익",
        "투자수익",
        "운영경비",
        "임대가격지수",
        "임대수입",
        "기타수입",
    )
    if panel == "SangkwonCard" or any(k in message or k in lower for k in sangkwon_keys):
        return "\n\n".join(
            [
                PRODUCT_OVERVIEW.strip(),
                format_negative_card("rent"),
                SANGKWON_REB.strip(),
                LIMITATIONS.strip(),
            ]
        )
    if is_howto_ui_question(message):
        return "\n\n".join(
            [
                PRODUCT_OVERVIEW.strip(),
                format_negative_card(app or "built"),
                UI_HOWTO.strip(),
                format_howto_answer(app, message),
                LIMITATIONS.strip(),
            ]
        )
    if any(
        k in message
        for k in (
            "1차",
            "2차",
            "상위지역",
            "상위행정",
            "하위행정",
            "직계 상위",
            "읍면동",
            "시군구",
        )
    ) and any(k in message for k in ("의미", "뜻", "비교", "결과", "의도", "무엇", "뭐야", "1차", "2차", "상위")):
        return "\n\n".join(
            [
                PRODUCT_OVERVIEW.strip(),
                NESTED_ADMIN_SCOPE.strip(),
                format_domain_card(app or "built"),
                format_negative_card(app or "built"),
                LIMITATIONS.strip(),
            ]
        )
    if any(
        k in message
        for k in (
            "통합회귀",
            "코호트",
            "유형 효과",
            "가격 차이",
            "가격격차",
            "오피스텔",
            "어떻게 분석",
            "어떤 분석",
            "어떤 방식",
            "어떤 방법",
        )
    ):
        return "\n\n".join(
            [
                PRODUCT_OVERVIEW.strip(),
                format_domain_card(app or "built"),
                format_negative_card(app or "built"),
                format_function_cards(app=app or "built"),
                LIMITATIONS.strip(),
            ]
        )
    if any(
        k in message
        for k in (
            "전환율",
            "전세환산",
            "월세환산",
            "전세전환",
            "월세전환",
            "단순평균",
            "원점회귀",
            "mean_simple",
            "반전세",
        )
    ):
        return "\n\n".join(
            [
                PRODUCT_OVERVIEW.strip(),
                format_negative_card("rent"),
                RENT_CONVERSION.strip(),
                LIMITATIONS.strip(),
            ]
        )
    return product_knowledge_pack(app=app, panel=panel)
