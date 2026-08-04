"""복합부동산 Local 후보 Provider."""

from __future__ import annotations

from app.built.regression.candidates.base import CandidateContext, CandidateSpec


class LocalCandidateProvider:
    """현재 선택 지역만 사용하는 기준선 후보."""

    provider_id = "local"

    def __init__(self, variables: list[str] | tuple[str, ...] = ()):
        self._variables = tuple(variables)

    def generate(self, context: CandidateContext) -> list[CandidateSpec]:
        codes = context.anchor_region_codes
        return [
            CandidateSpec(
                candidate_id="local",
                provider_id=self.provider_id,
                region_codes=codes,
                variables=self._variables,
                metadata={
                    "admin_level": context.admin_level,
                    "pooling": False,
                },
            )
        ]
