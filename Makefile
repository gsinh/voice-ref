# The commands a contributor runs. CI runs the same targets.
.PHONY: help setup secrets rotate-db-passwords up down logs ps db-reset seed lint fmt typecheck test check web-check

UV := uv --directory backend

help:            ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

setup:           ## Install dependencies, create .env and the secrets directory
	$(UV) sync --all-packages
	cd web && npm ci
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")
	@./scripts/make-secrets.sh

secrets:         ## Create missing secrets in ./secrets (keeps existing ones)
	@./scripts/make-secrets.sh

up:              ## Build and start the local stack, wait until healthy
	@./scripts/make-secrets.sh >/dev/null
	docker compose up -d --build --wait

down:            ## Stop the stack (keeps data)
	docker compose down

logs:            ## Follow logs
	docker compose logs -f

ps:              ## Show service status
	docker compose ps

seed:            ## Reset the demo data
	docker compose run --rm migrate seed

rotate-db-passwords: ## New module DB passwords: regenerate the URLs, re-run bootstrap
	rm -f secrets/BANK_DATABASE_URL secrets/ORCHESTRATOR_DATABASE_URL
	@./scripts/make-secrets.sh
	docker compose run --rm migrate bootstrap
	docker compose up -d --force-recreate backend

db-reset:        ## Delete the database volume; next `make up` re-creates everything
	docker compose down -v

lint:            ## Ruff lint + format check + module boundaries
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run lint-imports

fmt:             ## Auto-fix lint and formatting
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

typecheck:       ## mypy (strict)
	$(UV) run mypy apps libs modules

test:            ## Backend tests (integration tests need TEST_DATABASE_URL)
	$(UV) run pytest -q

web-check:       ## Web lint, typecheck, build
	cd web && npm run lint && npm run typecheck && npm run build

check: lint typecheck test web-check  ## Everything CI runs, locally
