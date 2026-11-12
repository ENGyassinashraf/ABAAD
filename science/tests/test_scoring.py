"""Unit tests for the task-weighted score and coverage (Guide §06, §14)."""

from __future__ import annotations

import math

import pytest

from abaad_science import (
    RUBRIC,
    rank_candidates,
    score_candidate,
    similarity_from_rubric,
)

W = {"terrain_shape": 3.0, "surface_processes": 4.0, "subsurface": 1.0, "geology_materials": 2.0}


def test_full_coverage_weighted_mean():
    r = score_candidate(W, {"terrain_shape": 1.0, "surface_processes": 0.5, "subsurface": 0.0, "geology_materials": 0.75})
    # (3*1 + 4*0.5 + 1*0 + 2*0.75) / 10 = 6.5 / 10
    assert r.status == "ranked"
    assert r.score == 65.0
    assert r.coverage == 100.0


def test_missing_is_unknown_not_zero():
    r = score_candidate(W, {"terrain_shape": 1.0, "surface_processes": 1.0, "geology_materials": 1.0})
    assert r.score == 100.0  # subsurface is unknown, so it is excluded, not counted as 0
    assert r.coverage == 90.0
    sub = next(d for d in r.dimensions if d.dimension == "subsurface")
    assert sub.similarity is None and sub.contribution is None


def test_low_coverage_is_insufficient_evidence_not_ranked():
    r = score_candidate(W, {"subsurface": 1.0})  # 1/10 = 10% coverage
    assert r.status == "insufficient_evidence"
    assert r.score is None
    assert r.coverage == 10.0


def test_no_assessments_at_all():
    r = score_candidate(W, {})
    assert r.status == "insufficient_evidence" and r.score is None and r.coverage == 0.0


def test_threshold_is_inclusive():
    r = score_candidate({"a": 1.0, "b": 1.0}, {"a": 0.5}, min_coverage=50.0)
    assert r.status == "ranked" and r.score == 50.0 and r.coverage == 50.0


def test_weights_change_the_score_for_a_different_task():
    sims = {"terrain_shape": 1.0, "surface_processes": 0.0}
    mobility = score_candidate({"terrain_shape": 4.0, "surface_processes": 1.0}, sims)
    aeolian = score_candidate({"terrain_shape": 1.0, "surface_processes": 4.0}, sims)
    assert mobility.score == 80.0 and aeolian.score == 20.0


@pytest.mark.parametrize("bad", [0, -1, math.inf, math.nan, True, "2"])
def test_invalid_weights_rejected(bad):
    with pytest.raises(ValueError, match="weight"):
        score_candidate({"a": bad}, {"a": 1.0})


@pytest.mark.parametrize("bad", [-0.1, 1.1, math.nan, "0.5", False])
def test_invalid_similarity_rejected(bad):
    with pytest.raises(ValueError, match="similarity"):
        score_candidate({"a": 1.0}, {"a": bad})


def test_similarity_for_unweighted_dimension_rejected():
    with pytest.raises(ValueError, match="does not weight"):
        score_candidate({"a": 1.0}, {"b": 1.0})


def test_empty_task_has_no_criteria():
    r = score_candidate({}, {})
    assert r.status == "no_criteria" and r.score is None


def test_rubric_levels_are_bounded_and_named():
    assert similarity_from_rubric("close") == 0.75
    assert all(0.0 <= v <= 1.0 for v in RUBRIC.values())
    with pytest.raises(ValueError):
        similarity_from_rubric("excellent")


def test_rank_only_ranked_candidates_with_deterministic_ties():
    results = {
        "B": score_candidate(W, {d: 0.5 for d in W}),             # 50, 100%
        "A": score_candidate(W, {d: 0.5 for d in W}),             # tie -> code order
        "C": score_candidate(W, {"terrain_shape": 1.0, "surface_processes": 1.0}),  # 100, 70%
        "D": score_candidate(W, {"subsurface": 1.0}),             # insufficient
    }
    ranks = rank_candidates(results)
    assert ranks == {"C": 1, "A": 2, "B": 3, "D": None}


def test_high_score_on_thin_evidence_never_outranks_without_coverage():
    thin = score_candidate(W, {"subsurface": 1.0})  # 100% similar but 10% coverage
    broad = score_candidate(W, {d: 0.6 for d in W})
    assert rank_candidates({"thin": thin, "broad": broad}) == {"broad": 1, "thin": None}
