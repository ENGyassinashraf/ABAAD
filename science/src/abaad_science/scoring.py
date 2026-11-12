"""Task-specific match score and data coverage (Project & Scientific Guide §06).

    Score    = 100 * sum(w_i * s_i) / sum(w_i)   over dimensions with a known s_i
    Coverage = 100 * sum(w_i known)  / sum(w_i)   over all task dimensions

A missing similarity is *unknown*, never zero. A candidate whose coverage is
below the threshold gets no score and no rank: it is reported as
"insufficient_evidence" so a high score built on very little evidence never
looks stronger than a moderate score built on broad evidence.

Similarity values come from a documented ordinal rubric (``RUBRIC``), not from
free-form numbers, so every s_i can be traced to a named level and its rationale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

#: Documented similarity rubric. Each curated assessment picks one level.
RUBRIC: dict[str, float] = {
    "strong": 1.0,    # source documents the same feature/process type at a comparable scale
    "close": 0.75,    # same feature/process type; scale, context or setting differs
    "partial": 0.5,   # related feature or process; only part of the dimension matches
    "weak": 0.25,     # contextual or indirect resemblance only
    "mismatch": 0.0,  # source documents a relevant difference
}

DEFAULT_MIN_COVERAGE = 50.0

STATUS_RANKED = "ranked"
STATUS_INSUFFICIENT = "insufficient_evidence"
STATUS_NO_CRITERIA = "no_criteria"


@dataclass(frozen=True)
class DimensionResult:
    dimension: str
    weight: float
    similarity: float | None  # None = unknown (no curated assessment)
    contribution: float | None  # weight * similarity, or None when unknown


@dataclass(frozen=True)
class ScoreResult:
    score: float | None
    coverage: float
    status: str
    min_coverage: float
    dimensions: tuple[DimensionResult, ...]


def similarity_from_rubric(level: str) -> float:
    try:
        return RUBRIC[level]
    except KeyError:
        raise ValueError(f"unknown rubric level {level!r}; expected one of {sorted(RUBRIC)}") from None


def _check_weight(dim: str, w: float) -> None:
    if not isinstance(w, (int, float)) or isinstance(w, bool) or not math.isfinite(w) or w <= 0:
        raise ValueError(f"weight for {dim!r} must be a finite number > 0, got {w!r}")


def _check_similarity(dim: str, s: float | None) -> None:
    if s is None:
        return
    if not isinstance(s, (int, float)) or isinstance(s, bool) or not math.isfinite(s) or not 0.0 <= s <= 1.0:
        raise ValueError(f"similarity for {dim!r} must be in [0, 1] or None, got {s!r}")


def score_candidate(
    weights: Mapping[str, float],
    similarities: Mapping[str, float | None],
    min_coverage: float = DEFAULT_MIN_COVERAGE,
) -> ScoreResult:
    """Score one candidate for one task. ``weights`` defines the task's
    dimensions; a dimension absent from ``similarities`` is unknown."""
    if not 0.0 <= min_coverage <= 100.0:
        raise ValueError("min_coverage must be between 0 and 100")
    extra = set(similarities) - set(weights)
    if extra:
        raise ValueError(f"similarities given for dimensions the task does not weight: {sorted(extra)}")
    for dim, w in weights.items():
        _check_weight(dim, w)
        _check_similarity(dim, similarities.get(dim))

    total_w = sum(weights.values())
    if total_w == 0:
        return ScoreResult(None, 0.0, STATUS_NO_CRITERIA, min_coverage, ())

    dims = []
    known_w = 0.0
    weighted = 0.0
    for dim in sorted(weights):
        w = float(weights[dim])
        s = similarities.get(dim)
        if s is None:
            dims.append(DimensionResult(dim, w, None, None))
            continue
        known_w += w
        weighted += w * s
        dims.append(DimensionResult(dim, w, float(s), w * s))

    coverage = round(100.0 * known_w / total_w, 1)
    if known_w == 0 or coverage < min_coverage:
        return ScoreResult(None, coverage, STATUS_INSUFFICIENT, min_coverage, tuple(dims))
    score = round(100.0 * weighted / known_w, 1)
    return ScoreResult(score, coverage, STATUS_RANKED, min_coverage, tuple(dims))


def rank_candidates(results: Mapping[str, ScoreResult]) -> dict[str, int | None]:
    """Rank only candidates with status 'ranked': higher score first, then
    higher coverage, then code (deterministic). Everything else gets None."""
    ranked = sorted(
        (code for code, r in results.items() if r.status == STATUS_RANKED),
        key=lambda c: (-results[c].score, -results[c].coverage, c),  # type: ignore[operator]
    )
    out: dict[str, int | None] = {code: None for code in results}
    for i, code in enumerate(ranked, start=1):
        out[code] = i
    return out
