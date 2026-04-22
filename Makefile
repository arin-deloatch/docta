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

uv-lock-check:
	uv lock --check

install-deps-test:
	uv sync --group dev

ruff:
	uv run ruff check src tests

pylint:
	uv run pylint src
	uv run pylint --disable=R0801 tests

black:
	uv run black src tests

black-check:
	uv run black --check src tests

type-check:
	uv run mypy src tests

bandit:
	uv run bandit -r src

test:
	uv run pytest

pre-commit: black-check ruff bandit pylint type-check

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
