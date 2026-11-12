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
    collection_id: str | None
    product_id: str
    product_name: str
    product_version: str
    body: str
    variable: str
    surface_type: str
    horizontal_crs: str | None  # None while horizontal_crs_status != 'verified' (F-02)
    horizontal_crs_status: str  # verified | pending | product_specific_unverified
    vertical_reference: str
    value_units: str
    native_resolution_value: float
    native_resolution_unit: str
    file_format: str
    licence_summary: str
    access_conditions: str
    source_url: str  # catalogue/product description page
    download_available: bool  # True only once a verified direct file URL exists (F-08)
    asset_count: int


class ProcessingInput(BaseModel):
    asset_id: int
    relative_path: str


class ProcessingLineage(BaseModel):
    method: str
    software: str
    software_version: str
    output_variable: str
    output_crs: str
    output_vertical_reference: str
    output_units: str
    script_path: str
    script_git_commit: str
    inputs: list[ProcessingInput]


class Asset(BaseModel):
    id: int
    dataset_code: str
    region_code: str | None
    asset_role: str
    source_item_id: str
    source_item_url: str
    original_label_path: str | None
    stac_item_url: str | None
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
    processing: ProcessingLineage | None  # non-null only for asset_role='derived'


_DATASET_COLS = (
    "d.code, d.provider, d.collection_id, d.product_id, d.product_name, d.product_version, b.code, d.variable,"
    " d.surface_type, d.horizontal_crs, d.horizontal_crs_status, d.vertical_reference, d.value_units,"
    " d.native_resolution_value, d.native_resolution_unit, d.file_format, d.licence_summary, d.access_conditions,"
    " d.source_url, d.download_url, d.id"
)


def _dataset_row(r, asset_count: int) -> Dataset:
    return Dataset(
        code=r[0], provider=r[1], collection_id=r[2], product_id=r[3], product_name=r[4], product_version=r[5],
        body=r[6], variable=r[7], surface_type=r[8], horizontal_crs=r[9], horizontal_crs_status=r[10],
        vertical_reference=r[11], value_units=r[12], native_resolution_value=r[13], native_resolution_unit=r[14],
        file_format=r[15], licence_summary=r[16], access_conditions=r[17], source_url=r[18],
        download_available=r[19] is not None, asset_count=asset_count,
    )


@router.get("/datasets", response_model=list[Dataset], summary="List dataset products")
def list_datasets() -> list[Dataset]:
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(f"SELECT {_DATASET_COLS} FROM dataset d JOIN planetary_body b ON b.id = d.body_id ORDER BY d.code")
        ).all()
        counts = dict(conn.execute(text("SELECT dataset_id, count(*) FROM data_asset GROUP BY dataset_id")).all())
    return [_dataset_row(r, counts.get(r[20], 0)) for r in rows]


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
            text("SELECT count(*) FROM data_asset WHERE dataset_id = :id"), {"id": row[20]}
        ).scalar_one()
    return _dataset_row(row, asset_count)


@router.get("/assets/{asset_id}", response_model=Asset, summary="Data asset metadata (no file serving)")
def get_asset(asset_id: int) -> Asset:
    with get_engine().connect() as conn:
        row = conn.execute(
            text(
                "SELECT a.id, d.code, r.code, a.asset_role, a.source_item_id, a.source_item_url,"
                " a.original_label_path, a.stac_item_url, a.crs, a.vertical_reference, a.value_units,"
                " a.width_px, a.height_px, a.sha256, a.size_bytes, a.window_min_x, a.window_min_y,"
                " a.window_max_x, a.window_max_y, a.validation_status, a.validated_at"
                " FROM data_asset a JOIN dataset d ON d.id = a.dataset_id LEFT JOIN region r ON r.id = a.region_id"
                " WHERE a.id = :id"
            ),
            {"id": asset_id},
        ).first()
        if row is None:
            raise ApiError(404, "not_found", f"asset {asset_id} not found")
        proc_row = conn.execute(
            text(
                "SELECT method, software, software_version, output_variable, output_crs,"
                " output_vertical_reference, output_units, script_path, script_git_commit, id"
                " FROM processing_record WHERE output_asset_id = :id"
            ),
            {"id": asset_id},
        ).first()
        processing = None
        if proc_row is not None:
            inputs = conn.execute(
                text(
                    "SELECT a.id, a.relative_path FROM processing_input pi"
                    " JOIN data_asset a ON a.id = pi.input_asset_id WHERE pi.processing_id = :pid"
                ),
                {"pid": proc_row[9]},
            ).all()
            processing = ProcessingLineage(
                method=proc_row[0], software=proc_row[1], software_version=proc_row[2], output_variable=proc_row[3],
                output_crs=proc_row[4], output_vertical_reference=proc_row[5], output_units=proc_row[6],
                script_path=proc_row[7], script_git_commit=proc_row[8],
                inputs=[ProcessingInput(asset_id=i[0], relative_path=i[1]) for i in inputs],
            )
    return Asset(
        id=row[0], dataset_code=row[1], region_code=row[2], asset_role=row[3], source_item_id=row[4],
        source_item_url=row[5], original_label_path=row[6], stac_item_url=row[7], crs=row[8],
        vertical_reference=row[9], value_units=row[10], width_px=row[11], height_px=row[12],
        checksum_sha256=row[13], size_bytes=row[14],
        acquisition_window={"min_x": row[15], "min_y": row[16], "max_x": row[17], "max_y": row[18],
                             "is_site_boundary": False},
        validation_status=row[19], validated_at=row[20], processing=processing,
    )
