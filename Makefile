.PHONY: install be-run be-test be-lint be-fmt agent-run agent-test agent-lint test lint check up down logs config clean

# Python 3.12 + uv. Chạy từ gốc repo.
install:
	cd be && uv sync --extra dev
	cd agent && uv sync --extra dev

# ---- Backend (cổng 8000) ----
be-run:
	cd be && uv run python -m vin15

be-test:
	cd be && uv run pytest

be-lint:
	cd be && uv run ruff check src tests

be-fmt:
	cd be && uv run ruff format src tests

# ---- Agent (cổng 8100) ----
agent-run:
	cd agent && uv run vin15-agent-api

agent-test:
	cd agent && uv run pytest

agent-lint:
	cd agent && uv run ruff check src tests

# ---- Cả hai ----
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
