"""복합부동산 후보 Provider 계약."""

from app.built.regression.candidates.base import (
    CandidateContext,
    CandidateProvider,
    CandidateSpec,
    CandidateValidation,
    validate_candidate,
)
from app.built.regression.candidates.adjacency import allowed_twin_sidoes, is_adjacent_region
from app.built.regression.candidates.factory import (
    CandidateFactoryResult,
    fetch_candidate_rows,
    generate_candidates,
    region_counts_from_db,
    region_counts_from_frame,
    region_price_levels_from_db,
)
from app.built.regression.candidates.local import LocalCandidateProvider
from app.built.regression.candidates.profile_adapter import normalize_profile_twin_neighbors
from app.built.regression.candidates.profile_twin import ProfileTwinCandidateProvider

__all__ = [
    "CandidateContext",
    "CandidateProvider",
    "CandidateSpec",
    "CandidateValidation",
    "CandidateFactoryResult",
    "LocalCandidateProvider",
    "ProfileTwinCandidateProvider",
    "normalize_profile_twin_neighbors",
    "validate_candidate",
    "allowed_twin_sidoes",
    "is_adjacent_region",
    "fetch_candidate_rows",
    "generate_candidates",
    "region_counts_from_db",
    "region_counts_from_frame",
    "region_price_levels_from_db",
]
