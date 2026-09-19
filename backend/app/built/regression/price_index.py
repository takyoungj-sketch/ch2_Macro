"""시군구 가격시점 지수 — 회귀식 밖 시간 보정 계층 (D-075).

회귀엔진은 물건 구조(면적·연식 등)만 설명하고, 거래시점 → 기준시점 환산은 이 모듈이
담당한다. 최종 추정값 = 구조 회귀 추정값 × 시점 보정.

**왜 연도 더미가 아닌가**

- 미래 예측이 목적이면 학습에 없는 연도의 더미는 계수를 추정할 수 없다.
- 더 결정적으로, 읍면동 n이 30~80인 국소 표본에서 연도 더미 4개는 비싼 지출이고 정작
  보고 싶은 면적·연식 계수의 정밀도를 깎는다. 전처리로 빼면 자유도를 쓰지 않는다.

**왜 고정 명세인가**

지수는 사용자가 화면에서 어떤 변수를 체크했는지와 무관해야 한다. 그러지 않으면 같은 거래가
변수 선택에 따라 다르게 환산되고, 시점 보정이 UI 상태에 의존하게 된다. 그래서 아래
`_INDEX_SPEC` 하나로만 추정한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# 지수 추정용 고정 구조 통제. 연면적·대지면적은 log, 연식은 선형.
_LOG_COLS = ("gross_area", "land_area")
_LINEAR_COLS = ("building_age",)

# 연도별 최소 거래 수. 로그가격 잔차 sd를 0.45로 보면 n=30에서 그 해 수준의 표준오차가
# 약 8%다. 이보다 얇은 연도는 아예 지수에 넣지 않는다. 남은 잡음은 아래 수축이 처리한다.
MIN_ROWS_PER_YEAR = 30
# 지수를 추정하려면 이만큼의 연도가 필요하다.
MIN_YEARS = 3
# 연간 변동 상한. 이를 넘는 계수는 추정 실패로 보고 보정을 포기한다.
MAX_YEAR_FACTOR = 3.0


@dataclass(frozen=True)
class YearIndex:
    """연도 → 기준시점 환산 배수.

    `factors[year]`를 곱하면 그 해 거래가격이 `base_year` 수준으로 환산된다.
    """

    base_year: int
    factors: dict[int, float] = field(default_factory=dict)
    n_by_year: dict[int, int] = field(default_factory=dict)
    note: str | None = None
    # 수축 후 남은 연도 효과의 평균 비율. 0에 가까우면 연도차가 표본오차 수준이라
    # 사실상 보정이 없다는 뜻이다.
    shrink_keep_ratio: float = 1.0

    @property
    def available(self) -> bool:
        """보정할 값이 실제로 있는가.

        수축이 연도 효과를 거의 다 지웠다면 배수가 전부 1에 가깝다. 그럴 때 「환산했다」고
        말하면 하지 않은 보정을 했다고 하는 셈이므로 보정 없음으로 취급한다.
        """
        return len(self.factors) >= MIN_YEARS and self.shrink_keep_ratio >= 0.05

    def factor(self, year: float | int | None) -> float:
        """그 해를 기준시점으로 올리는 배수. 모르는 해는 1.0 (보정 없음).

        학습 구간보다 뒤의 연도(예측 대상)는 **추세를 연장하지 않고** 마지막 학습 연도의
        수준을 이어 쓴다. 미래 지수는 알 수 없으므로 추세를 연장하면 모르는 것을 아는
        것처럼 만들고, 그 오차가 구조 계수 평가에 섞인다.
        """
        if year is None or not self.factors:
            return 1.0
        try:
            y = int(year)
        except (TypeError, ValueError):
            return 1.0
        if y in self.factors:
            return self.factors[y]
        known = sorted(self.factors)
        if y > known[-1]:
            return self.factors[known[-1]]
        if y < known[0]:
            return self.factors[known[0]]
        return 1.0

    def yearly_change_pct(self) -> list[tuple[int, float]]:
        """기준시점 대비 각 연도의 가격 수준(%) — 화면·진단용."""
        out: list[tuple[int, float]] = []
        for y in sorted(self.factors):
            f = self.factors[y]
            if f > 0:
                out.append((y, round((1.0 / f - 1.0) * 100, 2)))
        return out


_EMPTY = YearIndex(base_year=0, note="시점 보정 없음")


def last_complete_year(as_of_month: str | None = None) -> int:
    """지수에 쓸 마지막 **완결** 연도.

    12월까지 자료가 있는 해만 완결로 본다. 진행 중인 해는 거래가 몇십 건뿐이라
    기준시점으로 쓸 수 없다.
    """
    from datetime import date

    if as_of_month:
        try:
            y, m = (int(p) for p in as_of_month.strip().split("-")[:2])
            return y if m >= 12 else y - 1
        except (ValueError, TypeError):
            pass
    today = date.today()
    return today.year if today.month >= 12 else today.year - 1


def _design(df: pd.DataFrame) -> pd.DataFrame | None:
    parts: list[pd.DataFrame] = []
    for col in _LOG_COLS:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        s = s.where(s > 0)
        parts.append(pd.DataFrame({f"log_{col}": np.log(s)}))
    for col in _LINEAR_COLS:
        if col not in df.columns:
            continue
        parts.append(pd.DataFrame({col: pd.to_numeric(df[col], errors="coerce")}))
    if not parts:
        return None
    return pd.concat(parts, axis=1)


def _shrink_year_effects(
    gammas: dict[int, float],
    errors: dict[int, float],
) -> tuple[dict[int, float], float]:
    """연도 효과를 추정 잡음만큼 0으로 당긴다 (empirical Bayes).

    시군구 연도별 표본은 수십 건인 곳이 많아 연도 계수 자체가 흔들린다. 그 잡음을 그대로
    쓰면 모든 거래가격에 곱해져 증폭되고, 실측에서 CV가 오히려 나빠졌다.

    연도 효과의 참 분산 τ²를 `평균(γ²) − 평균(se²)`로 추정하고 각 연도를 `τ²/(τ²+se²)`만큼
    남긴다. 시장이 실제로 움직였으면 τ²가 se²보다 훨씬 커서 거의 그대로 쓰이고, 연도차가
    표본오차 수준이면 0으로 수축해 **보정하지 않는 것과 같아진다.** 임계값 하나로 켜고
    끄는 것보다 얇은 지역이 매끄럽게 퇴화한다.

    돌려주는 둘째 값은 평균 유지 비율 — 0에 가까우면 보정이 사실상 없다는 뜻이다.
    """
    if not gammas:
        return {}, 0.0
    g = np.asarray([gammas[y] for y in sorted(gammas)], dtype=float)
    s = np.asarray([errors.get(y, 0.0) for y in sorted(gammas)], dtype=float)
    tau2 = float(np.mean(g**2) - np.mean(s**2))
    if not np.isfinite(tau2) or tau2 <= 0:
        return {y: 0.0 for y in gammas}, 0.0
    out: dict[int, float] = {}
    kept: list[float] = []
    for y in gammas:
        se2 = float(errors.get(y, 0.0)) ** 2
        w = tau2 / (tau2 + se2) if (tau2 + se2) > 0 else 0.0
        out[y] = gammas[y] * w
        kept.append(w)
    return out, round(float(np.mean(kept)), 4)


def estimate_year_index(
    df: pd.DataFrame,
    *,
    years: list[int] | tuple[int, ...] | None = None,
    base_year: int | None = None,
    max_complete_year: int | None = None,
) -> YearIndex:
    """시군구 표본에서 품질 보정 연도 지수를 추정한다.

    `years`를 주면 그 연도만 쓴다. **CV는 반드시 학습 연도만 넘겨야 한다** — holdout
    연도가 섞이면 국소 모형이 그 해를 못 봤어도 전처리를 통해 정보를 받아, 확인 CV가
    실제보다 좋아진다 (D-075).

    `max_complete_year`보다 뒤의 연도는 지수에서 뺀다. 올해는 아직 진행 중이고 신고
    지연까지 겹쳐 거래가 몇십 건뿐인데, 그 해를 기준시점으로 잡으면 모든 예상값이 그
    얇은 표본에 매달린다. 실측에서 2026년(18~29건)이 기준으로 잡혀 수성구 예상값이
    35% 내려갔다. 빠진 연도의 거래는 마지막 기준연도 수준으로 간주한다.

    추정 실패(표본·연도 부족, 특이 행렬, 비현실적 계수)에는 보정을 포기하고 빈 지수를
    돌려준다. 잘못된 보정보다 보정 없음이 낫다.
    """
    if df.empty or "contract_year" not in df.columns or "price" not in df.columns:
        return _EMPTY

    price = pd.to_numeric(df["price"], errors="coerce")
    year = pd.to_numeric(df["contract_year"], errors="coerce")
    X = _design(df)
    if X is None:
        return _EMPTY

    frame = pd.concat([price.rename("_price"), year.rename("_year"), X], axis=1).dropna()
    frame = frame[frame["_price"] > 0]
    if years is not None:
        frame = frame[frame["_year"].isin([int(y) for y in years])]
    if frame.empty:
        return _EMPTY

    if max_complete_year is not None:
        frame = frame[frame["_year"] <= int(max_complete_year)]
        if frame.empty:
            return _EMPTY

    counts = frame["_year"].value_counts()
    keep = sorted(int(y) for y, n in counts.items() if n >= MIN_ROWS_PER_YEAR)
    if len(keep) < MIN_YEARS:
        return YearIndex(
            base_year=0,
            note=f"시점 보정 생략 — 거래 {MIN_ROWS_PER_YEAR}건 이상인 연도가 {len(keep)}개 (최소 {MIN_YEARS})",
        )
    frame = frame[frame["_year"].isin(keep)]

    base = int(base_year) if base_year is not None else keep[-1]
    if base not in keep:
        base = keep[-1]

    # 기준연도를 참조 범주로 두고 나머지 연도 더미. 계수가 곧 기준 대비 로그 가격차.
    dummies = pd.get_dummies(frame["_year"].astype(int), prefix="y", dtype=float)
    dummies = dummies.drop(columns=[f"y_{base}"], errors="ignore")
    design = pd.concat([frame[X.columns], dummies], axis=1)
    design = design.loc[:, design.nunique(dropna=False) > 1]
    if design.empty:
        return _EMPTY

    import statsmodels.api as sm

    try:
        model = sm.OLS(np.log(frame["_price"]), sm.add_constant(design)).fit()
    except (ValueError, np.linalg.LinAlgError):
        return YearIndex(base_year=0, note="시점 보정 생략 — 지수 회귀 적합 실패")

    gammas: dict[int, float] = {}
    errors: dict[int, float] = {}
    for y in keep:
        if y == base:
            continue
        name = f"y_{y}"
        if name not in model.params.index:
            continue
        gammas[y] = float(model.params[name])
        errors[y] = float(model.bse.get(name, 0.0))

    shrunk, keep_ratio = _shrink_year_effects(gammas, errors)

    factors: dict[int, float] = {base: 1.0}
    for y, gamma in shrunk.items():
        # 그 해가 기준보다 gamma만큼 낮으면(음수) 환산 배수는 exp(-gamma) > 1.
        f = float(np.exp(-gamma))
        if not np.isfinite(f) or f <= 0 or f > MAX_YEAR_FACTOR or f < 1.0 / MAX_YEAR_FACTOR:
            return YearIndex(
                base_year=0,
                note=f"시점 보정 생략 — {y}년 환산 배수 {f:.2f}가 비현실적",
            )
        factors[y] = round(f, 6)

    if len(factors) < MIN_YEARS:
        return YearIndex(base_year=0, note="시점 보정 생략 — 유효 연도 부족")

    return YearIndex(
        base_year=base,
        factors=factors,
        n_by_year={int(y): int(counts.get(y, 0)) for y in keep},
        shrink_keep_ratio=keep_ratio,
    )


class TimeAdjuster:
    """시군구 표본 하나로 지수를 반복 추정하는 캐시.

    CV는 fold마다 학습 연도 집합이 달라 지수를 다시 추정해야 한다. 지수는 후보 식·척도와
    무관하게 연도 집합만으로 정해지므로, 연도 집합을 키로 캐시하면 후보 31개 × 척도 3개를
    돌려도 지수 회귀는 fold 수만큼만 돈다.
    """

    __slots__ = ("_frame", "_cache", "_max_complete_year")

    def __init__(self, sigungu_df: pd.DataFrame, *, max_complete_year: int | None = None) -> None:
        cols = [
            c
            for c in ("price", "contract_year", *_LOG_COLS, *_LINEAR_COLS)
            if c in sigungu_df.columns
        ]
        self._frame = sigungu_df.loc[:, cols] if cols else sigungu_df.iloc[:0]
        self._max_complete_year = max_complete_year
        self._cache: dict[tuple[int, ...] | None, YearIndex] = {}

    def full(self) -> YearIndex:
        """전 구간 지수 — 기준시점은 창의 마지막 연도. 최종 적합·예측용."""
        return self._get(None)

    def for_train_years(self, years: list[int] | tuple[int, ...]) -> YearIndex:
        """학습 연도만으로 추정한 지수 — 기준시점은 그중 마지막 연도. CV용 (D-075)."""
        key = tuple(sorted(int(y) for y in years))
        if not key:
            return _EMPTY
        return self._get(key)

    def _get(self, key: tuple[int, ...] | None) -> YearIndex:
        if key not in self._cache:
            self._cache[key] = estimate_year_index(
                self._frame,
                years=list(key) if key is not None else None,
                max_complete_year=self._max_complete_year,
            )
        return self._cache[key]


def deflate_prices(df: pd.DataFrame, index: YearIndex) -> pd.DataFrame:
    """`price`를 기준시점 수준으로 환산한 사본. 원본 가격은 `price_nominal`에 남긴다.

    지수가 없으면 사본 없이 원본을 그대로 돌려준다.
    """
    if df.empty or not index.available or "contract_year" not in df.columns:
        return df
    out = df.copy()
    factors = pd.to_numeric(out["contract_year"], errors="coerce").map(index.factor)
    factors = factors.fillna(1.0)
    out["price_nominal"] = pd.to_numeric(out["price"], errors="coerce")
    out["price"] = out["price_nominal"] * factors
    return out
