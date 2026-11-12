"""Regression tests for the Phase 2 pre-merge hardening pass (see
docs/reports/PHASE2_COMPLETION.md, findings F-01, F-02, F-05). All rows are
synthetic test fixtures in a temp database; migrated_db is already at head
(0005, seeded with the three planetary bodies and seven research tasks)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from .conftest import raw


@pytest.fixture
def conn(migrated_db: Path) -> sqlite3.Connection:
    c = raw(migrated_db)
    c.execute("INSERT INTO region (id, code, body_id, region_role, region_level, validation_status, name)"
              " VALUES (1,'test_earth',1,'analog','region','regional_only','SYNTHETIC TEST REGION')")
    c.execute("INSERT INTO region (id, code, body_id, region_role, region_level, validation_status, name)"
              " VALUES (2,'test_mars',2,'reference','region','regional_only','SYNTHETIC TEST REGION')")
    c.execute("INSERT INTO region (id, code, body_id, region_role, region_level, validation_status, name)"
              " VALUES (3,'test_moon',3,'reference','region','regional_only','SYNTHETIC TEST REGION')")
    return c


def _claim_sql(reference_region_id, reference_body_id, task_id=1, analog_id=1, claim_class="B"):
    return (
        "INSERT INTO site_task_claim (analog_region_id, task_id, reference_region_id, reference_body_id,"
        " claim_evidence_class, reference_pairing_basis, supported_claim, similarities, differences,"
        " not_supported, spatial_scale, limitations)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (analog_id, task_id,
         reference_region_id, reference_body_id, claim_class,
         "body_level_only" if reference_region_id is None else "region_specific_in_source",
         "x", "x", "x", "x", "x", "x"),
    )


# --- F-01: claim <-> body <-> task matrix ------------------------------------

def test_reference_body_cannot_be_earth(conn):
    sql, params = _claim_sql(None, 1)  # body_id=1 is earth
    with pytest.raises(sqlite3.IntegrityError, match="must not be Earth"):
        conn.execute(sql, params)


def test_reference_body_must_match_task_applies_to(conn):
    # task_id=1 is 'aeolian_geomorphology', applies_to='mars'; reference_body_id=3 is moon.
    sql, params = _claim_sql(None, 3)
    with pytest.raises(sqlite3.IntegrityError, match="allowed by research_task.applies_to"):
        conn.execute(sql, params)


def test_reference_body_matches_mars_task_accepted(conn):
    sql, params = _claim_sql(None, 2)  # mars, matches the task
    conn.execute(sql, params)


def test_reference_region_body_must_match_reference_body(conn):
    # reference_region_id=2 is mars, but reference_body_id passed is... must mismatch to fail.
    # Use region 3 (moon) as reference_region but body_id=2 (mars) as reference_body: mismatch.
    sql, params = _claim_sql(3, 2)
    with pytest.raises(sqlite3.IntegrityError, match="must match reference_region_id"):
        conn.execute(sql, params)


def test_reference_region_body_match_accepted(conn):
    sql, params = _claim_sql(2, 2)  # region 2 and body 2 are both mars
    conn.execute(sql, params)


def test_matrix_enforced_on_update_too(conn):
    sql, params = _claim_sql(None, 2)
    conn.execute(sql, params)
    claim_id = conn.execute("SELECT id FROM site_task_claim").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="must not be Earth"):
        conn.execute("UPDATE site_task_claim SET reference_body_id = 1 WHERE id = ?", (claim_id,))


def test_region_body_immutable_once_claimed(conn):
    sql, params = _claim_sql(None, 2)
    conn.execute(sql, params)
    with pytest.raises(sqlite3.IntegrityError, match="cannot change while a site_task_claim references"):
        conn.execute("UPDATE region SET body_id = 2 WHERE id = 1")


def test_region_role_immutable_once_claimed(conn):
    sql, params = _claim_sql(None, 2)
    conn.execute(sql, params)
    with pytest.raises(sqlite3.IntegrityError, match="cannot change while a site_task_claim references"):
        conn.execute("UPDATE region SET region_role = 'reference' WHERE id = 1")


def test_region_edit_allowed_when_not_claimed(conn):
    conn.execute("UPDATE region SET region_role = 'reference' WHERE id = 1")


def test_research_task_applies_to_immutable_once_claimed(conn):
    sql, params = _claim_sql(None, 2)
    conn.execute(sql, params)
    with pytest.raises(sqlite3.IntegrityError, match="cannot change while a site_task_claim references"):
        conn.execute("UPDATE research_task SET applies_to = 'moon' WHERE id = 1")


# --- F-02: dataset CRS is never forced, and gates validated assets -----------

DATASET_SQL = (
    "INSERT INTO dataset (code, provider, product_id, product_name, product_version, body_id, variable,"
    " surface_type, horizontal_crs, horizontal_crs_status, vertical_reference, value_units,"
    " native_resolution_value, native_resolution_unit, file_format, licence_summary, access_conditions, source_url)"
    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)


def test_dataset_accepts_pending_crs_with_null_horizontal_crs(conn):
    conn.execute(DATASET_SQL, (
        "TEST-DS", "test", "p1", "Test product", "v1", 2, "topography", "altimetry_grid",
        None, "pending", "height", "metre", 1, "pixel_per_degree", "IMG", "open", "x", "https://x",
    ))


def test_dataset_rejects_verified_without_horizontal_crs(conn):
    with pytest.raises(sqlite3.IntegrityError, match="ck_dataset_crs_status_shape"):
        conn.execute(DATASET_SQL, (
            "TEST-DS", "test", "p1", "Test product", "v1", 2, "topography", "altimetry_grid",
            None, "verified", "height", "metre", 1, "pixel_per_degree", "IMG", "open", "x", "https://x",
        ))


def test_dataset_no_longer_forces_mars_crs_family(conn):
    """F-02: a Mars dataset may now be 'verified' with a non-IAU_2015:49* CRS
    (e.g. a product-specific definition) -- the old forcing trigger is gone."""
    conn.execute(DATASET_SQL, (
        "TEST-DS", "test", "p1", "Test product", "v1", 2, "topography", "altimetry_grid",
        "SOME:PRODUCT_SPECIFIC_CRS", "verified", "height", "metre", 1, "pixel_per_degree", "IMG", "open", "x", "https://x",
    ))


ASSET_SQL = (
    "INSERT INTO data_asset (dataset_id, region_id, asset_role, relative_path, file_format, sha256, size_bytes,"
    " downloaded_at, source_item_id, source_item_url, crs, vertical_reference, value_units, width_px, height_px,"
    " pixel_size_x, pixel_size_y, dtype, window_min_x, window_min_y, window_max_x, window_max_y, validation_status)"
    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)
SHA = "0" * 64


def _insert_pending_dataset(conn, body_id=2) -> int:
    conn.execute(DATASET_SQL, (
        "TEST-DS", "test", "p1", "Test product", "v1", body_id, "topography", "altimetry_grid",
        None, "pending", "height", "metre", 1, "pixel_per_degree", "IMG", "open", "x", "https://x",
    ))
    return conn.execute("SELECT id FROM dataset WHERE code='TEST-DS'").fetchone()[0]


def test_asset_cannot_be_validated_against_pending_crs_dataset(conn):
    dataset_id = _insert_pending_dataset(conn)
    with pytest.raises(sqlite3.IntegrityError, match="horizontal_crs_status is not verified"):
        conn.execute(ASSET_SQL, (
            dataset_id, None, "original", "data/raw/x.tif", "GeoTIFF", SHA, 10, "2026-11-12T00:00:00Z",
            "x", "https://x", "IAU_2015:49900", "radius", "metre", 10, 10, 1, 1, "float32", 0, 0, 1, 1, "validated",
        ))


def test_asset_unvalidated_allowed_against_pending_crs_dataset(conn):
    dataset_id = _insert_pending_dataset(conn)
    conn.execute(ASSET_SQL, (
        dataset_id, None, "original", "data/raw/x.tif", "GeoTIFF", SHA, 10, "2026-11-12T00:00:00Z",
        "x", "https://x", "IAU_2015:49900", "radius", "metre", 10, 10, 1, 1, "float32", 0, 0, 1, 1, "unvalidated",
    ))


def test_asset_region_body_must_match_dataset_body(conn):
    dataset_id = _insert_pending_dataset(conn, body_id=2)  # mars
    with pytest.raises(sqlite3.IntegrityError, match="same body as its dataset"):
        conn.execute(ASSET_SQL, (
            dataset_id, 1, "original", "data/raw/x.tif", "GeoTIFF", SHA, 10, "2026-11-12T00:00:00Z",  # region 1 is earth
            "x", "https://x", "IAU_2015:49900", "radius", "metre", 10, 10, 1, 1, "float32", 0, 0, 1, 1, "unvalidated",
        ))


def test_asset_validated_requires_timestamp_still_enforced(conn):
    dataset_id = _insert_pending_dataset(conn)
    conn.execute(
        "UPDATE dataset SET horizontal_crs='IAU_2015:49900', horizontal_crs_status='verified' WHERE id=?",
        (dataset_id,),
    )
    with pytest.raises(sqlite3.IntegrityError, match="ck_data_asset_validated_has_timestamp"):
        conn.execute(ASSET_SQL, (
            # vertical_reference/value_units deliberately match the dataset's
            # ("height"/"metre") so only the missing-timestamp CHECK fires.
            dataset_id, None, "original", "data/raw/x.tif", "GeoTIFF", SHA, 10, "2026-11-12T00:00:00Z",
            "x", "https://x", "IAU_2015:49900", "height", "metre", 10, 10, 1, 1, "float32", 0, 0, 1, 1, "validated",
        ))
