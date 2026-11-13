"""Phase 2 pre-merge hardening (see docs/reports/PHASE2_COMPLETION.md, F-01..F-10).

- F-01: site_task_claim gets an explicit, always-present reference_body_id;
  enforced against research_task.applies_to and reference_region's body,
  on INSERT and UPDATE. region.body_id/region_role and research_task.applies_to
  become immutable once referenced by a claim (reject the UPDATE outright).
- F-02: dataset.horizontal_crs is no longer forced into an IAU_2015 family by
  trigger (removed trg_dataset_crs_matches_body_*). It is now nullable, with
  an explicit horizontal_crs_status ('verified'|'pending'|'product_specific_unverified').
  An asset can never be marked validated against a dataset whose CRS is not verified.
- F-02/7.2/8.2: dataset gets collection_id (stable identity alongside
  provider/product_id/product_version) and download_url (the verified direct
  file URL; NULL means "not yet confirmed", and ingestion must refuse to
  download without it -- source_url remains the catalogue/product page URL).
- F-05: data_asset/processing_input get the UPDATE-side triggers that only
  existed on INSERT, plus a body-consistency check against region and a
  raw/clipped vs dataset CRS/vertical-reference/units check. processing_record
  gets explicit output_variable/output_units/output_crs/output_vertical_reference
  columns, checked against the actual output asset.
- F-06: publication.source_access gains 'partial_full_text' plus an
  access_note column, so an honestly-partial read is never stored as
  full_text_checked.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

INT, TXT, REAL = sa.Integer, sa.Text, sa.REAL
STRICT = {"sqlite_strict": True}

OLD_DATASET_CRS_TRIGGERS = ("trg_dataset_crs_matches_body_ins", "trg_dataset_crs_matches_body_upd")

# Triggers from 0003 that reference publication, dataset, site_task_claim or
# processing_record -- all four are rebuilt below, so (per the Phase 1 lesson,
# P1-12/P1-13) every trigger that mentions any of them, even one defined on a
# different table, must be dropped before and re-created verbatim after.
_REBUILT_FROM_0003 = (
    "trg_claim_roles_ins", "trg_claim_roles_upd",
    "trg_claim_publish_requires_support_ins", "trg_claim_publish_requires_support_upd",
    "trg_region_geometry_dataset_body_ins", "trg_region_geometry_dataset_body_upd",
    "trg_processing_input_same_body_ins",
)


def _triggers_from_0003() -> dict[str, str]:
    path = Path(__file__).with_name("0003_phase2_provenance_schema.py")
    spec = importlib.util.spec_from_file_location("abaad_rev_0003", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.PHASE2_TRIGGERS

NEW_TRIGGERS = {
    # --- region / research_task immutability once referenced by a claim -----
    "trg_region_immutable_when_claimed_upd": """
CREATE TRIGGER trg_region_immutable_when_claimed_upd
BEFORE UPDATE OF body_id, region_role ON region
WHEN (NEW.body_id <> OLD.body_id OR NEW.region_role <> OLD.region_role)
 AND EXISTS (SELECT 1 FROM site_task_claim WHERE analog_region_id = OLD.id OR reference_region_id = OLD.id)
BEGIN SELECT RAISE(ABORT,
  'region.body_id/region_role cannot change while a site_task_claim references this region'); END""",
    "trg_research_task_immutable_when_claimed_upd": """
CREATE TRIGGER trg_research_task_immutable_when_claimed_upd
BEFORE UPDATE OF applies_to ON research_task
WHEN NEW.applies_to <> OLD.applies_to AND EXISTS (SELECT 1 FROM site_task_claim WHERE task_id = OLD.id)
BEGIN SELECT RAISE(ABORT,
  'research_task.applies_to cannot change while a site_task_claim references this task'); END""",
    # --- claim <-> reference_body <-> task matrix (F-01) ---------------------
    "trg_claim_reference_matrix_ins": """
CREATE TRIGGER trg_claim_reference_matrix_ins
BEFORE INSERT ON site_task_claim
WHEN (SELECT code FROM planetary_body WHERE id = NEW.reference_body_id) = 'earth'
 OR (
   (SELECT applies_to FROM research_task WHERE id = NEW.task_id) <> 'both'
   AND (SELECT applies_to FROM research_task WHERE id = NEW.task_id)
       <> (SELECT code FROM planetary_body WHERE id = NEW.reference_body_id)
 )
 OR (NEW.reference_region_id IS NOT NULL
     AND (SELECT body_id FROM region WHERE id = NEW.reference_region_id) <> NEW.reference_body_id)
BEGIN SELECT RAISE(ABORT,
  'reference_body_id must not be Earth, must be allowed by research_task.applies_to, and must match reference_region_id''s body when a reference region is set'); END""",
    "trg_claim_reference_matrix_upd": """
CREATE TRIGGER trg_claim_reference_matrix_upd
BEFORE UPDATE OF reference_body_id, reference_region_id, task_id ON site_task_claim
WHEN (SELECT code FROM planetary_body WHERE id = NEW.reference_body_id) = 'earth'
 OR (
   (SELECT applies_to FROM research_task WHERE id = NEW.task_id) <> 'both'
   AND (SELECT applies_to FROM research_task WHERE id = NEW.task_id)
       <> (SELECT code FROM planetary_body WHERE id = NEW.reference_body_id)
 )
 OR (NEW.reference_region_id IS NOT NULL
     AND (SELECT body_id FROM region WHERE id = NEW.reference_region_id) <> NEW.reference_body_id)
BEGIN SELECT RAISE(ABORT,
  'reference_body_id must not be Earth, must be allowed by research_task.applies_to, and must match reference_region_id''s body when a reference region is set'); END""",
    # --- validated asset requires a verified dataset CRS (F-02) ---------------
    "trg_data_asset_validated_requires_verified_crs_ins": """
CREATE TRIGGER trg_data_asset_validated_requires_verified_crs_ins
BEFORE INSERT ON data_asset
WHEN NEW.validation_status IN ('validated', 'validated_with_issues')
 AND (SELECT horizontal_crs_status FROM dataset WHERE id = NEW.dataset_id) <> 'verified'
BEGIN SELECT RAISE(ABORT,
  'an asset cannot be validated while its dataset horizontal_crs_status is not verified'); END""",
    "trg_data_asset_validated_requires_verified_crs_upd": """
CREATE TRIGGER trg_data_asset_validated_requires_verified_crs_upd
BEFORE UPDATE OF validation_status, dataset_id ON data_asset
WHEN NEW.validation_status IN ('validated', 'validated_with_issues')
 AND (SELECT horizontal_crs_status FROM dataset WHERE id = NEW.dataset_id) <> 'verified'
BEGIN SELECT RAISE(ABORT,
  'an asset cannot be validated while its dataset horizontal_crs_status is not verified'); END""",
    # --- data_asset body consistency against region (F-05/4.1) ----------------
    "trg_data_asset_region_body_matches_ins": """
CREATE TRIGGER trg_data_asset_region_body_matches_ins
BEFORE INSERT ON data_asset
WHEN NEW.region_id IS NOT NULL
 AND (SELECT body_id FROM region WHERE id = NEW.region_id) <> (SELECT body_id FROM dataset WHERE id = NEW.dataset_id)
BEGIN SELECT RAISE(ABORT, 'data_asset.region_id must be for the same body as its dataset'); END""",
    "trg_data_asset_region_body_matches_upd": """
CREATE TRIGGER trg_data_asset_region_body_matches_upd
BEFORE UPDATE OF region_id, dataset_id ON data_asset
WHEN NEW.region_id IS NOT NULL
 AND (SELECT body_id FROM region WHERE id = NEW.region_id) <> (SELECT body_id FROM dataset WHERE id = NEW.dataset_id)
BEGIN SELECT RAISE(ABORT, 'data_asset.region_id must be for the same body as its dataset'); END""",
    # --- raw/clipped asset must match its dataset's verified CRS/vertical/units (F-05/4.1) --
    "trg_data_asset_raw_clipped_matches_dataset_ins": """
CREATE TRIGGER trg_data_asset_raw_clipped_matches_dataset_ins
BEFORE INSERT ON data_asset
WHEN NEW.asset_role IN ('original', 'clipped')
 AND (SELECT horizontal_crs_status FROM dataset WHERE id = NEW.dataset_id) = 'verified'
 AND (
   NEW.crs <> (SELECT horizontal_crs FROM dataset WHERE id = NEW.dataset_id)
   OR NEW.vertical_reference <> (SELECT vertical_reference FROM dataset WHERE id = NEW.dataset_id)
   OR NEW.value_units <> (SELECT value_units FROM dataset WHERE id = NEW.dataset_id)
 )
BEGIN SELECT RAISE(ABORT,
  'an original/clipped asset must match its parent dataset''s CRS, vertical_reference and value_units'); END""",
    "trg_data_asset_raw_clipped_matches_dataset_upd": """
CREATE TRIGGER trg_data_asset_raw_clipped_matches_dataset_upd
BEFORE UPDATE OF asset_role, crs, vertical_reference, value_units, dataset_id ON data_asset
WHEN NEW.asset_role IN ('original', 'clipped')
 AND (SELECT horizontal_crs_status FROM dataset WHERE id = NEW.dataset_id) = 'verified'
 AND (
   NEW.crs <> (SELECT horizontal_crs FROM dataset WHERE id = NEW.dataset_id)
   OR NEW.vertical_reference <> (SELECT vertical_reference FROM dataset WHERE id = NEW.dataset_id)
   OR NEW.value_units <> (SELECT value_units FROM dataset WHERE id = NEW.dataset_id)
 )
BEGIN SELECT RAISE(ABORT,
  'an original/clipped asset must match its parent dataset''s CRS, vertical_reference and value_units'); END""",
    # --- processing_record output metadata must match the actual output asset (F-05/4.1) ----
    "trg_processing_record_output_matches_asset_ins": """
CREATE TRIGGER trg_processing_record_output_matches_asset_ins
BEFORE INSERT ON processing_record
WHEN (SELECT crs FROM data_asset WHERE id = NEW.output_asset_id) <> NEW.output_crs
 OR (SELECT vertical_reference FROM data_asset WHERE id = NEW.output_asset_id) <> NEW.output_vertical_reference
 OR (SELECT value_units FROM data_asset WHERE id = NEW.output_asset_id) <> NEW.output_units
BEGIN SELECT RAISE(ABORT,
  'processing_record output_crs/output_vertical_reference/output_units must match the output data_asset'); END""",
    "trg_processing_record_output_matches_asset_upd": """
CREATE TRIGGER trg_processing_record_output_matches_asset_upd
BEFORE UPDATE OF output_asset_id, output_crs, output_vertical_reference, output_units ON processing_record
WHEN (SELECT crs FROM data_asset WHERE id = NEW.output_asset_id) <> NEW.output_crs
 OR (SELECT vertical_reference FROM data_asset WHERE id = NEW.output_asset_id) <> NEW.output_vertical_reference
 OR (SELECT value_units FROM data_asset WHERE id = NEW.output_asset_id) <> NEW.output_units
BEGIN SELECT RAISE(ABORT,
  'processing_record output_crs/output_vertical_reference/output_units must match the output data_asset'); END""",
    # --- processing_input same-body, now also on UPDATE (F-05/4.2) ------------
    "trg_processing_input_same_body_upd": """
CREATE TRIGGER trg_processing_input_same_body_upd
BEFORE UPDATE OF processing_id, input_asset_id ON processing_input
WHEN (SELECT d2.body_id FROM data_asset a2 JOIN dataset d2 ON d2.id = a2.dataset_id
      WHERE a2.id = NEW.input_asset_id)
     <> (SELECT d1.body_id FROM processing_record r JOIN data_asset a1 ON a1.id = r.output_asset_id
         JOIN dataset d1 ON d1.id = a1.dataset_id WHERE r.id = NEW.processing_id)
BEGIN SELECT RAISE(ABORT, 'processing_input: input and output assets must belong to the same body'); END""",
}


def upgrade() -> None:
    old_triggers = _triggers_from_0003()
    for name in OLD_DATASET_CRS_TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    for name in _REBUILT_FROM_0003:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")

    # publication: honest partial-read access level + a note on what was actually checked.
    with op.batch_alter_table("publication", recreate="always", table_kwargs=STRICT) as batch:
        batch.add_column(sa.Column("access_note", TXT, nullable=True))
        batch.drop_constraint("ck_publication_source_access_enum", type_="check")
        batch.create_check_constraint(
            "ck_publication_source_access_enum",
            "source_access IN ('full_text_checked','partial_full_text','abstract_only','secondary_record')",
        )

    # dataset: CRS honesty + stable identity + catalogue vs download URL split.
    with op.batch_alter_table("dataset", recreate="always", table_kwargs=STRICT) as batch:
        batch.alter_column("horizontal_crs", nullable=True)
        batch.add_column(sa.Column("horizontal_crs_status", TXT, nullable=False, server_default=sa.text("'pending'")))
        batch.add_column(sa.Column("collection_id", TXT, nullable=True))
        batch.add_column(sa.Column("download_url", TXT, nullable=True))
        batch.create_check_constraint(
            "ck_dataset_horizontal_crs_status_enum",
            "horizontal_crs_status IN ('verified','pending','product_specific_unverified')",
        )
        batch.create_check_constraint(
            "ck_dataset_crs_status_shape",
            "horizontal_crs_status <> 'verified' OR horizontal_crs IS NOT NULL",
        )
        batch.drop_constraint("uq_dataset_provider_product_version", type_="unique")
        batch.create_unique_constraint(
            "uq_dataset_provider_collection_product_version",
            ["provider", "collection_id", "product_id", "product_version"],
        )

    # site_task_claim: add reference_body_id (nullable first, backfilled, then tightened).
    with op.batch_alter_table("site_task_claim", recreate="always", table_kwargs=STRICT) as batch:
        batch.add_column(sa.Column("reference_body_id", INT, nullable=True))
    op.execute(
        "UPDATE site_task_claim SET reference_body_id = (SELECT id FROM planetary_body WHERE code = 'mars')"
        " WHERE reference_body_id IS NULL"
    )
    with op.batch_alter_table("site_task_claim", recreate="always", table_kwargs=STRICT) as batch:
        batch.alter_column("reference_body_id", nullable=False)
        batch.create_foreign_key(
            "fk_site_task_claim_reference_body_id_planetary_body", "planetary_body", ["reference_body_id"], ["id"]
        )

    # processing_record: explicit, checked output metadata (F-05/4.1).
    with op.batch_alter_table("processing_record", recreate="always", table_kwargs=STRICT) as batch:
        batch.add_column(sa.Column("output_variable", TXT, nullable=True))
        batch.add_column(sa.Column("output_units", TXT, nullable=True))
        batch.add_column(sa.Column("output_crs", TXT, nullable=True))
        batch.add_column(sa.Column("output_vertical_reference", TXT, nullable=True))
    # Backfill from the (only ever synthetic/test, never production) existing rows, then tighten.
    op.execute(
        "UPDATE processing_record SET"
        " output_units = (SELECT value_units FROM data_asset WHERE id = output_asset_id),"
        " output_crs = (SELECT crs FROM data_asset WHERE id = output_asset_id),"
        " output_vertical_reference = (SELECT vertical_reference FROM data_asset WHERE id = output_asset_id),"
        " output_variable = coalesce(output_variable, method)"
        " WHERE output_units IS NULL"
    )
    with op.batch_alter_table("processing_record", recreate="always", table_kwargs=STRICT) as batch:
        batch.alter_column("output_variable", nullable=False)
        batch.alter_column("output_units", nullable=False)
        batch.alter_column("output_crs", nullable=False)
        batch.alter_column("output_vertical_reference", nullable=False)

    for name in _REBUILT_FROM_0003:
        op.execute(old_triggers[name])
    for ddl in NEW_TRIGGERS.values():
        op.execute(ddl)


def downgrade() -> None:
    old_triggers = _triggers_from_0003()
    for name in NEW_TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    for name in _REBUILT_FROM_0003:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")

    with op.batch_alter_table("processing_record", recreate="always", table_kwargs=STRICT) as batch:
        batch.drop_column("output_vertical_reference")
        batch.drop_column("output_crs")
        batch.drop_column("output_units")
        batch.drop_column("output_variable")

    with op.batch_alter_table("site_task_claim", recreate="always", table_kwargs=STRICT) as batch:
        batch.drop_constraint("fk_site_task_claim_reference_body_id_planetary_body", type_="foreignkey")
        batch.drop_column("reference_body_id")

    with op.batch_alter_table("dataset", recreate="always", table_kwargs=STRICT) as batch:
        batch.drop_constraint("uq_dataset_provider_collection_product_version", type_="unique")
        batch.create_unique_constraint("uq_dataset_provider_product_version", ["provider", "product_id", "product_version"])
        batch.drop_constraint("ck_dataset_crs_status_shape", type_="check")
        batch.drop_constraint("ck_dataset_horizontal_crs_status_enum", type_="check")
        batch.drop_column("download_url")
        batch.drop_column("collection_id")
        batch.drop_column("horizontal_crs_status")
        batch.alter_column("horizontal_crs", nullable=False)

    with op.batch_alter_table("publication", recreate="always", table_kwargs=STRICT) as batch:
        batch.drop_constraint("ck_publication_source_access_enum", type_="check")
        batch.create_check_constraint(
            "ck_publication_source_access_enum", "source_access IN ('full_text_checked','abstract_only','secondary_record')"
        )
        batch.drop_column("access_note")

    for name in _REBUILT_FROM_0003:
        op.execute(old_triggers[name])

    # OLD_DATASET_CRS_TRIGGERS is intentionally NOT restored here: removing the
    # forced-CRS-family rule is the point of F-02 and is not meant to be undone
    # by a downgrade; only the schema additions above are reverted.
