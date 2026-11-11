"""회귀 설계행렬 식별성 공통 함수 (복합 B-12 → 집합 C-03 공용).

복합 `app/built/regression/engine.py` 에 있던 p×p SVD 버전을 그대로 옮겼다.
복합 엔진은 같은 이름으로 다시 내보내므로 동작·테스트는 바뀌지 않는다.
"""

from __future__ import annotations

import numpy as np


def _scaled_design_svd(exog: np.ndarray) -> tuple[int, np.ndarray] | None:
    """열 노름으로 정규화한 설계행렬의 rank와 우특이벡터(p×p) — 거래 수 n과 무관한 메모리.

    n ≥ p 이면 ``full_matrices=False`` 로 U를 n×p만 만든다(n×n 금지 — 2만 건이면 3.2GB).
    n < p 이면 영공간이 p−n 차원 이상이라 완전한 p×p Vᵀ가 필요하므로
    ``full_matrices=True`` 로 두되, 이때 U는 n×n(n < p)이라 작다.
    rank 허용오차는 ``np.linalg.matrix_rank`` 기본값(S.max · max(n, p) · eps)과 같다.
    """
    arr = np.asarray(exog, dtype=float)
    if arr.ndim != 2 or arr.shape[1] == 0 or arr.shape[0] == 0:
        return None
    n, p = arr.shape
    norms = np.linalg.norm(arr, axis=0)
    norms[norms == 0.0] = 1.0
    scaled = arr / norms
    _u, s, vt = np.linalg.svd(scaled, full_matrices=n < p)
    tol = (s.max() if s.size else 0.0) * max(n, p) * np.finfo(float).eps
    rank = int((s > tol).sum())
    return rank, vt


def design_rank(exog: np.ndarray) -> int:
    """정규화 설계행렬 rank. 전체 적합·CV fold가 같은 허용오차를 쓰게 한 곳에 둔다 (B-12)."""
    out = _scaled_design_svd(exog)
    return 0 if out is None else out[0]


def nonidentifiable_columns(exog: np.ndarray, names: list[str]) -> list[str]:
    """rank 부족 설계에서 한 값으로 정해지지 않는 계수 이름 (B-12).

    열 노름으로 정규화한 설계행렬의 영공간 벡터에 성분이 있는 열이 식별 불가다.
    rank가 꽉 차면 빈 목록. 예측값(열 공간)은 이와 무관하게 계산된다.
    계산은 p×p 우특이벡터만 쓰므로 메모리가 거래 수와 무관하다(코덱스 검수 P1).
    """
    out = _scaled_design_svd(exog)
    if out is None:
        return []
    rank, vt = out
    if rank >= vt.shape[1]:
        return []
    null = vt[rank:]
    weight = np.abs(null).max(axis=0)
    return [names[j] for j in range(len(names)) if weight[j] > 1e-6]


def lstsq_r_squared(y: np.ndarray, exog: np.ndarray) -> float | None:
    """최소노름 최소제곱 해의 R²(상수항 포함 설계 가정, 중심화 SST). 식별 불가 설계에도 정의된다."""
    yv = np.asarray(y, dtype=float)
    a = np.asarray(exog, dtype=float)
    if a.ndim != 2 or a.shape[0] == 0 or a.shape[0] != yv.shape[0]:
        return None
    coef, *_ = np.linalg.lstsq(a, yv, rcond=None)
    resid = yv - a @ coef
    sst = float(((yv - yv.mean()) ** 2).sum())
    if sst <= 0:
        return None
    return 1.0 - float((resid**2).sum()) / sst
