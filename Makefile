.PHONY: help install dev-install format lint test test-cov clean docker-up docker-down run api

# Default target
help:
	@echo "PatchWeave - Intelligent Cloud Security Remediation System"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Setup targets:"
	@echo "  install        Install production dependencies"
	@echo "  dev-install    Install development dependencies"
	@echo "  setup          Full development setup (install + docker)"
	@echo ""
	@echo "Development targets:"
	@echo "  format         Format code with ruff"
	@echo "  lint           Run linting checks"
	@echo "  test           Run tests"
	@echo "  test-cov       Run tests with coverage report"
	@echo "  clean          Clean build artifacts"
	@echo ""
	@echo "Docker targets:"
	@echo "  docker-up      Start LocalStack and ChromaDB"
	@echo "  docker-down    Stop all containers"
	@echo "  docker-logs    Show container logs"
	@echo "  docker-health  Check container health"
	@echo ""
	@echo "Run targets:"
	@echo "  run            Run the main application"
	@echo "  api            Run the FastAPI server"
	@echo "  load-playbooks Load playbooks into ChromaDB"

# =============================================================================
# Setup
# =============================================================================

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"

setup: dev-install docker-up
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@make docker-health
	@echo "Development environment ready!"

# =============================================================================
# Code Quality
# =============================================================================

format:
	ruff format src tests
	ruff check --fix src tests

lint:
	ruff check src tests
	ruff format --check src tests

# =============================================================================
# Testing
# =============================================================================

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v -m unit

test-integration:
	pytest tests/integration/ -v -m integration

test-cov:
	pytest tests/ --cov=patchweave --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

# =============================================================================
# Docker
# =============================================================================

docker-up:
	docker-compose up -d localstack-test localstack-prod chromadb
	@echo "Waiting for services to start..."
	@sleep 5

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-health:
	@echo "Checking LocalStack TEST (4566) health..."
	@curl -s http://localhost:4566/_localstack/health | python -m json.tool || echo "LocalStack TEST not ready"
	@echo ""
	@echo "Checking LocalStack PROD (4567) health..."
	@curl -s http://localhost:4567/_localstack/health | python -m json.tool || echo "LocalStack PROD not ready"
	@echo ""
	@echo "Checking ChromaDB health..."
	@curl -s http://localhost:8000/api/v1/heartbeat | python -m json.tool || echo "ChromaDB not ready"

docker-clean:
	docker-compose down -v
	rm -rf localstack_test_data localstack_prod_data chroma_data

# =============================================================================
# Application
# =============================================================================

run:
	python -m patchweave.main

api:
	uvicorn patchweave.api.app:app --host 0.0.0.0 --port 8080 --reload

load-playbooks:
	python -m patchweave.scripts.load_playbooks

# =============================================================================
# Cleanup
# =============================================================================

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf src/*.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

clean-all: clean docker-clean
	rm -rf .venv/
	rm -rf logs/

# =============================================================================
# Development Helpers
# =============================================================================

# Create a test S3 bucket in LocalStack
test-s3:
	aws --endpoint-url=http://localhost:4566 s3 mb s3://test-bucket
	aws --endpoint-url=http://localhost:4566 s3 ls

# Show all LocalStack services
localstack-services:
	curl -s http://localhost:4566/_localstack/health | python -m json.tool
