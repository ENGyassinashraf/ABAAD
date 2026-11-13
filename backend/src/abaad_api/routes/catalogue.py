"""Read-only catalogue endpoints: planetary bodies and the research-task
vocabulary. See docs/DECISIONS.md P2-02 for the claim_evidence_class vs
measurement.evidence_grade distinction documented in the /tasks footer."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from ..db import get_engine

router = APIRouter(tags=["catalogue"])


class Body(BaseModel):
    code: str
    name: str
    default_crs_code: str
    mean_radius_m: float


class Task(BaseModel):
    code: str
    name: str
    description: str
    applies_to: str


class TaskListResponse(BaseModel):
    items: list[Task]
    footer: str


EVIDENCE_FOOTER = (
    "claim_evidence_class (A/B/C) documents how directly a site-task claim is supported: "
    "A = direct full-text evidence, B = direct but partially accessible evidence (e.g. an abstract, "
    "or an authoritative program page), C = indirect/contextual evidence (never published). It is a "
    "documentation label, never a numeric score. measurement.evidence_grade (A/B/C/D) is a separate "
    "scale describing the provenance of a single measured value; Phase 2 creates no measurement rows."
)


@router.get("/bodies", response_model=list[Body], summary="Planetary bodies")
def list_bodies() -> list[Body]:
    with get_engine().connect() as conn:
        rows = conn.execute(text("SELECT code, name, default_crs_code, mean_radius_m FROM planetary_body ORDER BY code")).all()
    return [Body(code=r[0], name=r[1], default_crs_code=r[2], mean_radius_m=r[3]) for r in rows]


@router.get("/tasks", response_model=TaskListResponse, summary="Research-task vocabulary")
def list_tasks() -> TaskListResponse:
    with get_engine().connect() as conn:
        rows = conn.execute(text("SELECT code, name, description, applies_to FROM research_task ORDER BY code")).all()
    return TaskListResponse(
        items=[Task(code=r[0], name=r[1], description=r[2], applies_to=r[3]) for r in rows],
        footer=EVIDENCE_FOOTER,
    )
