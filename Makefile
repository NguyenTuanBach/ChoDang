.PHONY: install be-run be-test be-lint be-fmt seed-dev agent-run agent-llm-check agent-test agent-lint fe-run fe-lint test lint check up down logs config clean

# Python 3.12 + uv. Chạy từ gốc repo.
install:
	cd be && uv sync --extra dev
	cd agent && uv sync --extra dev
	cd fe && npm ci

# ---- Backend (cổng 8000) ----
be-run:
	cd be && uv run python -m vin15

be-test:
	cd be && uv run pytest

# ---- Postgres local (Docker, pgvector) cho test tích hợp: nhanh hơn Supabase từ xa ~100 lần ----
# Chạy: make db-up && make be-test-db   (db-down dừng, db-reset xóa cả dữ liệu)
.PHONY: db-up db-down db-reset be-test-db e2e
LOCAL_DB_URL ?= postgresql://vin15:vin15@127.0.0.1:55434/vin15
db-up:
	@docker inspect vin15-pg >/dev/null 2>&1 || docker run -d --name vin15-pg -e POSTGRES_PASSWORD=vin15 -e POSTGRES_USER=vin15 -e POSTGRES_DB=vin15 \
		-p 127.0.0.1:55434:5432 -v vin15-pg-data:/var/lib/postgresql/data --health-cmd "pg_isready -U vin15" --health-interval 2s --health-retries 30 \
		pgvector/pgvector:0.8.0-pg17 >/dev/null
	@docker start vin15-pg >/dev/null
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' vin15-pg)" = healthy ]; do sleep 1; done
	@docker exec vin15-pg psql -U vin15 -d vin15 -q -c "create extension if not exists vector; create extension if not exists unaccent; create extension if not exists btree_gist;"
	@echo "Postgres local sẵn sàng: $(LOCAL_DB_URL)"
db-down:
	docker stop vin15-pg
db-reset:
	-docker rm -f vin15-pg
	-docker volume rm vin15-pg-data
be-test-db:
	cd be && TEST_DATABASE_URL=$(LOCAL_DB_URL) uv run pytest
# BE thật + agent thật (tiến trình riêng) + LLM giả, qua WebSocket. Cần make db-up và make install.
e2e:
	cd be && TEST_DATABASE_URL=$(LOCAL_DB_URL) uv run pytest -m e2e tests/e2e

be-lint:
	cd be && uv run ruff check src tests

be-fmt:
	cd be && uv run ruff format src tests

# Dữ liệu giả cho dev (người dùng, hồ sơ thực tập, bộ quy chế mẫu). Cần DATABASE_URL; từ chối khi APP_ENV=production.
seed-dev:
	cd be && uv run python scripts/seed_dev.py

# ---- Agent (cổng 8100) ----
agent-run:
	cd agent && uv run vin15-agent-api

agent-llm-check:
	cd agent && uv run python -m vin15_agent.runtime.llm_check

agent-test:
	cd agent && uv run pytest

agent-lint:
	cd agent && uv run ruff check src tests

# Đánh giá trợ lý chính sách bằng LLM THẬT (cần BE đã seed, tốn khóa LLM; không chạy trong CI mặc định).
# Ví dụ: make agent-eval ARGS="--persona sv_a --group grounded"
.PHONY: agent-eval
agent-eval:
	cd agent && uv run python -m vin15_agent.runtime.agent_eval $(ARGS)

# ---- Cả hai ----
# ---- Frontend Next.js (cổng 3000) ----
fe-run:
	cd fe && npm run dev

fe-lint:
	cd fe && npm run lint && npx tsc --noEmit

test: be-test agent-test
lint: be-lint agent-lint
check: lint test

# ---- Docker (cp .env.example .env trước) ----
config:
	docker compose config -q

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -not -path "*/.venv/*" -prune -exec rm -rf {} +
