"""Read-only publication and site-task claim endpoints.

Unpublished by default: claims in 'draft'/'reviewed' state and every class-C
claim are excluded unless ``include_unpublished=true``, and then each result
carries ``"unpublished": true``. Evidence class letters are always returned
with their name, never as a bare letter.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from ..db import get_engine
from ..errors import ApiError

router = APIRouter(tags=["evidence"])

CLASS_LABELS = {
    "A": "Direct full-text evidence",
    "B": "Direct but partially accessible evidence",
    "C": "Indirect/contextual evidence (never published)",
}


class EvidenceClass(BaseModel):
    code: str
    label: str


class Source(BaseModel):
    id: int
    doi: str | None
    url: str | None
    title: str
    authors: str | None
    year: int | None
    source_type: str | None
    source_access: str
    peer_reviewed: bool
    institution: str | None
    licence: str | None
    citation: str | None
    accessed_on: str | None


class PagedSources(BaseModel):
    items: list[Source]
    total: int
    limit: int
    offset: int


class ClaimSource(BaseModel):
    source_id: int
    role: str
    locator: str | None
    note: str | None


class Claim(BaseModel):
    id: int
    analog_region_code: str
    task_code: str
    reference_region_code: str | None
    claim_evidence_class: EvidenceClass
    reference_pairing_basis: str
    supported_claim: str
    similarities: str
    differences: str
    not_supported: str
    spatial_scale: str
    limitations: str
    publication_state: str
    unpublished: bool = False
    has_disputing_source: bool
    sources: list[ClaimSource]


class PagedClaims(BaseModel):
    items: list[Claim]
    total: int
    limit: int
    offset: int


def _source_row(r) -> Source:
    return Source(
        id=r[0], doi=r[1], url=r[2], title=r[3], authors=r[4], year=r[5], source_type=r[6],
        source_access=r[7], peer_reviewed=bool(r[8]), institution=r[9], licence=r[10], citation=r[11],
        accessed_on=r[12],
    )


_SOURCE_COLS = (
    "id, doi, url, title, authors, year, source_type, source_access, peer_reviewed, institution, licence,"
    " citation, accessed_on"
)


@router.get("/sources", response_model=PagedSources, summary="List publications and program pages")
def list_sources(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)) -> PagedSources:
    with get_engine().connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM publication")).scalar_one()
        rows = conn.execute(
            text(f"SELECT {_SOURCE_COLS} FROM publication ORDER BY id LIMIT :limit OFFSET :offset"),
            {"limit": limit, "offset": offset},
        ).all()
    return PagedSources(items=[_source_row(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/sources/{source_id}", response_model=Source, summary="Publication or program page detail")
def get_source(source_id: int) -> Source:
    with get_engine().connect() as conn:
        row = conn.execute(text(f"SELECT {_SOURCE_COLS} FROM publication WHERE id = :id"), {"id": source_id}).first()
    if row is None:
        raise ApiError(404, "not_found", f"source {source_id} not found")
    return _source_row(row)


_CLAIM_SELECT = (
    "SELECT stc.id, ar.code, t.code, rr.code, stc.claim_evidence_class, stc.reference_pairing_basis,"
    " stc.supported_claim, stc.similarities, stc.differences, stc.not_supported, stc.spatial_scale,"
    " stc.limitations, stc.publication_state"
    " FROM site_task_claim stc"
    " JOIN region ar ON ar.id = stc.analog_region_id"
    " JOIN research_task t ON t.id = stc.task_id"
    " LEFT JOIN region rr ON rr.id = stc.reference_region_id"
)


def _build_claim(conn, row) -> Claim:
    claim_id = row[0]
    cls = row[4]
    sources = conn.execute(
        text("SELECT publication_id, role, locator, note FROM site_task_claim_source WHERE claim_id = :id"),
        {"id": claim_id},
    ).all()
    has_disputing = any(s[1] == "disputes" for s in sources)
    is_unpublished = row[12] != "published" or cls == "C"
    return Claim(
        id=claim_id, analog_region_code=row[1], task_code=row[2], reference_region_code=row[3],
        claim_evidence_class=EvidenceClass(code=cls, label=CLASS_LABELS[cls]),
        reference_pairing_basis=row[5], supported_claim=row[6], similarities=row[7], differences=row[8],
        not_supported=row[9], spatial_scale=row[10], limitations=row[11], publication_state=row[12],
        unpublished=is_unpublished, has_disputing_source=has_disputing,
        sources=[ClaimSource(source_id=s[0], role=s[1], locator=s[2], note=s[3]) for s in sources],
    )


@router.get("/claims", response_model=PagedClaims, summary="List site-task claims")
def list_claims(
    region: str | None = None,
    task: str | None = None,
    claim_class: str | None = Query(default=None, alias="class"),
    state: str | None = None,
    include_unpublished: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PagedClaims:
    clauses, params = [], {}
    if region:
        clauses.append("(ar.code = :region OR rr.code = :region)"); params["region"] = region
    if task:
        clauses.append("t.code = :task"); params["task"] = task
    if claim_class:
        clauses.append("stc.claim_evidence_class = :cls"); params["cls"] = claim_class
    if state:
        clauses.append("stc.publication_state = :state"); params["state"] = state
    if not include_unpublished:
        clauses.append("stc.publication_state = 'published' AND stc.claim_evidence_class <> 'C'")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_engine().connect() as conn:
        total = conn.execute(
            text(f"SELECT count(*) FROM site_task_claim stc JOIN region ar ON ar.id = stc.analog_region_id"
                 f" JOIN research_task t ON t.id = stc.task_id LEFT JOIN region rr ON rr.id = stc.reference_region_id{where}"),
            params,
        ).scalar_one()
        rows = conn.execute(
            text(f"{_CLAIM_SELECT}{where} ORDER BY stc.id LIMIT :limit OFFSET :offset"),
            {**params, "limit": limit, "offset": offset},
        ).all()
        items = [_build_claim(conn, r) for r in rows]
    return PagedClaims(items=items, total=total, limit=limit, offset=offset)


@router.get("/claims/{claim_id}", response_model=Claim, summary="Site-task claim detail")
def get_claim(claim_id: int) -> Claim:
    with get_engine().connect() as conn:
        row = conn.execute(text(f"{_CLAIM_SELECT} WHERE stc.id = :id"), {"id": claim_id}).first()
        if row is None:
            raise ApiError(404, "not_found", f"claim {claim_id} not found")
        return _build_claim(conn, row)
