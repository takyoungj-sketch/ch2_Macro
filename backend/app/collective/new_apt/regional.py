"""대전 vs 충북 M2 복제 + 대전 hold-out 고정 전이 실험.

통합 표본의 평균 MAPE가 좋아졌다고 채택하지 않는다.
채택 판단의 핵심은 동일한 대전 hold-out에서 충북 학습 추가가 대전 예측을 돕는지다.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.collective.new_apt.constants import (
    NEW_AGE_MAX,
    SIDO_CHUNGBUK,
    SIDO_DAEJEON,
    SIDO_NAMES,
    TRANSFER_MAPE_DELTA_PP,
)
from app.collective.new_apt.models import (
    LocationMode,
    fit_spec,
    holdout_buildings,
    land_dispersion,
    prepare_track_a,
)


def transfer_verdict(
    dj_mape: float | None,
    pooled_mape: float | None,
    *,
    threshold: float = TRANSFER_MAPE_DELTA_PP,
) -> dict[str, Any]:
    if dj_mape is None or pooled_mape is None:
        return {
            "code": "unmeasured",
            "delta_mape": None,
            "improves_daejeon": False,
            "adopt_pooled": False,
            "summary": "대전 hold-out MAPE를 측정하지 못해 통합 여부를 판단할 수 없다.",
        }
    delta = round(float(pooled_mape) - float(dj_mape), 2)
    if delta <= -threshold:
        summary = (
            f"충북을 학습에 넣었더니 동일 대전 hold-out MAPE가 {abs(delta):.1f}%p 낮아졌다. "
            "표본만 늘어난 게 아니라 M2 구조가 안정화됐을 가능성이 있다. 그래도 당장 대전 식을 바꾸지는 않는다."
        )
        improves = True
    elif delta >= threshold:
        summary = (
            f"충북을 넣으면 동일 대전 hold-out MAPE가 {delta:.1f}%p 나빠진다. "
            "지역별 가격 형성 구조가 다를 수 있어 통합 채택은 하지 않는다."
        )
        improves = False
    else:
        summary = (
            "대전 hold-out은 거의 같다. 통합 평균이 좋아 보여도 충북 표본 비중·난이도 때문일 수 있어 "
            "그 숫자만으로 채택하지 않는다."
        )
        improves = False
    return {
        "code": "improves" if improves else ("worsens" if delta >= threshold else "similar"),
        "delta_mape": delta,
        "improves_daejeon": improves,
        "adopt_pooled": False,
        "summary": summary,
    }


def _land_split(work: pd.DataFrame, hold_keys: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    land_ok = work["land_p50"].notna()
    train = work[~work["building_key"].astype(str).isin(hold_keys) & land_ok]
    hold = work[
        work["building_key"].astype(str).isin(hold_keys)
        & work["age"].notna()
        & (work["age"] <= NEW_AGE_MAX)
        & land_ok
    ]
    return train, hold


def _pack(
    fitted: dict[str, Any],
    *,
    model_id: str,
    region: str,
    purpose: str,
    location: LocationMode,
    n_train_buildings: int,
    n_hold_buildings: int,
    hold_scope: str,
) -> dict[str, Any]:
    row = dict(fitted)
    row.update(
        {
            "id": model_id,
            "region": region,
            "purpose": purpose,
            "location": location,
            "n_train_buildings": n_train_buildings,
            "n_hold_buildings": n_hold_buildings,
            "hold_scope": hold_scope,
            "is_baseline": model_id == "A",
            "primary_pool": model_id == "C_sido",
        }
    )
    return row


def _sample_counts(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "n_cells": 0,
            "n_buildings": 0,
            "n_land": 0,
            "land_join_pct": 0.0,
            "n_sigungu": 0,
        }
    land = df["land_p50"].notna()
    return {
        "n_cells": int(len(df)),
        "n_buildings": int(df["building_key"].nunique()),
        "n_land": int(land.sum()),
        "land_join_pct": round(float(land.mean() * 100), 1),
        "n_sigungu": int(df["sigungu_code"].nunique()) if "sigungu_code" in df.columns else 0,
        "land_dispersion": land_dispersion(df[land]) if int(land.sum()) else {},
    }


def run_region_compare(dj_df: pd.DataFrame, cb_df: pd.DataFrame) -> dict[str, Any]:
    dj = prepare_track_a(dj_df)
    cb = prepare_track_a(cb_df)
    dj_hold_keys = holdout_buildings(dj)
    cb_hold_keys = holdout_buildings(cb)

    dj_train, dj_hold = _land_split(dj, dj_hold_keys)
    cb_train, cb_hold = _land_split(cb, cb_hold_keys)
    pool_train = pd.concat([dj_train, cb[cb["land_p50"].notna()]], ignore_index=True)

    a = fit_spec(dj_train, dj_hold, product="M2", location="land", track="region")
    b = fit_spec(cb_train, cb_hold, product="M2", location="land", track="region")
    c_naive = fit_spec(pool_train, dj_hold, product="M2", location="land", track="region")
    c_sido = fit_spec(pool_train, dj_hold, product="M2", location="sido_fe_land", track="region")
    c_gu = fit_spec(pool_train, dj_hold, product="M2", location="gu_fe_land", track="region")

    pool = pd.concat([dj, cb], ignore_index=True)
    own_keys = holdout_buildings(pool)
    own_train, own_hold = _land_split(pool, own_keys)
    c_own = fit_spec(own_train, own_hold, product="M2", location="sido_fe_land", track="region")

    models = [
        _pack(
            a,
            model_id="A",
            region="대전",
            purpose="현재 잠정 기준",
            location="land",
            n_train_buildings=int(dj_train["building_key"].nunique()) if not dj_train.empty else 0,
            n_hold_buildings=int(dj_hold["building_key"].nunique()) if not dj_hold.empty else 0,
            hold_scope="대전 hold-out",
        ),
        _pack(
            b,
            model_id="B",
            region="충북",
            purpose="외부 지역에서 구조 확인",
            location="land",
            n_train_buildings=int(cb_train["building_key"].nunique()) if not cb_train.empty else 0,
            n_hold_buildings=int(cb_hold["building_key"].nunique()) if not cb_hold.empty else 0,
            hold_scope="충북 hold-out",
        ),
        _pack(
            c_naive,
            model_id="C_naive",
            region="대전+충북",
            purpose="지역 FE 없이 섞기 (비교용, 채택 금지)",
            location="land",
            n_train_buildings=int(pool_train["building_key"].nunique()) if not pool_train.empty else 0,
            n_hold_buildings=int(dj_hold["building_key"].nunique()) if not dj_hold.empty else 0,
            hold_scope="동일 대전 hold-out",
        ),
        _pack(
            c_sido,
            model_id="C_sido",
            region="대전+충북",
            purpose="표본 확대 + 광역 지역 효과",
            location="sido_fe_land",
            n_train_buildings=int(pool_train["building_key"].nunique()) if not pool_train.empty else 0,
            n_hold_buildings=int(dj_hold["building_key"].nunique()) if not dj_hold.empty else 0,
            hold_scope="동일 대전 hold-out",
        ),
        _pack(
            c_gu,
            model_id="C_gu",
            region="대전+충북",
            purpose="표본 확대 + 시군구 지역 효과",
            location="gu_fe_land",
            n_train_buildings=int(pool_train["building_key"].nunique()) if not pool_train.empty else 0,
            n_hold_buildings=int(dj_hold["building_key"].nunique()) if not dj_hold.empty else 0,
            hold_scope="동일 대전 hold-out",
        ),
    ]

    verdict = transfer_verdict(a.get("holdout_mape"), c_sido.get("holdout_mape"))
    transfer_rows = [
        {
            "model_id": "A",
            "train": "대전",
            "test": "대전 hold-out",
            "mape": a.get("holdout_mape"),
            "mae": a.get("holdout_mae"),
            "n_hold": a.get("n_holdout"),
        },
        {
            "model_id": "C_sido",
            "train": "대전+충북 (광역FE)",
            "test": "동일 대전 hold-out",
            "mape": c_sido.get("holdout_mape"),
            "mae": c_sido.get("holdout_mae"),
            "n_hold": c_sido.get("n_holdout"),
        },
        {
            "model_id": "C_gu",
            "train": "대전+충북 (시군구FE)",
            "test": "동일 대전 hold-out",
            "mape": c_gu.get("holdout_mape"),
            "mae": c_gu.get("holdout_mae"),
            "n_hold": c_gu.get("n_holdout"),
        },
        {
            "model_id": "C_naive",
            "train": "대전+충북 (지역FE 없음)",
            "test": "동일 대전 hold-out",
            "mape": c_naive.get("holdout_mape"),
            "mae": c_naive.get("holdout_mae"),
            "n_hold": c_naive.get("n_holdout"),
        },
    ]

    return {
        "baseline": "M2",
        "baseline_status": "daejeon_provisional",
        "baseline_role": "대전 M2는 잠정 기준식이다. 충북 복제·전이 실험 전에는 최종으로 확정하지 않는다.",
        "adopt_pooled": False,
        "samples": {
            "daejeon": {"sido_code": SIDO_DAEJEON, "sido_name": SIDO_NAMES[SIDO_DAEJEON], **_sample_counts(dj)},
            "chungbuk": {"sido_code": SIDO_CHUNGBUK, "sido_name": SIDO_NAMES[SIDO_CHUNGBUK], **_sample_counts(cb)},
        },
        "models": models,
        "transfer": {
            "holdout": "daejeon_frozen",
            "n_hold_buildings": int(dj_hold["building_key"].nunique()) if not dj_hold.empty else 0,
            "n_hold_cells": int(len(dj_hold)),
            "rows": transfer_rows,
            "verdict": verdict,
            "misleading_overall": {
                "label": "통합 표본 자체 hold-out (채택 기준 아님)",
                "mape": c_own.get("holdout_mape"),
                "mae": c_own.get("holdout_mae"),
                "n_hold": c_own.get("n_holdout"),
                "n_hold_buildings": int(own_hold["building_key"].nunique()) if not own_hold.empty else 0,
                "note": "충북 데이터가 많거나 쉬운 표본이면 평균만 좋아질 수 있다. 대전 고정 테스트와 따로 본다.",
            },
        },
        "next_steps": [
            "시공사군(M3)은 충북까지 연 뒤에 본다. 대전만의 시공사 신호는 아직 확정하지 않는다.",
            "M4는 넣지 않는다.",
            "신축 대단지 hold-out 개선은 지역 비교 다음 단계다.",
        ],
        "notes": [
            "A·B는 같은 M2(연도+토지+세대수+최고층+주차+vintage)다.",
            "C는 대전과 충북을 섞되, 본선은 광역(시도) 효과를 통제한다. 시군구 FE는 비교용이다.",
            "전이 실험의 테스트 단지는 대전 hold-out과 동일하다. 충북 학습 추가가 대전 예측을 돕는지가 핵심이다.",
            "통합 평균 MAPE가 낮아졌다고 대전 식을 바꾸지 않는다.",
        ],
    }
