"""Recommend stage2 Twin neighbor validation — suggest 경로와 공유.

Twin은 지역 구조 후보이다. 거래가격으로 고르지 않는다.
채택 권고는 탐색 CV가 아니라 확인 CV + 계수 안정이다.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.built.regression.candidates import (
    CandidateContext,
    LocalCandidateProvider,
    ProfileTwinCandidateProvider,
    generate_candidates,
    region_counts_from_db,
)
from app.built.regression.candidates.profile_adapter import normalize_profile_twin_neighbors
from app.built.regression.selection.blocks import BlockId
from app.built.schemas import (
    RecommendationPoolCandidate,
    RegressionSelectionRequest,
    TwinGateResult,
    TwinValidationVerdict,
)

# Midcheck / TWIN_VALIDATION_STATUS §2 — 운영 재보정 전 초안
TWIN_VALIDATION_EPSILON_PP = 0.5

_LABEL_KO = {
    "improved": "개선",
    "tie": "동등",
    "worse": "악화",
    "skipped": "검증 생략",
}


@dataclass(frozen=True)
class ValidatedTwinNeighbors:
    neighbors: list[dict[str, object]]
    twin_codes: tuple[str, ...]
    rejected_n: int
    gate_summary: str | None = None


def _anchor_codes(req: RegressionSelectionRequest, admin_level: str, df) -> tuple[str, ...]:
    codes = tuple(c for c in (req.region_codes or []) if str(c).strip())
    if codes:
        return codes
    code_column = {
        "sigungu": "sigungu_code",
        "gu": "sigungu_code",
        "eupmyeondong": "eupmyeondong_code",
        "beopjungri": "beopjungri_code",
    }.get(admin_level)
    if code_column and code_column in df.columns:
        return tuple(str(c).strip() for c in df[code_column].dropna().unique() if str(c).strip())
    return ()


def build_twin_validation_verdict(
    *,
    ran: bool,
    skipped_reason: str | None,
    local_cv_mape: float | None,
    decision: str,
    primary: RecommendationPoolCandidate | None,
    pools: list[RecommendationPoolCandidate],
    epsilon_pp: float = TWIN_VALIDATION_EPSILON_PP,
    prefix=None,
) -> TwinValidationVerdict:
    """탐색/확인 분리 판정. prefix가 있으면 그것을 SSOT로 쓴다."""
    if prefix is not None:
        band = float(getattr(prefix, "practical_band_pp", epsilon_pp) or epsilon_pp)
        adopt = bool(prefix.adopt_recommended)
        search_band = prefix.search_band
        if not ran:
            verdict = "skipped"
        elif search_band == "improved" and adopt:
            verdict = "improved"
        elif search_band == "worse":
            verdict = "worse"
        else:
            verdict = "tie"
        compared = None
        if search_band == "improved":
            compared = min(
                (s for s in prefix.steps if s.prefix_k > 0 and s.search_cv_mape is not None),
                key=lambda s: s.search_cv_mape or 1e9,
                default=None,
            )
        local_step = prefix.steps[0] if prefix.steps else None
        return TwinValidationVerdict(
            verdict=verdict,
            label_ko=_LABEL_KO[verdict],
            summary_ko=prefix.decision_reason,
            epsilon_pp=band,
            practical_band_pp=band,
            local_cv_mape=local_step.search_cv_mape if local_step else local_cv_mape,
            compared_cv_mape=compared.search_cv_mape if compared else None,
            cv_mape_delta=compared.search_cv_delta if compared else None,
            local_confirm_cv_mape=local_step.confirm_cv_mape if local_step else None,
            compared_confirm_cv_mape=compared.confirm_cv_mape if compared else None,
            compared_candidate_id=compared.step_id if compared else None,
            twin_adopt_recommended=adopt,
            confirm_skipped_reason=prefix.confirm_skipped_reason,
        )

    if not ran:
        reason = (skipped_reason or "Twin pool 검증을 실행하지 않았습니다.").strip()
        return TwinValidationVerdict(
            verdict="skipped",
            label_ko=_LABEL_KO["skipped"],
            summary_ko=reason,
            epsilon_pp=epsilon_pp,
            practical_band_pp=epsilon_pp,
            local_cv_mape=local_cv_mape,
            twin_adopt_recommended=False,
        )

    compared: RecommendationPoolCandidate | None = None
    if decision != "local" and primary is not None and primary.cv_mape is not None:
        compared = primary
    else:
        scored = [p for p in pools if p.cv_mape is not None]
        if scored:
            compared = min(scored, key=lambda p: float(p.cv_mape))  # type: ignore[arg-type]

    if local_cv_mape is None or compared is None or compared.cv_mape is None:
        return TwinValidationVerdict(
            verdict="skipped",
            label_ko=_LABEL_KO["skipped"],
            summary_ko="Local·Twin CV-MAPE를 비교할 수 없어 판정을 생략합니다.",
            epsilon_pp=epsilon_pp,
            local_cv_mape=local_cv_mape,
            compared_cv_mape=compared.cv_mape if compared else None,
            compared_candidate_id=compared.candidate_id if compared else None,
            twin_adopt_recommended=False,
        )

    delta = round(float(local_cv_mape) - float(compared.cv_mape), 2)
    if delta >= epsilon_pp:
        verdict = "improved"
        summary = (
            f"Local CV-MAPE {local_cv_mape:.2f}% → Twin {compared.cv_mape:.2f}% "
            f"(Δ {delta:+.2f}%p ≥ ε {epsilon_pp}%p). Twin 채택을 권고합니다."
        )
    elif delta <= -epsilon_pp:
        verdict = "worse"
        summary = (
            f"Twin CV-MAPE {compared.cv_mape:.2f}%가 Local {local_cv_mape:.2f}%보다 "
            f"나쁨(Δ {delta:+.2f}%p). Local 유지를 권고합니다."
        )
    else:
        verdict = "tie"
        summary = (
            f"Local {local_cv_mape:.2f}%와 Twin {compared.cv_mape:.2f}% 차이가 "
            f"ε({epsilon_pp}%p) 미만(Δ {delta:+.2f}%p). Twin 미채택을 권고합니다."
        )

    return TwinValidationVerdict(
        verdict=verdict,
        label_ko=_LABEL_KO[verdict],
        summary_ko=summary,
        epsilon_pp=epsilon_pp,
        local_cv_mape=round(float(local_cv_mape), 2),
        compared_cv_mape=round(float(compared.cv_mape), 2),
        cv_mape_delta=delta,
        compared_candidate_id=compared.candidate_id,
        twin_adopt_recommended=verdict == "improved",
    )


def validate_recommend_twin_neighbors(
    conn,
    *,
    req: RegressionSelectionRequest,
    admin_level: str,
    search_pool: list[BlockId],
    anchor_df,
) -> ValidatedTwinNeighbors:
    """Profile Twin neighbors를 normalize + Candidate validation으로 필터한다."""
    raw = req.profile_twin_neighbors or []
    if not raw:
        return ValidatedTwinNeighbors(neighbors=[], twin_codes=(), rejected_n=0)

    normalized: list[dict[str, object]] = []
    for row in raw:
        if row.get("region_code") or row.get("twin_region_code"):
            normalized.append(dict(row))
        else:
            payload = {
                "algorithm_version": 21,
                "profile_version": req.profile_version,
                "window_years": req.profile_window_years,
                "neighbors": [row],
            }
            normalized.extend(normalize_profile_twin_neighbors(payload, admin_level=admin_level))

    if not normalized:
        return ValidatedTwinNeighbors(
            neighbors=[],
            twin_codes=(),
            rejected_n=len(raw),
            gate_summary="Profile Twin(algo 21) 형식이 아니어서 제외되었습니다.",
        )

    anchor_codes = _anchor_codes(req, admin_level, anchor_df)
    context = CandidateContext(
        admin_level=admin_level,
        anchor_region_codes=anchor_codes,
        profile_version=req.profile_version,
        profile_as_of_month=req.profile_as_of_month,
        profile_window_years=req.profile_window_years,
    )
    providers = [
        LocalCandidateProvider(search_pool),
        ProfileTwinCandidateProvider(normalized, search_pool),
    ]
    all_region_codes: set[str] = set(anchor_codes)
    for provider in providers:
        for spec in provider.generate(context):
            all_region_codes.update(spec.region_codes)

    region_counts = region_counts_from_db(
        conn,
        admin_level=admin_level,
        region_codes=tuple(all_region_codes),
        asset_type=req.asset_type,
        contract_year_from=req.contract_year_from,
        contract_year_to=req.contract_year_to,
        as_of_month=req.as_of_month,
        window_years=req.window_years,
    )
    result = generate_candidates(providers, context=context, region_counts=region_counts)
    accepted_twin_codes: set[str] = set()
    for spec in result.accepted:
        if spec.provider_id == "profile_twin":
            accepted_twin_codes.update(spec.region_codes)
    accepted_twin_codes.difference_update(anchor_codes)

    filtered: list[dict[str, object]] = []
    for row in normalized:
        code = str(row.get("region_code") or row.get("twin_region_code") or "").strip()
        if code in accepted_twin_codes:
            filtered.append(row)

    rejected = max(0, len(normalized) - len(filtered))
    summary = None
    if rejected:
        summary = f"Twin 후보 {len(normalized)}개 중 {rejected}개는 표본·계약 검증에서 제외"
    twin_codes = tuple(
        str(row.get("region_code") or row.get("twin_region_code") or "").strip()
        for row in filtered
        if str(row.get("region_code") or row.get("twin_region_code") or "").strip()
    )
    from app.recommendation.twin_structure import rank_neighbors_by_structure

    ranked = rank_neighbors_by_structure(filtered, top_k=5)
    ranked_codes = tuple(
        str(row.get("region_code") or "").strip()
        for row in ranked
        if str(row.get("region_code") or "").strip()
    )
    return ValidatedTwinNeighbors(
        neighbors=ranked,
        twin_codes=ranked_codes,
        rejected_n=rejected,
        gate_summary=summary,
    )


def hard_gate_summary(gates: list[TwinGateResult]) -> str | None:
    rejected = [g for g in gates if not g.accepted]
    if not rejected:
        return None
    return f"인접 기준으로 Twin {len(rejected)}곳 제외"
