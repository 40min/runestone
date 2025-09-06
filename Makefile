# Runestone Project Makefile
# This Makefile provides convenient commands for development, testing, and deployment

.PHONY: help setup clean info
.PHONY: install install-dev install-backend install-frontend install-all
.PHONY: lint lint-check backend-lint frontend-lint
.PHONY: test test-coverage backend-test frontend-test
.PHONY: run run-backend run-frontend run-dev
.PHONY: dev-test dev-full ci-lint ci-test

# =============================================================================
# HELP AND INFO
# =============================================================================

# Default target - show help
help:
	@echo "Runestone Development Commands"
	@echo "=============================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  setup            - Set up development environment with pre-commit hooks"
	@echo "  install          - Install production dependencies only"
	@echo "  install-dev      - Install all dependencies (production + development)"
	@echo "  install-backend  - Install backend dependencies"
	@echo "  install-frontend - Install frontend dependencies"
	@echo "  install-all      - Install all dependencies concurrently"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             - Run all linting and formatting (with fixes)"
	@echo "  lint-check       - Run linting checks only (no fixes)"
	@echo "  backend-lint     - Run backend linting and formatting"
	@echo "  frontend-lint    - Run frontend linting"
	@echo ""
	@echo "Testing:"
	@echo "  test             - Run all test suites"
	@echo "  test-coverage    - Run tests with coverage report"
	@echo "  backend-test     - Run backend tests only"
	@echo "  frontend-test    - Run frontend tests only"
	@echo ""
	@echo "Running Applications:"
	@echo "  run              - Run CLI application (requires IMAGE_PATH and GEMINI_API_KEY)"
	@echo "  run-backend      - Start FastAPI backend server"
	@echo "  run-frontend     - Start frontend development server"
	@echo "  run-dev          - Start both backend and frontend concurrently"
	@echo ""
	@echo "Development Workflows:"
	@echo "  dev-test         - Quick development test (install-dev + lint-check + test)"
	@echo "  dev-full         - Full development check (install-dev + lint + test-coverage)"
	@echo ""
	@echo "CI/CD:"
	@echo "  ci-lint          - CI linting pipeline"
	@echo "  ci-test          - CI testing pipeline"
	@echo ""
	@echo "Utilities:"
	@echo "  clean            - Clean temporary files and caches"
	@echo "  info             - Show environment information"

# Show environment information
info:
	@echo "Environment Information:"
	@echo "======================="
	@echo "Python version: $(shell python --version 2>/dev/null || echo 'Python not found')"
	@echo "UV version: $(shell uv --version 2>/dev/null || echo 'UV not installed')"
	@echo "Node version: $(shell node --version 2>/dev/null || echo 'Node not found')"
	@echo "NPM version: $(shell npm --version 2>/dev/null || echo 'NPM not found')"
	@echo "Current directory: $(shell pwd)"
	@echo "Virtual environment: $(shell echo $$VIRTUAL_ENV || echo 'None active')"

# =============================================================================
# SETUP AND INSTALLATION
# =============================================================================

# Set up development environment
setup: install-dev
	@echo "Setting up pre-commit hooks..."
	@uv run pre-commit install
	@echo "✅ Development environment setup complete!"

# Install production dependencies only
install:
	@echo "📦 Installing production dependencies..."
	@uv sync --no-dev

# Install all dependencies (production + development)
install-dev:
	@echo "📦 Installing all dependencies (production + development)..."
	@uv sync --extra dev

# Install backend dependencies (same as install-dev for this project)
install-backend:
	@echo "📦 Installing backend dependencies..."
	@uv sync --extra dev

# Install frontend dependencies
install-frontend:
	@echo "📦 Installing frontend dependencies..."
	@cd frontend && npm install

# Install all dependencies concurrently
install-all:
	@echo "📦 Installing all dependencies concurrently..."
	@$(MAKE) install-backend & \
	$(MAKE) install-frontend & \
	wait
	@echo "✅ All dependencies installed!"

# =============================================================================
# CODE QUALITY AND LINTING
# =============================================================================

# Run all linting and formatting (with fixes)
lint: backend-lint frontend-lint
	@echo "✅ All linting complete!"

# Run linting checks only (no fixes)
lint-check:
	@echo "🔍 Checking code formatting and linting..."
	@uv run black --check src/ tests/
	@uv run isort --check-only src/ tests/
	@uv run flake8 --max-line-length=120 --extend-ignore=E203,W503 src/ tests/
	@cd frontend && npm run lint
	@echo "✅ Linting checks complete!"

# Run backend linting and formatting
backend-lint:
	@echo "🔧 Running backend code formatting and linting..."
	@uv run black src/ tests/
	@uv run isort src/ tests/
	@uv run flake8 --max-line-length=120 --extend-ignore=E203,W503 src/ tests/
	@echo "✅ Backend linting complete!"

# Run frontend linting
frontend-lint:
	@echo "🔧 Running frontend linting..."
	@cd frontend && npm run lint
	@echo "✅ Frontend linting complete!"

# =============================================================================
# TESTING
# =============================================================================

# Run all test suites
test: backend-test frontend-test
	@echo "✅ All tests complete!"

# Run tests with coverage report
test-coverage:
	@echo "🧪 Running backend tests with coverage..."
	@uv run pytest tests/ -v --cov=src/runestone --cov-report=term-missing --cov-report=html
	@echo "🧪 Running frontend tests..."
	@cd frontend && npm run test:run
	@echo "✅ Test coverage complete! Check htmlcov/ for detailed report."

# Run backend tests only
backend-test:
	@echo "🧪 Running backend test suite..."
	@uv run pytest tests/ -v

# Run frontend tests only
frontend-test:
	@echo "🧪 Running frontend test suite..."
	@cd frontend && npm run test:run

# =============================================================================
# RUNNING APPLICATIONS
# =============================================================================

# Run CLI application
run:
	@if [ -z "$(IMAGE_PATH)" ]; then \
		echo "❌ Error: IMAGE_PATH is required. Usage: make run IMAGE_PATH=path/to/image.jpg"; \
		exit 1; \
	fi
	@if [ -z "$(GEMINI_API_KEY)" ]; then \
		echo "❌ Error: GEMINI_API_KEY environment variable is required"; \
		exit 1; \
	fi
	@echo "🚀 Running Runestone with image: $(IMAGE_PATH)"
	@uv run runestone process "$(IMAGE_PATH)" --verbose

# Start FastAPI backend server
run-backend:
	@echo "🚀 Starting FastAPI backend server..."
	@echo "📍 Backend will be available at: http://localhost:8000"
	@echo "📚 API documentation at: http://localhost:8000/docs"
	@uv run uvicorn runestone.api.main:app --reload --host 0.0.0.0 --port 8000

# Start frontend development server
run-frontend:
	@echo "🚀 Starting frontend development server..."
	@echo "📍 Frontend will be available at: http://localhost:5173"
	@cd frontend && npm run dev

# Start both backend and frontend concurrently
run-dev:
	@echo "🚀 Starting full development environment..."
	@echo "📍 Backend: http://localhost:8000"
	@echo "📍 Frontend: http://localhost:5173"
	@echo "📚 API Docs: http://localhost:8000/docs"
	@echo "Press Ctrl+C to stop both servers"
	@(cd frontend && npm run dev) & \
	uv run uvicorn runestone.api.main:app --reload --host 0.0.0.0 --port 8000

# =============================================================================
# DEVELOPMENT WORKFLOWS
# =============================================================================

# Quick development test workflow
dev-test: install-dev lint-check test
	@echo "✅ Development test workflow complete!"

# Full development check workflow
dev-full: install-dev lint test-coverage
	@echo "✅ Full development workflow complete!"

# =============================================================================
# CI/CD WORKFLOWS
# =============================================================================

# CI linting pipeline
ci-lint: install-dev lint-check
	@echo "✅ CI linting pipeline complete!"

# CI testing pipeline
ci-test: install-dev test-coverage
	@echo "✅ CI testing pipeline complete!"

# =============================================================================
# UTILITIES
# =============================================================================

# Clean up temporary files and caches
clean:
	@echo "🧹 Cleaning up temporary files and caches..."
	@rm -rf __pycache__ .pytest_cache .coverage htmlcov
	@rm -rf src/runestone.egg-info dist build
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@cd frontend && npm run clean 2>/dev/null || true
	@echo "✅ Cleanup complete!"