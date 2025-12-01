.PHONY: install run test migrate makemigrations docker-up docker-down docker-build logs lint format shell clean help

# Default target
.DEFAULT_GOAL := help

install: ## Install dependencies using poetry
	poetry install

run: ## Run the FastAPI server with hot reload
	poetry run uvicorn app.main:app --reload

test: ## Run tests using pytest
	poetry run pytest

migrate: ## Apply database migrations
	poetry run alembic upgrade head

makemigrations: ## Create a new migration file (usage: make makemigrations msg="message")
	poetry run alembic revision --autogenerate -m "$(msg)"

docker-up: ## Start services using Docker Compose
	docker-compose up -d

docker-down: ## Stop services using Docker Compose
	docker-compose down

docker-build: ## Build docker images
	docker-compose build

logs: ## View docker logs
	docker-compose logs -f

lint: ## Run ruff check
	poetry run ruff check .

format: ## Run ruff format
	poetry run ruff format .

shell: ## Enter poetry shell
	poetry shell

clean: ## Remove pycache and other temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
