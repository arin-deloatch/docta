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
- **Automated polling daemon**: Monitor GraphQL APIs for documentation changes and trigger pipelines automatically
- **Structured reporting**: Generate detailed JSON reports with change analysis
- **QA generation (optional)**: Generate question-answer pairs from documentation changes using RAGAS

## Requirements

- Python 3.11+ (3.12+ recommended)
- uv (package manager)

## Installation

### Core Installation

```bash
git clone <repository-url>
cd docta
uv sync
```

This installs the `docta` CLI with core document comparison features.

### Optional Features

**QA Generation** (adds LLM dependencies):
```bash
uv sync --extra qa
```

**GraphQL Daemon** (included in core, requires environment configuration):
- See [GraphQL Polling Daemon](#graphql-polling-daemon) section for setup

## Quick Start

### Core Workflow: Document Comparison

Run both manifest comparison and semantic diffing in one command:

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
- `artifacts/delta_report.json` - Hash-based change detection (what changed)
- `artifacts/semantic_diff_report.json` - Detailed semantic analysis (how it changed)

**Alternative: Two-Stage Pipeline**

Run the stages separately for more control:

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

## Commands Reference

The `docta` CLI is organized into three command groups:

### `docta diff` - Document Comparison

Compare documentation versions and generate semantic diffs.

- **`diff compare`** - Generate delta report by comparing file hashes
- **`diff scan`** - Perform semantic content extraction on changed files
- **`diff full`** - Run complete pipeline (compare + scan)

### `docta daemon` - GraphQL Polling Service

Automated change detection via GraphQL API polling.

- **`daemon start`** - Start the polling daemon
- **`daemon stop`** - Stop the daemon (use Ctrl+C or systemd)
- **`daemon status`** - Check daemon status and statistics
- **`daemon run-once`** - Run single poll cycle for testing

### `docta qa` - QA Generation

Generate question-answer pairs from documentation (requires `--extra qa`).

- **`qa generate`** - Generate QA from modified documents
- **`qa from-added`** - Generate QA from newly added documents
- **`qa unified`** - Generate QA from both modified and added documents
- **`qa version`** - Show version information

## Output

### Delta Report

JSON file containing categorized document changes:

- **`unchanged`** - Files with identical content hashes
- **`modified`** - Files at same path with different content
- **`renamed_candidates`** - Potential renames detected via similarity matching (configurable threshold)
- **`added`** - New files in newer version
- **`removed`** - Files no longer present

### Semantic Diff Report

JSON file with detailed block-level changes:

- Section additions/removals/modifications
- Text content changes with similarity scores
- Code block changes
- Table structure and data changes
- List modifications
- Metadata changes

Changes are reported semantically (e.g., "Installation section: added 3 paragraphs, modified 1 code block") rather than as raw HTML diffs.

---

## Document Comparison

### How Semantic Comparison Works

DOCTA uses a multi-stage approach to identify meaningful documentation changes:

1. **Manifest Building** - Scans directories, computes SHA-256 hashes
2. **Delta Detection** - Identifies changed/added/removed/renamed files
3. **Content Extraction** - Parses HTML into semantic blocks:
   - Headings (h1-h6)
   - Paragraphs and text blocks
   - Code blocks (with language detection)
   - Tables (structure + data)
   - Lists (ordered/unordered)
4. **Block-level Comparison** - Uses fuzzy matching to compare extracted blocks
5. **Change Categorization** - Labels changes by type and severity

This approach ignores cosmetic HTML changes (class names, formatting) and focuses on actual content changes.

### Advanced Usage

**Tuning Rename Detection:**
```bash
docta diff full \
  --rename-threshold 90.0 \  # Higher = stricter matching (default: 85.0)
  ...
```

**Processing Only Modified Files:**
```bash
docta diff scan \
  --include-modified true \
  --include-renamed false \  # Skip rename candidates
  --max-docs 100 \           # Process first 100 modified docs
  ...
```

**Security Options:**
```bash
docta diff full \
  --allow-symlinks \         # Process symlinked files (default: disabled)
  --allow-overwrite \        # Overwrite existing output files
  ...
```

### Common Options

All `diff` commands support:
- `--old-root` - Path to older documentation corpus
- `--new-root` - Path to newer documentation corpus
- `--old-version` - Label for old version (default: "1.0")
- `--new-version` - Label for new version (default: "2.0")
- `--rename-threshold` - Similarity threshold 0-100 (default: 85.0)
- `--allow-overwrite` - Overwrite existing files (default: false)
- `--allow-symlinks` - Process symlinked files (default: false)
- `--verbose, -v` - Enable debug logging

---

## GraphQL Polling Daemon

The daemon automates documentation change detection by polling a GraphQL API at regular intervals and triggering the diff + QA pipeline when changes are detected.

### Architecture

```
GraphQL API → Daemon polls → Changes detected → Fetch content → Run pipeline
   ↓                                                                  ↓
OAuth Auth                                               Diff + QA Generation
```

**Key Features:**
- OAuth 2.0 authentication
- Configurable polling intervals
- State tracking (detects only new changes)
- Automatic retry with exponential backoff
- Multiple query sets for different products/versions
- Integrated QA generation

### Configuration

Create a configuration file (e.g., `config/graphql_polling.yaml`):

```yaml
graphql:
  endpoint: "https://api.example.com/graphql"
  api_scope: "api.graphql"
  
  ssl:
    verify: true
    cert_path: "certs/ca.crt"  # Optional custom CA certificate
  
  polling:
    interval_minutes: 60
    initial_delay_seconds: 10
    retry_attempts: 3
    retry_backoff_seconds: 30
    timeout_seconds: 30
  
  query_sets:
    - name: "product_v2"
      enabled: true
      query: |
        query GetDocuments($filter: DocumentFilter) {
          documents(filter: $filter) {
            edges {
              node {
                id
                title
                content {
                  url
                  lastModified
                }
                version
              }
            }
          }
        }
      variables:
        filter:
          product: "example-product"
          version: "2.0"
      pipeline:
        version_label: "PRODUCT_V2"
        output_dir: "output/product_v2"
        run_qa_generation: true
        qa_config: "config/system.yaml"
        max_concurrent_fetches: 10

state:
  file_path: "config/state/polling_state.json"
  backup_enabled: true
  backup_count: 5

content:
  download_dir: "data/fetched_content"
  max_file_size_mb: 100
  timeout_seconds: 60

logging:
  level: "INFO"
  console:
    enabled: true
    format: "json"
```

See `prod/graphql_polling.yaml` for a complete example.

### Environment Variables

Required OAuth credentials (store in `.env` or systemd EnvironmentFile):

```bash
GRAPHQL_CLIENT_ID=your-client-id
GRAPHQL_CLIENT_SECRET=your-client-secret
GRAPHQL_TOKEN_URL=https://auth.example.com/oauth/token
APOLLOGRAPHQL_CLIENT_NAME=docta-poller
```

Optional:
```bash
GOOGLE_API_KEY=your-google-api-key  # For QA generation with Gemini
OPENAI_API_KEY=your-openai-api-key  # For QA generation with OpenAI
```

### Running the Daemon

**Development (foreground):**
```bash
uv run docta daemon start \
  --config config/graphql_polling.yaml \
  --foreground \
  --verbose
```

**Testing (single poll cycle):**
```bash
uv run docta daemon run-once \
  --config config/graphql_polling.yaml \
  --verbose
```

**Testing (force all documents as new):**
```bash
uv run docta daemon run-once \
  --config config/graphql_polling.yaml \
  --force-new  # Skip diffing, run QA on all docs
```

**Production (systemd):**

1. Copy service file:
```bash
sudo cp deployment/systemd/docta-graphql-poller.service /etc/systemd/system/
```

2. Create environment file:
```bash
sudo cp /path/to/.env /etc/docta/graphql.env
sudo chmod 600 /etc/docta/graphql.env
```

3. Start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable docta-graphql-poller
sudo systemctl start docta-graphql-poller
```

**Production (Docker):**
```bash
cd deployment/docker
docker-compose up -d
```

### Monitoring

**Check daemon status:**
```bash
docta daemon status --config config/graphql_polling.yaml
```

**Output:**
```
=== GraphQL Polling Daemon Status ===

State file: config/state/polling_state.json
Last updated: 2026-04-15T14:30:00Z
Total query sets: 1

Query Set: product_v2
  Last poll: 2026-04-15T14:30:00Z
  Last success: 2026-04-15T14:30:00Z
  Total documents: 450
  Total polls: 25
  Documents with changes: 12
  Total pipeline runs: 3
```

**View logs:**
- Systemd: `journalctl -u docta-graphql-poller -f`
- Docker: `docker logs -f docta-graphql-poller`

### State Management

The daemon tracks document state in `polling_state.json`:
- Document revision IDs
- Last modified timestamps
- Polling history and statistics

This enables incremental change detection - only modified/added documents trigger pipelines.

**Reset state (reprocess all documents):**
```bash
rm config/state/polling_state.json
docta daemon run-once --config ... --force-new
```

---

## QA Generation

Generate question-answer pairs from documentation changes using [RAGAS](https://docs.ragas.io/). This is useful for creating test datasets to evaluate RAG systems and documentation understanding.

### Installation

Install QA generation dependencies:

```bash
uv sync --extra qa
```

This adds ~50+ packages including:
- `ragas>=0.4.3` - QA generation framework
- `langchain-*` - LLM provider integrations
- `litellm` - Multi-provider LLM support

### Quick Start

**1. Set up API key:**

```bash
# For Google Gemini
export GOOGLE_API_KEY="your-api-key"

# For OpenAI
export OPENAI_API_KEY="your-api-key"
```

**2. Generate QA pairs:**

**From modified documents (semantic diff report):**
```bash
docta qa generate \
  artifacts/semantic_diff_report.json \
  output/qa_pairs_modified.json \
  --config config/system.yaml \
  --testset-size 50 \
  --num-documents 10 \
  --overwrite
```

**From newly added documents (delta report):**
```bash
docta qa from-added \
  artifacts/delta_report.json \
  output/qa_pairs_added.json \
  --config config/system.yaml \
  --testset-size 50 \
  --overwrite
```

**From both sources (recommended for production):**
```bash
docta qa unified \
  artifacts/delta_report.json \
  artifacts/semantic_diff_report.json \
  output/qa_pairs_all.json \
  --config config/system.yaml \
  --testset-size 100 \
  --overwrite
```

### Configuration

Create a YAML config file (e.g., `config/system.yaml`):

```yaml
# LLM Configuration
llm:
  provider: google          # google, openai, vertex
  model: gemini-2.0-flash-exp
  temperature: 0.0

# Embedding Configuration
embedding:
  provider: google
  model: text-embedding-004

# Generation Settings
generation:
  testset_size: 50          # Number of QA pairs (max: 10000)
  
  # Query Distribution - must sum to 1.0
  query_distribution:
    specific: 0.5           # Simple factual questions
    abstract: 0.25          # Reasoning questions
    comparative: 0.25       # Comparison questions

# Filtering Configuration
filtering:
  min_text_length: 50       # Skip short snippets
  max_text_length: 10000    # Skip very long sections
  min_similarity: 0.0       # For modified docs
  max_similarity: 95.0      # Skip near-identical changes
  
  change_types:             # For modified docs
    - text_change
```

### How It Works

QA generation uses two parallel ingestion paths:

1. **Modified Documents** → Extract text snippets from semantic diff changes
2. **Added Documents** → Extract sections from full document structure

Both paths feed into RAGAS synthesizers which generate:
- Question (various types: factual, reasoning, comparative)
- Ground truth answer
- Source metadata (location, version, change type)

### Output Format

```json
{
  "question": "How do you enable two-factor authentication in IdM?",
  "ground_truth_answer": "Use the ipa config-mod command with --user-auth-type=otp...",
  "source_topic_slug": "idm-authentication",
  "source_location": "Chapter 3. Security > 3.2. Two-Factor Authentication",
  "source_change_type": "text_change",
  "source_versions": ["9", "10"],
  "question_type": "single_hop_specific_query_synthesizer",
  "metadata": {
    "query_style": "WEB_SEARCH_LIKE",
    "query_length": "SHORT",
    "persona_name": "IdM Systems Administrator"
  }
}
```

### Error Handling

The pipeline includes automatic error recovery:

- **Batch Processing Fallback**: If content causes parsing errors, automatically falls back to batch processing
- **Problematic Content Skipping**: Documents that fail after retries are logged and skipped
- **Detailed Logging**: Failed documents tracked by topic and index

### Common Options

- `--config, -c` - Path to YAML configuration file
- `--testset-size, -n` - Number of QA pairs to generate (default: 50, max: 10000)
- `--num-documents, -d` - Limit number of source documents
- `--format, -f` - Output format: json, yaml, or auto
- `--overwrite` - Allow overwriting existing output
- `--verbose, -v` - Enable verbose logging

### Best Practices

- **Command Selection**:
  - Use `generate` for change-focused QA (what's new/different)
  - Use `from-added` for comprehensive new content coverage
  - Use `unified` for complete coverage (recommended)

- **Performance Tips**:
  - Start with small `testset_size` (10-50) to validate config
  - Use `--num-documents` to limit processing during development
  - Use `--verbose` to monitor extraction statistics
  - If seeing frequent errors, reduce `max_text_length` or switch to gpt-4o

- **Supported Providers**:
  - Google Gemini (`langchain-google-genai`)
  - Google Vertex AI (`langchain-google-vertexai`)
  - OpenAI (`langchain-openai`)

---

## Architecture

The project follows a modular architecture:

```
src/
├── docta/                        # Core diff tracking
│   ├── cli/                      # Modular CLI (unified entry point)
│   │   ├── __init__.py          # Main app + subcommand registration
│   │   ├── diff.py              # Document comparison commands
│   │   ├── daemon.py            # GraphQL polling daemon commands
│   │   ├── qa.py                # QA generation commands
│   │   └── _error_handling.py  # Shared error handling decorators
│   ├── models/                   # Data models
│   │   ├── models.py            # Core delta report models
│   │   ├── content.py           # Content block models
│   │   └── html_diff.py         # Semantic diff models
│   ├── extract/                  # Content extraction
│   │   ├── content_extractor.py # HTML content extraction
│   │   └── block_differ.py      # Block-level diff logic
│   ├── compare/                  # Comparison logic
│   │   ├── lineage.py           # Manifest comparison & delta detection
│   │   └── semantic_diff.py     # Semantic content comparison
│   ├── graphql/                  # GraphQL polling daemon
│   │   ├── factory.py           # Component initialization factory
│   │   ├── client.py            # GraphQL client with OAuth
│   │   ├── fetcher.py           # Content fetcher
│   │   ├── scheduler.py         # Polling scheduler
│   │   ├── pipeline.py          # Pipeline runner
│   │   └── state.py             # State management
│   ├── output/                   # Report generation
│   │   └── reporting.py         # JSON report writers & summaries
│   └── utils/                    # Utilities
│       ├── inventory.py         # File scanning & hashing
│       ├── security.py          # Path validation & security
│       ├── scanner.py           # Delta report scanner
│       ├── cli_helpers.py       # CLI validation helpers
│       ├── text_utils.py        # Text processing utilities
│       └── constants.py         # Constants & configuration
└── qa_generation/                # QA generation (optional)
    ├── config/                   # Configuration management
    ├── models/                   # QA data models
    ├── generators/               # QA generation logic
    ├── llm/                      # LLM provider abstraction
    ├── ingest/                   # Data ingestion (dual paths)
    ├── output/                   # Output writers
    └── pipeline/                 # Orchestration
```

### Key Components

**CLI Architecture:**
- **Modular Design** (`cli/`): Organized into focused command groups (diff, daemon, qa)
- **Error Handling** (`cli/_error_handling.py`): Shared decorators for consistent error reporting
- **Component Factory** (`graphql/factory.py`): Reusable initialization for daemon components

**Core Diff Tracking:**
- **Manifest Building** (`utils/inventory.py`): Scans directories, computes file hashes, builds manifests
- **Delta Detection** (`compare/lineage.py`): Compares manifests, identifies changes, detects renames
- **Content Extraction** (`extract/content_extractor.py`): Parses HTML, extracts semantic blocks
- **Semantic Comparison** (`extract/block_differ.py`): Compares content blocks using fuzzy matching
- **Security** (`utils/security.py`): Path validation, symlink protection, output validation

**GraphQL Polling Daemon:**
- **Scheduler** (`graphql/scheduler.py`): Automated polling with configurable intervals
- **Client** (`graphql/client.py`): OAuth-authenticated GraphQL queries
- **Pipeline Runner** (`graphql/pipeline.py`): Orchestrates diff + QA generation
- **State Management** (`graphql/state.py`): Tracks changes and polling history

**QA Generation (Optional):**
- **Pipeline Orchestration** (`qa_generation/pipeline/orchestrator.py`): End-to-end QA generation
- **Snippet Extraction** (`ingest/snippet_extractor.py`): Filters and extracts text from changes
- **Document Processor** (`ingest/added_doc_processor.py`): Processes newly added documents
- **RAGAS Generator** (`generators/ragas_generator.py`): Generates QA pairs using RAGAS framework
- **LLM Provider** (`llm/provider.py`): Factory for LLM and embedding models

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

### Core Dependencies

- **beautifulsoup4** - HTML parsing
- **html2text** - HTML to text conversion
- **lxml** - Fast XML/HTML processing
- **pydantic** - Data validation and settings
- **rapidfuzz** - Fuzzy string matching for rename detection
- **requests** - HTTP client for content fetching
- **structlog** - Structured logging
- **typer** - CLI framework

### Optional Dependencies (QA Generation)

Install with `uv sync --extra qa`:

- **ragas>=0.4.3** - QA test generation framework
- **litellm** - Multi-provider LLM support
- **langchain-core** - LangChain core functionality
- **langchain-google-genai** - Google Gemini integration
- **langchain-openai** - OpenAI integration
- **pyyaml** - YAML configuration support

## Security

- **Path traversal protection** via `utils/security.py`
- **Symlink validation** (disabled by default, opt-in via `--allow-symlinks`)
- **Output path validation** (prevents writing outside project directory)
- **Hash-based integrity checking** (SHA-256 for file comparison)
- **No secrets in repository** - API keys via environment variables only
- **OAuth 2.0 authentication** for GraphQL API access

**Security Best Practices:**
- Never commit credentials
- Use environment files for secrets (`.env`, systemd `EnvironmentFile`)
- Set appropriate file permissions (`chmod 600` for credential files)
- Review security hardening in systemd service file
