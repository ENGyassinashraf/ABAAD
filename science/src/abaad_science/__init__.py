"""ABAAD science engine.

This package must stay free of web-framework, database and UI imports so
that the scientific logic can be tested and reproduced on its own.
"""

from .scoring import (
    DEFAULT_MIN_COVERAGE,
    RUBRIC,
    DimensionResult,
    ScoreResult,
    rank_candidates,
    score_candidate,
    similarity_from_rubric,
)

__version__ = "0.2.0"

#: Methodology the engine implements (Project & Scientific Guide §06).
METHODOLOGY_BASELINE = "ABAAD Project & Scientific Guide §06 (task-weighted score + separate coverage)"

__all__ = [
    "DEFAULT_MIN_COVERAGE",
    "METHODOLOGY_BASELINE",
    "RUBRIC",
    "DimensionResult",
    "ScoreResult",
    "rank_candidates",
    "score_candidate",
    "similarity_from_rubric",
]
