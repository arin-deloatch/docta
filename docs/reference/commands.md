# Commands Reference

The `docta` CLI is organized into three command groups.

---

## `docta diff` — Document Comparison

Compare documentation versions and generate semantic diffs.

| Command | Description |
|---------|-------------|
| `diff compare` | Generate delta report by comparing file hashes |
| `diff scan` | Perform semantic content extraction on changed files |
| `diff full` | Run complete pipeline (compare + scan) |

Full documentation: [Document Comparison](../usage/diff.md)

---

## `docta daemon` — GraphQL Polling Service

Automated change detection via GraphQL API polling.

| Command | Description |
|---------|-------------|
| `daemon start` | Start the polling daemon (runs in foreground) |
| `daemon stop` | Print stop instructions (use `Ctrl+C` or `docker-compose down`) |
| `daemon status` | Check daemon status and polling statistics |
| `daemon run-once` | Run a single poll cycle for testing |

Full documentation: [GraphQL Daemon](../usage/daemon.md)

---

## `docta qa` — QA Generation

Generate question-answer pairs from documentation (requires `uv sync --extra qa`).

| Command | Description |
|---------|-------------|
| `qa generate` | Generate QA from modified documents (semantic diff report) |
| `qa from-added` | Generate QA from newly added documents (delta report) |
| `qa unified` | Generate QA from both modified and added documents |
| `qa version` | Show QA component version information |

Full documentation: [QA Generation](../usage/qa.md)
