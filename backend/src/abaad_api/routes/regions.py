"""Read-only region, geometry and coverage endpoints.

Missing values are never rendered as zero, empty or absent: a region/slot
with no geometry or asset is 'present', 'gap' (with its coverage_gap reason)
or 'not yet curated' (neither exists).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..db import get_engine
from ..errors import ApiError

router = APIRouter(tags=["regions"])


class Alias(BaseModel):
    alias: str
    alias_kind: str
    language: str | None = None


class RegionSummary(BaseModel):
    code: str
    body: str
    region_role: str
    region_level: str
    validation_status: str
    name: str
    parent_code: str | None = None
    country_code: str | None = None
    site_type: str | None = None
    origin_status: str


class RegionDetail(RegionSummary):
    aliases: list[Alias]
    children: list[str]
    claim_count: int


class PagedRegions(BaseModel):
    items: list[RegionSummary]
    total: int
    limit: int
    offset: int


class Geometry(BaseModel):
    geometry_role: str
    encoding: str
    geometry_text: str
    crs_code: str
    coordinate_units: str
    latitude_type: str
    longitude_direction: str
    longitude_domain: str
    axis_order: str
    geometry_status: str
    geometry_method: str | None
    positional_uncertainty_m: float | None
    uncertainty_note: str | None
    source_publication_id: int | None
    source_locator: str | None


class CoverageGapOut(BaseModel):
    state: str
    reason: str
    resolution_hint: str | None = None


class CoverageCell(BaseModel):
    region_code: str
    slot: str
    status: str  # present | gap | not_yet_curated
    gap: CoverageGapOut | None = None


SLOTS = ("geometry", "elevation", "imagery", "literature_observations")


def _row_to_summary(r: Any) -> RegionSummary:
    return RegionSummary(
        code=r[0], body=r[1], region_role=r[2], region_level=r[3], validation_status=r[4],
        name=r[5], parent_code=r[6], country_code=r[7], site_type=r[8], origin_status=r[9],
    )


_SELECT_REGION = (
    "SELECT r.code, b.code, r.region_role, r.region_level, r.validation_status, r.name,"
    " p.code, r.country_code, r.site_type, r.origin_status, r.id"
    " FROM region r JOIN planetary_body b ON b.id = r.body_id"
    " LEFT JOIN region p ON p.id = r.parent_region_id"
)


@router.get("/regions", response_model=PagedRegions, summary="List regions")
def list_regions(
    body: str | None = None,
    role: str | None = Query(default=None, alias="role"),
    level: str | None = None,
    parent: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PagedRegions:
    clauses, params = [], {}
    if body:
        clauses.append("b.code = :body"); params["body"] = body
    if role:
        clauses.append("r.region_role = :role"); params["role"] = role
    if level:
        clauses.append("r.region_level = :level"); params["level"] = level
    if parent:
        clauses.append("p.code = :parent"); params["parent"] = parent
    if status:
        clauses.append("r.validation_status = :status"); params["status"] = status
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_engine().connect() as conn:
        total = conn.execute(
            text(f"SELECT count(*) FROM region r JOIN planetary_body b ON b.id = r.body_id"
                 f" LEFT JOIN region p ON p.id = r.parent_region_id{where}"), params
        ).scalar_one()
        rows = conn.execute(
            text(f"{_SELECT_REGION}{where} ORDER BY r.code LIMIT :limit OFFSET :offset"),
            {**params, "limit": limit, "offset": offset},
        ).all()
    return PagedRegions(items=[_row_to_summary(r) for r in rows], total=total, limit=limit, offset=offset)


def _get_region_row(conn: Connection, code: str) -> Any:
    row = conn.execute(text(f"{_SELECT_REGION} WHERE r.code = :code"), {"code": code}).first()
    if row is None:
        raise ApiError(404, "not_found", f"region {code!r} not found")
    return row


@router.get("/regions/{code}", response_model=RegionDetail, summary="Region detail")
def get_region(code: str) -> RegionDetail:
    with get_engine().connect() as conn:
        row = _get_region_row(conn, code)
        region_id = row[10]
        aliases = conn.execute(
            text("SELECT alias, alias_kind, language FROM region_alias WHERE region_id = :id ORDER BY alias"),
            {"id": region_id},
        ).all()
        children = conn.execute(
            text("SELECT code FROM region WHERE parent_region_id = :id ORDER BY code"), {"id": region_id}
        ).all()
        claim_count = conn.execute(
            text("SELECT count(*) FROM site_task_claim WHERE analog_region_id = :id OR reference_region_id = :id"),
            {"id": region_id},
        ).scalar_one()
    summary = _row_to_summary(row)
    return RegionDetail(
        **summary.model_dump(),
        aliases=[Alias(alias=a[0], alias_kind=a[1], language=a[2]) for a in aliases],
        children=[c[0] for c in children],
        claim_count=claim_count,
    )


@router.get("/regions/{code}/geometries", response_model=list[Geometry], summary="Region geometries")
def get_region_geometries(code: str) -> list[Geometry]:
    with get_engine().connect() as conn:
        row = _get_region_row(conn, code)
        geoms = conn.execute(
            text(
                "SELECT geometry_role, encoding, geometry_text, crs_code, coordinate_units, latitude_type,"
                " longitude_direction, longitude_domain, axis_order, geometry_status, geometry_method,"
                " positional_uncertainty_m, uncertainty_note, source_publication_id, source_locator"
                " FROM region_geometry WHERE region_id = :id ORDER BY geometry_role"
            ),
            {"id": row[10]},
        ).all()
    return [
        Geometry(
            geometry_role=g[0], encoding=g[1], geometry_text=g[2], crs_code=g[3], coordinate_units=g[4],
            latitude_type=g[5], longitude_direction=g[6], longitude_domain=g[7], axis_order=g[8],
            geometry_status=g[9], geometry_method=g[10], positional_uncertainty_m=g[11], uncertainty_note=g[12],
            source_publication_id=g[13], source_locator=g[14],
        )
        for g in geoms
    ]


@router.get("/coverage", response_model=list[CoverageCell], summary="Region x slot coverage matrix")
def coverage(body: str | None = None) -> list[CoverageCell]:
    """present (a source-traced/approximate geometry or validated asset exists),
    gap (a coverage_gap row, with its reason), or not_yet_curated (neither)."""
    clauses, params = [], {}
    if body:
        clauses.append("b.code = :body"); params["body"] = body
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_engine().connect() as conn:
        regions = conn.execute(
            text(f"SELECT r.id, r.code FROM region r JOIN planetary_body b ON b.id = r.body_id{where} ORDER BY r.code"),
            params,
        ).all()
        geometry_present = {
            row[0] for row in conn.execute(text("SELECT DISTINCT region_id FROM region_geometry"))
        }
        gaps = {
            (row[0], row[1]): (row[2], row[3], row[4])
            for row in conn.execute(text("SELECT region_id, slot, state, reason, resolution_hint FROM coverage_gap"))
        }
    out: list[CoverageCell] = []
    for region_id, code in regions:
        for slot in SLOTS:
            if slot == "geometry" and region_id in geometry_present:
                out.append(CoverageCell(region_code=code, slot=slot, status="present"))
            elif (region_id, slot) in gaps:
                state, reason, hint = gaps[(region_id, slot)]
                out.append(CoverageCell(region_code=code, slot=slot, status="gap",
                                         gap=CoverageGapOut(state=state, reason=reason, resolution_hint=hint)))
            else:
                out.append(CoverageCell(region_code=code, slot=slot, status="not_yet_curated"))
    return out
