"""Initial core schema: catalogue + provenance core (Phase 1 subset of R1 · 4).

All tables are SQLite STRICT; only INTEGER, REAL and TEXT column types are used.
Every constraint and trigger is explicitly named so that migration tests can
prove they survive later table rebuilds. No data is inserted.

Revision ID: 0001
Revises:
Create Date: 2026-11-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

INT, TXT, REAL = sa.Integer, sa.Text, sa.REAL
STRICT = {"sqlite_strict": True}


def _bool(col: str, table: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"{col} IN (0, 1)", name=f"ck_{table}_{col}_bool")


def _enum(col: str, table: str, values: list[str], nullable: bool = False) -> sa.CheckConstraint:
    allowed = ", ".join(f"'{v}'" for v in values)
    expr = f"{col} IN ({allowed})"
    if nullable:
        expr = f"{col} IS NULL OR {expr}"
    return sa.CheckConstraint(expr, name=f"ck_{table}_{col}_enum")


# Trigger DDL is kept as module constants; 0002 re-creates the measurement
# triggers verbatim after rebuilding that table.
TRIGGERS = {
    "trg_region_geometry_body_matches_region_ins": """
CREATE TRIGGER trg_region_geometry_body_matches_region_ins
BEFORE INSERT ON region_geometry
WHEN NEW.body_id <> (SELECT body_id FROM region WHERE id = NEW.region_id)
BEGIN SELECT RAISE(ABORT, 'region_geometry.body_id must equal the region body'); END""",
    "trg_region_geometry_body_matches_region_upd": """
CREATE TRIGGER trg_region_geometry_body_matches_region_upd
BEFORE UPDATE OF body_id, region_id ON region_geometry
WHEN NEW.body_id <> (SELECT body_id FROM region WHERE id = NEW.region_id)
BEGIN SELECT RAISE(ABORT, 'region_geometry.body_id must equal the region body'); END""",
    "trg_region_geometry_rfc7946_earth_only_ins": """
CREATE TRIGGER trg_region_geometry_rfc7946_earth_only_ins
BEFORE INSERT ON region_geometry
WHEN NEW.encoding = 'rfc7946_geojson'
 AND (SELECT code FROM planetary_body WHERE id = NEW.body_id) IS NOT 'earth'
BEGIN SELECT RAISE(ABORT, 'RFC 7946 GeoJSON is allowed only for Earth geometry'); END""",
    "trg_region_geometry_rfc7946_earth_only_upd": """
CREATE TRIGGER trg_region_geometry_rfc7946_earth_only_upd
BEFORE UPDATE OF encoding, body_id ON region_geometry
WHEN NEW.encoding = 'rfc7946_geojson'
 AND (SELECT code FROM planetary_body WHERE id = NEW.body_id) IS NOT 'earth'
BEGIN SELECT RAISE(ABORT, 'RFC 7946 GeoJSON is allowed only for Earth geometry'); END""",
}

MEASUREMENT_TRIGGERS = {
    "trg_measurement_no_gap_ins": """
CREATE TRIGGER trg_measurement_no_gap_ins
BEFORE INSERT ON measurement
WHEN NEW.is_current = 1 AND EXISTS (
  SELECT 1 FROM data_gap WHERE region_id = NEW.region_id AND parameter_id = NEW.parameter_id)
BEGIN SELECT RAISE(ABORT, 'a data_gap already exists for this region/parameter'); END""",
    "trg_measurement_no_gap_upd": """
CREATE TRIGGER trg_measurement_no_gap_upd
BEFORE UPDATE OF is_current, region_id, parameter_id ON measurement
WHEN NEW.is_current = 1 AND EXISTS (
  SELECT 1 FROM data_gap WHERE region_id = NEW.region_id AND parameter_id = NEW.parameter_id)
BEGIN SELECT RAISE(ABORT, 'a data_gap already exists for this region/parameter'); END""",
    "trg_measurement_reject_synthetic_ins": """
CREATE TRIGGER trg_measurement_reject_synthetic_ins
BEFORE INSERT ON measurement
WHEN NEW.is_synthetic = 1
BEGIN SELECT RAISE(ABORT, 'synthetic rows are not allowed in the production database'); END""",
    "trg_measurement_reject_synthetic_upd": """
CREATE TRIGGER trg_measurement_reject_synthetic_upd
BEFORE UPDATE OF is_synthetic ON measurement
WHEN NEW.is_synthetic = 1
BEGIN SELECT RAISE(ABORT, 'synthetic rows are not allowed in the production database'); END""",
}

GAP_TRIGGERS = {
    "trg_gap_no_measurement_ins": """
CREATE TRIGGER trg_gap_no_measurement_ins
BEFORE INSERT ON data_gap
WHEN EXISTS (SELECT 1 FROM measurement WHERE region_id = NEW.region_id
             AND parameter_id = NEW.parameter_id AND is_current = 1)
BEGIN SELECT RAISE(ABORT, 'a current measurement already exists for this region/parameter'); END""",
    "trg_gap_no_measurement_upd": """
CREATE TRIGGER trg_gap_no_measurement_upd
BEFORE UPDATE OF region_id, parameter_id ON data_gap
WHEN EXISTS (SELECT 1 FROM measurement WHERE region_id = NEW.region_id
             AND parameter_id = NEW.parameter_id AND is_current = 1)
BEGIN SELECT RAISE(ABORT, 'a current measurement already exists for this region/parameter'); END""",
}


def upgrade() -> None:
    op.create_table(
        "planetary_body",
        sa.Column("id", INT, primary_key=True),
        sa.Column("code", TXT, nullable=False),
        sa.Column("name", TXT, nullable=False),
        sa.Column("default_crs_code", TXT, nullable=False),
        sa.Column("mean_radius_m", REAL, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_planetary_body"),
        sa.UniqueConstraint("code", name="uq_planetary_body_code"),
        sa.CheckConstraint("mean_radius_m > 0", name="ck_planetary_body_radius_positive"),
        **STRICT,
    )

    op.create_table(
        "publication",
        sa.Column("id", INT, primary_key=True),
        sa.Column("doi", TXT, nullable=True),
        sa.Column("title", TXT, nullable=False),
        sa.Column("year", INT, nullable=True),
        sa.Column("source_access", TXT, nullable=False),
        sa.Column("peer_reviewed", INT, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_publication"),
        sa.UniqueConstraint("doi", name="uq_publication_doi"),
        _enum("source_access", "publication", ["full_text_checked", "abstract_only", "secondary_record"]),
        _bool("peer_reviewed", "publication"),
        **STRICT,
    )

    op.create_table(
        "region",
        sa.Column("id", INT, primary_key=True),
        sa.Column("code", TXT, nullable=False),
        sa.Column("body_id", INT, nullable=False),
        sa.Column("region_role", TXT, nullable=False),
        sa.Column("parent_region_id", INT, nullable=True),
        sa.Column("region_level", TXT, nullable=False),
        sa.Column("validation_status", TXT, nullable=False),
        sa.Column("name", TXT, nullable=False),
        sa.Column("description", TXT, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_region"),
        sa.UniqueConstraint("code", name="uq_region_code"),
        sa.ForeignKeyConstraint(["body_id"], ["planetary_body.id"], name="fk_region_body_id_planetary_body"),
        sa.ForeignKeyConstraint(["parent_region_id"], ["region.id"], name="fk_region_parent_region_id_region"),
        _enum("region_role", "region", ["reference", "analog"]),
        _enum("region_level", "region", ["region", "subregion", "feature"]),
        _enum("validation_status", "region", ["site_confirmed", "validation_pending", "regional_only"]),
        sa.CheckConstraint("parent_region_id IS NULL OR parent_region_id <> id", name="ck_region_not_own_parent"),
        **STRICT,
    )
    op.create_index("ix_region_body_id", "region", ["body_id"])
    op.create_index("ix_region_parent_region_id", "region", ["parent_region_id"])

    op.create_table(
        "region_geometry",
        sa.Column("id", INT, primary_key=True),
        sa.Column("region_id", INT, nullable=False),
        sa.Column("body_id", INT, nullable=False),
        sa.Column("geometry_role", TXT, nullable=False),
        sa.Column("encoding", TXT, nullable=False),
        sa.Column("geometry_text", TXT, nullable=True),
        sa.Column("crs_code", TXT, nullable=False),
        sa.Column("coordinate_units", TXT, nullable=False),
        sa.Column("latitude_type", TXT, nullable=False),
        sa.Column("longitude_direction", TXT, nullable=False),
        sa.Column("longitude_domain", TXT, nullable=False),
        sa.Column("axis_order", TXT, nullable=False),
        sa.Column("min_x", REAL, nullable=True),
        sa.Column("min_y", REAL, nullable=True),
        sa.Column("max_x", REAL, nullable=True),
        sa.Column("max_y", REAL, nullable=True),
        sa.Column("geometry_status", TXT, nullable=False),
        sa.Column("source_publication_id", INT, nullable=True),
        sa.Column("source_locator", TXT, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_region_geometry"),
        sa.ForeignKeyConstraint(["region_id"], ["region.id"], name="fk_region_geometry_region_id_region", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["body_id"], ["planetary_body.id"], name="fk_region_geometry_body_id_planetary_body"),
        sa.ForeignKeyConstraint(["source_publication_id"], ["publication.id"], name="fk_region_geometry_source_publication_id_publication"),
        _enum("geometry_role", "region_geometry", ["outline", "point_locator", "traverse"]),
        _enum("encoding", "region_geometry", ["rfc7946_geojson", "ogc_wkt"]),
        _enum("coordinate_units", "region_geometry", ["degree", "metre"]),
        _enum("latitude_type", "region_geometry", ["geodetic_wgs84", "planetocentric", "planetographic", "not_applicable"]),
        _enum("longitude_direction", "region_geometry", ["east", "west", "not_applicable"]),
        _enum("longitude_domain", "region_geometry", ["-180..180", "0..360", "not_applicable"]),
        _enum("axis_order", "region_geometry", ["lon_lat", "lat_lon", "x_y"]),
        _enum("geometry_status", "region_geometry", ["source_traced", "approximate", "undefined"]),
        sa.CheckConstraint(
            "encoding <> 'rfc7946_geojson' OR (crs_code = 'OGC:CRS84' AND coordinate_units = 'degree'"
            " AND latitude_type = 'geodetic_wgs84' AND axis_order = 'lon_lat')",
            name="ck_region_geometry_rfc7946_only_wgs84",
        ),
        sa.CheckConstraint(
            "geometry_status = 'undefined' OR geometry_text IS NOT NULL",
            name="ck_region_geometry_text_unless_undefined",
        ),
        sa.CheckConstraint(
            "geometry_status <> 'source_traced' OR source_publication_id IS NOT NULL",
            name="ck_region_geometry_traced_has_source",
        ),
        sa.CheckConstraint(
            "(min_x IS NULL AND min_y IS NULL AND max_x IS NULL AND max_y IS NULL) OR "
            "(min_x <= max_x AND min_y <= max_y)",
            name="ck_region_geometry_extent_order",
        ),
        **STRICT,
    )
    op.create_index("ix_region_geometry_region_id", "region_geometry", ["region_id"])

    op.create_table(
        "parameter",
        sa.Column("id", INT, primary_key=True),
        sa.Column("code", TXT, nullable=False),
        sa.Column("name", TXT, nullable=False),
        sa.Column("canonical_unit", TXT, nullable=True),
        sa.Column("value_type", TXT, nullable=False),
        sa.Column("comparison_class", TXT, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_parameter"),
        sa.UniqueConstraint("code", name="uq_parameter_code"),
        _enum("value_type", "parameter", ["scalar", "angle_full", "angle_axial", "distribution", "category"]),
        _enum("comparison_class", "parameter", ["D", "M", "C", "N"]),
        **STRICT,
    )

    op.create_table(
        "measurement",
        sa.Column("id", INT, primary_key=True),
        sa.Column("region_id", INT, nullable=False),
        sa.Column("parameter_id", INT, nullable=False),
        sa.Column("value_kind", TXT, nullable=False),
        sa.Column("value_num", REAL, nullable=True),
        sa.Column("interval_lower", REAL, nullable=True),
        sa.Column("interval_upper", REAL, nullable=True),
        sa.Column("value_text", TXT, nullable=True),
        sa.Column("unit", TXT, nullable=True),
        sa.Column("point_uncertainty_type", TXT, nullable=True),
        sa.Column("point_uncertainty", REAL, nullable=True),
        sa.Column("evidence_grade", TXT, nullable=False),
        sa.Column("source_access", TXT, nullable=False),
        sa.Column("is_current", INT, nullable=False, server_default=sa.text("1")),
        sa.Column("is_synthetic", INT, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", TXT, nullable=False, server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%SZ','now'))")),
        sa.PrimaryKeyConstraint("id", name="pk_measurement"),
        sa.ForeignKeyConstraint(["region_id"], ["region.id"], name="fk_measurement_region_id_region"),
        sa.ForeignKeyConstraint(["parameter_id"], ["parameter.id"], name="fk_measurement_parameter_id_parameter"),
        _enum("value_kind", "measurement", ["point", "interval", "category", "distribution"]),
        _enum("point_uncertainty_type", "measurement", ["sd", "plus_minus", "ci95", "none_reported"], nullable=True),
        _enum("evidence_grade", "measurement", ["A", "B", "C", "D"]),
        _enum("source_access", "measurement",
              ["full_text_checked", "abstract_only", "secondary_record", "dataset_opened", "raw_data_unavailable"]),
        _bool("is_current", "measurement"),
        _bool("is_synthetic", "measurement"),
        sa.CheckConstraint(
            "value_kind <> 'point' OR (value_num IS NOT NULL AND interval_lower IS NULL AND interval_upper IS NULL)",
            name="ck_measurement_point_shape",
        ),
        sa.CheckConstraint(
            "value_kind <> 'interval' OR (interval_lower IS NOT NULL AND interval_upper IS NOT NULL"
            " AND interval_lower <= interval_upper AND value_num IS NULL"
            " AND point_uncertainty IS NULL AND point_uncertainty_type IS NULL)",
            name="ck_measurement_interval_shape",
        ),
        sa.CheckConstraint(
            "value_kind <> 'category' OR value_text IS NOT NULL",
            name="ck_measurement_category_shape",
        ),
        **STRICT,
    )
    op.create_index("ix_measurement_region_id_parameter_id", "measurement", ["region_id", "parameter_id"])
    op.create_index(
        "uq_measurement_current_region_parameter",
        "measurement",
        ["region_id", "parameter_id"],
        unique=True,
        sqlite_where=sa.text("is_current = 1"),
    )

    op.create_table(
        "measurement_source",
        sa.Column("id", INT, primary_key=True),
        sa.Column("measurement_id", INT, nullable=False),
        sa.Column("source_kind", TXT, nullable=False),
        sa.Column("publication_id", INT, nullable=True),
        sa.Column("role", TXT, nullable=False),
        sa.Column("locator", TXT, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_measurement_source"),
        sa.ForeignKeyConstraint(["measurement_id"], ["measurement.id"], name="fk_measurement_source_measurement_id_measurement", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["publication_id"], ["publication.id"], name="fk_measurement_source_publication_id_publication"),
        # Phase 1 subset: only publication sources. Dataset/file/derivation-run
        # sources arrive with the data layer in Phase 2.
        _enum("source_kind", "measurement_source", ["publication"]),
        _enum("role", "measurement_source", ["primary", "supporting"]),
        sa.CheckConstraint(
            "(source_kind = 'publication') = (publication_id IS NOT NULL)",
            name="ck_measurement_source_one_source",
        ),
        **STRICT,
    )
    op.create_index("ix_measurement_source_measurement_id", "measurement_source", ["measurement_id"])

    op.create_table(
        "data_gap",
        sa.Column("id", INT, primary_key=True),
        sa.Column("region_id", INT, nullable=False),
        sa.Column("parameter_id", INT, nullable=False),
        sa.Column("reason", TXT, nullable=False),
        sa.Column("note", TXT, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_data_gap"),
        sa.UniqueConstraint("region_id", "parameter_id", name="uq_data_gap_region_id_parameter_id"),
        sa.ForeignKeyConstraint(["region_id"], ["region.id"], name="fk_data_gap_region_id_region"),
        sa.ForeignKeyConstraint(["parameter_id"], ["parameter.id"], name="fk_data_gap_parameter_id_parameter"),
        _enum("reason", "data_gap",
              ["not_measured", "not_public", "resolution_inadequate", "not_applicable", "not_yet_curated"]),
        **STRICT,
    )

    for ddl in (TRIGGERS | MEASUREMENT_TRIGGERS | GAP_TRIGGERS).values():
        op.execute(ddl)


def downgrade() -> None:
    for name in (TRIGGERS | MEASUREMENT_TRIGGERS | GAP_TRIGGERS):
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    for table in (
        "data_gap",
        "measurement_source",
        "measurement",
        "parameter",
        "region_geometry",
        "region",
        "publication",
        "planetary_body",
    ):
        op.drop_table(table)
