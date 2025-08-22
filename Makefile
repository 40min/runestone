.PHONY: help install install-dev lint test test-coverage run clean setup

# Default target
help:
	@echo "Available commands:"
	@echo "  setup        - Set up the development environment"
	@echo "  install      - Install production dependencies"
	@echo "  install-dev  - Install development dependencies"
	@echo "  lint         - Run all linting checks"
	@echo "  lint-check   - Run linting in check mode (no fixes)"
	@echo "  test         - Run test suite"
	@echo "  test-coverage - Run tests with coverage report"
	@echo "  run          - Run the application (requires IMAGE_PATH and GEMINI_API_KEY)"
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

# Lint checking with fixes
lint:
	@echo "Running code formatters..."
	black src/ tests/
	isort src/ tests/
	@echo "Running linting checks..."
	flake8 src/ tests/

# Lint checking without fixes
lint-check:
	@echo "Checking code formatting..."
	black --check src/ tests/
	isort --check-only src/ tests/
	@echo "Running linting checks..."
	flake8 src/ tests/

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
