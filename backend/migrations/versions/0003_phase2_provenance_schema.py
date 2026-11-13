"""Phase 2: provenance schema — region aliases, research tasks, site-task
claims, datasets/assets/processing lineage and coverage gaps.

Rebuilds (batch, ``recreate="always"``) four Phase 1 tables to add columns:
``publication``, ``region``, ``region_geometry``, ``measurement_source``.
Every trigger that references any of these four tables is dropped first and
re-created afterwards (Phase 1 finding P1-12/P1-13), together with the new
Phase 2 triggers.

Phase 2 correction (this session, overriding the Phase 1 §4.1 wording of
``claim_evidence_class``): class ``A`` requires the claim's ``supports``
source to be ``full_text_checked``; a source read only at ``abstract_only``
or ``secondary_record`` can never carry class A. This is enforced here at
the only point a trigger can see both rows together: the moment a claim is
moved to ``published``. The curation loader (``scripts/load_curation.py``)
enforces the same rule at load time for every claim regardless of state, so
a non-published class-A claim cannot reach the database with abstract-only
support either.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
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


# Triggers from 0001 that touch region_geometry / region / planetary_body and
# therefore must be dropped before, and re-created after, the batch rebuilds
# of publication / region / region_geometry / measurement_source below.
PHASE1_REBUILD_TRIGGERS = {
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

# New Phase 2 triggers.
PHASE2_TRIGGERS = {
    "trg_region_country_earth_only_ins": """
CREATE TRIGGER trg_region_country_earth_only_ins
BEFORE INSERT ON region
WHEN NEW.country_code IS NOT NULL
 AND (SELECT code FROM planetary_body WHERE id = NEW.body_id) IS NOT 'earth'
BEGIN SELECT RAISE(ABORT, 'region.country_code is only valid for Earth regions'); END""",
    "trg_region_country_earth_only_upd": """
CREATE TRIGGER trg_region_country_earth_only_upd
BEFORE UPDATE OF country_code, body_id ON region
WHEN NEW.country_code IS NOT NULL
 AND (SELECT code FROM planetary_body WHERE id = NEW.body_id) IS NOT 'earth'
BEGIN SELECT RAISE(ABORT, 'region.country_code is only valid for Earth regions'); END""",
    "trg_region_geometry_dataset_body_ins": """
CREATE TRIGGER trg_region_geometry_dataset_body_ins
BEFORE INSERT ON region_geometry
WHEN NEW.source_dataset_id IS NOT NULL
 AND (SELECT body_id FROM dataset WHERE id = NEW.source_dataset_id) <> NEW.body_id
BEGIN SELECT RAISE(ABORT, 'region_geometry.source_dataset_id must be for the same body'); END""",
    "trg_region_geometry_dataset_body_upd": """
CREATE TRIGGER trg_region_geometry_dataset_body_upd
BEFORE UPDATE OF source_dataset_id, body_id ON region_geometry
WHEN NEW.source_dataset_id IS NOT NULL
 AND (SELECT body_id FROM dataset WHERE id = NEW.source_dataset_id) <> NEW.body_id
BEGIN SELECT RAISE(ABORT, 'region_geometry.source_dataset_id must be for the same body'); END""",
    "trg_claim_roles_ins": """
CREATE TRIGGER trg_claim_roles_ins
BEFORE INSERT ON site_task_claim
WHEN (SELECT body_id FROM region WHERE id = NEW.analog_region_id)
       <> (SELECT id FROM planetary_body WHERE code = 'earth')
 OR (SELECT region_role FROM region WHERE id = NEW.analog_region_id) <> 'analog'
 OR (NEW.reference_region_id IS NOT NULL AND (
       (SELECT region_role FROM region WHERE id = NEW.reference_region_id) <> 'reference'
       OR (SELECT body_id FROM region WHERE id = NEW.reference_region_id)
            = (SELECT id FROM planetary_body WHERE code = 'earth')))
BEGIN SELECT RAISE(ABORT,
  'analog_region must be an Earth region with role analog; reference_region (if set) must have role reference and must not be Earth'); END""",
    "trg_claim_roles_upd": """
CREATE TRIGGER trg_claim_roles_upd
BEFORE UPDATE OF analog_region_id, reference_region_id ON site_task_claim
WHEN (SELECT body_id FROM region WHERE id = NEW.analog_region_id)
       <> (SELECT id FROM planetary_body WHERE code = 'earth')
 OR (SELECT region_role FROM region WHERE id = NEW.analog_region_id) <> 'analog'
 OR (NEW.reference_region_id IS NOT NULL AND (
       (SELECT region_role FROM region WHERE id = NEW.reference_region_id) <> 'reference'
       OR (SELECT body_id FROM region WHERE id = NEW.reference_region_id)
            = (SELECT id FROM planetary_body WHERE code = 'earth')))
BEGIN SELECT RAISE(ABORT,
  'analog_region must be an Earth region with role analog; reference_region (if set) must have role reference and must not be Earth'); END""",
    # Publish gate: a `supports` source must exist; class A needs that source to be a
    # peer-reviewed publication AND full_text_checked (session correction: never A from
    # an abstract alone); class B needs a program page, data release or peer-reviewed
    # publication; class C can never publish (also enforced by a CHECK constraint).
    "trg_claim_publish_requires_support_ins": """
CREATE TRIGGER trg_claim_publish_requires_support_ins
BEFORE INSERT ON site_task_claim
WHEN NEW.publication_state = 'published'
 AND NOT EXISTS (
   SELECT 1 FROM site_task_claim_source s JOIN publication p ON p.id = s.publication_id
   WHERE s.claim_id = NEW.id AND s.role = 'supports'
     AND (NEW.claim_evidence_class <> 'A' OR (p.peer_reviewed = 1 AND p.source_access = 'full_text_checked'))
     AND (NEW.claim_evidence_class <> 'B'
          OR p.source_type IN ('program_page', 'data_release') OR p.peer_reviewed = 1))
BEGIN SELECT RAISE(ABORT,
  'published claim needs a qualifying supports source for its evidence class'); END""",
    "trg_claim_publish_requires_support_upd": """
CREATE TRIGGER trg_claim_publish_requires_support_upd
BEFORE UPDATE OF publication_state ON site_task_claim
WHEN NEW.publication_state = 'published'
 AND NOT EXISTS (
   SELECT 1 FROM site_task_claim_source s JOIN publication p ON p.id = s.publication_id
   WHERE s.claim_id = NEW.id AND s.role = 'supports'
     AND (NEW.claim_evidence_class <> 'A' OR (p.peer_reviewed = 1 AND p.source_access = 'full_text_checked'))
     AND (NEW.claim_evidence_class <> 'B'
          OR p.source_type IN ('program_page', 'data_release') OR p.peer_reviewed = 1))
BEGIN SELECT RAISE(ABORT,
  'published claim needs a qualifying supports source for its evidence class'); END""",
    "trg_dataset_crs_matches_body_ins": """
CREATE TRIGGER trg_dataset_crs_matches_body_ins
BEFORE INSERT ON dataset
WHEN (
  (SELECT code FROM planetary_body WHERE id = NEW.body_id) = 'mars'
    AND NEW.horizontal_crs NOT LIKE 'IAU_2015:49%'
) OR (
  (SELECT code FROM planetary_body WHERE id = NEW.body_id) = 'moon'
    AND NEW.horizontal_crs NOT LIKE 'IAU_2015:30%'
) OR (
  (SELECT code FROM planetary_body WHERE id = NEW.body_id) = 'earth'
    AND NEW.horizontal_crs LIKE 'IAU_%'
)
BEGIN SELECT RAISE(ABORT, 'dataset.horizontal_crs does not match the dataset body'); END""",
    "trg_dataset_crs_matches_body_upd": """
CREATE TRIGGER trg_dataset_crs_matches_body_upd
BEFORE UPDATE OF horizontal_crs, body_id ON dataset
WHEN (
  (SELECT code FROM planetary_body WHERE id = NEW.body_id) = 'mars'
    AND NEW.horizontal_crs NOT LIKE 'IAU_2015:49%'
) OR (
  (SELECT code FROM planetary_body WHERE id = NEW.body_id) = 'moon'
    AND NEW.horizontal_crs NOT LIKE 'IAU_2015:30%'
) OR (
  (SELECT code FROM planetary_body WHERE id = NEW.body_id) = 'earth'
    AND NEW.horizontal_crs LIKE 'IAU_%'
)
BEGIN SELECT RAISE(ABORT, 'dataset.horizontal_crs does not match the dataset body'); END""",
    "trg_processing_input_same_body_ins": """
CREATE TRIGGER trg_processing_input_same_body_ins
BEFORE INSERT ON processing_input
WHEN (SELECT d2.body_id FROM data_asset a2 JOIN dataset d2 ON d2.id = a2.dataset_id
      WHERE a2.id = NEW.input_asset_id)
     <> (SELECT d1.body_id FROM processing_record r JOIN data_asset a1 ON a1.id = r.output_asset_id
         JOIN dataset d1 ON d1.id = a1.dataset_id WHERE r.id = NEW.processing_id)
BEGIN SELECT RAISE(ABORT, 'processing_input: input and output assets must belong to the same body'); END""",
}


def _create_dataset_and_rest(body_check: dict[str, sa.CheckConstraint]) -> None:
    pass


def upgrade() -> None:
    # 1) Drop every trigger that will break when publication / region /
    #    region_geometry / measurement_source are renamed during the batch rebuilds.
    for name in PHASE1_REBUILD_TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")

    # 2) publication: add columns (all nullable so Phase 1 rows, if any, survive).
    with op.batch_alter_table("publication", recreate="always", table_kwargs=STRICT) as batch:
        batch.add_column(sa.Column("source_type", TXT, nullable=True))
        batch.add_column(sa.Column("authors", TXT, nullable=True))
        batch.add_column(sa.Column("institution", TXT, nullable=True))
        batch.add_column(sa.Column("url", TXT, nullable=True))
        batch.add_column(sa.Column("licence", TXT, nullable=True))
        batch.add_column(sa.Column("citation", TXT, nullable=True))
        batch.add_column(sa.Column("accessed_on", TXT, nullable=True))
        batch.create_check_constraint(
            "ck_publication_source_type_enum",
            "source_type IS NULL OR source_type IN "
            "('journal_article','conference_abstract','data_release','program_page','product_page')",
        )
        batch.create_check_constraint("ck_publication_doi_or_url", "doi IS NOT NULL OR url IS NOT NULL")

    # 3) region: add columns.
    with op.batch_alter_table("region", recreate="always", table_kwargs=STRICT) as batch:
        batch.add_column(sa.Column("country_code", TXT, nullable=True))
        batch.add_column(sa.Column("site_type", TXT, nullable=True))
        batch.add_column(
            sa.Column("origin_status", TXT, nullable=False, server_default=sa.text("'not_applicable'"))
        )
        batch.create_check_constraint(
            "ck_region_country_code_shape",
            "country_code IS NULL OR (length(country_code) = 2 AND country_code = upper(country_code))",
        )
        batch.create_check_constraint(
            "ck_region_origin_status_enum",
            "origin_status IN ('not_applicable','confirmed','disputed','unresolved')",
        )

    # 4) region_geometry: add columns; replace the "traced has source" rule with the
    #    stricter "no source, no geometry" rule (source + method + uncertainty note
    #    for every geometry that is not 'undefined').
    with op.batch_alter_table("region_geometry", recreate="always", table_kwargs=STRICT) as batch:
        batch.add_column(sa.Column("geometry_method", TXT, nullable=True))
        batch.add_column(sa.Column("positional_uncertainty_m", REAL, nullable=True))
        batch.add_column(sa.Column("uncertainty_note", TXT, nullable=True))
        batch.add_column(sa.Column("source_dataset_id", INT, nullable=True))
        batch.create_check_constraint(
            "ck_region_geometry_geometry_method_enum",
            "geometry_method IS NULL OR geometry_method IN "
            "('published_coordinates','published_bounds','digitized_figure','dataset_extent','gazetteer_entry')",
        )
        batch.create_check_constraint(
            "ck_region_geometry_positional_uncertainty_nonneg", "positional_uncertainty_m IS NULL OR positional_uncertainty_m >= 0"
        )
        batch.drop_constraint("ck_region_geometry_traced_has_source", type_="check")
        batch.create_check_constraint(
            "ck_region_geometry_has_source_method_note",
            "geometry_status = 'undefined' OR ("
            "(source_publication_id IS NOT NULL OR source_dataset_id IS NOT NULL)"
            " AND geometry_method IS NOT NULL AND uncertainty_note IS NOT NULL)",
        )
        batch.create_foreign_key(
            "fk_region_geometry_source_dataset_id_dataset", "dataset", ["source_dataset_id"], ["id"]
        )

    # 5) measurement_source: source_kind gains 'data_asset'; one matching id column.
    with op.batch_alter_table("measurement_source", recreate="always", table_kwargs=STRICT) as batch:
        batch.add_column(sa.Column("data_asset_id", INT, nullable=True))
        batch.drop_constraint("ck_measurement_source_source_kind_enum", type_="check")
        batch.create_check_constraint(
            "ck_measurement_source_source_kind_enum", "source_kind IN ('publication', 'data_asset')"
        )
        batch.drop_constraint("ck_measurement_source_one_source", type_="check")
        batch.create_check_constraint(
            "ck_measurement_source_one_source",
            "(source_kind = 'publication') = (publication_id IS NOT NULL) AND "
            "(source_kind = 'data_asset') = (data_asset_id IS NOT NULL)",
        )
        batch.create_foreign_key(
            "fk_measurement_source_data_asset_id_data_asset", "data_asset", ["data_asset_id"], ["id"]
        )

    # 6) New tables (order matters for foreign keys).
    op.create_table(
        "region_alias",
        sa.Column("id", INT, primary_key=True),
        sa.Column("region_id", INT, nullable=False),
        sa.Column("alias", TXT, nullable=False),
        sa.Column("alias_kind", TXT, nullable=False),
        sa.Column("language", TXT, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_region_alias"),
        sa.UniqueConstraint("region_id", "alias", name="uq_region_alias_region_id_alias"),
        sa.ForeignKeyConstraint(["region_id"], ["region.id"], name="fk_region_alias_region_id_region", ondelete="CASCADE"),
        _enum("alias_kind", "region_alias", ["legacy", "alternate", "local_language", "transliteration"]),
        **STRICT,
    )

    op.create_table(
        "research_task",
        sa.Column("id", INT, primary_key=True),
        sa.Column("code", TXT, nullable=False),
        sa.Column("name", TXT, nullable=False),
        sa.Column("description", TXT, nullable=False),
        sa.Column("applies_to", TXT, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_research_task"),
        sa.UniqueConstraint("code", name="uq_research_task_code"),
        _enum("applies_to", "research_task", ["mars", "moon", "both"]),
        **STRICT,
    )

    op.create_table(
        "site_task_claim",
        sa.Column("id", INT, primary_key=True),
        sa.Column("analog_region_id", INT, nullable=False),
        sa.Column("task_id", INT, nullable=False),
        sa.Column("reference_region_id", INT, nullable=True),
        sa.Column("claim_evidence_class", TXT, nullable=False),
        sa.Column("reference_pairing_basis", TXT, nullable=False),
        sa.Column("supported_claim", TXT, nullable=False),
        sa.Column("similarities", TXT, nullable=False),
        sa.Column("differences", TXT, nullable=False),
        sa.Column("not_supported", TXT, nullable=False),
        sa.Column("spatial_scale", TXT, nullable=False),
        sa.Column("limitations", TXT, nullable=False),
        sa.Column("publication_state", TXT, nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_at", TXT, nullable=False, server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%SZ','now'))")),
        sa.PrimaryKeyConstraint("id", name="pk_site_task_claim"),
        sa.ForeignKeyConstraint(["analog_region_id"], ["region.id"], name="fk_site_task_claim_analog_region_id_region"),
        sa.ForeignKeyConstraint(["task_id"], ["research_task.id"], name="fk_site_task_claim_task_id_research_task"),
        sa.ForeignKeyConstraint(["reference_region_id"], ["region.id"], name="fk_site_task_claim_reference_region_id_region"),
        _enum("claim_evidence_class", "site_task_claim", ["A", "B", "C"]),
        _enum(
            "reference_pairing_basis", "site_task_claim",
            ["region_specific_in_source", "project_decision_provisional", "body_level_only"],
        ),
        _enum("publication_state", "site_task_claim", ["draft", "reviewed", "published"]),
        sa.CheckConstraint(
            "(reference_pairing_basis = 'body_level_only') = (reference_region_id IS NULL)",
            name="ck_site_task_claim_pairing_shape",
        ),
        sa.CheckConstraint(
            "claim_evidence_class <> 'C' OR publication_state <> 'published'",
            name="ck_site_task_claim_class_c_never_published",
        ),
        **STRICT,
    )
    op.create_index(
        "uq_site_task_claim_analog_task_reference",
        "site_task_claim",
        ["analog_region_id", "task_id", "reference_region_id"],
        unique=True,
    )

    op.create_table(
        "site_task_claim_source",
        sa.Column("id", INT, primary_key=True),
        sa.Column("claim_id", INT, nullable=False),
        sa.Column("publication_id", INT, nullable=False),
        sa.Column("role", TXT, nullable=False),
        sa.Column("locator", TXT, nullable=True),
        sa.Column("note", TXT, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_site_task_claim_source"),
        sa.UniqueConstraint(
            "claim_id", "publication_id", "role", name="uq_site_task_claim_source_claim_publication_role"
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["site_task_claim.id"], name="fk_site_task_claim_source_claim_id_site_task_claim", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"], ["publication.id"], name="fk_site_task_claim_source_publication_id_publication"
        ),
        _enum("role", "site_task_claim_source", ["supports", "disputes", "context"]),
        **STRICT,
    )
    op.create_index("ix_site_task_claim_source_claim_id", "site_task_claim_source", ["claim_id"])

    op.create_table(
        "dataset",
        sa.Column("id", INT, primary_key=True),
        sa.Column("code", TXT, nullable=False),
        sa.Column("provider", TXT, nullable=False),
        sa.Column("product_id", TXT, nullable=False),
        sa.Column("product_name", TXT, nullable=False),
        sa.Column("product_version", TXT, nullable=False),
        sa.Column("body_id", INT, nullable=False),
        sa.Column("variable", TXT, nullable=False),
        sa.Column("surface_type", TXT, nullable=False),
        sa.Column("horizontal_crs", TXT, nullable=False),
        sa.Column("vertical_reference", TXT, nullable=False),
        sa.Column("value_units", TXT, nullable=False),
        sa.Column("nodata_value", REAL, nullable=True),
        sa.Column("native_resolution_value", REAL, nullable=False),
        sa.Column("native_resolution_unit", TXT, nullable=False),
        sa.Column("temporal_coverage", TXT, nullable=True),
        sa.Column("file_format", TXT, nullable=False),
        sa.Column("licence_summary", TXT, nullable=False),
        sa.Column("access_conditions", TXT, nullable=False),
        sa.Column("source_url", TXT, nullable=False),
        sa.Column("publication_id", INT, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_dataset"),
        sa.UniqueConstraint("code", name="uq_dataset_code"),
        sa.UniqueConstraint(
            "provider", "product_id", "product_version", name="uq_dataset_provider_product_version"
        ),
        sa.ForeignKeyConstraint(["body_id"], ["planetary_body.id"], name="fk_dataset_body_id_planetary_body"),
        sa.ForeignKeyConstraint(["publication_id"], ["publication.id"], name="fk_dataset_publication_id_publication"),
        _enum("surface_type", "dataset", ["dsm", "dtm", "altimetry_grid", "reflectance", "other"]),
        _enum("native_resolution_unit", "dataset", ["metre", "arcsecond", "pixel_per_degree"]),
        sa.CheckConstraint("native_resolution_value > 0", name="ck_dataset_resolution_positive"),
        **STRICT,
    )

    op.create_table(
        "data_asset",
        sa.Column("id", INT, primary_key=True),
        sa.Column("dataset_id", INT, nullable=False),
        sa.Column("region_id", INT, nullable=True),
        sa.Column("asset_role", TXT, nullable=False),
        sa.Column("relative_path", TXT, nullable=False),
        sa.Column("file_format", TXT, nullable=False),
        sa.Column("sha256", TXT, nullable=False),
        sa.Column("size_bytes", INT, nullable=False),
        sa.Column("downloaded_at", TXT, nullable=False),
        sa.Column("source_item_id", TXT, nullable=False),
        sa.Column("source_item_url", TXT, nullable=False),
        sa.Column("original_label_path", TXT, nullable=True),
        sa.Column("stac_item_url", TXT, nullable=True),
        sa.Column("crs", TXT, nullable=False),
        sa.Column("vertical_reference", TXT, nullable=False),
        sa.Column("value_units", TXT, nullable=False),
        sa.Column("nodata_value", REAL, nullable=True),
        sa.Column("width_px", INT, nullable=False),
        sa.Column("height_px", INT, nullable=False),
        sa.Column("pixel_size_x", REAL, nullable=False),
        sa.Column("pixel_size_y", REAL, nullable=False),
        sa.Column("dtype", TXT, nullable=False),
        sa.Column("window_min_x", REAL, nullable=False),
        sa.Column("window_min_y", REAL, nullable=False),
        sa.Column("window_max_x", REAL, nullable=False),
        sa.Column("window_max_y", REAL, nullable=False),
        sa.Column("window_is_site_boundary", INT, nullable=False, server_default=sa.text("0")),
        sa.Column("completeness_pct", REAL, nullable=True),
        sa.Column("known_artefacts", TXT, nullable=True),
        sa.Column("accuracy_statement", TXT, nullable=True),
        sa.Column("validation_status", TXT, nullable=False, server_default=sa.text("'unvalidated'")),
        sa.Column("validated_at", TXT, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_data_asset"),
        sa.UniqueConstraint("relative_path", name="uq_data_asset_relative_path"),
        sa.ForeignKeyConstraint(["dataset_id"], ["dataset.id"], name="fk_data_asset_dataset_id_dataset"),
        sa.ForeignKeyConstraint(["region_id"], ["region.id"], name="fk_data_asset_region_id_region"),
        _enum("asset_role", "data_asset", ["original", "clipped", "derived"]),
        _enum("validation_status", "data_asset", ["unvalidated", "validated", "validated_with_issues", "failed"]),
        sa.CheckConstraint(
            "relative_path LIKE 'data/%' AND relative_path NOT LIKE '%..%'", name="ck_data_asset_path_under_data"
        ),
        sa.CheckConstraint(
            "length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'", name="ck_data_asset_sha256_shape"
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_data_asset_size_nonneg"),
        sa.CheckConstraint("window_is_site_boundary = 0", name="ck_data_asset_window_not_boundary"),
        sa.CheckConstraint(
            "completeness_pct IS NULL OR (completeness_pct >= 0 AND completeness_pct <= 100)",
            name="ck_data_asset_completeness_range",
        ),
        sa.CheckConstraint(
            "validation_status <> 'validated' OR validated_at IS NOT NULL",
            name="ck_data_asset_validated_has_timestamp",
        ),
        **STRICT,
    )
    op.create_index("ix_data_asset_dataset_id", "data_asset", ["dataset_id"])

    op.create_table(
        "processing_record",
        sa.Column("id", INT, primary_key=True),
        sa.Column("output_asset_id", INT, nullable=False),
        sa.Column("method", TXT, nullable=False),
        sa.Column("software", TXT, nullable=False),
        sa.Column("software_version", TXT, nullable=False),
        sa.Column("parameters_json", TXT, nullable=False),
        sa.Column("analysis_scale_value", REAL, nullable=True),
        sa.Column("analysis_scale_unit", TXT, nullable=True),
        sa.Column("resampling_method", TXT, nullable=False),
        sa.Column("processed_at", TXT, nullable=False),
        sa.Column("script_path", TXT, nullable=False),
        sa.Column("script_git_commit", TXT, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_processing_record"),
        sa.UniqueConstraint("output_asset_id", name="uq_processing_record_output_asset_id"),
        sa.ForeignKeyConstraint(
            ["output_asset_id"], ["data_asset.id"], name="fk_processing_record_output_asset_id_data_asset"
        ),
        sa.CheckConstraint("json_valid(parameters_json)", name="ck_processing_record_params_json"),
        _enum(
            "resampling_method", "processing_record",
            ["none", "nearest", "bilinear", "cubic", "average", "other"],
        ),
        **STRICT,
    )

    op.create_table(
        "processing_input",
        sa.Column("processing_id", INT, nullable=False),
        sa.Column("input_asset_id", INT, nullable=False),
        sa.PrimaryKeyConstraint("processing_id", "input_asset_id", name="pk_processing_input"),
        sa.ForeignKeyConstraint(
            ["processing_id"], ["processing_record.id"],
            name="fk_processing_input_processing_id_processing_record", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["input_asset_id"], ["data_asset.id"], name="fk_processing_input_input_asset_id_data_asset"
        ),
        **STRICT,
    )

    op.create_table(
        "coverage_gap",
        sa.Column("id", INT, primary_key=True),
        sa.Column("region_id", INT, nullable=False),
        sa.Column("slot", TXT, nullable=False),
        sa.Column("state", TXT, nullable=False),
        sa.Column("reason", TXT, nullable=False),
        sa.Column("resolution_hint", TXT, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_coverage_gap"),
        sa.UniqueConstraint("region_id", "slot", name="uq_coverage_gap_region_id_slot"),
        sa.ForeignKeyConstraint(["region_id"], ["region.id"], name="fk_coverage_gap_region_id_region", ondelete="CASCADE"),
        _enum("slot", "coverage_gap", ["geometry", "elevation", "imagery", "literature_observations"]),
        _enum("state", "coverage_gap", ["not_applicable", "not_acquired", "unavailable", "blocked_on_source"]),
        **STRICT,
    )

    # 7) Triggers: re-create the Phase 1 ones that were dropped, then add the new ones.
    for ddl in (PHASE1_REBUILD_TRIGGERS | PHASE2_TRIGGERS).values():
        op.execute(ddl)


def downgrade() -> None:
    for name in (PHASE1_REBUILD_TRIGGERS | PHASE2_TRIGGERS):
        op.execute(f"DROP TRIGGER IF EXISTS {name}")

    # Batch-rebuild the four Phase 1 tables back to their 0002 shape FIRST: their
    # foreign keys to dataset/data_asset must still resolve while those tables exist.
    with op.batch_alter_table("measurement_source", recreate="always", table_kwargs=STRICT) as batch:
        batch.drop_constraint("ck_measurement_source_one_source", type_="check")
        batch.drop_constraint("ck_measurement_source_source_kind_enum", type_="check")
        batch.drop_constraint("fk_measurement_source_data_asset_id_data_asset", type_="foreignkey")
        batch.drop_column("data_asset_id")
        batch.create_check_constraint(
            "ck_measurement_source_source_kind_enum", "source_kind IN ('publication')"
        )
        batch.create_check_constraint(
            "ck_measurement_source_one_source", "(source_kind = 'publication') = (publication_id IS NOT NULL)"
        )

    with op.batch_alter_table("region_geometry", recreate="always", table_kwargs=STRICT) as batch:
        batch.drop_constraint("fk_region_geometry_source_dataset_id_dataset", type_="foreignkey")
        batch.drop_constraint("ck_region_geometry_has_source_method_note", type_="check")
        batch.drop_constraint("ck_region_geometry_positional_uncertainty_nonneg", type_="check")
        batch.drop_constraint("ck_region_geometry_geometry_method_enum", type_="check")
        batch.drop_column("source_dataset_id")
        batch.drop_column("uncertainty_note")
        batch.drop_column("positional_uncertainty_m")
        batch.drop_column("geometry_method")
        batch.create_check_constraint(
            "ck_region_geometry_traced_has_source",
            "geometry_status <> 'source_traced' OR source_publication_id IS NOT NULL",
        )

    with op.batch_alter_table("region", recreate="always", table_kwargs=STRICT) as batch:
        batch.drop_constraint("ck_region_origin_status_enum", type_="check")
        batch.drop_constraint("ck_region_country_code_shape", type_="check")
        batch.drop_column("origin_status")
        batch.drop_column("site_type")
        batch.drop_column("country_code")

    with op.batch_alter_table("publication", recreate="always", table_kwargs=STRICT) as batch:
        batch.drop_constraint("ck_publication_doi_or_url", type_="check")
        batch.drop_constraint("ck_publication_source_type_enum", type_="check")
        batch.drop_column("accessed_on")
        batch.drop_column("citation")
        batch.drop_column("licence")
        batch.drop_column("url")
        batch.drop_column("institution")
        batch.drop_column("authors")
        batch.drop_column("source_type")

    # Now that nothing references them, drop the Phase 2 tables (reverse create order).
    for table in (
        "coverage_gap",
        "processing_input",
        "processing_record",
        "data_asset",
        "dataset",
        "site_task_claim_source",
        "site_task_claim",
        "research_task",
        "region_alias",
    ):
        op.drop_table(table)

    for ddl in PHASE1_REBUILD_TRIGGERS.values():
        op.execute(ddl)
