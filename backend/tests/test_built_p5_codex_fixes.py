"""복합 점검 5단계 (2026-11-11 코덱스 검수 보완) — B-12 메모리 · 배포 범위 · T-2 공통 0건.

1. nonidentifiable_columns 가 n×n U 행렬을 만들지 않는다 (2만 거래 ≈ 3.2GB 방지).
   결과(식별 불가 열 목록)는 기존 full SVD 구현과 같다. CV fold rank 판정도 같은 함수.
2. built 배포 범위가 import 하는 공통 지역 모듈을 포함한다.
3. Local·Twin 공통 내 지역 거래가 0건이면 전체 Twin 거래로 채점하지 않고 「계산 불가」.
"""

from __future__ import annotations

import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.built.regression.engine import design_rank, nonidentifiable_columns

REPO = Path(__file__).resolve().parents[2]


# ── 1. B-12 식별 불가 검사 메모리 ────────────────────────────────────────────


def _reference_nonidentifiable(exog: np.ndarray, names: list[str]) -> list[str]:
    """4단계까지의 구현 (full_matrices=True). 결과 동일성 비교용 — 작은 n에서만 쓴다."""
    arr = np.asarray(exog, dtype=float)
    norms = np.linalg.norm(arr, axis=0)
    norms[norms == 0.0] = 1.0
    scaled = arr / norms
    rank = int(np.linalg.matrix_rank(scaled))
    if rank >= arr.shape[1]:
        return []
    _u, _s, vt = np.linalg.svd(scaled, full_matrices=True)
    weight = np.abs(vt[rank:]).max(axis=0)
    return [names[j] for j in range(len(names)) if weight[j] > 1e-6]


def _designs():
    rng = np.random.default_rng(11)
    out = []
    # (a) 꽉 찬 rank
    x = np.column_stack([np.ones(200), rng.uniform(10, 500, 200), rng.integers(0, 2, 200)])
    out.append((x, ["const", "gross_area", "zone_a"]))
    # (b) 더미 합 = 상수 (함정)
    d1 = rng.integers(0, 2, 300).astype(float)
    x = np.column_stack([np.ones(300), rng.uniform(10, 500, 300), d1, 1 - d1, rng.normal(size=300)])
    out.append((x, ["const", "gross_area", "use_a", "use_b", "age"]))
    # (c) 연속 변수 선형결합 + 척도 차이 큼
    g = rng.uniform(100, 5000, 250)
    la = rng.uniform(50, 900, 250)
    x = np.column_stack([np.ones(250), g, la, 2 * g - 3 * la, rng.integers(0, 2, 250)])
    out.append((x, ["const", "gross_area", "land_area", "combo", "road_a"]))
    # (d) n < p (영공간이 p−n 차원 이상)
    x = rng.normal(size=(6, 9))
    out.append((x, [f"c{i}" for i in range(9)]))
    # (e) 전부 0 열
    x = np.column_stack([np.ones(100), rng.normal(size=100), np.zeros(100)])
    out.append((x, ["const", "a", "struct_zero"]))
    return out


@pytest.mark.parametrize("idx", range(5))
def test_nonidentifiable_matches_reference(idx):
    exog, names = _designs()[idx]
    assert nonidentifiable_columns(exog, names) == _reference_nonidentifiable(exog, names)
    assert design_rank(exog) == int(np.linalg.matrix_rank(exog / np.where(
        np.linalg.norm(exog, axis=0) == 0, 1.0, np.linalg.norm(exog, axis=0))))


def test_nonidentifiable_large_design_memory_and_time():
    """20,000×30 설계 — 이전 구현은 U(20,000²·8B ≈ 3.2GB)를 만들었다."""
    rng = np.random.default_rng(5)
    n, p = 20_000, 30
    x = np.column_stack([np.ones(n), rng.normal(size=(n, p - 2))])
    x = np.column_stack([x, x[:, 1] + 2 * x[:, 2]])  # 마지막 열 = 공선 → 식별 불가 3개
    names = ["const", *[f"x{i}" for i in range(1, p - 1)], "combo"]
    tracemalloc.start()
    t0 = time.perf_counter()
    bad = nonidentifiable_columns(x, names)
    elapsed = time.perf_counter() - t0
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert bad == ["x1", "x2", "combo"]
    assert peak < 64 * 1024 * 1024, f"peak {peak / 1e6:.1f}MB"  # X 자체 4.8MB 수준, n×n이면 3.2GB
    assert elapsed < 10.0, f"{elapsed:.2f}s"
    assert design_rank(x) == p - 1


def test_cv_fold_uses_same_rank_helper(monkeypatch):
    """CV fold 열 정리(_estimable_columns)도 같은 design_rank 를 쓴다."""
    import app.built.regression.engine as engine
    from app.built.regression.selection import fit

    calls = []
    real = engine.design_rank

    def spy(m):
        calls.append(np.asarray(m).shape)
        return real(m)

    monkeypatch.setattr(engine, "design_rank", spy)
    fn = fit._estimable_columns
    rng = np.random.default_rng(1)
    d = rng.integers(0, 2, 50).astype(float)
    x_train = pd.DataFrame({"const": 1.0, "gross_area": rng.uniform(1, 9, 50), "use_a": d, "use_b": 1 - d})
    assert fn(x_train) == []  # 더미 함정 → fold 건너뜀
    assert calls, "fold rank 판정이 design_rank 를 거치지 않았다"


# ── 2. built 배포 범위 ───────────────────────────────────────────────────────


def _built_covered() -> list[str]:
    text = (REPO / "deploy/scripts/deploy-from-windows.ps1").read_text(encoding="utf-8")
    block = text.split("$BuiltBackendAppPaths = @(", 1)[1].split(")", 1)[0]
    paths = [p.strip().strip('"') for p in block.replace("\n", ",").split(",") if p.strip().strip('"')]
    return [*paths, "backend/app/collective/schemas.py", "pipeline/region_canonical.py"]


def test_built_deploy_includes_region_modules():
    covered = _built_covered()
    for rel in ("backend/app/region_sido.py", "backend/app/region_canonical.py", "backend/app/region_scope.py"):
        assert rel in covered
    text = (REPO / "deploy/scripts/deploy-from-windows.ps1").read_text(encoding="utf-8")
    assert 'Invoke-Scp @("pipeline/region_canonical.py") "pipeline/"' in text
    assert "Invoke-RemoteImportCheck" in text and "import app.main" in text


def test_built_closure_has_no_changed_region_module_outside_scope():
    out = subprocess.run(
        [sys.executable, "-W", "ignore", str(REPO / "deploy/scripts/deploy_import_closure.py"),
         "--covered", *_built_covered(),
         "--start", "backend/app/built", "backend/app/recommendation", "backend/app/map", "backend/app/ai"],
        capture_output=True, text=True, cwd=REPO, check=True,
    ).stdout.split()
    assert not [p for p in out if p.endswith(("region_sido.py", "region_scope.py", "region_canonical.py"))]
    # 범위를 빼면 다시 잡힌다 (점검기가 실제로 동작)
    bare = subprocess.run(
        [sys.executable, "-W", "ignore", str(REPO / "deploy/scripts/deploy_import_closure.py"),
         "--covered", "backend/app/built", "--start", "backend/app/built"],
        capture_output=True, text=True, cwd=REPO, check=True,
    ).stdout.split()
    assert "backend/app/region_sido.py" in bare


# ── 3. T-2 공통 채점 거래 0건 ────────────────────────────────────────────────


def _ctx(df):
    from app.built.regression.selection.context import SelectionContext

    return SelectionContext(df=df, scope_label="x", admin_level="eupmyeondong", addr4_city=False,
                            mode="addr4", unified=False)


def _rows(ids, rng, years=(2021, 2022, 2023, 2024)):
    rows = []
    for k, i in enumerate(ids):
        gross = 50 + float(rng.uniform(0, 200))
        rows.append({"transaction_id": i, "price": 300 + 9 * gross + float(rng.normal(0, 40)),
                     "gross_area": gross, "contract_year": years[k % len(years)]})
    return pd.DataFrame(rows)


def _metrics():
    from app.built.schemas import PoolingCandidateMetrics

    return PoolingCandidateMetrics(candidate_id="twin_prefix_k1", label="Local + 1곳", n=200,
                                   blocks=["gross_area"], response_scale="linear")


def test_zero_common_anchor_trades_is_unavailable_not_full_twin(monkeypatch):
    """코덱스 재현: Twin 표본에 내 지역 거래가 하나도 남지 않으면(공통 0건) 예전에는
    Twin 거래 전체로 채점해 Local과 다른 거래를 비교했다. 이제 탐색·확인 CV 모두 계산 불가."""
    from app.built.regression.selection import pooling

    rng = np.random.default_rng(7)
    local = _rows(range(0, 80), rng)
    pooled = _rows(range(1000, 1200), rng)  # 공통 id 0건
    called = []
    real = pooling._cv_phases
    monkeypatch.setattr(pooling, "_cv_phases", lambda *a, **k: called.append(k.get("score_ids")) or real(*a, **k))
    m = pooling._attach_paired_anchor_cv(
        _metrics(), local_ctx=_ctx(local), local_fit=SimpleNamespace(blocks=["gross_area"], response_scale="linear"),
        local_region_col=None, pooled_ctx=_ctx(pooled), twin_region_col=None,
    )
    assert called == []  # 전체 Twin 거래 채점(fallback) 없음
    assert m.cv_mape is None and m.confirm_cv_mape is None
    assert m.search_eval_n == 0 and m.confirm_eval_n == 0
    assert m.scored_on == "anchor_common"
    assert m.paired_local_cv_mape is None and m.paired_local_confirm_cv_mape is None

    # 판정은 T-1·T-5 보류 경로
    from app.recommendation.twin_structure import decide_twin_prefix

    row = {"candidate_id": m.candidate_id, "label": m.label, "prefix_k": 1, "n": m.n, "blocks": ["gross_area"],
           "scored_on": m.scored_on, "search_cv_mape": m.cv_mape, "confirm_cv_mape": m.confirm_cv_mape,
           "search_eval_n": m.search_eval_n, "confirm_eval_n": m.confirm_eval_n,
           "local_search_cv_mape": m.paired_local_cv_mape, "local_confirm_cv_mape": m.paired_local_confirm_cv_mape,
           "local_search_eval_n": m.paired_local_search_eval_n, "local_confirm_eval_n": m.paired_local_confirm_eval_n,
           "key_coefficients": {}}
    d = decide_twin_prefix(local_n=80, local_search_cv=None, local_confirm_cv=None, local_coeffs={},
                           local_blocks=["gross_area"], prefixes=[row])
    assert d.search_band == "unavailable" and d.judgment_basis == "none" and d.decision == "local"


def test_nonzero_common_still_scores_on_common_trades():
    from app.built.regression.selection import pooling

    rng = np.random.default_rng(8)
    local = _rows(range(0, 80), rng)
    pooled = pd.concat([local, _rows(range(1000, 1200), rng)], ignore_index=True)
    m = pooling._attach_paired_anchor_cv(
        _metrics(), local_ctx=_ctx(local), local_fit=SimpleNamespace(blocks=["gross_area"], response_scale="linear"),
        local_region_col=None, pooled_ctx=_ctx(pooled), twin_region_col=None,
    )
    assert m.scored_on == "anchor_common"
    assert m.search_eval_n and m.search_eval_n == m.paired_local_search_eval_n
    assert m.search_eval_n <= 80


def test_anchor_common_ids_distinguishes_missing_column_from_empty():
    from app.built.regression.selection.pooling import _anchor_common_ids

    a = pd.DataFrame({"transaction_id": [1, 2]})
    assert _anchor_common_ids(a, pd.DataFrame({"transaction_id": [3]})) == set()
    assert _anchor_common_ids(a, pd.DataFrame({"x": [1]})) is None
    assert _anchor_common_ids(a, a) == {1, 2}
