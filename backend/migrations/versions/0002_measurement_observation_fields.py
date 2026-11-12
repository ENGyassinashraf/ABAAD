"""Add observation_date and resolution_adequacy to measurement (R1 · 4 fields).

This migration deliberately uses Alembic batch mode with recreate="always".
On SQLite that copies the table, drops the original and renames the copy, so
it is the migration path that can silently lose STRICT, CHECK constraints and
triggers. The migration tests run it and inspect sqlite_master afterwards.

Rules followed here:
* ``table_kwargs={"sqlite_strict": True}`` keeps the rebuilt table STRICT.
* Every CHECK constraint is named in 0001, so batch mode carries it over.
* SQLite drops a table's triggers together with the table, so the measurement
  triggers are re-created verbatim from 0001 after the rebuild (both ways).
* Triggers on OTHER tables that reference measurement (the data_gap
  triggers) must also be dropped first: otherwise the final
  ``ALTER TABLE _alembic_tmp_measurement RENAME TO measurement`` fails with
  "error in trigger trg_gap_no_measurement_ins: no such table". They are
  re-created afterwards from the same frozen 0001 DDL.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _measurement_triggers() -> dict[str, str]:
    """Frozen DDL (from revision 0001) of every trigger that references measurement."""
    path = Path(__file__).with_name("0001_initial_core_schema.py")
    spec = importlib.util.spec_from_file_location("abaad_rev_0001", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.MEASUREMENT_TRIGGERS | module.GAP_TRIGGERS


def _drop_triggers(names) -> None:
    for name in names:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")


def upgrade() -> None:
    triggers = _measurement_triggers()
    _drop_triggers(triggers)
    with op.batch_alter_table(
        "measurement", recreate="always", table_kwargs={"sqlite_strict": True}
    ) as batch:
        batch.add_column(sa.Column("observation_date", sa.Text(), nullable=True))
        batch.add_column(sa.Column("resolution_adequacy", sa.Text(), nullable=True))
        batch.create_check_constraint(
            "ck_measurement_resolution_adequacy_enum",
            "resolution_adequacy IS NULL OR resolution_adequacy IN "
            "('adequate', 'marginal', 'inadequate', 'not_applicable')",
        )
    for ddl in triggers.values():
        op.execute(ddl)


def downgrade() -> None:
    triggers = _measurement_triggers()
    _drop_triggers(triggers)
    with op.batch_alter_table(
        "measurement", recreate="always", table_kwargs={"sqlite_strict": True}
    ) as batch:
        batch.drop_constraint("ck_measurement_resolution_adequacy_enum", type_="check")
        batch.drop_column("resolution_adequacy")
        batch.drop_column("observation_date")
    for ddl in triggers.values():
        op.execute(ddl)
