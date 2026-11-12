"""Read-only dataset and data-asset endpoints. No file serving: an asset's
file lives only on disk (git-ignored); this API returns metadata only."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from ..db import get_engine
from ..errors import ApiError

router = APIRouter(tags=["data"])


class Dataset(BaseModel):
    code: str
    provider: str
    product_id: str
    product_name: str
    product_version: str
    body: str
    variable: str
    surface_type: str
    horizontal_crs: str
    vertical_reference: str
    value_units: str
    native_resolution_value: float
    native_resolution_unit: str
    file_format: str
    licence_summary: str
    access_conditions: str
    source_url: str
    asset_count: int


class Asset(BaseModel):
    id: int
    dataset_code: str
    region_code: str | None
    asset_role: str
    crs: str
    vertical_reference: str
    value_units: str
    width_px: int
    height_px: int
    checksum_sha256: str
    size_bytes: int
    acquisition_window: dict
    validation_status: str
    validated_at: str | None


_DATASET_COLS = (
    "d.code, d.provider, d.product_id, d.product_name, d.product_version, b.code, d.variable, d.surface_type,"
    " d.horizontal_crs, d.vertical_reference, d.value_units, d.native_resolution_value, d.native_resolution_unit,"
    " d.file_format, d.licence_summary, d.access_conditions, d.source_url, d.id"
)


def _dataset_row(r, asset_count: int) -> Dataset:
    return Dataset(
        code=r[0], provider=r[1], product_id=r[2], product_name=r[3], product_version=r[4], body=r[5],
        variable=r[6], surface_type=r[7], horizontal_crs=r[8], vertical_reference=r[9], value_units=r[10],
        native_resolution_value=r[11], native_resolution_unit=r[12], file_format=r[13], licence_summary=r[14],
        access_conditions=r[15], source_url=r[16], asset_count=asset_count,
    )


@router.get("/datasets", response_model=list[Dataset], summary="List dataset products")
def list_datasets() -> list[Dataset]:
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(f"SELECT {_DATASET_COLS} FROM dataset d JOIN planetary_body b ON b.id = d.body_id ORDER BY d.code")
        ).all()
        counts = dict(conn.execute(text("SELECT dataset_id, count(*) FROM data_asset GROUP BY dataset_id")).all())
    return [_dataset_row(r, counts.get(r[17], 0)) for r in rows]


@router.get("/datasets/{code}", response_model=Dataset, summary="Dataset product detail")
def get_dataset(code: str) -> Dataset:
    with get_engine().connect() as conn:
        row = conn.execute(
            text(f"SELECT {_DATASET_COLS} FROM dataset d JOIN planetary_body b ON b.id = d.body_id WHERE d.code = :code"),
            {"code": code},
        ).first()
        if row is None:
            raise ApiError(404, "not_found", f"dataset {code!r} not found")
        asset_count = conn.execute(
            text("SELECT count(*) FROM data_asset WHERE dataset_id = :id"), {"id": row[17]}
        ).scalar_one()
    return _dataset_row(row, asset_count)


@router.get("/assets/{asset_id}", response_model=Asset, summary="Data asset metadata (no file serving)")
def get_asset(asset_id: int) -> Asset:
    with get_engine().connect() as conn:
        row = conn.execute(
            text(
                "SELECT a.id, d.code, r.code, a.asset_role, a.crs, a.vertical_reference, a.value_units,"
                " a.width_px, a.height_px, a.sha256, a.size_bytes, a.window_min_x, a.window_min_y,"
                " a.window_max_x, a.window_max_y, a.validation_status, a.validated_at"
                " FROM data_asset a JOIN dataset d ON d.id = a.dataset_id LEFT JOIN region r ON r.id = a.region_id"
                " WHERE a.id = :id"
            ),
            {"id": asset_id},
        ).first()
    if row is None:
        raise ApiError(404, "not_found", f"asset {asset_id} not found")
    return Asset(
        id=row[0], dataset_code=row[1], region_code=row[2], asset_role=row[3], crs=row[4],
        vertical_reference=row[5], value_units=row[6], width_px=row[7], height_px=row[8],
        checksum_sha256=row[9], size_bytes=row[10],
        acquisition_window={"min_x": row[11], "min_y": row[12], "max_x": row[13], "max_y": row[14],
                             "is_site_boundary": False},
        validation_status=row[15], validated_at=row[16],
    )
