# Runestone Project Makefile
# This Makefile provides convenient commands for development, testing, and deployment

.PHONY: help setup clean info
.PHONY: install install-dev install-backend install-frontend install-all
.PHONY: lint lint-check backend-lint frontend-lint
.PHONY: test test-coverage backend-test frontend-test
.PHONY: run run-backend run-frontend run-dev run-recall load-vocab
.PHONY: test-prompts-ocr test-prompts-analysis test-prompts-search test-prompts-vocabulary
.PHONY: dev-test dev-full ci-lint ci-test
.PHONY: db-init db-migrate db-upgrade db-downgrade db-current db-history
.PHONY: init-state docker-up docker-down docker-build restart-recall rebuild-restart-recall rebuild-restart-all

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
	@echo "  load-vocab       - Load vocabulary from CSV file (requires CSV_PATH, optional: DB_NAME, SKIP_EXISTENCE_CHECK)"
	@echo "  run-backend      - Start FastAPI backend server"
	@echo "  run-frontend     - Start frontend development server"
	@echo "  run-dev          - Start both backend and frontend concurrently"
	@echo "  run-recall       - Start the Rune Recall Telegram Bot Worker"
	@echo ""
	@echo "Test Prompts:"
	@echo "  test-prompts-ocr          - Test and display OCR prompt"
	@echo "  test-prompts-analysis     - Test analysis prompt (requires TEXT='sample text')"
	@echo "  test-prompts-search       - Test search prompt (requires TOPICS='topic1 topic2 ...')"
	@echo "  test-prompts-vocabulary   - Test vocabulary improvement prompt (requires WORD='word', optional: MODE=example_only|extra_info_only|all_fields)"
	@echo ""
	@echo "Development Workflows:"
	@echo "  dev-test         - Quick development test (install-dev + lint-check + test)"
	@echo "  dev-full         - Full development check (install-dev + lint + test-coverage)"
	@echo ""
	@echo "CI/CD:"
	@echo "  ci-lint          - CI linting pipeline"
	@echo "  ci-test          - CI testing pipeline"
	@echo ""
	@echo "Database Migrations:"
	@echo "  db-init          - Mark database as having the latest migration revision (for existing databases)"
	@echo "  db-migrate       - Create a new migration (requires MESSAGE='your migration message')"
	@echo "  db-upgrade       - Apply migrations to database (initialize new databases or upgrade existing ones)"
	@echo "  db-downgrade     - Downgrade migrations (requires REVISION=revision_id or REVISION=-1)"
	@echo "  db-current       - Show current migration revision"
	@echo "  db-history       - Show migration history"
	@echo ""
	@echo "Docker:"
	@echo "  init-state       - Initialize state directory and database with proper permissions"
	@echo "  docker-up        - Initialize state and start Docker services"
	@echo "  docker-down      - Stop and remove Docker services"
	@echo "  docker-build     - Build Docker images without cache"
	@echo "  restart-recall   - Restart the recall container"
	@echo "  rebuild-restart-recall - Rebuild and restart the recall container"
	@echo "  rebuild-restart-all - Rebuild and restart all containers"
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

# Load vocabulary from CSV file
load-vocab:
	@if [ -z "$(CSV_PATH)" ]; then \
		echo "❌ Error: CSV_PATH is required. Usage: make load-vocab CSV_PATH=path/to/vocab.csv [DB_NAME=name.db] [SKIP_EXISTENCE_CHECK=true]"; \
		exit 1; \
	fi
	@echo "📚 Loading vocabulary from CSV: $(CSV_PATH)"
	@uv run runestone load-vocab "$(CSV_PATH)" \
		$(if $(DB_NAME),--db-name "$(DB_NAME)") \
		$(if $(filter true,$(SKIP_EXISTENCE_CHECK)),--skip-existence-check)

# Start FastAPI backend server
run-backend: db-upgrade
	@echo "🚀 Starting FastAPI backend server..."
	@echo "📍 Backend will be available at: http://localhost:8010"
	@echo "📚 API documentation at: http://localhost:8010/docs"
	@uv run uvicorn runestone.api.main:app --reload --host 0.0.0.0 --port 8010

# Start frontend development server
run-frontend:
	@echo "🚀 Starting frontend development server..."
	@echo "📍 Frontend will be available at: http://localhost:5173"
	@cd frontend && npm run dev

# Start both backend and frontend concurrently
run-dev: db-upgrade
	@echo "🚀 Starting full development environment..."
	@echo "📍 Backend: http://localhost:8010"
	@echo "📍 Frontend: http://localhost:5173"
	@echo "📚 API Docs: http://localhost:8010/docs"
	@echo "Press Ctrl+C to stop both servers"
	@(cd frontend && npm run dev) & \
	uv run uvicorn runestone.api.main:app --reload --host 0.0.0.0 --port 8010

# Start Rune Recall Telegram Bot Worker
run-recall:
	@echo "🚀 Starting Rune Recall Telegram Bot Worker..."
	@uv run python recall_main.py

# =============================================================================
# TEST PROMPTS
# =============================================================================

# Test OCR prompt building
test-prompts-ocr:
	@echo "🧪 Testing OCR prompt..."
	@uv run runestone test-prompts ocr

# Test analysis prompt building
test-prompts-analysis:
	@if [ -z "$(TEXT)" ]; then \
		echo "❌ Error: TEXT is required. Usage: make test-prompts-analysis TEXT='sample text'"; \
		exit 1; \
	fi
	@echo "🧪 Testing analysis prompt with text: $(TEXT)"
	@uv run runestone test-prompts analysis "$(TEXT)"

# Test search prompt building
test-prompts-search:
	@if [ -z "$(TOPICS)" ]; then \
		echo "❌ Error: TOPICS is required. Usage: make test-prompts-search TOPICS='topic1 topic2 ...'"; \
		exit 1; \
	fi
	@echo "🧪 Testing search prompt with topics: $(TOPICS)"
	@uv run runestone test-prompts search $(TOPICS)

# Test vocabulary improvement prompt building
test-prompts-vocabulary:
	@if [ -z "$(WORD)" ]; then \
		echo "❌ Error: WORD is required. Usage: make test-prompts-vocabulary WORD='word' [MODE=example_only|extra_info_only|all_fields]"; \
		exit 1; \
	fi
	@echo "🧪 Testing vocabulary improvement prompt for word: $(WORD)"
	@uv run runestone test-prompts vocabulary "$(WORD)" $(if $(MODE),--mode $(MODE))

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
# DATABASE MIGRATIONS
# =============================================================================

# Mark database as having the latest migration revision (for existing databases)
db-init:
	@echo "🗄️  Initializing database with current schema..."
	@uv run alembic stamp head
	@echo "✅ Database initialized!"

# Create a new migration
db-migrate:
	@if [ -z "$(MESSAGE)" ]; then \
		echo "❌ Error: MESSAGE is required. Usage: make db-migrate MESSAGE='your migration message'"; \
		exit 1; \
	fi
	@echo "🔄 Creating new migration: $(MESSAGE)"
	@uv run alembic revision --autogenerate -m "$(MESSAGE)"
	@echo "✅ Migration created!"

# Apply migrations to the database (initialize new databases or upgrade existing ones)
db-upgrade:
	@echo "⬆️  Upgrading database to latest migration..."
	@uv run alembic upgrade head
	@echo "✅ Database upgraded!"

# Downgrade migrations (specify revision or use -1 for one step back)
db-downgrade:
	@if [ -z "$(REVISION)" ]; then \
		echo "❌ Error: REVISION is required. Usage: make db-downgrade REVISION=revision_id or REVISION=-1"; \
		exit 1; \
	fi
	@echo "⬇️  Downgrading database to revision: $(REVISION)"
	@uv run alembic downgrade $(REVISION)
	@echo "✅ Database downgraded!"

# Show current migration revision
db-current:
	@echo "📍 Current migration revision:"
	@uv run alembic current

# Show migration history
db-history:
	@echo "📚 Migration history:"
	@uv run alembic history


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

# =============================================================================
# DOCKER COMMANDS
# =============================================================================

# Initialize state directory and database with proper permissions for Docker containers
init-state:
	@echo "🔧 Initializing state directory and database for Docker containers..."
	@./scripts/init-state.sh
	@echo "✅ State directory and database initialized!"

# Initialize state and start all Docker services
docker-up: init-state
	@echo "🐳 Starting Docker services..."
	@docker compose up -d
	@echo "✅ Docker services started!"
	@echo "📍 Backend: http://localhost:8010"
	@echo "📍 Frontend: http://localhost:3010"
	@echo "📚 API Docs: http://localhost:8010/docs"

# Stop and remove Docker services
docker-down:
	@echo "🛑 Stopping Docker services..."
	@docker compose down
	@echo "✅ Docker services stopped!"

# Build Docker images without cache
docker-build:
	@echo "🔨 Building Docker images..."
	@docker compose build --no-cache
	@echo "✅ Docker images built!"

# Restart the recall container
restart-recall:
	@echo "🔄 Restarting recall container..."
	@docker compose restart recall
	@echo "✅ Recall container restarted!"

# Rebuild and restart the recall container
rebuild-restart-recall:
	@echo "🔨 Rebuilding and restarting recall container..."
	@docker compose up --build --force-recreate -d recall
	@echo "✅ Recall container rebuilt and restarted!"

# Rebuild and restart all containers
rebuild-restart-all:
	@echo "🔨 Rebuilding and restarting all containers..."
	@docker compose up --build --force-recreate -d
