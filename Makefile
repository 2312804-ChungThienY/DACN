# Lệnh tắt cho Linux/macOS (Windows: scripts/lms.ps1) – SPEC 6.4
.PHONY: setup seed mock etl-backfill users api web test e2e bench docker

setup:
	python -m pip install -r requirements.txt
	cd frontend && npm install
	python -m database.migrate up --target analytics
	python -m database.migrate up --target moodle

seed:
	python -m mockdata.seed_structure --reset

mock:
	python -m mockdata.generate_activity --reset

etl-backfill:
	python -m etl.jobs.backfill --from 2026-09-07

users:
	python -m backend.app.cli sync-users

api:
	python -m uvicorn backend.app.main:app --port 8000

web:
	cd frontend && npm run dev

test:
	python -m pytest -q
	cd frontend && npm test

e2e:
	cd frontend && npx playwright test

bench:
	python -m perf.build_x10
	python -m perf.explain_queries --dataset x1
	python -m perf.explain_queries --dataset x10

docker:
	docker compose --env-file docker/.env up --build -d
