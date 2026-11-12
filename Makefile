# ABAAD — Phase 1 developer commands. Run `make help` for the list.
SHELL := /bin/bash
UV := uv run --frozen

.PHONY: help install migrate dev stop status test test-backend test-frontend test-e2e \
        backup restore verify-data doctor spike-fixtures

help: ## Show this help
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS=":.*?## "}; {printf "  make %-15s %s\n", $$1, $$2}'

install: ## Install Python (uv) and Node (pnpm) dependencies from the lockfiles
	uv sync --frozen
	pnpm --dir frontend install --frozen-lockfile

migrate: ## Create/upgrade the SQLite database (var/abaad.sqlite)
	$(UV) alembic -c backend/alembic.ini upgrade head

dev: ## Start backend (:8000) and frontend (:3000) in the background
	@./scripts/dev.sh

stop: ## Stop only the processes started by `make dev`
	@./scripts/stop.sh

status: ## Show whether the dev processes are running
	@for f in backend frontend; do \
	  if [ -f .run/$$f.pid ] && kill -0 $$(cat .run/$$f.pid) 2>/dev/null; then echo "$$f: running (PID $$(cat .run/$$f.pid))"; \
	  else echo "$$f: not running"; fi; done

test: test-backend test-frontend test-e2e ## Run every automated test

test-backend: ## Python tests (backend, migrations, science package, scripts)
	$(UV) pytest

test-frontend: ## TypeScript type check and unit tests
	pnpm --dir frontend run typecheck
	pnpm --dir frontend run test:unit

test-e2e: ## Playwright end-to-end tests in Google Chrome (own ports 3100/8100)
	pnpm --dir frontend run test:e2e

backup: ## Online backup of the SQLite database to var/backups/
	$(UV) python scripts/backup.py backup

restore: ## Restore a backup: make restore FILE=var/backups/abaad-....sqlite
	@test -n "$(FILE)" || { echo "Usage: make restore FILE=var/backups/<file>.sqlite"; exit 1; }
	$(UV) python scripts/backup.py restore "$(FILE)"

verify-data: ## Check data/manifest.json against the files in data/
	$(UV) python scripts/verify_data.py

doctor: ## Environment report (OS, CPU, Python, SQLite, Node, GIS imports)
	$(UV) python scripts/doctor.py

spike-fixtures: ## Regenerate the synthetic map-spike fixtures
	$(UV) python spike/generate_fixtures.py
