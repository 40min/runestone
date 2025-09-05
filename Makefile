.PHONY: help install install-all install-dev install-frontend lint lint-frontend test test-coverage test-frontend run run-backend run-frontend clean setup

# Default target
help:
	@echo "Available commands:"
	@echo "  setup        - Set up the development environment"
	@echo "  install      - Install production dependencies"
	@echo "  install-all  - Install all dependencies (production + dev)"
	@echo "  install-dev  - Install development dependencies"
	@echo "  lint         - Run all linting checks"
	@echo "  lint-check   - Run linting in check mode (no fixes)"
	@echo "  lint-frontend - Run frontend linting checks"
	@echo "  test         - Run test suite"
	@echo "  test-coverage - Run tests with coverage report"
	@echo "  test-frontend - Run frontend test suite"
	@echo "  run          - Run the application (requires IMAGE_PATH and GEMINI_API_KEY)"
	@echo "  run-backend  - Run the FastAPI backend server"
	@echo "  install-frontend - Install frontend dependencies"
	@echo "  run-frontend - Run the frontend development server"
	@echo "  clean        - Clean up temporary files and caches"

# Set up development environment
setup: install-dev
	@echo "Setting up pre-commit hooks..."
	pre-commit install
	@echo "Development environment setup complete!"

# Install production dependencies
install:
	@echo "Installing production dependencies..."
	uv sync --no-dev

# Install development dependencies
install-dev:
	@echo "Installing development dependencies..."
	uv sync --extra dev

# Install all dependencies
install-all:
	@echo "Installing all dependencies..."
	uv sync --extra dev

# Lint checking with fixes
lint:
	@echo "Running code formatters..."
	uv run black src/ tests/
	uv run isort src/ tests/
	@echo "Running linting checks..."
	uv run flake8 --max-line-length=120 --extend-ignore=E203,W503 src/ tests/
	@echo "Running frontend linting..."
	cd frontend && npm run lint

# Lint checking without fixes
lint-check:
	@echo "Checking code formatting..."
	uv run black --check src/ tests/
	uv run isort --check-only src/ tests/
	@echo "Running linting checks..."
	uv run flake8 --max-line-length=120 --extend-ignore=E203,W503 src/ tests/

# Run frontend linting
lint-frontend:
	@echo "Running frontend linting checks..."
	cd frontend && npm run lint

# Run test suite
test:
	@echo "Running test suite..."
	pytest tests/ -v

# Run tests with coverage
test-coverage:
	@echo "Running test suite with coverage..."
	pytest tests/ -v --cov=src/runestone --cov-report=term-missing --cov-report=html

# Run the application (example usage)
run:
	@if [ -z "$(IMAGE_PATH)" ]; then \
		echo "Error: IMAGE_PATH is required. Usage: make run IMAGE_PATH=path/to/image.jpg"; \
		exit 1; \
	fi
	@if [ -z "$(GEMINI_API_KEY)" ]; then \
		echo "Error: GEMINI_API_KEY environment variable is required"; \
		exit 1; \
	fi
	@echo "Running Runestone with image: $(IMAGE_PATH)"
	runestone process "$(IMAGE_PATH)" --verbose

# Run the FastAPI backend server
run-backend:
	@echo "Starting FastAPI backend server..."
	uvicorn runestone.api.main:app --reload --host 0.0.0.0 --port 8000

# Install frontend dependencies
install-frontend:
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Run frontend test suite
test-frontend:
	@echo "Running frontend test suite..."
	cd frontend && npm run test:run


# Run the frontend development server
run-frontend:
	@echo "Starting frontend development server..."
	cd frontend && npm run dev

# Clean up temporary files and caches
clean:
	@echo "Cleaning up temporary files..."
	rm -rf __pycache__ .pytest_cache .coverage htmlcov
	rm -rf src/runestone.egg-info dist build
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "Cleanup complete!"

# Development convenience targets
dev-test: install-dev lint-check test

dev-full: install-dev lint test-coverage

# CI/CD friendly targets
ci-lint: install-dev lint-check

ci-test: install-dev test-coverage

# Show current environment info
info:
	@echo "Python version: $(shell python --version)"
	@echo "UV version: $(shell uv --version 2>/dev/null || echo 'UV not installed')"
	@echo "Current directory: $(shell pwd)"
	@echo "Virtual environment: $(shell echo $$VIRTUAL_ENV || echo 'None')"