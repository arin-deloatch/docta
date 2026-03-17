<p align="center">
  <img src="assets/doc-diff.png" alt="AI Generated Triangle" width="400"/>
</p>

<h1 align="center">DOCTA</h1>

<p align="center"><i>A tool for tracking and analyzing differences across documentation versions using semantic content extraction.</i></p>

---
<p align="center" style="font-weight: bold;"><i>This repository is under heavy construction.</i></p>

## Features

- **Hash-based delta detection**: Quickly identify changed, added, removed, and renamed documents
- **Semantic content comparison**: Extract and compare content blocks (headings, text, code, tables) while ignoring cosmetic HTML changes
- **Fuzzy rename detection**: Identify renamed/moved documents using similarity matching
- **Structured reporting**: Generate detailed JSON reports with change analysis

## Quick Start

### Full Pipeline (Recommended)

Run both manifest comparison and semantic diffing in one command:

```bash
uv run python -m doc_diff_tracker.cli full-diff \
  --old-root data/rhel9_and_10/9 \
  --new-root data/rhel9_and_10/10 \
  --old-version "9" \
  --new-version "10" \
  --output-dir artifacts \
  --max-docs 50 \
  --allow-overwrite
```

This creates two reports:
- `artifacts/delta_report.json` - Hash-based change detection
- `artifacts/semantic_diff_report.json` - Detailed semantic content comparison

### Two-Stage Pipeline

You can also run the stages separately:

**Stage 1: Generate delta report**
```bash
uv run python -m doc_diff_tracker.cli compare \
  --old-root data/rhel9_and_10/9 \
  --new-root data/rhel9_and_10/10 \
  --old-version "9" \
  --new-version "10" \
  --output artifacts/delta_report.json \
  --allow-overwrite
```

**Stage 2: Semantic content comparison**
```bash
uv run python -m doc_diff_tracker.cli scan \
  --report artifacts/delta_report.json \
  --old-root data/rhel9_and_10/9 \
  --new-root data/rhel9_and_10/10 \
  --output artifacts/semantic_diff_report.json \
  --max-docs 50 \
  --allow-overwrite
```

## Commands

### `full-diff`
Combines manifest comparison and semantic diffing into one workflow.

**Options:**
- `--old-root` - Path to older documentation corpus
- `--new-root` - Path to newer documentation corpus
- `--old-version` - Label for old version (default: "9")
- `--new-version` - Label for new version (default: "10")
- `--output-dir` - Output directory for reports (default: "artifacts")
- `--rename-threshold` - Similarity threshold for rename detection (default: 85.0)
- `--max-docs` - Limit semantic comparison to N documents (default: all)
- `--include-modified` - Include modified docs in semantic scan (default: true)
- `--include-renamed` - Include renamed docs in semantic scan (default: true)
- `--allow-overwrite` - Allow overwriting existing files (default: false)
- `--allow-symlinks` - Process symlinked files (default: false)

### `compare`
Generate delta report by comparing file hashes and paths.

### `scan`
Perform semantic content extraction and comparison on a delta report.

## Output

### Delta Report
Contains lists of:
- `unchanged` - Files with identical content
- `modified` - Files with same path, different content
- `renamed_candidates` - Potential renames/moves (based on content similarity)
- `added` - New files in newer version
- `removed` - Files no longer present

### Semantic Diff Report
Detailed block-level changes:
- Section additions/removals/modifications
- Text content changes with similarity scores
- Code block changes
- Table structure and data changes
- List modifications
- Metadata changes

Changes are reported semantically (e.g., "Installation section: added 3 paragraphs") rather than as raw HTML differences.