# Agent Guidelines

This file instructs AI coding agents (Claude Code, GitHub Copilot, Cursor, etc.) on how
to work correctly in this repository.

---

## Package management

- Use `uv` exclusively. Never generate `pip install`, `requirements.txt`, Poetry, or
  pipenv commands.
- Add dependencies with `uv add <package>` and commit `uv.lock` alongside every change.
- Sync environments with `uv sync`.

## Python version

- Minimum: Python 3.13. Do not use APIs or syntax unavailable in 3.13.

## Formatting and linting

- Formatter: `black` with `line-length = 200`.
- Linter: `ruff` with `line-length = 200`.
- Type checker: `pyright` in strict mode.
- Run `make all` to verify before suggesting a change is complete.

## Logging

- Use `structlog` for all logging. Never use `print()` in production code paths.
- Log levels: `DEBUG` for development, `INFO` for standard operations, `ERROR` for failures.
- Never log secrets, tokens, or raw credentials at any level.

## Testing

- Framework: `pytest`, tests live in `tests/`.
- All new features require tests. Critical logic requires unit-level tests.
- Do not mock databases or external services in a way that diverges from production behavior.
- Prefer deterministic tests — no randomness.

## Commit style

- Follow Conventional Commits: `fix:`, `feat:`, `chore:`, `docs:`, `ci:`, `refactor:`, `test:`.
- One concern per commit. Do not bundle unrelated changes.
- Commit messages in present tense, imperative mood.

## Configuration files

- Format: YAML only. Two-space indentation. snake_case keys. No tabs.
- Registry files live under `config/registry/`.

## Data models

- Use pydantic v2 for all models. Never use plain dataclasses or untyped dicts.

## Off-limits without explicit discussion

- `uv.lock` — never edit manually.
- `deployment/k8s/` — Kubernetes manifests; coordinate before changing.
- Core abstractions (CLI entrypoint, daemon loop, diff engine) — ask before refactoring.

## Secrets

- Never hardcode API keys, tokens, or credentials.
- All secrets must be read from environment variables.
- Reference `.env.example` for the expected variable names.
