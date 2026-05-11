# Development

## Setup

```bash
# Install all dependencies including dev tools
uv sync --group dev

# For QA generation features
uv sync --extra qa

# For docs tooling
uv sync --group docs
```

## Code quality

```bash
# Format code
uv run black .

# Lint
uv run ruff check .
uv run pylint src

# Type check
uv run mypy src tests
uv run pyright src tests

# Security scan
uv run bandit -r src/

# Run all checks (format-check, lint, type-check, security, test)
make all
```

## Testing

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src --cov-report=term-missing

# Via Makefile
make test
make coverage
```

Tests live under `tests/` and are organized by module. Integration tests that make real LLM API calls are marked with `@pytest.mark.integration` and excluded from the default run:

```bash
# Run integration tests explicitly
uv run pytest -m integration
```

## Makefile targets

| Target | Description |
|--------|-------------|
| `make all` | Run black-check, lint, type-check, security, test |
| `make black` | Format code with black |
| `make black-check` | Check formatting without modifying files |
| `make lint` | Run ruff + pylint |
| `make type-check` | Run mypy + pyright |
| `make security` | Run bandit |
| `make test` | Run pytest |
| `make coverage` | Run pytest with coverage report |

## Docs

```bash
# Preview docs locally
uv run mkdocs serve

# Build docs site
uv run mkdocs build
```

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](https://github.com/arin-deloatch/docta/blob/main/CONTRIBUTING.md) for setup instructions, coding standards, and the pull request process. Review the [Code of Conduct](https://github.com/arin-deloatch/docta/blob/main/CODE_OF_CONDUCT.md) before participating.

---

## Dependencies

### Core

| Package | Purpose |
|---------|---------|
| `beautifulsoup4` | HTML parsing |
| `html2text` | HTML to text conversion |
| `lxml` | Fast XML/HTML processing |
| `pydantic` | Data validation and settings |
| `rapidfuzz` | Fuzzy string matching for rename detection |
| `requests` | HTTP client for content fetching |
| `structlog` | Structured logging |
| `typer` | CLI framework |

### Optional (QA generation)

Install with `uv sync --extra qa`:

| Package | Purpose |
|---------|---------|
| `ragas>=0.4.3` | QA test generation framework |
| `litellm` | Multi-provider LLM support |
| `instructor` | Structured output from LLMs |
| `pyyaml` | YAML configuration support |
