"""Profile-native Twin Engine (D-029 Phase B).

Pipeline: Candidate → Catalog → Vector → Weight → Similarity → Top-N
"""

from profile_twin.catalog import TwinCatalog, load_twin_catalog
from profile_twin.similarity import SimilarityResult, compute_similarity
from profile_twin.vector import TwinVector, project_profile
from profile_twin.weight import TwinWeights, load_twin_weights

__all__ = [
    "TwinCatalog",
    "TwinVector",
    "TwinWeights",
    "SimilarityResult",
    "load_twin_catalog",
    "load_twin_weights",
    "project_profile",
    "compute_similarity",
]
