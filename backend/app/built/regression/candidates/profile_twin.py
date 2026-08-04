"""Regional Profile-native Twin Candidate Provider.

이 Provider는 Twin API/DB를 직접 호출하지 않는다.
Profile 계층이 조회·버전 고정한 이웃 결과를 받아 후보만 만든다.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.built.regression.candidates.base import CandidateContext, CandidateSpec


class ProfileTwinCandidateProvider:
    provider_id = "profile_twin"

    def __init__(
        self,
        neighbors: Iterable[Mapping[str, object]],
        variables: list[str] | tuple[str, ...] = (),
        *,
        algorithm_version: int = 21,
    ):
        self._neighbors = list(neighbors)
        self._variables = tuple(variables)
        self._algorithm_version = algorithm_version

    def generate(self, context: CandidateContext) -> list[CandidateSpec]:
        if not context.profile_version:
            return []
        neighbor_codes = tuple(
            str(row.get("region_code") or row.get("twin_region_code") or "").strip()
            for row in self._neighbors
        )
        neighbor_codes = tuple(code for code in neighbor_codes if code)
        if not neighbor_codes:
            return []
        region_codes = tuple(dict.fromkeys((*context.anchor_region_codes, *neighbor_codes)))
        return [
            CandidateSpec(
                candidate_id=f"profile-twin-{i + 1}",
                provider_id=self.provider_id,
                region_codes=region_codes[: i + 2],
                variables=self._variables,
                metadata={
                    "admin_level": context.admin_level,
                    "algorithm_version": self._algorithm_version,
                    "profile_version": context.profile_version,
                    "profile_as_of_month": context.profile_as_of_month,
                    "profile_window_years": context.profile_window_years,
                    "similarity_score": row.get("similarity_score"),
                    "pooling": False,
                    "validated": False,
                },
            )
            for i, row in enumerate(self._neighbors)
        ]
