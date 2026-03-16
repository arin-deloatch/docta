.PHONY: help install lint format type-check security test all clean

help:
	@echo "Available targets:"
	@echo "  install      - Install dependencies using uv"
	@echo "  lint         - Run all linters (ruff, pylint)"
	@echo "  format       - Format code with black"
	@echo "  format-check - Check code formatting without changes"
	@echo "  type-check   - Run type checkers (mypy, pyright)"
	@echo "  security     - Run security checks (bandit)"
	@echo "  test         - Run tests with pytest"
	@echo "  all          - Run format, lint, type-check, security, and test"
	@echo "  clean        - Remove cache and build artifacts"

install:
	uv sync

lint:
	uv run ruff check src
	uv run pylint src/

format:
	uv run black src

format-check:
	uv run black --check src

type-check:
	uv run mypy src/
	uv run pyright src

security:
	uv run bandit -r src/

test:
	uv run pytest

pre-commit: format lint type-check security

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
