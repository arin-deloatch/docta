# Contributing to DOCTA

Thank you for your interest in contributing. This document covers everything you need
to open a pull request, write a good commit, and keep the project moving smoothly.

---

## Getting started

```bash
# Clone your fork (external contributors) or the repo directly (maintainers)
git clone https://github.com/<your-username>/docta.git
cd docta

# Install all dependencies (including dev extras)
uv sync

# Verify everything works
uv run pytest
make all
```

---

## Contribution model

### External contributors

Fork the repository, make your changes in a branch on your fork, then open a pull request
back to `main`. GitHub will not let external contributors push branches directly to this
repo.

```
your-fork/feat/my-feature  →  PR  →  arin-deloatch/docta:main
```

### Maintainers

Work directly off branches in this repo using the naming conventions below. Push and open
a PR against `main` — do not push directly to `main`.

---

## Branch naming

| Prefix      | When to use                                |
|-------------|--------------------------------------------|
| `feat/`     | New feature or capability                  |
| `fix/`      | Bug fix                                    |
| `chore/`    | Maintenance, tooling, dependency updates   |
| `docs/`     | Documentation-only changes                 |
| `refactor/` | Code restructuring without behavior change |

---

## Commit conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/). Every
commit message drives the automated CHANGELOG and version bump when a release is cut.

| Prefix          | What it signals                     | Version bump |
|-----------------|-------------------------------------|--------------|
| `fix: ...`      | Bug fix                             | patch        |
| `feat: ...`     | New feature                         | minor        |
| `feat!: ...`    | Breaking change                     | major        |
| `chore: ...`    | Maintenance (no behavior change)    | none         |
| `docs: ...`     | Documentation only                  | none         |
| `ci: ...`       | CI/CD pipeline changes              | none         |
| `refactor: ...` | Refactor without behavior change    | none         |
| `test: ...`     | Test additions or changes           | none         |

Breaking changes can also be indicated with a `BREAKING CHANGE:` footer on any commit type.

**Examples:**

```
feat: add semantic diff caching for repeated queries
fix: correct polling interval off-by-one in daemon loop
feat!: remove deprecated --legacy-mode flag
chore: update litellm to 1.82.7
```

Keep commits small and focused — one concern per commit.

---

## PR process

1. Ensure `make all` passes locally before opening a PR.
2. Write tests for any new behavior. Critical logic requires unit-level tests.
3. Add type hints to all public functions.
4. Do not include unrelated file changes.
5. Reference any related issues in the PR description.

---

## Code style

| Tool    | Command               | Config            |
|---------|-----------------------|-------------------|
| black   | `uv run black .`      | `line-length = 200` |
| ruff    | `uv run ruff check .` | `line-length = 200` |
| pyright | `uv run pyright`      | strict mode       |
| pytest  | `uv run pytest`       | `tests/` directory |

- Use `structlog` for all logging. Never use `print()` in production code paths.
- All public functions must have type hints with explicit return types.
- Use pydantic v2 for all models. Never use plain dataclasses or untyped dicts.
- Standard library imports first, third-party second, local last. No wildcard imports.

---

## Dependency changes

Always use `uv` to manage dependencies. Never edit `pyproject.toml` dependency lists
by hand or use `pip install`.

```bash
uv add <package>        # runtime dependency
uv add --dev <package>  # dev dependency
uv sync                 # sync after pulling changes
```

Commit `uv.lock` alongside every dependency change.

---

## Release process

Releases are fully automated via [release-please](https://github.com/googleapis/release-please).

1. Merge one or more Conventional Commits to `main`.
2. release-please opens (or updates) a Release PR with a bumped version in `pyproject.toml`
   and a generated `CHANGELOG.md`.
3. Review and merge the Release PR when ready to ship.
4. release-please tags the commit (e.g., `v0.2.0`) and a versioned Docker image is
   published automatically to `quay.io/rh-ee-adeloatc/docta`.

There is no need to manually create tags or edit `CHANGELOG.md`.

---

## Maintainer notes

Required secrets and one-time infrastructure setup are documented in the workflow files
under `.github/workflows/`.
