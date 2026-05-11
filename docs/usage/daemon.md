# GraphQL Polling Daemon

The daemon automates documentation change detection by polling a GraphQL API at regular intervals and triggering the diff + QA pipeline when changes are detected.

## Architecture

```
GraphQL API → Daemon polls → Changes detected → Fetch content → Run pipeline
   ↓                                                                  ↓
OAuth Auth                                               Diff + QA Generation
```

**Key features:**

- OAuth 2.0 authentication
- Configurable polling intervals
- State tracking (detects only new changes since the last poll)
- Automatic retry with exponential backoff
- Multiple query sets for different products/versions
- Integrated QA generation

---

## Configuration

Create a configuration file (e.g., `config/graphql_polling.yaml`):

```yaml
graphql:
  endpoint: "https://api.example.com/graphql"
  api_scope: "api.graphql"

  ssl:
    verify: true
    cert_path: "certs/ca.crt"  # optional custom CA certificate

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

See `config/graphql_polling.yaml` in the repository for a complete example with all supported options.

---

## Environment variables

Required OAuth credentials (store in `.env`):

```bash
GRAPHQL_CLIENT_ID=your-client-id
GRAPHQL_CLIENT_SECRET=your-client-secret
GRAPHQL_TOKEN_URL=https://auth.example.com/oauth/token
APOLLOGRAPHQL_CLIENT_NAME=docta-poller
```

Optional (for QA generation):

```bash
GOOGLE_API_KEY=your-google-api-key   # for Gemini
OPENAI_API_KEY=your-openai-api-key   # for OpenAI
```

---

## Running the daemon

### Development (foreground)

```bash
uv run docta daemon start \
  --config config/graphql_polling.yaml \
  --foreground \
  --verbose
```

Stop with `Ctrl+C`.

### Testing (single poll cycle)

```bash
uv run docta daemon run-once \
  --config config/graphql_polling.yaml \
  --verbose
```

Run only a specific query set:

```bash
uv run docta daemon run-once \
  --config config/graphql_polling.yaml \
  --query-set product_v2
```

Force-treat all documents as new (skip diffing, useful for initial bootstrap):

```bash
uv run docta daemon run-once \
  --config config/graphql_polling.yaml \
  --force-new
```

### Production (Docker)

Background daemonization is not implemented in the CLI — use Docker instead:

```bash
cd deployment/docker
docker-compose up -d
```

---

## Monitoring

### Check daemon status

```bash
docta daemon status --config config/graphql_polling.yaml
```

Example output:

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

### View logs (Docker)

```bash
docker logs -f docta-graphql-poller
```

---

## State management

The daemon tracks document state in `polling_state.json`:

- Document revision IDs
- Last modified timestamps
- Polling history and statistics

This enables incremental change detection — only modified or added documents trigger pipelines.

### Reset state (reprocess all documents)

```bash
rm config/state/polling_state.json
docta daemon run-once --config config/graphql_polling.yaml --force-new
```

---

## Command options

### `daemon start`

| Option | Description | Default |
|--------|-------------|---------|
| `--config` | Path to configuration file | `config/graphql_polling.yaml` |
| `--foreground`, `-f` | Run in foreground | `false` |
| `--verbose`, `-v` | Enable debug logging | `false` |

### `daemon run-once`

| Option | Description | Default |
|--------|-------------|---------|
| `--config` | Path to configuration file | **required** |
| `--query-set` | Run only this named query set | all sets |
| `--force-new` | Treat all documents as new | `false` |
| `--verbose`, `-v` | Enable debug logging | `false` |

### `daemon status`

| Option | Description | Default |
|--------|-------------|---------|
| `--config` | Path to configuration file | `config/graphql_polling.yaml` |

### `daemon stop`

Prints instructions only — stops are handled by `Ctrl+C` (foreground) or `docker-compose down` (Docker).
