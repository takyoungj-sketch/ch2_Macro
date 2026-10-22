"""회귀 결측 공통 규칙.

원본 행은 지우지 않는다. 빈칸 처리는 식을 맞출 때만 적용하고, 꺼 둔 변수는 표본을 줄이지 않는다.
숫자는 그 변수를 켠 식에서 빼고, 범주 빈칸은 미상으로 둔다. 미상은 기준 범주가 아니다.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

UNKNOWN = "미상"
CategoricalMissing = Literal["keep_unknown", "drop"]

_BLANK = {"", "nan", "none", "null", "(null)", "(미상)", "미상"}


def normalize_categories(series: pd.Series) -> pd.Series:
    def one(value: object) -> str:
        try:
            if pd.isna(value):
                return UNKNOWN
        except TypeError:
            pass
        text = str(value).strip()
        if text.lower() in _BLANK or text in {"미상", "(미상)", "(null)"}:
            return UNKNOWN
        return text

    return series.map(one)


def pick_reference(series: pd.Series) -> str | None:
    """가장 많은 실제 범주. 동점이면 이름순. 미상만 있으면 None."""
    if series.empty:
        return None
    counts = series.astype(str).value_counts()
    real = counts[counts.index != UNKNOWN]
    if real.empty:
        return None
    top = int(real.max())
    tied = sorted(str(value) for value in real[real == top].index)
    return tied[0]


def categorical_dummies(
    series: pd.Series,
    prefix: str,
    *,
    reference: str | None = None,
) -> tuple[pd.DataFrame, list[str], str | None]:
    """미상을 포함한 더미. 기준 범주 열은 만들지 않는다."""
    normalized = normalize_categories(series)
    levels = sorted(set(normalized.astype(str).unique()))
    if reference == UNKNOWN:
        reference = None
    ref = pick_reference(normalized) if reference is None else reference
    if ref is None or len(levels) < 2:
        return pd.DataFrame(index=normalized.index), levels, ref
    columns: dict[str, pd.Series] = {}
    for level in levels:
        if level == ref:
            continue
        name = f"{prefix}_{level}" if prefix else level
        columns[name] = (normalized == level).astype(float)
    frame = pd.DataFrame(columns, index=normalized.index) if columns else pd.DataFrame(index=normalized.index)
    return frame, levels, ref


def drop_unknown_rows(frame: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, int]:
    """켜진 범주 열에 미상이 있는 행만 뺀다."""
    if frame.empty or not columns:
        return frame, 0
    keep = pd.Series(True, index=frame.index)
    for column in columns:
        if column not in frame.columns:
            continue
        keep &= normalize_categories(frame[column]) != UNKNOWN
    excluded = int((~keep).sum())
    return frame.loc[keep].copy(), excluded


RARE_UNKNOWN_N = 5


def rare_unknown_warning(
    frame: pd.DataFrame,
    columns: list[tuple[str, str]],
    *,
    unit: str = "건",
) -> str | None:
    """미상 범주를 유지했는데 건수가 적으면 그 계수가 흔들릴 수 있다."""
    bits: list[str] = []
    for column, label in columns:
        if column not in frame.columns:
            continue
        n = int((normalize_categories(frame[column]) == UNKNOWN).sum())
        if 0 < n < RARE_UNKNOWN_N:
            bits.append(f"{label} {n}{unit}")
    if not bits:
        return None
    return "미상 범주가 적습니다 (" + ", ".join(bits) + "). 그 계수는 불안정할 수 있습니다."


def treatment_label(mode: str, excluded: int, *, unit: str = "거래") -> str:
    if mode == "drop":
        if unit == "단지":
            return f"범주 결측 단지 {excluded}곳 제외"
        return f"범주 결측 거래 {excluded}건 제외"
    return "범주 결측은 미상 범주로 유지. 미상은 기준 범주가 아님"
