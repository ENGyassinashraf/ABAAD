"""Comparison engine schema (Project & Scientific Guide §06, §13, §14).

- comparison_dimension: the five comparison dimensions (seeded here).
- task_dimension_weight: per-task weights w_i with a written rationale
  (loaded from curation/comparison.json, never hard-coded in code).
- dimension_assessment: one curated similarity s_i per (Earth analog,
  planetary reference, dimension). s_i must equal its named rubric level,
  must cite a registered source with a locator, and must say how the
  evidence was obtained (literature / remote / dataset / field / hypothesis).
  A missing row means "unknown" -- it is never stored as zero.
- research_task gains rover_mobility (applies_to 'both'), the scope's
  mobility task, so a Moon reference has a selectable task.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

INT, TXT, REAL = sa.Integer, sa.Text, sa.REAL
STRICT = {"sqlite_strict": True}

DIMENSIONS = [
    ("terrain_shape", "Terrain shape", "Landform geometry, slope, relief and roughness (imagery, DEM, landform mapping)."),
    ("geology_materials", "Geology and materials", "Rock and sediment type, mineralogy, grain size (published maps, spectral data, samples)."),
    ("surface_processes", "Surface processes", "Active or past wind, water and erosion/deposition processes and their landforms."),
    ("subsurface", "Subsurface", "Buried structure and layering (GPR profiles, boreholes, documented field measurements)."),
    ("environment", "Environment", "Temperature, aridity, wind, water, atmosphere, gravity and radiation context."),
]

RUBRIC_SQL = (
    "similarity = CASE rubric_level WHEN 'strong' THEN 1.0 WHEN 'close' THEN 0.75"
    " WHEN 'partial' THEN 0.5 WHEN 'weak' THEN 0.25 WHEN 'mismatch' THEN 0.0 END"
)

TRIGGERS = {
    "trg_assessment_roles_ins": """
CREATE TRIGGER trg_assessment_roles_ins
BEFORE INSERT ON dimension_assessment
WHEN (SELECT b.code FROM region r JOIN planetary_body b ON b.id = r.body_id WHERE r.id = NEW.analog_region_id) IS NOT 'earth'
 OR (SELECT region_role FROM region WHERE id = NEW.analog_region_id) IS NOT 'analog'
 OR (SELECT b.code FROM region r JOIN planetary_body b ON b.id = r.body_id WHERE r.id = NEW.reference_region_id) = 'earth'
 OR (SELECT region_role FROM region WHERE id = NEW.reference_region_id) IS NOT 'reference'
BEGIN SELECT RAISE(ABORT, 'dimension_assessment: analog must be an Earth analog region and reference a non-Earth reference region'); END""",
    "trg_assessment_roles_upd": """
CREATE TRIGGER trg_assessment_roles_upd
BEFORE UPDATE OF analog_region_id, reference_region_id ON dimension_assessment
WHEN (SELECT b.code FROM region r JOIN planetary_body b ON b.id = r.body_id WHERE r.id = NEW.analog_region_id) IS NOT 'earth'
 OR (SELECT region_role FROM region WHERE id = NEW.analog_region_id) IS NOT 'analog'
 OR (SELECT b.code FROM region r JOIN planetary_body b ON b.id = r.body_id WHERE r.id = NEW.reference_region_id) = 'earth'
 OR (SELECT region_role FROM region WHERE id = NEW.reference_region_id) IS NOT 'reference'
BEGIN SELECT RAISE(ABORT, 'dimension_assessment: analog must be an Earth analog region and reference a non-Earth reference region'); END""",
    "trg_region_immutable_when_assessed_upd": """
CREATE TRIGGER trg_region_immutable_when_assessed_upd
BEFORE UPDATE OF body_id, region_role ON region
WHEN (NEW.body_id <> OLD.body_id OR NEW.region_role <> OLD.region_role)
 AND EXISTS (SELECT 1 FROM dimension_assessment WHERE analog_region_id = OLD.id OR reference_region_id = OLD.id)
BEGIN SELECT RAISE(ABORT, 'region.body_id/region_role cannot change while a dimension_assessment references this region'); END""",
}


def upgrade() -> None:
    op.create_table(
        "comparison_dimension",
        sa.Column("id", INT, primary_key=True),
        sa.Column("code", TXT, nullable=False),
        sa.Column("name", TXT, nullable=False),
        sa.Column("description", TXT, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_comparison_dimension"),
        sa.UniqueConstraint("code", name="uq_comparison_dimension_code"),
        **STRICT,
    )
    op.create_table(
        "task_dimension_weight",
        sa.Column("task_id", INT, nullable=False),
        sa.Column("dimension_id", INT, nullable=False),
        sa.Column("weight", REAL, nullable=False),
        sa.Column("rationale", TXT, nullable=False),
        sa.PrimaryKeyConstraint("task_id", "dimension_id", name="pk_task_dimension_weight"),
        sa.ForeignKeyConstraint(["task_id"], ["research_task.id"], name="fk_task_dimension_weight_task_id_research_task", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dimension_id"], ["comparison_dimension.id"], name="fk_task_dimension_weight_dimension_id_comparison_dimension"),
        sa.CheckConstraint("weight > 0 AND weight <= 10", name="ck_task_dimension_weight_range"),
        sa.CheckConstraint("length(trim(rationale)) > 0", name="ck_task_dimension_weight_rationale"),
        **STRICT,
    )
    op.create_table(
        "dimension_assessment",
        sa.Column("id", INT, primary_key=True),
        sa.Column("analog_region_id", INT, nullable=False),
        sa.Column("reference_region_id", INT, nullable=False),
        sa.Column("dimension_id", INT, nullable=False),
        sa.Column("rubric_level", TXT, nullable=False),
        sa.Column("similarity", REAL, nullable=False),
        sa.Column("evidence_basis", TXT, nullable=False),
        sa.Column("rationale", TXT, nullable=False),
        # A similarity needs evidence on BOTH sides: one source for the Earth
        # analog and one for the planetary reference (may be the same paper).
        sa.Column("analog_publication_id", INT, nullable=False),
        sa.Column("analog_locator", TXT, nullable=False),
        sa.Column("reference_publication_id", INT, nullable=False),
        sa.Column("reference_locator", TXT, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_dimension_assessment"),
        sa.UniqueConstraint("analog_region_id", "reference_region_id", "dimension_id",
                            name="uq_dimension_assessment_pair_dimension"),
        sa.ForeignKeyConstraint(["analog_region_id"], ["region.id"], name="fk_dimension_assessment_analog_region_id_region"),
        sa.ForeignKeyConstraint(["reference_region_id"], ["region.id"], name="fk_dimension_assessment_reference_region_id_region"),
        sa.ForeignKeyConstraint(["dimension_id"], ["comparison_dimension.id"], name="fk_dimension_assessment_dimension_id_comparison_dimension"),
        sa.ForeignKeyConstraint(["analog_publication_id"], ["publication.id"], name="fk_dimension_assessment_analog_publication_id_publication"),
        sa.ForeignKeyConstraint(["reference_publication_id"], ["publication.id"], name="fk_dimension_assessment_reference_publication_id_publication"),
        sa.CheckConstraint("rubric_level IN ('strong','close','partial','weak','mismatch')", name="ck_dimension_assessment_rubric_level_enum"),
        sa.CheckConstraint(RUBRIC_SQL, name="ck_dimension_assessment_similarity_matches_rubric"),
        sa.CheckConstraint(
            "evidence_basis IN ('published_literature','remote_observation','dataset_derived','field_measured','hypothesized')",
            name="ck_dimension_assessment_evidence_basis_enum",
        ),
        sa.CheckConstraint(
            "length(trim(rationale)) > 0 AND length(trim(analog_locator)) > 0 AND length(trim(reference_locator)) > 0",
            name="ck_dimension_assessment_text",
        ),
        **STRICT,
    )
    op.bulk_insert(
        sa.table("comparison_dimension", sa.column("code"), sa.column("name"), sa.column("description")),
        [{"code": c, "name": n, "description": d} for c, n, d in DIMENSIONS],
    )
    op.bulk_insert(
        sa.table("research_task", sa.column("code"), sa.column("name"), sa.column("description"), sa.column("applies_to")),
        [{"code": "rover_mobility", "name": "Rover mobility",
          "description": "Screening terrain for rover/test-vehicle mobility (slope, roughness, obstacles, loose material). "
                         "Satellite data can screen morphology but cannot prove traction or bearing capacity.",
          "applies_to": "both"}],
    )
    for ddl in TRIGGERS.values():
        op.execute(ddl)


def downgrade() -> None:
    for name in TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    op.drop_table("dimension_assessment")
    op.drop_table("task_dimension_weight")
    op.drop_table("comparison_dimension")
    op.execute("DELETE FROM research_task WHERE code = 'rover_mobility'"
               " AND NOT EXISTS (SELECT 1 FROM site_task_claim c WHERE c.task_id = research_task.id)")
