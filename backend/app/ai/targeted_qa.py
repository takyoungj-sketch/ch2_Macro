"""질문별 targeted 답변 — generic Explain dump 방지."""

from __future__ import annotations

import re
from typing import Any

from app.recommendation.cv_fitness import lookup_cv_fitness

from app.ai.bundles.comparison import is_model_comparison_question

_FITNESS_LABEL_HINTS = (
    "주의",
    "우수",
    "보통",
    "부적합",
    "매우 우수",
    "높은 편",
    "낮음",
    "높음",
    "상당히 높음",
    "매우 높음",
    "보통 이하",
    "활용 가능",
    "탐색적 활용",
    "신중 활용",
    "안정적",
    "등급",
    "뱃지",
    "배지",
    "적합",
    "라벨",
    "표시",
    "해석 강도",
)

_MAPE_HINTS = ("mape", "cv-mape", "cv mape", "cv_mape", "오차")


def _mentions_mape_fitness(message: str) -> bool:
    lower = message.lower()
    has_mape = any(h in lower for h in _MAPE_HINTS)
    has_fitness = any(h in message for h in _FITNESS_LABEL_HINTS)
    return has_mape and has_fitness


def _fmt_mape(v: Any) -> str:
    try:
        return f"{float(v):.1f}%"
    except (TypeError, ValueError):
        return str(v)


def answer_mape_fitness_question(message: str, diagnostics: dict[str, Any]) -> str | None:
    """MAPE/CV-MAPE 해석 강도 질문."""
    if not _mentions_mape_fitness(message):
        return None

    mape = diagnostics.get("mape")
    cv_mape = diagnostics.get("cv_mape")
    metric_val = cv_mape if cv_mape is not None else mape
    metric_name = "CV-MAPE" if cv_mape is not None else "MAPE"

    fitness_raw = diagnostics.get("cv_fitness") or diagnostics.get("predictive_fit")
    if isinstance(fitness_raw, dict) and fitness_raw.get("label_ko"):
        tier_label = str(fitness_raw["label_ko"])
        tier = str(fitness_raw.get("tier") or "")
    elif metric_val is not None:
        tier_obj = lookup_cv_fitness(float(metric_val))
        tier_label = tier_obj.label_ko
        tier = tier_obj.tier
    else:
        return (
            "### 답변\n\n"
            "현재 화면 Bundle에 MAPE 수치가 없습니다. 회귀·모형 탐색을 실행한 뒤 "
            "다시 질문해 주세요.\n\n"
            "### 한계\n\n"
            "해석 강도는 CH2 내부 구간이며 감정·투자 판단이 아닙니다."
        )

    lines = ["### 답변", ""]
    if metric_val is not None:
        lines.append(
            f"이번 화면 **{metric_name} {_fmt_mape(metric_val)}** 의 해석 강도는 **「{tier_label}」** 입니다."
        )
    else:
        lines.append(f"이번 화면 해석 강도 라벨은 **「{tier_label}」** 입니다.")

    lines.append(
        "이 라벨은 모형이 맞다/틀리다가 아닙니다. "
        "지역 거래 구조를 어느 강도로 읽을지 정하는 언어입니다. "
        "개별 물건 가격을 맞히기 위한 AVM 점수가 아닙니다."
    )
    if asked_label_is_caution(message) or tier in {"elevated", "caution"} or tier_label == "높은 편":
        lines.append(
            "「높은 편」은 CV-MAPE **45% 이상 60% 미만**입니다. "
            "개별 거래 차이는 크지만 계수 방향·상대 영향은 볼 수 있습니다."
        )
    elif tier in {"high", "very_high", "unsuitable", "exploratory"} or tier_label in {
        "높음",
        "상당히 높음",
        "매우 높음",
        "예측 부적합",
        "탐색적 활용",
    }:
        lines.append(
            "오차가 큰 편이면 예측값으로 읽지 말고 구조 탐색으로 해석하세요. "
            "분석을 버린다는 뜻이 아닙니다."
        )
    elif tier == "low" or tier_label == "낮음":
        lines.append("「낮음」은 CV-MAPE **30% 미만**으로, 구조적 관계가 비교적 안정적입니다.")
    elif tier == "moderate" or "보통" in tier_label:
        lines.append(
            "「보통」은 CV-MAPE **30% 이상 45% 미만**입니다. "
            "지역 가격구조 분석에 활용할 수 있습니다."
        )

    lines.extend(["", "### 근거", ""])
    if mape is not None:
        lines.append(f"- in-sample MAPE: {_fmt_mape(mape)}")
    if cv_mape is not None:
        lines.append(f"- CV-MAPE: {_fmt_mape(cv_mape)}")
    lines.append(
        "- 해석 강도: <30% 낮음 · 30~45% 보통 · 45~60% 높은 편 · ≥60% 높음. "
        "CV 단독 적부가 아니라 설명력·검증 안정성·표본과 함께 읽습니다."
    )
    n = diagnostics.get("n")
    if n is not None:
        lines.append(f"- 표본 n={n}건")

    lines.extend([
        "",
        "### 한계",
        "",
        "회귀 카드 MAPE는 표본 안 설명 오차이고, 모형 추천은 CV-MAPE를 봅니다. "
        "감정평가·투자 판단 근거가 아닙니다.",
    ])
    return "\n".join(lines)


def asked_label_is_caution(message: str) -> bool:
    return "주의" in message


def answer_model_comparison_question(message: str, diagnostics: dict[str, Any]) -> str | None:
    """로그·log-log·선형 등 방법론 비교."""
    if not is_model_comparison_question(message):
        return None

    lower = message.lower()
    asks_log_log = "log-log" in lower or "log log" in lower or "loglog" in lower
    asks_log = "로그" in message or "log" in lower
    asks_linear = "선형" in message or "linear" in lower

    model_type = diagnostics.get("model_type")
    n = diagnostics.get("n")

    lines = ["### 답변", ""]

    if asks_log_log and asks_log:
        lines.append(
            "**Semi-log(로그·금액 회귀)** 는 보통 **log(거래금액) ~ 연면적·연식 등(원척도)** 입니다. "
            "연속 독립변수 1단위 증가 시 금액이 **약 % 단위로 변하는** 패턴을 봅니다."
        )
        lines.append(
            "**Log-log** 는 **log(금액) ~ log(면적) 등** 으로, 계수가 **탄력성(%)** 에 가깝게 읽힙니다. "
            "면적·규모 효과가 **비율 스케일**일 때 해석이 자연스러울 수 있습니다."
        )
        lines.append(
            "CH2 복합 기본 통계는 선형·semi-log·log-log를 사용자가 고릅니다. "
            "모형 추천은 **같은 표본**에서 세 척도를 적합하고, 예측형은 **원척도 CV-MAPE**로 고릅니다. "
            "log-log는 연면적·대지 블록이 있을 때만 후보이며, **면적만 log**(연식·더미는 선형) 입니다. "
            "설명형 AIC는 log(금액) 식끼리만 비교합니다."
        )
    elif asks_log and asks_linear:
        lines.append(
            "**선형(총액 OLS)**: 금액(만원) ~ 변수 — 계수가 **만원 단위**로 직관적이나, "
            "금액 분포가 치우치면 잔차가 불안정할 수 있습니다."
        )
        lines.append(
            "**로그(금액) semi-log**: log(금액) ~ 변수 — **% 변화** 해석에 가깝고 왜도 큰 금액에 자주 씁니다. "
            "추천은 같은 표본의 선형·semi-log·log-log 중 원척도 CV-MAPE로 고릅니다."
        )
    else:
        lines.append(
            "CH2에서 **모형 타입(선형·log·log-log·변수 조합)** 은 scope·자산유형·분포에 따라 "
            "Adj R²·MAPE·CV-MAPE trade-off로 비교합니다. "
            "한 타입이 항상 우월하지 않습니다."
        )

    lines.extend(["", "### 근거", ""])
    if model_type is not None:
        lines.append(f"- 현재 화면 model_type: `{model_type}`")
    if n is not None:
        lines.append(f"- 표본 n={n}건")
    adj = diagnostics.get("adj_r_squared")
    if adj is not None:
        lines.append(f"- Adj R²={float(adj):.3f}")
    lines.append("- CH2: 선형 vs semi-log vs log-log — 원척도 CV-MAPE·같은 표본")

    lines.extend([
        "",
        "### 한계",
        "",
        "방법론 설명이며 **이번 scope 최적 모형을 단정하지 않습니다**. "
        "가격·투자 판단이 아닙니다.",
    ])
    return "\n".join(lines)


_CONVERSION_HINTS = (
    "전환율",
    "전세환산",
    "월세환산",
    "전세전환",
    "월세전환",
    "단순평균",
    "원점회귀",
    "mean_simple",
    "반전세",
    "적용 전환",
)


def answer_conversion_method_question(message: str, diagnostics: dict[str, Any] | None = None) -> str | None:
    """주거 전월세 전환율 채택 이유 — 실험 종료(D-040). 재계산 없음."""
    if not any(h in message or h in message.lower() for h in _CONVERSION_HINTS):
        return None
    diag = diagnostics or {}
    r = diag.get("r_selected")
    window = diag.get("window_years")
    method = diag.get("conversion_method") or "mean_simple"
    scope = diag.get("conversion_scope")
    applied = diag.get("conversion_applied")
    lines = [
        "### 답변",
        "",
        "CH2 적용 전환율은 **한국부동산원 공표값·고정 5%가 아닙니다.** "
        "같은 건물의 전세·반전세 거래로 건물별 \(r_b=12M/(J-D)\)를 구한 뒤 "
        "**지역·주택유형·선택한 연수**의 **단순평균**을 씁니다. "
        "목적은 반전세를 전세·월세 축으로 맞추는 비교이지, 시장 금리를 추정하는 것이 아닙니다.",
        "",
        "2026-08 서울 실험(동일기간 + 마지막 1년 hold-out, 시군구·동 × 3·5·7년)에서 "
        "**단순평균이 hold-out MAPE 여섯 칸 모두 1위**였고, 원점회귀는 전부 열위, "
        "가중회귀는 가장 나빴습니다. 그래서 `r_selected = mean_simple`을 확정했고 "
        "산식을 더 나누지 않습니다.",
        "",
        "연립에서 건물별 전환율 편차가 큰 것은 개별 건물 이질성이며 방법론 실패가 아닙니다. "
        "유형별 회귀·가중은 만들지 않습니다. \(r_b\) 분포는 품질 확인용입니다.",
    ]
    screen = []
    if r is not None:
        try:
            screen.append(f"이번 화면 적용 r **{float(r):.2f}%**")
        except (TypeError, ValueError):
            screen.append(f"이번 화면 적용 r **{r}**")
    if window is not None:
        screen.append(f"{window}년 창")
    if scope:
        screen.append(f"적용 단위 {scope}")
    if method:
        screen.append(f"방법 {method}")
    if applied is False:
        screen.append("이번 칸은 게이트 미달(전환율 없음)")
    if screen:
        lines.extend(["", "이번 화면: " + " · ".join(screen) + "."])
    lines.extend(
        [
            "",
            "### 한계",
            "",
            "환산 P50은 **비교값**이며 시세·적정 전세가 아닙니다. "
            "정의는 헤더·표 옆 **`?`**, 실험 기록은 `docs/RENT_CONVERSION_EXPERIMENT.md` 입니다.",
        ]
    )
    return "\n".join(lines)


def try_targeted_answer(message: str, diagnostics: dict[str, Any]) -> str | None:
    """Explain/CH2 경로 — 질문에 맞는 짧은 답 우선."""
    if ans := answer_conversion_method_question(message, diagnostics):
        return ans
    if ans := answer_mape_fitness_question(message, diagnostics):
        return ans
    if ans := answer_model_comparison_question(message, diagnostics):
        return ans
    return None


def is_generic_screen_question(message: str) -> bool:
    """화면 전체 개요만 묻는 경우 — generic Explain dump 허용."""
    generic = (
        "이 화면",
        "무엇을 보여",
        "개요",
        "한눈",
        "전체 설명",
        "화면 설명",
    )
    if any(g in message for g in generic):
        return True
    if re.match(r"^(이\s*)?결과를?\s*(설명|소개)", message.strip()):
        return True
    return False
