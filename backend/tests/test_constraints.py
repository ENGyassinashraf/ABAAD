"""Behavioural checks on a migrated database: the constraints are enforced,
not just declared. All rows are synthetic test fixtures in a temp file."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from .conftest import raw

EARTH_WKT_ROW = (
    "INSERT INTO region_geometry (region_id, body_id, geometry_role, encoding, geometry_text, crs_code,"
    " coordinate_units, latitude_type, longitude_direction, longitude_domain, axis_order, geometry_status)"
    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
)


@pytest.fixture
def conn(migrated_db: Path) -> sqlite3.Connection:
    c = raw(migrated_db)
    c.execute("INSERT INTO planetary_body VALUES (1,'earth','Earth (test)','OGC:CRS84',6371008.8)")
    c.execute("INSERT INTO planetary_body VALUES (2,'mars','Mars (test)','IAU_2015:49900',3396190.0)")
    c.execute("INSERT INTO region (id, code, body_id, region_role, region_level, validation_status, name)"
              " VALUES (1,'test_earth',1,'analog','region','regional_only','SYNTHETIC TEST REGION')")
    c.execute("INSERT INTO region (id, code, body_id, region_role, region_level, validation_status, name)"
              " VALUES (2,'test_mars',2,'reference','region','regional_only','SYNTHETIC TEST REGION')")
    c.execute("INSERT INTO parameter VALUES (1,'test_param','SYNTHETIC TEST PARAMETER','m','scalar','D')")
    return c


def test_foreign_keys_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute("INSERT INTO region (code, body_id, region_role, region_level, validation_status, name)"
                     " VALUES ('orphan',99,'analog','region','regional_only','x')")


def test_named_check_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError, match="ck_region_validation_status_enum"):
        conn.execute("INSERT INTO region (code, body_id, region_role, region_level, validation_status, name)"
                     " VALUES ('bad',1,'analog','region','validated','x')")


def test_strict_typing_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError, match="cannot store TEXT value in REAL column"):
        conn.execute("INSERT INTO planetary_body VALUES (3,'moon','Moon','IAU_2015:30100','not-a-number')")


def test_interval_is_stored_as_bounds_without_midpoint(conn):
    conn.execute("INSERT INTO measurement (region_id, parameter_id, value_kind, interval_lower, interval_upper,"
                 " unit, evidence_grade, source_access) VALUES (1,1,'interval',2,15,'m','A','abstract_only')")
    with pytest.raises(sqlite3.IntegrityError, match="ck_measurement_interval_shape"):
        conn.execute("INSERT INTO measurement (region_id, parameter_id, value_kind, value_num, interval_lower,"
                     " interval_upper, evidence_grade, source_access, is_current)"
                     " VALUES (1,1,'interval',8.5,2,15,'A','abstract_only',0)")


def test_rfc7946_rejected_for_mars(conn):
    with pytest.raises(sqlite3.IntegrityError, match="only for Earth"):
        conn.execute(EARTH_WKT_ROW, (2, 2, "point_locator", "rfc7946_geojson",
                                     '{"type":"Point","coordinates":[0,0]}', "OGC:CRS84", "degree",
                                     "geodetic_wgs84", "east", "-180..180", "lon_lat", "approximate"))


def test_rfc7946_requires_wgs84_fields(conn):
    with pytest.raises(sqlite3.IntegrityError, match="ck_region_geometry_rfc7946_only_wgs84"):
        conn.execute(EARTH_WKT_ROW, (1, 1, "point_locator", "rfc7946_geojson",
                                     '{"type":"Point","coordinates":[0,0]}', "EPSG:3857", "metre",
                                     "not_applicable", "east", "-180..180", "x_y", "approximate"))


def test_planetary_wkt_accepted(conn):
    conn.execute(EARTH_WKT_ROW, (2, 2, "point_locator", "ogc_wkt", "POINT (45 30)", "IAU_2015:49900",
                                 "degree", "planetocentric", "east", "-180..180", "lon_lat", "approximate"))


def test_geometry_body_must_match_region(conn):
    with pytest.raises(sqlite3.IntegrityError, match="must equal the region body"):
        conn.execute(EARTH_WKT_ROW, (2, 1, "point_locator", "ogc_wkt", "POINT (0 0)", "OGC:CRS84",
                                     "degree", "geodetic_wgs84", "east", "-180..180", "lon_lat", "approximate"))


def test_measurement_and_gap_are_exclusive(conn):
    conn.execute("INSERT INTO measurement (region_id, parameter_id, value_kind, value_num, evidence_grade,"
                 " source_access) VALUES (1,1,'point',1.0,'B','dataset_opened')")
    with pytest.raises(sqlite3.IntegrityError, match="current measurement already exists"):
        conn.execute("INSERT INTO data_gap (region_id, parameter_id, reason) VALUES (1,1,'not_measured')")


def test_only_one_current_measurement(conn):
    conn.execute("INSERT INTO measurement (region_id, parameter_id, value_kind, value_num, evidence_grade,"
                 " source_access) VALUES (1,1,'point',1.0,'B','dataset_opened')")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute("INSERT INTO measurement (region_id, parameter_id, value_kind, value_num, evidence_grade,"
                     " source_access) VALUES (1,1,'point',2.0,'B','dataset_opened')")


def test_production_rejects_synthetic_rows(conn):
    with pytest.raises(sqlite3.IntegrityError, match="synthetic rows are not allowed"):
        conn.execute("INSERT INTO measurement (region_id, parameter_id, value_kind, value_num, evidence_grade,"
                     " source_access, is_synthetic) VALUES (1,1,'point',1.0,'B','dataset_opened',1)")
