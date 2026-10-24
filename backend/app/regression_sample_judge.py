"""회귀 표본의 공통 판정.

계산 불가는 계수를 낼 수 없을 때다. rank가 0이거나 잔차 자유도 ``n - rank(X)`` 가
1 미만일 때다. ``X`` 는 상수항을 포함한 설계행렬이다.

참고용은 계산은 되는데 유효 표본이 30 미만이거나, 계수 하나당 관측이 5 미만일 때다.
일반은 둘 다 충족할 때다. 30과 5는 통계적 보증이 아니라 CH2 Macro의 분석 제공 기준이다.

열 수보다 rank가 작아도 잔차 자유도가 1 이상이면 계산 불가가 아니다.
식은 등급대로 보여주고, 모형 식별 표시를 따로 붙인다.

유형별 최소 하한(토지 15, 복합 10, 집합 5, 지역 학습 단지 20, 임대 8)은
각 엔진이 식 제공 전에 적용한다. 이 모듈은 그 하한을 통과한 적합을 등급 짓는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

STANDARD_N = 30
OBS_PER_COEF = 5

Tier = Literal["blocked", "caution", "standard"]


def residual_df(n: int, rank: int) -> int:
    """적합에 쓴 행 수와 설계행렬 계수로 잔차 자유도를 계산한다."""
    return int(n) - int(rank)


@dataclass(frozen=True)
class MissingFunnel:
    """결측으로 표본이 줄어든 경로.

    적용 순서: 전체 → 종속변수 결측 → 켜진 숫자 변수 결측 → 범주 결측 제외 → 최종.
    ``n_excluded_target`` 은 금액·단가·단지 중앙값처럼 종속변수가 없어 관측이 아닌 행이다.
    """

    n_source: int
    n_excluded_target: int
    n_excluded_numeric: int
    n_excluded_categorical: int
    n_fit: int

    def balances(self) -> bool:
        return (
            self.n_source
            - self.n_excluded_target
            - self.n_excluded_numeric
            - self.n_excluded_categorical
            == self.n_fit
        )


@dataclass(frozen=True)
class TypeExtra:
    """관측 단위가 거래 건수와 다른 조건. 최소 하한은 엔진이 식 제공 전에 적용한다."""

    code: str
    observed: int
    minimum: int
    unit: str


@dataclass(frozen=True)
class DesignFacts:
    n: int
    rank: int

    @property
    def residual_df(self) -> int:
        return residual_df(self.n, self.rank)


@dataclass(frozen=True)
class SampleVerdict:
    tier: Tier
    n: int
    rank: int
    n_columns: int
    reasons: tuple[str, ...]
    identification: bool


def blocked_reasons(n: int, rank: int) -> tuple[str, ...]:
    """계산 불가 사유. 비어 있으면 계수를 낼 수 있다."""
    reasons: list[str] = []
    if rank < 1:
        reasons.append("설계행렬 계수 없음")
    elif residual_df(n, rank) < 1:
        reasons.append("잔차 자유도 없음")
    return tuple(reasons)


def is_computable(n: int, rank: int) -> bool:
    return not blocked_reasons(n, rank)


def judge_sample(n: int, rank: int, n_columns: int | None = None) -> SampleVerdict:
    """유효 표본과 rank로 계산 불가·참고용·일반을 가른다."""
    n = int(n)
    rank = int(rank)
    columns = int(n_columns if n_columns is not None else rank)
    reasons = blocked_reasons(n, rank)
    identification = not reasons and columns > rank
    if reasons:
        tier: Tier = "blocked"
    elif n < STANDARD_N or rank < 1 or (n / rank) < OBS_PER_COEF:
        tier = "caution"
    else:
        tier = "standard"
    return SampleVerdict(
        tier=tier,
        n=n,
        rank=rank,
        n_columns=columns,
        reasons=reasons,
        identification=identification,
    )


def judge_exog(exog) -> SampleVerdict:
    """적합에 쓴 설계행렬(상수항 포함)로 판정한다."""
    arr = np.asarray(exog, dtype=float)
    if arr.ndim != 2 or arr.shape[0] == 0 or arr.shape[1] == 0:
        return judge_sample(0, 0, 0)
    n, k = int(arr.shape[0]), int(arr.shape[1])
    return judge_sample(n, int(np.linalg.matrix_rank(arr)), k)


PROVISION_FOLLOWUP = (
    "표본 수가 권장 기준에 미달하므로 회귀계수가 불안정할 수 있습니다. "
    "R²와 MAPE는 해당 표본의 적합 결과이며, 새로운 거래에 대한 예측 정확도를 보장하지 않습니다."
)


def provision_note(verdict: SampleVerdict, *, unit: str = "건") -> str | None:
    if verdict.tier != "caution":
        return None
    return f"분석 제공 기준(30{unit}, 계수당 5{unit})에 못 미쳐 참고용"


def identification_note(verdict: SampleVerdict) -> str | None:
    if not verdict.identification:
        return None
    return (
        f"모형 식별: 설계 열 {verdict.n_columns}개, 독립 계수 {verdict.rank}개. "
        "계수가 한 값으로 정해지지 않습니다."
    )


def blocked_note(verdict: SampleVerdict) -> str | None:
    if verdict.tier != "blocked":
        return None
    return "계산 불가: " + ", ".join(verdict.reasons)


def sample_notes(verdict: SampleVerdict, *, unit: str = "건") -> list[str]:
    """응답 warnings에 넣을 문장. 계산 불가이면 그 사유만 반환한다."""
    blocked = blocked_note(verdict)
    if blocked:
        return [blocked]
    notes: list[str] = []
    provision = provision_note(verdict, unit=unit)
    if provision:
        notes.append(provision)
    identified = identification_note(verdict)
    if identified:
        notes.append(identified)
    return notes
