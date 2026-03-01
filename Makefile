.PHONY: help dev up down build test lint migrate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start all services in development mode
	docker compose up --build

up: ## Start all services (detached)
	docker compose up -d

down: ## Stop all services
	docker compose down

build: ## Build all containers
	docker compose build

logs: ## Tail logs from all services
	docker compose logs -f

# --- Backend ---
backend-shell: ## Open a shell in the backend container
	docker compose exec backend bash

migrate: ## Run database migrations
	docker compose exec backend alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create msg="add users table")
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

test-backend: ## Run backend tests
	docker compose exec backend pytest -v

lint-backend: ## Lint backend code
	docker compose exec backend ruff check app/

# --- Frontend ---
frontend-shell: ## Open a shell in the frontend container
	docker compose exec frontend sh

test-frontend: ## Run frontend tests
	docker compose exec frontend npm test

lint-frontend: ## Lint frontend code
	docker compose exec frontend npm run lint
