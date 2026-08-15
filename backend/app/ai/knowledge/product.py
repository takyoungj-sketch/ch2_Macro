"""CH2 제품·데이터 파이프라인 지식 (Product Knowledge Pack)."""

from __future__ import annotations

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

RECOMMEND_LOGIC = """
모형 추천·Twin:
- 기본: Local scope 회귀·CV-MAPE 기반 모형 탐색
- Twin(쌍둥이): 유사 지역 프로필 기반 **조건부** 보조 — 기본값 아님
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

CH2 연간 표시 (화면은 연 단위):
- 임대료·층별임대료: 4분기 월단가 평균 × 12, 천원→만원 (만원/㎡·년). 4분기 없으면 빈칸.
- 순영업소득(금액): 분기 유량 4분기 합, 천원→만원.
- 순영업소득(%)·임대수입%·기타수입%·운영경비%·공실률·전환율·임대가격지수: 분기 산술평균.
- 소득·자본·투자수익률: 부동산원 연간식 ∏(1+r_q/100)−1. 4분기 필수. 분기 I+C=T 이나 연간 복리값은 더해서 같지 않음.
- 동수·호수·평균층수·평균면적: 그 해 마지막 유효 분기.

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


def product_knowledge_pack(*, app: str = "built", panel: str = "") -> str:
    """질문·화면에 맞게 발췌할 수 있는 큐레이션 지식."""
    parts = [PRODUCT_OVERVIEW.strip(), APP_STRUCTURE.strip()]
    if app == "built":
        parts.append(REGRESSION_LOGIC.strip())
        if panel in ("RecommendationCard", "ModelSelectionCard"):
            parts.append(RECOMMEND_LOGIC.strip())
    elif app == "land":
        parts.append(
            "land: 용도지역×지목 매트릭스 셀 회귀·장기추세·유료 필지 분석. "
            "셀별 n·Adj R²·모델(log/선형)은 Bundle facts만 인용."
        )
    elif app == "collective":
        parts.append(
            "collective: 단지/코호트 회귀·고정효과(FE). "
            "주거·비주거는 분석 단위만 다르고 통계 UX는 동일."
        )
    elif app == "rent":
        parts.append(RENT_CONVERSION.strip())
        parts.append(SANGKWON_REB.strip())
        if panel == "SangkwonCard":
            parts.append(
                "지금 화면은 상권분석 모달이다. 주거 전환율·환산 P50이 아니라 "
                "부동산원 상업용 상권 공표(연간 표시)만 인용한다."
            )
    parts.append(LIMITATIONS.strip())
    return "\n\n".join(parts)


def product_knowledge_excerpt(*, app: str, panel: str, message: str) -> str:
    """LLM 컨텍스트용 — 전체 팩 또는 토픽별 발췌."""
    lower = message.lower()
    if any(k in lower or k in message for k in ("twin", "쌍둥이", "추천", "stage", "모형")):
        return product_knowledge_pack(app=app, panel=panel or "RecommendationCard")
    if any(k in message for k in ("데이터", "마트", "파이프", "원천", "정제")):
        return "\n\n".join([PRODUCT_OVERVIEW.strip(), DATA_PIPELINE.strip(), LIMITATIONS.strip()])
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
        return "\n\n".join([PRODUCT_OVERVIEW.strip(), SANGKWON_REB.strip(), LIMITATIONS.strip()])
    if any(k in message for k in ("앱", "복합", "토지", "집합", "화면", "구조")):
        return "\n\n".join([PRODUCT_OVERVIEW.strip(), APP_STRUCTURE.strip()])
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
        return "\n\n".join([PRODUCT_OVERVIEW.strip(), RENT_CONVERSION.strip(), LIMITATIONS.strip()])
    return product_knowledge_pack(app=app, panel=panel)
