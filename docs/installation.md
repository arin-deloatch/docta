# Installation

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package manager)

## Core installation

```bash
git clone https://github.com/arin-deloatch/docta
cd docta
uv sync
```

This installs the `docta` CLI with core document comparison features.

## Optional features

### QA Generation

Adds LLM dependencies for generating question-answer pairs from documentation changes:

```bash
uv sync --extra qa
```

This adds approximately 50 packages including `ragas`, `litellm`, and `instructor`. See [QA Generation](usage/qa.md) for usage.

### GraphQL Daemon

Included in the core installation. Requires environment configuration before use. See [GraphQL Daemon](usage/daemon.md) for setup.

## Development environment

```bash
# Install all dev tools (black, ruff, pylint, mypy, pyright, bandit, pytest)
uv sync --group dev

# Install docs tooling
uv sync --group docs

# Install everything
uv sync --group dev --group docs --extra qa
```
