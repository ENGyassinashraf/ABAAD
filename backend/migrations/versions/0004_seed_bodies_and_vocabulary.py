"""Phase 2 seed data: the three planetary bodies and the research-task
vocabulary. Data-only; no schema change. Downgrade deletes only the rows
inserted here (matched by code), never a blanket DELETE.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

BODIES = [
    # code, name, default_crs_code, mean_radius_m
    ("earth", "Earth", "OGC:CRS84", 6371008.8),
    ("mars", "Mars", "IAU_2015:49900", 3396190.0),
    ("moon", "Moon", "IAU_2015:30100", 1737400.0),
]

# code, name, description, applies_to — see the Phase 2 spec §7. All seven
# are Mars-focused in Phase 2 (D-P2-02: no Earth lunar analog is added).
RESEARCH_TASKS = [
    ("aeolian_geomorphology", "Aeolian geomorphology", "Wind-formed landforms: dunes, sand sheets, yardangs.", "mars"),
    ("fluvial_paleohydrology", "Fluvial paleohydrology", "Ancient river/channel systems and their deposits.", "mars"),
    ("shallow_subsurface_gpr", "Shallow subsurface sounding", "Ground-penetrating radar and electromagnetic induction.", "mars"),
    ("life_detection_drilling", "Life-detection drilling", "Automated drilling, sample handling and life-detection instruments.", "mars"),
    ("cold_arid_environment", "Cold arid environment", "Cold, hyperarid terrestrial analog conditions.", "mars"),
    ("ice_cemented_ground_drilling", "Ice-cemented ground drilling", "Drilling into ice-cemented ground.", "mars"),
    ("basaltic_volcanology", "Basaltic volcanology", "Basaltic lava flow-field morphology and emplacement.", "mars"),
]

PLANETARY_BODY = sa.table(
    "planetary_body",
    sa.column("code"), sa.column("name"), sa.column("default_crs_code"), sa.column("mean_radius_m"),
)
RESEARCH_TASK = sa.table(
    "research_task",
    sa.column("code"), sa.column("name"), sa.column("description"), sa.column("applies_to"),
)


def upgrade() -> None:
    op.bulk_insert(
        PLANETARY_BODY,
        [{"code": c, "name": n, "default_crs_code": crs, "mean_radius_m": r} for c, n, crs, r in BODIES],
    )
    op.bulk_insert(
        RESEARCH_TASK,
        [{"code": c, "name": n, "description": d, "applies_to": a} for c, n, d, a in RESEARCH_TASKS],
    )


def downgrade() -> None:
    conn = op.get_bind()
    for code, *_ in BODIES:
        conn.execute(sa.text("DELETE FROM planetary_body WHERE code = :code"), {"code": code})
    for code, *_ in RESEARCH_TASKS:
        conn.execute(sa.text("DELETE FROM research_task WHERE code = :code"), {"code": code})
