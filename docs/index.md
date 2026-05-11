<p align="center">
  <img src="https://raw.githubusercontent.com/arin-deloatch/docta/main/assets/docta.png" alt="DOCTA logo" width="400"/>
</p>

<p align="center"><i>A tool for tracking and analyzing differences across documentation versions using semantic content extraction.</i></p>

---

## Features

- **Hash-based delta detection**: Quickly identify changed, added, removed, and renamed documents
- **Semantic content comparison**: Extract and compare content blocks (headings, text, code, tables) while ignoring cosmetic HTML changes
- **Fuzzy rename detection**: Identify renamed/moved documents using similarity matching
- **Automated polling daemon**: Monitor GraphQL APIs for documentation changes and trigger pipelines automatically
- **Structured reporting**: Generate detailed JSON reports with change analysis
- **QA generation (optional)**: Generate question-answer pairs from documentation changes using RAGAS

---

## Quick Start

### One-command pipeline

```bash
uv run docta diff full \
  --old-root data/docs_v1 \
  --new-root data/docs_v2 \
  --old-version "1.0" \
  --new-version "2.0" \
  --output-dir artifacts \
  --max-docs 50 \
  --allow-overwrite
```

This creates two reports:

- `artifacts/delta_report.json` — hash-based change detection (what changed)
- `artifacts/semantic_diff_report.json` — detailed semantic analysis (how it changed)

### Two-stage pipeline

```bash
# Stage 1: Generate delta report
uv run docta diff compare \
  --old-root data/docs_v1 \
  --new-root data/docs_v2 \
  --old-version "1.0" \
  --new-version "2.0" \
  --output artifacts/delta_report.json \
  --allow-overwrite

# Stage 2: Semantic content comparison
uv run docta diff scan \
  --report artifacts/delta_report.json \
  --old-root data/docs_v1 \
  --new-root data/docs_v2 \
  --output artifacts/semantic_diff_report.json \
  --max-docs 50 \
  --allow-overwrite
```

---

## Next steps

- [Installation](installation.md) — requirements and setup
- [Document Comparison](usage/diff.md) — how semantic diffing works and all options
- [GraphQL Daemon](usage/daemon.md) — automated polling and pipeline configuration
- [QA Generation](usage/qa.md) — generating QA pairs from documentation changes
- [Commands Reference](reference/commands.md) — full command listing
