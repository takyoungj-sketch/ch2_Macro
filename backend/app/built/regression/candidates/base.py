"""후보모형 Provider 공통 계약.

Provider는 지역 후보를 제안하고 메타데이터를 반환한다.
적합·순위·최종 채택은 Regression/Evaluation Engine의 책임이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class CandidateContext:
    """후보 생성에 필요한 고정 입력."""

    admin_level: str
    anchor_region_codes: tuple[str, ...] = ()
    profile_version: str | None = None
    profile_as_of_month: str | None = None
    profile_window_years: int | None = None


@dataclass(frozen=True)
class CandidateSpec:
    """Candidate Factory가 Evaluation Engine에 넘기는 후보 정의."""

    candidate_id: str
    provider_id: str
    region_codes: tuple[str, ...]
    variables: tuple[str, ...]
    model_family: str = "ols"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateValidation:
    """후보 생성 직후의 데이터·계약 검증 결과."""

    candidate_id: str
    accepted: bool
    checks: dict[str, bool] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class CandidateProvider(Protocol):
    """Local/Twin/RegionGroup/Province 등의 후보 생성 인터페이스."""

    provider_id: str

    def generate(self, context: CandidateContext) -> list[CandidateSpec]:
        """후보를 제안한다. 회귀 적합은 수행하지 않는다."""
        ...


def validate_candidate(
    candidate: CandidateSpec,
    *,
    context: CandidateContext,
    region_counts: dict[str, int],
    min_region_n: int = 5,
) -> CandidateValidation:
    """후보를 Pooling 전에 검증한다.

    이 함수는 가격 종속변수나 회귀 성능을 사용하지 않는다.
    따라서 후보 생성 단계에서 target leakage가 발생하지 않는다.
    """

    checks: dict[str, bool] = {
        "same_admin_level": candidate.metadata.get("admin_level") == context.admin_level,
        "has_regions": bool(candidate.region_codes),
        "profile_snapshot": True,
        "region_coverage": True,
    }
    reasons: list[str] = []
    warnings: list[str] = []

    if not checks["has_regions"]:
        reasons.append("후보 지역이 없습니다.")
    if not checks["same_admin_level"]:
        reasons.append("후보와 앵커의 행정레벨이 다릅니다.")
    if candidate.provider_id != "local" and not context.profile_version:
        checks["profile_snapshot"] = False
        reasons.append("Profile 후보인데 profile_version이 없습니다.")
    if candidate.provider_id != "local" and candidate.metadata.get("algorithm_version") != 21:
        checks["profile_snapshot"] = False
        reasons.append("Profile-native Twin 알고리즘 v21이 아닙니다.")
    if candidate.provider_id != "local":
        for key, expected in (
            ("profile_version", context.profile_version),
            ("profile_as_of_month", context.profile_as_of_month),
            ("profile_window_years", context.profile_window_years),
        ):
            if expected is not None and candidate.metadata.get(key) != expected:
                checks["profile_snapshot"] = False
                reasons.append(f"Profile snapshot {key}가 앵커와 다릅니다.")

    counts = [int(region_counts.get(code, 0)) for code in candidate.region_codes]
    if counts and any(count <= 0 for count in counts):
        checks["region_coverage"] = False
        reasons.append("후보 지역이 built 원장에 없거나 거래가 없습니다.")
    if counts and min(counts) < min_region_n:
        checks["minimum_region_n"] = False
        warnings.append(f"개별 지역 거래수가 최소 기준({min_region_n})보다 작습니다.")
    else:
        checks["minimum_region_n"] = True

    accepted = not reasons and all(checks.values())
    return CandidateValidation(
        candidate_id=candidate.candidate_id,
        accepted=accepted,
        checks=checks,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
    )
