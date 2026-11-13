"""Task-specific comparison of Earth analog candidates against one planetary
reference region (Project & Scientific Guide §03, §06, §13, §14).

The score arithmetic lives in the plain-Python ``abaad_science`` package;
this module only gathers curated inputs and attaches provenance. Missing
assessments stay unknown, low coverage is reported as insufficient evidence,
and every number carries its rubric level, rationale and both sources.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from abaad_science import RUBRIC, rank_candidates, score_candidate
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..db import get_engine
from ..errors import ApiError
from .evidence import CLASS_LABELS

router = APIRouter(tags=["compare"])

MIN_COVERAGE = 50.0
FEATURED_COUNTRY = "EG"  # Project Scope: the three curated Egyptian candidates come first

METHOD = {
    "score_formula": "Score = 100 x sum(w_i x s_i) / sum(w_i) over dimensions with a curated assessment",
    "coverage_formula": "Coverage = 100 x sum(w_i of assessed dimensions) / sum(all task weights w_i)",
    "missing_data": "A dimension without a curated assessment is unknown -- it is excluded, never counted as zero.",
    "ranking": f"Only candidates with coverage >= {MIN_COVERAGE:g}% get a score and a rank; others are 'insufficient evidence'.",
    "rubric": {k: v for k, v in RUBRIC.items()},
    "min_coverage": MIN_COVERAGE,
    "not_a_similarity_percentage": (
        "This is a task-specific match score for one research task and one reference region, with its coverage shown "
        "beside it. It is not a percentage similarity between Earth and Mars or the Moon."
    ),
}

GENERAL_LIMITATIONS = [
    "Earth sites cannot reproduce Martian or lunar gravity, radiation, atmospheric pressure and composition, or vacuum.",
    "No result certifies a site as safe or ready for a real mission without field checks.",
    "Satellite imagery cannot by itself prove soil strength, traction, mineralogy or subsurface properties.",
    "Rubric levels are curated judgements traced to the cited sources; weights are a documented project methodology.",
    "Most sources were read at abstract or page level only; see each source's access level.",
]


class SourceRef(BaseModel):
    id: int
    title: str
    citation: str | None
    url: str | None
    doi: str | None
    source_access: str
    accessed_on: str | None


class DimensionOut(BaseModel):
    dimension: str
    name: str
    weight: float
    similarity: float | None
    rubric_level: str | None
    contribution: float | None
    evidence_basis: str | None
    rationale: str | None
    analog_source: SourceRef | None
    analog_locator: str | None
    reference_source: SourceRef | None
    reference_locator: str | None


class ClaimSummary(BaseModel):
    id: int
    task_code: str
    reference_region_code: str | None
    reference_body: str
    claim_evidence_class: dict
    reference_pairing_basis: str
    publication_state: str
    unpublished: bool
    limitations: str
    supported_claim: str | None  # only for published claims (or local/test with the unpublished gate)
    similarities: str | None
    differences: str | None


class GeometryOut(BaseModel):
    lon: float
    lat: float
    crs_code: str
    latitude_type: str
    longitude_domain: str
    geometry_status: str
    geometry_method: str | None
    uncertainty_note: str | None
    source: SourceRef | None
    source_locator: str | None


class OutlineOut(BaseModel):
    """A stored outline (polygon ring, lon/lat in the region's CRS). Only
    shown with its status: an approximate outline is never a boundary."""
    rings: list[list[list[float]]]
    crs_code: str
    geometry_status: str
    uncertainty_note: str | None
    source: SourceRef | None


class RegionOut(BaseModel):
    code: str
    name: str
    body: str
    region_level: str
    parent_code: str | None
    country_code: str | None
    site_type: str | None
    origin_status: str
    group: str  # 'egyptian' | 'global' | 'reference'
    geometry: GeometryOut | None
    outline: OutlineOut | None = None
    geometry_gap: str | None


class EvidenceQualityOut(BaseModel):
    """Provenance summary, kept separate from score and coverage. It only
    restates stored categories (claim evidence class, source access level,
    evidence basis); it is not a number and is never combined with the score."""
    claim_class: dict | None  # best visible site-task claim class {code, label}
    assessed_dimensions: int
    source_access: dict[str, int]  # distinct cited sources per access level
    evidence_basis: dict[str, int]  # assessed dimensions per evidence basis


class CandidateOut(BaseModel):
    region: RegionOut
    status: str  # ranked | insufficient_evidence
    score: float | None
    coverage: float
    rank: int | None
    dimensions: list[DimensionOut]
    claims: list[ClaimSummary]
    evidence_quality: EvidenceQualityOut


class TaskOut(BaseModel):
    code: str
    name: str
    description: str
    applies_to: str


class WeightOut(BaseModel):
    dimension: str
    name: str
    weight: float


class CompareResponse(BaseModel):
    reference: RegionOut
    task: TaskOut
    weights: list[WeightOut]
    weight_rationale: str | None
    method: dict
    candidates: list[CandidateOut]
    limitations: list[str]
    generated_at: str


class ReferenceOption(BaseModel):
    region: RegionOut
    tasks: list[TaskOut]


class OptionsResponse(BaseModel):
    bodies: list[dict]
    references: list[ReferenceOption]


# --- helpers ------------------------------------------------------------------

def _source(conn: Connection, pub_id: int | None) -> SourceRef | None:
    if pub_id is None:
        return None
    r = conn.execute(
        text("SELECT id, title, citation, url, doi, source_access, accessed_on FROM publication WHERE id = :id"),
        {"id": pub_id},
    ).first()
    if r is None:
        return None
    return SourceRef(id=r[0], title=r[1], citation=r[2], url=r[3], doi=r[4], source_access=r[5], accessed_on=r[6])


def _geometry(conn: Connection, region_id: int) -> GeometryOut | None:
    g = conn.execute(
        text(
            "SELECT encoding, geometry_text, crs_code, latitude_type, longitude_domain, geometry_status, geometry_method,"
            " uncertainty_note, source_publication_id, source_locator FROM region_geometry"
            " WHERE region_id = :id AND geometry_role = 'point_locator' AND geometry_status <> 'undefined'"
        ),
        {"id": region_id},
    ).first()
    if g is None:
        return None
    if g[0] == "rfc7946_geojson":
        lon, lat = json.loads(g[1])["coordinates"]
    else:  # "POINT (lon lat)"
        lon, lat = (float(v) for v in g[1].split("(", 1)[1].rstrip(")").split())
    return GeometryOut(
        lon=lon, lat=lat, crs_code=g[2], latitude_type=g[3], longitude_domain=g[4], geometry_status=g[5],
        geometry_method=g[6], uncertainty_note=g[7], source=_source(conn, g[8]), source_locator=g[9],
    )


def _outline(conn: Connection, region_id: int) -> OutlineOut | None:
    g = conn.execute(
        text(
            "SELECT geometry_text, crs_code, geometry_status, uncertainty_note, source_publication_id FROM region_geometry"
            " WHERE region_id = :id AND geometry_role = 'outline' AND encoding = 'ogc_wkt'"
            " AND geometry_status <> 'undefined' AND geometry_text LIKE 'POLYGON%'"
        ),
        {"id": region_id},
    ).first()
    if g is None:
        return None
    body = g[0].split("(", 1)[1].rsplit(")", 1)[0]  # "(x y, ...), (...)"
    rings = []
    for ring in body.split("),"):
        pts = ring.strip().strip("()").split(",")
        rings.append([[float(v) for v in p.split()] for p in pts])
    return OutlineOut(rings=rings, crs_code=g[1], geometry_status=g[2], uncertainty_note=g[3], source=_source(conn, g[4]))


def _evidence_quality(dims: list, claims: list) -> EvidenceQualityOut:
    assessed = [d for d in dims if d.similarity is not None]
    access: dict[str, int] = {}
    seen: set[int] = set()
    for d in assessed:
        for s in (d.analog_source, d.reference_source):
            if s is not None and s.id not in seen:
                seen.add(s.id)
                access[s.source_access] = access.get(s.source_access, 0) + 1
    basis: dict[str, int] = {}
    for d in assessed:
        if d.evidence_basis:
            basis[d.evidence_basis] = basis.get(d.evidence_basis, 0) + 1
    visible = sorted((c.claim_evidence_class["code"] for c in claims if not c.unpublished))
    best = visible[0] if visible else None  # 'A' < 'B' < 'C'
    return EvidenceQualityOut(
        claim_class={"code": best, "label": CLASS_LABELS[best]} if best else None,
        assessed_dimensions=len(assessed), source_access=access, evidence_basis=basis,
    )


_REGION_SQL = (
    "SELECT r.id, r.code, r.name, b.code, r.region_level, p.code, r.country_code, r.site_type, r.origin_status, r.region_role"
    " FROM region r JOIN planetary_body b ON b.id = r.body_id LEFT JOIN region p ON p.id = r.parent_region_id"
)


def _region(conn: Connection, row) -> RegionOut:
    group = "reference" if row[9] == "reference" else ("egyptian" if row[6] == FEATURED_COUNTRY else "global")
    gap = conn.execute(
        text("SELECT reason FROM coverage_gap WHERE region_id = :id AND slot = 'geometry' AND state <> 'not_applicable'"),
        {"id": row[0]},
    ).scalar()
    return RegionOut(
        code=row[1], name=row[2], body=row[3], region_level=row[4], parent_code=row[5], country_code=row[6],
        site_type=row[7], origin_status=row[8], group=group, geometry=_geometry(conn, row[0]), outline=_outline(conn, row[0]),
        geometry_gap=gap,
    )


def _task_applies(applies_to: str, body: str) -> bool:
    return applies_to == "both" or applies_to == body


def _claims(conn: Connection, analog_id: int, task_id: int, reference_id: int, reference_body_id: int) -> list[ClaimSummary]:
    show_text_for_drafts = os.environ.get("ABAAD_ALLOW_UNPUBLISHED_API") == "1"
    rows = conn.execute(
        text(
            "SELECT c.id, t.code, rr.code, rb.code, c.claim_evidence_class, c.reference_pairing_basis, c.publication_state,"
            " c.limitations, c.supported_claim, c.similarities, c.differences"
            " FROM site_task_claim c JOIN research_task t ON t.id = c.task_id"
            " JOIN planetary_body rb ON rb.id = c.reference_body_id LEFT JOIN region rr ON rr.id = c.reference_region_id"
            " WHERE c.analog_region_id = :a AND c.task_id = :t"
            " AND (c.reference_region_id = :r OR (c.reference_region_id IS NULL AND c.reference_body_id = :b))"
            " ORDER BY c.reference_region_id IS NULL, c.id"
        ),
        {"a": analog_id, "t": task_id, "r": reference_id, "b": reference_body_id},
    ).all()
    out = []
    for r in rows:
        published = r[6] == "published" and r[4] != "C"
        reveal = published or show_text_for_drafts
        out.append(ClaimSummary(
            id=r[0], task_code=r[1], reference_region_code=r[2], reference_body=r[3],
            claim_evidence_class={"code": r[4], "label": CLASS_LABELS[r[4]]}, reference_pairing_basis=r[5],
            publication_state=r[6], unpublished=not published, limitations=r[7],
            supported_claim=r[8] if reveal else None, similarities=r[9] if reveal else None,
            differences=r[10] if reveal else None,
        ))
    return out


# --- endpoints ----------------------------------------------------------------

@router.get("/compare/options", response_model=OptionsResponse, summary="Planetary references and the tasks valid for each")
def compare_options() -> OptionsResponse:
    with get_engine().connect() as conn:
        tasks = conn.execute(text("SELECT code, name, description, applies_to FROM research_task ORDER BY name")).all()
        refs = conn.execute(text(f"{_REGION_SQL} WHERE r.region_role = 'reference' ORDER BY b.code, r.name")).all()
        bodies = [
            {"code": r[0], "name": r[1]}
            for r in conn.execute(text(
                "SELECT DISTINCT b.code, b.name FROM planetary_body b JOIN region r ON r.body_id = b.id"
                " WHERE r.region_role = 'reference' ORDER BY b.code"))
        ]
        references = []
        for row in refs:
            region = _region(conn, row)
            valid = [TaskOut(code=t[0], name=t[1], description=t[2], applies_to=t[3])
                     for t in tasks if _task_applies(t[3], region.body)]
            references.append(ReferenceOption(region=region, tasks=valid))
    return OptionsResponse(bodies=bodies, references=references)


@router.get("/compare", response_model=CompareResponse, summary="Rank Earth analog candidates for one reference region and task")
def compare(
    reference: str = Query(..., min_length=1, max_length=64, description="Planetary reference region code"),
    task: str = Query(..., min_length=1, max_length=64, description="Research task code"),
) -> CompareResponse:
    with get_engine().connect() as conn:
        ref_row = conn.execute(text(f"{_REGION_SQL} WHERE r.code = :c"), {"c": reference}).first()
        if ref_row is None:
            raise ApiError(404, "not_found", f"reference region {reference!r} not found")
        if ref_row[9] != "reference":
            raise ApiError(422, "validation_error", f"{reference!r} is an Earth analog region, not a planetary reference")
        t = conn.execute(
            text("SELECT id, code, name, description, applies_to FROM research_task WHERE code = :c"), {"c": task}
        ).first()
        if t is None:
            raise ApiError(404, "not_found", f"research task {task!r} not found")
        if not _task_applies(t[4], ref_row[3]):
            raise ApiError(422, "validation_error",
                           f"task {task!r} applies to {t[4]!r}, not to a {ref_row[3]} reference region")

        ref_body_id = conn.execute(text("SELECT body_id FROM region WHERE id = :id"), {"id": ref_row[0]}).scalar()
        weight_rows = conn.execute(
            text(
                "SELECT d.code, d.name, w.weight, w.rationale FROM task_dimension_weight w"
                " JOIN comparison_dimension d ON d.id = w.dimension_id WHERE w.task_id = :t ORDER BY w.weight DESC, d.code"
            ),
            {"t": t[0]},
        ).all()
        weights = {r[0]: r[2] for r in weight_rows}
        dim_names = {r[0]: r[1] for r in conn.execute(text("SELECT code, name FROM comparison_dimension"))}

        candidate_rows = conn.execute(
            text(f"{_REGION_SQL} WHERE r.region_role = 'analog' AND b.code = 'earth' ORDER BY r.code")
        ).all()
        results, payloads = {}, {}
        for row in candidate_rows:
            assessments = {
                a[0]: a for a in conn.execute(
                    text(
                        "SELECT d.code, a.similarity, a.rubric_level, a.evidence_basis, a.rationale,"
                        " a.analog_publication_id, a.analog_locator, a.reference_publication_id, a.reference_locator"
                        " FROM dimension_assessment a JOIN comparison_dimension d ON d.id = a.dimension_id"
                        " WHERE a.analog_region_id = :a AND a.reference_region_id = :r"
                    ),
                    {"a": row[0], "r": ref_row[0]},
                )
            }
            sims = {d: assessments[d][1] for d in weights if d in assessments}
            result = score_candidate(weights, sims, MIN_COVERAGE)
            results[row[1]] = result
            dims = []
            for dr in result.dimensions:
                a = assessments.get(dr.dimension)
                dims.append(DimensionOut(
                    dimension=dr.dimension, name=dim_names[dr.dimension], weight=dr.weight, similarity=dr.similarity,
                    contribution=dr.contribution, rubric_level=a[2] if a else None, evidence_basis=a[3] if a else None,
                    rationale=a[4] if a else None, analog_source=_source(conn, a[5]) if a else None,
                    analog_locator=a[6] if a else None, reference_source=_source(conn, a[7]) if a else None,
                    reference_locator=a[8] if a else None,
                ))
            # Assessed dimensions this task does not weight (e.g. a documented lunar environment mismatch
            # under a task without an environment weight) are still shown for transparency, weight 0.
            for code, a in assessments.items():
                if code not in weights:
                    dims.append(DimensionOut(
                        dimension=code, name=dim_names[code], weight=0.0, similarity=a[1], contribution=None,
                        rubric_level=a[2], evidence_basis=a[3], rationale=a[4], analog_source=_source(conn, a[5]),
                        analog_locator=a[6], reference_source=_source(conn, a[7]), reference_locator=a[8],
                    ))
            payloads[row[1]] = (row, dims)

        ranks = rank_candidates(results)

        def sort_key(code: str):
            row = payloads[code][0]
            featured = 0 if row[6] == FEATURED_COUNTRY else 1
            rank = ranks[code]
            return (0 if rank is not None else 1, rank or 0, featured, -results[code].coverage, code)

        candidates = []
        for code in sorted(payloads, key=sort_key):
            row, dims = payloads[code]
            r = results[code]
            claims = _claims(conn, row[0], t[0], ref_row[0], ref_body_id)
            candidates.append(CandidateOut(
                region=_region(conn, row), status=r.status, score=r.score, coverage=r.coverage, rank=ranks[code],
                dimensions=dims, claims=claims, evidence_quality=_evidence_quality(dims, claims),
            ))

        return CompareResponse(
            reference=_region(conn, ref_row),
            task=TaskOut(code=t[1], name=t[2], description=t[3], applies_to=t[4]),
            weights=[WeightOut(dimension=w[0], name=w[1], weight=w[2]) for w in weight_rows],
            weight_rationale=weight_rows[0][3] if weight_rows else None,
            method=METHOD, candidates=candidates, limitations=GENERAL_LIMITATIONS,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
