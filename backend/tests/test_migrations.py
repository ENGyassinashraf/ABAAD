"""Migration survival tests: STRICT, named CHECKs, foreign keys, indexes and
triggers must exist after upgrade, after the batch-rebuild migration (0002),
after a downgrade and after a re-upgrade. Evidence is read from sqlite_master."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from .conftest import ALEMBIC_INI, downgrade, raw, upgrade

TABLES = {
    "planetary_body", "publication", "region", "region_geometry",
    "parameter", "measurement", "measurement_source", "data_gap",
}

EXPECTED_CHECKS = {
    "planetary_body": {"ck_planetary_body_radius_positive"},
    "publication": {"ck_publication_source_access_enum", "ck_publication_peer_reviewed_bool"},
    "region": {
        "ck_region_region_role_enum", "ck_region_region_level_enum",
        "ck_region_validation_status_enum", "ck_region_not_own_parent",
    },
    "region_geometry": {
        "ck_region_geometry_geometry_role_enum", "ck_region_geometry_encoding_enum",
        "ck_region_geometry_coordinate_units_enum", "ck_region_geometry_latitude_type_enum",
        "ck_region_geometry_longitude_direction_enum", "ck_region_geometry_longitude_domain_enum",
        "ck_region_geometry_axis_order_enum", "ck_region_geometry_geometry_status_enum",
        "ck_region_geometry_rfc7946_only_wgs84", "ck_region_geometry_text_unless_undefined",
        "ck_region_geometry_traced_has_source", "ck_region_geometry_extent_order",
    },
    "parameter": {"ck_parameter_value_type_enum", "ck_parameter_comparison_class_enum"},
    "measurement": {
        "ck_measurement_value_kind_enum", "ck_measurement_point_uncertainty_type_enum",
        "ck_measurement_evidence_grade_enum", "ck_measurement_source_access_enum",
        "ck_measurement_is_current_bool", "ck_measurement_is_synthetic_bool",
        "ck_measurement_point_shape", "ck_measurement_interval_shape",
        "ck_measurement_category_shape",
    },
    "measurement_source": {
        "ck_measurement_source_source_kind_enum", "ck_measurement_source_role_enum",
        "ck_measurement_source_one_source",
    },
    "data_gap": {"ck_data_gap_reason_enum"},
}
CHECKS_ADDED_IN_0002 = {"measurement": {"ck_measurement_resolution_adequacy_enum"}}
HEAD_REVISION = "0003"
MISSION_TABLES = {"mission_scenario", "mission_run", "mission_route", "mission_event", "mission_report"}

EXPECTED_FKS = {  # (from_column, to_table) pairs
    "region": {("body_id", "planetary_body"), ("parent_region_id", "region")},
    "region_geometry": {("region_id", "region"), ("body_id", "planetary_body"),
                        ("source_publication_id", "publication")},
    "measurement": {("region_id", "region"), ("parameter_id", "parameter")},
    "measurement_source": {("measurement_id", "measurement"), ("publication_id", "publication")},
    "data_gap": {("region_id", "region"), ("parameter_id", "parameter")},
}

EXPECTED_TRIGGERS = {
    "trg_region_geometry_body_matches_region_ins", "trg_region_geometry_body_matches_region_upd",
    "trg_region_geometry_rfc7946_earth_only_ins", "trg_region_geometry_rfc7946_earth_only_upd",
    "trg_measurement_no_gap_ins", "trg_measurement_no_gap_upd",
    "trg_measurement_reject_synthetic_ins", "trg_measurement_reject_synthetic_upd",
    "trg_gap_no_measurement_ins", "trg_gap_no_measurement_upd",
}
EXPECTED_INDEXES = {
    "ix_region_body_id", "ix_region_parent_region_id", "ix_region_geometry_region_id",
    "ix_measurement_region_id_parameter_id", "uq_measurement_current_region_parameter",
    "ix_measurement_source_measurement_id",
}


def schema(db: Path) -> dict:
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master").fetchall()
    fks = {
        t: {(r[3], r[2]) for r in conn.execute(f"PRAGMA foreign_key_list({t})")}
        for t in TABLES if any(r[1] == t for r in rows)
    }
    version = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    conn.close()
    return {
        "tables": {r[1]: r[3] for r in rows if r[0] == "table"},
        "triggers": {r[1] for r in rows if r[0] == "trigger"},
        "indexes": {r[1] for r in rows if r[0] == "index" and r[3]},
        "fks": fks,
        "version": version,
    }


def assert_full_schema(db: Path, at_head: bool) -> None:
    s = schema(db)
    assert TABLES <= set(s["tables"]), f"missing tables: {TABLES - set(s['tables'])}"
    for table in TABLES:
        ddl = s["tables"][table]
        assert ddl.rstrip().endswith("STRICT"), f"{table} is not STRICT:\n{ddl}"
        expected = set(EXPECTED_CHECKS[table])
        if at_head:
            expected |= CHECKS_ADDED_IN_0002.get(table, set())
        for name in expected:
            assert f"CONSTRAINT {name} CHECK" in ddl, f"{table}: CHECK {name} missing"
        if not at_head:
            for name in CHECKS_ADDED_IN_0002.get(table, set()):
                assert name not in ddl
    for table, fks in EXPECTED_FKS.items():
        assert fks <= s["fks"][table], f"{table}: foreign keys {fks - s['fks'][table]} missing"
    assert s["triggers"] == EXPECTED_TRIGGERS, f"trigger mismatch: {s['triggers'] ^ EXPECTED_TRIGGERS}"
    assert EXPECTED_INDEXES <= s["indexes"], f"missing indexes: {EXPECTED_INDEXES - s['indexes']}"
    assert s["version"] == ([(HEAD_REVISION,)] if at_head else [("0001",)])
    if at_head:
        assert MISSION_TABLES <= set(s["tables"]), f"missing mission tables: {MISSION_TABLES - set(s['tables'])}"
        for table in MISSION_TABLES:
            assert s["tables"][table].rstrip().endswith("STRICT"), f"{table} is not STRICT"
    else:
        assert not (MISSION_TABLES & set(s["tables"]))


def test_upgrade_from_clean_state(migrated_db: Path):
    assert_full_schema(migrated_db, at_head=True)
    ddl = schema(migrated_db)["tables"]["measurement"]
    assert "observation_date TEXT" in ddl and "resolution_adequacy TEXT" in ddl


def test_only_strict_types_are_used(migrated_db: Path):
    conn = sqlite3.connect(migrated_db)
    allowed = {"INT", "INTEGER", "REAL", "TEXT", "BLOB", "ANY"}
    for table in TABLES:
        for col in conn.execute(f"PRAGMA table_info({table})"):
            assert col[2] in allowed, f"{table}.{col[1]} has non-STRICT type {col[2]}"


def test_downgrade_then_reupgrade_preserves_everything(migrated_db: Path):
    downgrade(migrated_db, "0001")
    assert_full_schema(migrated_db, at_head=False)
    upgrade(migrated_db)
    assert_full_schema(migrated_db, at_head=True)


def test_downgrade_to_base_removes_schema(migrated_db: Path):
    downgrade(migrated_db, "base")
    s = schema(migrated_db)
    assert not (TABLES & set(s["tables"]))
    assert not s["triggers"]


def test_triggers_still_fire_after_batch_rebuild(migrated_db: Path):
    """Survival is not just presence: the re-created triggers must work."""
    conn = raw(migrated_db)
    conn.execute("INSERT INTO planetary_body VALUES (1,'earth','Earth (test)','OGC:CRS84',6371008.8)")
    conn.execute("INSERT INTO region (id, code, body_id, region_role, region_level, validation_status, name)"
                 " VALUES (1,'test_region',1,'analog','region','regional_only','SYNTHETIC TEST REGION')")
    conn.execute("INSERT INTO parameter VALUES (1,'test_param','SYNTHETIC TEST PARAMETER','m','scalar','D')")
    conn.execute("INSERT INTO data_gap (region_id, parameter_id, reason) VALUES (1,1,'not_measured')")
    with pytest.raises(sqlite3.IntegrityError, match="data_gap already exists"):
        conn.execute("INSERT INTO measurement (region_id, parameter_id, value_kind, value_num, evidence_grade,"
                     " source_access) VALUES (1,1,'point',1.0,'B','dataset_opened')")


def test_failed_migration_is_atomic(tmp_path: Path):
    """A migration that fails half-way must leave no partial change behind."""
    scripts = tmp_path / "migrations"
    shutil.copytree(ALEMBIC_INI.parent / "migrations", scripts)
    (scripts / "versions" / "0099_broken.py").write_text(
        'revision = "0099"\ndown_revision = "0003"\nbranch_labels = None\ndepends_on = None\n'
        "from alembic import op\n"
        "def upgrade():\n"
        '    op.execute("DROP TRIGGER trg_measurement_no_gap_ins")\n'
        '    op.execute("DROP TABLE data_gap")\n'
        '    raise RuntimeError("deliberate failure for the atomicity test")\n'
        "def downgrade():\n    pass\n"
    )
    db = tmp_path / "atomic.sqlite"
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(scripts))
    import argparse
    cfg.cmd_opts = argparse.Namespace(x=[f"db={db}"])
    command.upgrade(cfg, HEAD_REVISION)
    with pytest.raises(RuntimeError, match="deliberate failure"):
        command.upgrade(cfg, "0099")
    assert_full_schema(db, at_head=True)
