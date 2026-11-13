"""Mission Lab MVP: saved scenarios, runs, routes, events and reports.

Five new STRICT tables; no existing table is changed or rebuilt, so no
trigger has to be dropped or re-created. JSON columns are TEXT with a named
``json_valid`` CHECK. Every row describes a SIMULATION on synthetic terrain;
``data_status`` records that explicitly.

Originally written as 0003 on the Mission Lab branch; renumbered to 0007 when
it was integrated after the Phase 2 migrations (0003-0006).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-13
"""

from __future__ import annotations

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TABLES = {
    "mission_scenario": """
CREATE TABLE mission_scenario (
  id INTEGER NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  body_code TEXT NOT NULL,
  reference_region_code TEXT NOT NULL,
  objective_code TEXT NOT NULL,
  training_site_kind TEXT NOT NULL,
  training_site_region_id INTEGER,
  training_site_json TEXT NOT NULL,
  terrain_json TEXT NOT NULL,
  data_status TEXT NOT NULL,
  config_json TEXT NOT NULL,
  model_version TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  CONSTRAINT pk_mission_scenario PRIMARY KEY (id),
  CONSTRAINT fk_mission_scenario_training_site_region_id_region FOREIGN KEY (training_site_region_id) REFERENCES region (id),
  CONSTRAINT ck_mission_scenario_version_positive CHECK (version >= 1),
  CONSTRAINT ck_mission_scenario_site_kind_enum CHECK (training_site_kind IN ('synthetic_environment', 'curated_region')),
  CONSTRAINT ck_mission_scenario_site_shape CHECK ((training_site_kind = 'curated_region') = (training_site_region_id IS NOT NULL)),
  CONSTRAINT ck_mission_scenario_data_status_enum CHECK (data_status IN ('synthetic', 'processed', 'real', 'partial')),
  CONSTRAINT ck_mission_scenario_json CHECK (json_valid(training_site_json) AND json_valid(terrain_json) AND json_valid(config_json))
) STRICT""",
    "mission_run": """
CREATE TABLE mission_run (
  id INTEGER NOT NULL,
  scenario_id INTEGER NOT NULL,
  scenario_version INTEGER NOT NULL,
  case_label TEXT NOT NULL,
  comparison_group TEXT,
  seed INTEGER NOT NULL,
  config_snapshot_json TEXT NOT NULL,
  status TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  phases_json TEXT NOT NULL,
  frames_json TEXT NOT NULL,
  simulation_version TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT NOT NULL,
  CONSTRAINT pk_mission_run PRIMARY KEY (id),
  CONSTRAINT fk_mission_run_scenario_id_mission_scenario FOREIGN KEY (scenario_id) REFERENCES mission_scenario (id) ON DELETE CASCADE,
  CONSTRAINT ck_mission_run_case_enum CHECK (case_label IN ('custom', 'baseline', 'stress', 'mitigated')),
  CONSTRAINT ck_mission_run_status_enum CHECK (status IN ('COMPLETED', 'COMPLETED_WITH_DEVIATIONS', 'PARTIAL', 'SAFE_HOLD', 'NO_ROUTE')),
  CONSTRAINT ck_mission_run_json CHECK (json_valid(config_snapshot_json) AND json_valid(summary_json) AND json_valid(phases_json) AND json_valid(frames_json))
) STRICT""",
    "mission_route": """
CREATE TABLE mission_route (
  id INTEGER NOT NULL,
  run_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  planner_version TEXT NOT NULL,
  weights_json TEXT NOT NULL,
  constraints_json TEXT NOT NULL,
  route_json TEXT NOT NULL,
  is_demonstration INTEGER NOT NULL,
  CONSTRAINT pk_mission_route PRIMARY KEY (id),
  CONSTRAINT uq_mission_route_run_id_kind UNIQUE (run_id, kind),
  CONSTRAINT fk_mission_route_run_id_mission_run FOREIGN KEY (run_id) REFERENCES mission_run (id) ON DELETE CASCADE,
  CONSTRAINT ck_mission_route_kind_enum CHECK (kind IN ('recommended', 'alternate')),
  CONSTRAINT ck_mission_route_is_demonstration_bool CHECK (is_demonstration IN (0, 1)),
  CONSTRAINT ck_mission_route_json CHECK (json_valid(weights_json) AND json_valid(constraints_json) AND json_valid(route_json))
) STRICT""",
    "mission_event": """
CREATE TABLE mission_event (
  id INTEGER NOT NULL,
  run_id INTEGER NOT NULL,
  seq INTEGER NOT NULL,
  sim_time_s REAL NOT NULL,
  event_type TEXT NOT NULL,
  phase INTEGER NOT NULL,
  x_m REAL NOT NULL,
  y_m REAL NOT NULL,
  payload_json TEXT NOT NULL,
  result TEXT NOT NULL,
  CONSTRAINT pk_mission_event PRIMARY KEY (id),
  CONSTRAINT uq_mission_event_run_id_seq UNIQUE (run_id, seq),
  CONSTRAINT fk_mission_event_run_id_mission_run FOREIGN KEY (run_id) REFERENCES mission_run (id) ON DELETE CASCADE,
  CONSTRAINT ck_mission_event_phase_range CHECK (phase BETWEEN 1 AND 8),
  CONSTRAINT ck_mission_event_time_nonneg CHECK (sim_time_s >= 0),
  CONSTRAINT ck_mission_event_json CHECK (json_valid(payload_json))
) STRICT""",
    "mission_report": """
CREATE TABLE mission_report (
  id INTEGER NOT NULL,
  run_id INTEGER NOT NULL,
  report_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  snapshot_sha256 TEXT NOT NULL,
  artifact_path TEXT NOT NULL,
  has_viewer_snapshot INTEGER NOT NULL DEFAULT 0,
  CONSTRAINT pk_mission_report PRIMARY KEY (id),
  CONSTRAINT fk_mission_report_run_id_mission_run FOREIGN KEY (run_id) REFERENCES mission_run (id) ON DELETE CASCADE,
  CONSTRAINT ck_mission_report_sha256_shape CHECK (length(snapshot_sha256) = 64),
  CONSTRAINT ck_mission_report_has_viewer_snapshot_bool CHECK (has_viewer_snapshot IN (0, 1))
) STRICT""",
}
INDEXES = [
    "CREATE INDEX ix_mission_run_scenario_id ON mission_run (scenario_id)",
    "CREATE INDEX ix_mission_event_run_id ON mission_event (run_id)",
    "CREATE INDEX ix_mission_report_run_id ON mission_report (run_id)",
]


def upgrade() -> None:
    for ddl in TABLES.values():
        op.execute(ddl)
    for ddl in INDEXES:
        op.execute(ddl)


def downgrade() -> None:
    for name in reversed(list(TABLES)):
        op.execute(f"DROP TABLE {name}")
