# Architecture

DOCTA follows a modular architecture with clear separation between the core diff tracking engine and the optional QA generation feature.

## Source tree

```text
src/
├── docta/                        # Core diff tracking
│   ├── cli/                      # Modular CLI (unified entry point)
│   │   ├── __init__.py           # Main app + subcommand registration
│   │   ├── diff.py               # Document comparison commands
│   │   ├── daemon.py             # GraphQL polling daemon commands
│   │   ├── qa.py                 # QA generation commands
│   │   └── _error_handling.py   # Shared error handling decorators
│   ├── models/                   # Data models
│   │   ├── models.py             # Core delta report models
│   │   ├── content.py            # Content block models
│   │   └── html_diff.py          # Semantic diff models
│   ├── extract/                  # Content extraction
│   │   ├── content_extractor.py  # HTML content extraction
│   │   └── block_differ.py       # Block-level diff logic
│   ├── compare/                  # Comparison logic
│   │   ├── lineage.py            # Manifest comparison & delta detection
│   │   └── semantic_diff.py      # Semantic content comparison
│   ├── graphql/                  # GraphQL polling daemon
│   │   ├── factory.py            # Component initialization factory
│   │   ├── client.py             # GraphQL client with OAuth
│   │   ├── config.py             # Daemon configuration
│   │   ├── fetcher.py            # Content fetcher
│   │   ├── models.py             # GraphQL data models
│   │   ├── scheduler.py          # Polling scheduler
│   │   ├── pipeline.py           # Pipeline runner
│   │   └── state.py              # State management
│   ├── output/                   # Report generation
│   │   └── reporting.py          # JSON report writers & summaries
│   └── utils/                    # Utilities
│       ├── inventory.py          # File scanning & hashing
│       ├── security.py           # Path validation & security
│       ├── scanner.py            # Delta report scanner
│       ├── cli_helpers.py        # CLI validation helpers
│       ├── text_utils.py         # Text processing utilities
│       └── constants.py          # Constants & configuration
└── qa_generation/                # QA generation (optional extra)
    ├── config/                   # Configuration management
    ├── models/                   # QA data models
    ├── generators/               # QA generation logic
    ├── llm/                      # LLM provider abstraction
    ├── ingest/                   # Data ingestion (dual paths)
    ├── output/                   # Output writers
    └── pipeline/                 # Orchestration
```

---

## Key components

### CLI layer (`cli/`)

- **Modular design**: three focused command groups (`diff`, `daemon`, `qa`), each in its own file
- **Error handling** (`_error_handling.py`): shared decorators for consistent error reporting across all commands
- **Lazy imports**: GraphQL and QA dependencies are imported only when their commands are invoked, so the core CLI starts without requiring optional packages

### Core diff tracking

- **Manifest building** (`utils/inventory.py`): scans directories, computes SHA-256 hashes, builds file manifests
- **Delta detection** (`compare/lineage.py`): compares manifests, identifies changes, detects renames via fuzzy matching
- **Content extraction** (`extract/content_extractor.py`): parses HTML, extracts semantic blocks (headings, paragraphs, code, tables, lists)
- **Semantic comparison** (`extract/block_differ.py`): compares content blocks using RapidFuzz similarity matching
- **Security** (`utils/security.py`): path validation, symlink protection, output path enforcement

### GraphQL polling daemon (`graphql/`)

- **Factory** (`factory.py`): initializes all daemon components from configuration in one call
- **Scheduler** (`scheduler.py`): manages polling intervals, retry logic, and backoff
- **Client** (`client.py`): OAuth 2.0 authenticated GraphQL queries
- **Pipeline runner** (`pipeline.py`): orchestrates diff + QA generation after fetching changes
- **State manager** (`state.py`): persists document revision state to enable incremental change detection

### QA generation (`qa_generation/`)

- **Pipeline orchestrator** (`pipeline/orchestrator.py`): end-to-end QA generation from either source
- **Snippet extraction** (`ingest/snippet_extractor.py`): filters and extracts text snippets from semantic diff changes
- **Document processor** (`ingest/added_doc_processor.py`): processes newly added documents with no prior version
- **RAGAS generator** (`generators/ragas_generator.py`): generates QA pairs using the RAGAS framework
- **LLM provider** (`llm/provider.py`): factory for LLM and embedding models (Google, OpenAI, Vertex)
