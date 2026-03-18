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

## Requirements

- Python 3.13+
- uv (package manager)

## Installation

Clone the repository and install dependencies:

```bash
git clone <repository-url>
cd doc-diff-tracker
uv sync
```

This installs the `doc-diff-tracker` CLI command.

## Quick Start

### Full Pipeline (Recommended)

Run both manifest comparison and semantic diffing in one command:

```bash
uv run doc-diff-tracker full-diff \
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
uv run doc-diff-tracker compare \
  --old-root data/rhel9_and_10/9 \
  --new-root data/rhel9_and_10/10 \
  --old-version "9" \
  --new-version "10" \
  --output artifacts/delta_report.json \
  --allow-overwrite
```

**Stage 2: Semantic content comparison**
```bash
uv run doc-diff-tracker scan \
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

## Architecture

The project follows a modular architecture:

```
src/doc_diff_tracker/
├── cli.py                    # CLI entry point (Typer-based)
├── models/                   # Data models
│   ├── models.py            # Core delta report models
│   ├── content.py           # Content block models
│   └── html_diff.py         # Semantic diff models
├── extract/                  # Content extraction
│   ├── content_extractor.py # HTML content extraction
│   └── block_differ.py      # Block-level diff logic
├── compare/                  # Comparison logic
│   ├── lineage.py           # Manifest comparison & delta detection
│   └── semantic_diff.py     # Semantic content comparison
├── output/                   # Report generation
│   └── reporting.py         # JSON report writers & summaries
└── utils/                    # Utilities
    ├── inventory.py         # File scanning & hashing
    ├── security.py          # Path validation & security
    ├── scanner.py           # Delta report scanner
    ├── cli_helpers.py       # CLI validation helpers
    ├── text_utils.py        # Text processing utilities
    └── constants.py         # Constants & configuration
```

### Key Components

- **Manifest Building** (`utils/inventory.py`): Scans directories, computes file hashes, builds manifests
- **Delta Detection** (`compare/lineage.py`): Compares manifests, identifies changes, detects renames
- **Content Extraction** (`extract/content_extractor.py`): Parses HTML, extracts semantic blocks (headings, paragraphs, code, tables, lists)
- **Semantic Comparison** (`extract/block_differ.py`): Compares content blocks using fuzzy matching and similarity scoring
- **Security** (`utils/security.py`): Path validation, symlink protection, output validation

## Development

### Setup

```bash
# Install dependencies including dev tools
uv sync

# Install dev dependencies explicitly
uv add --dev black ruff mypy pyright pylint
```

### Code Quality

```bash
# Format code
uv run black .

# Lint
uv run ruff check .

# Type check
uv run pyright

# Security scan
uv run bandit -r src/
```

### Testing

Tests are not yet implemented (contributions welcome).

## Dependencies

- **beautifulsoup4** - HTML parsing
- **html2text** - HTML to text conversion
- **lxml** - Fast XML/HTML processing
- **pydantic** - Data validation and settings
- **rapidfuzz** - Fuzzy string matching for rename detection
- **typer** - CLI framework

## Security

- Path traversal protection via `utils/security.py`
- Symlink validation (disabled by default, opt-in via `--allow-symlinks`)
- Output path validation
- Hash-based integrity checking