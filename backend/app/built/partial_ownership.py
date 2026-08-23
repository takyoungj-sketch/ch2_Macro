"""복합 지분거래 필터 (D-049).

목록 WHERE에는 넣지 않는다. 회귀·예측·Twin 단가 게이트에만 쓴다.
기본은 제외(include_partial=False).
"""

from __future__ import annotations


def apply_partial_ownership_filter(
    clauses: list[str],
    *,
    include_partial: bool,
) -> None:
    if not include_partial:
        clauses.append("is_partial_ownership IS NOT TRUE")


def format_partial_n_note(*, include_partial: bool, partial_tx_count: int) -> str:
    n = int(partial_tx_count or 0)
    verb = "포함" if include_partial else "제외"
    return f"지분 {n:,}건 {verb}"
