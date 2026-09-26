# The commands a contributor runs. CI runs the same targets.
.PHONY: help setup up down logs ps db-reset lint fmt typecheck test check web-check

help:            ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

setup:           ## Install Python + web dependencies, create .env if missing
	uv sync --all-packages
	cd services/web && npm ci
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

up:              ## Build and start the core stack, wait until healthy
	docker compose up -d --build --wait

down:            ## Stop the stack (keeps data)
	docker compose down

logs:            ## Follow logs
	docker compose logs -f

ps:              ## Show service status
	docker compose ps

db-reset:        ## Delete the database volume and re-seed on next `make up`
	docker compose down -v

lint:            ## Ruff lint + format check
	uv run ruff check .
	uv run ruff format --check .

fmt:             ## Auto-fix lint and formatting
	uv run ruff check --fix .
	uv run ruff format .

typecheck:       ## mypy (strict)
	uv run mypy libs services

test:            ## Python unit tests
	uv run pytest -q

web-check:       ## Web lint, typecheck, build
	cd services/web && npm run lint && npm run typecheck && npm run build

check: lint typecheck test web-check  ## Everything CI runs, locally
