# Database and migration verification report (deliverable 4)

Tested in the cloud workspace (SQLite 3.45.1). The owner's Mac runs the same tests through `make test-backend`.

## Schema
Revisions `0001` (8 STRICT tables, 10 triggers, 6 indexes) and `0002` (rebuilds `measurement` via Alembic batch mode with `recreate="always"`). The full DDL after `upgrade head` is in [evidence/schema-after-head.sql](evidence/schema-after-head.sql). No rows are seeded.

## Evidence (pytest, `backend/tests/test_migrations.py`, `test_constraints.py`, `test_db_and_health.py`)

| Property | How it is verified | Result (cloud) |
| --- | --- | --- |
| SQLite ≥ 3.37.0 | `sqlite3.sqlite_version` checked at engine creation, in `/health` and in `test_runtime_sqlite_supports_strict` | PASS (3.45.1) |
| STRICT on every table | `sqlite_master.sql` ends with `STRICT` after upgrade, after downgrade to 0001 and after re-upgrade | PASS |
| Only STRICT-legal column types | `PRAGMA table_info` types ⊆ {INT, INTEGER, REAL, TEXT, BLOB, ANY} | PASS |
| Named CHECK constraints (34 from 0001 + 1 added in 0002 = 35) | Each `CONSTRAINT <name> CHECK` is present after every migration step | PASS |
| Foreign keys (11) | `PRAGMA foreign_key_list` per table after every step | PASS |
| Triggers (10) | Exact set in `sqlite_master` after every step | PASS |
| Triggers still *fire* after the batch rebuild | Inserting a measurement where a data gap exists is refused | PASS |
| Indexes, incl. partial unique `uq_measurement_current_region_parameter` | Present after every step | PASS |
| Atomic migrations | A deliberately failing revision 0003 drops a trigger and a table, then raises; afterwards the schema is unchanged | PASS |
| `PRAGMA foreign_keys=ON` and WAL on every app connection | Checked on 3 connections | PASS |
| Enforcement | FK violation, named CHECK, STRICT type error, interval shape (no midpoint), RFC 7946 refused for Mars, RFC 7946 needs WGS 84 fields, geometry body = region body, measurement ⟂ data gap, one current measurement, synthetic rows refused | 10/10 PASS |

## Problems found and fixed
1. **Alembic rebuild failed** with "error in trigger trg_gap_no_measurement_ins: no such table: main.measurement". Triggers on *other* tables that reference the rebuilt table must also be dropped and re-created (DECISIONS P1-12).
2. **Partial migration on failure.** Python's sqlite3 did not wrap DDL in a transaction, so that failure had already dropped triggers. Fixed with explicit `BEGIN` handling (DECISIONS P1-13) and covered by the atomicity test.

## Backup and restore
`make backup` uses `sqlite3.Connection.backup` (SQLite's online backup API), then `PRAGMA integrity_check`. `make restore FILE=…` verifies the backup, refuses while the backend runs, keeps a `pre-restore-*.sqlite` safety copy, restores, and re-checks integrity. Covered by `scripts/tests/test_scripts.py`, which damages the data after a backup, restores it, and checks the rows and STRICT DDL are back. Manual cloud run: backup written, integrity ok, 9 tables (8 + `alembic_version`), revision 0002; restore succeeded.
