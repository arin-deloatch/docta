# Document Comparison

DOCTA uses a multi-stage approach to identify meaningful documentation changes by comparing two HTML documentation corpora.

## How it works

1. **Manifest Building** — scans directories, computes SHA-256 hashes
2. **Delta Detection** — identifies changed/added/removed/renamed files
3. **Content Extraction** — parses HTML into semantic blocks:
    - Headings (h1–h6)
    - Paragraphs and text blocks
    - Code blocks (with language detection)
    - Tables (structure + data)
    - Lists (ordered/unordered)
4. **Block-level Comparison** — uses fuzzy matching to compare extracted blocks
5. **Change Categorization** — labels changes by type and severity

This approach ignores cosmetic HTML changes (class names, formatting) and focuses on actual content changes.

---

## Commands

### `diff compare`

Generate a delta report by comparing file hashes between two corpus roots.

```bash
uv run docta diff compare \
  --old-root data/docs_v1 \
  --new-root data/docs_v2 \
  --old-version "1.0" \
  --new-version "2.0" \
  --output artifacts/delta_report.json \
  --allow-overwrite
```

### `diff scan`

Perform semantic content extraction on changed files identified by a delta report.

```bash
uv run docta diff scan \
  --report artifacts/delta_report.json \
  --old-root data/docs_v1 \
  --new-root data/docs_v2 \
  --output artifacts/semantic_diff_report.json \
  --max-docs 50 \
  --allow-overwrite
```

### `diff full`

Run the complete pipeline (compare + scan) in one command.

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

---

## Advanced usage

### Tuning rename detection

```bash
docta diff full \
  --rename-threshold 90.0 \
  --old-root data/docs_v1 \
  --new-root data/docs_v2
```

Higher threshold = stricter matching. Default is `85.0`.

### Processing only modified files

```bash
docta diff scan \
  --report artifacts/delta_report.json \
  --old-root data/docs_v1 \
  --new-root data/docs_v2 \
  --include-modified true \
  --include-renamed false \
  --max-docs 100
```

### Security options

```bash
docta diff full \
  --allow-symlinks \
  --allow-overwrite \
  --old-root data/docs_v1 \
  --new-root data/docs_v2
```

---

## Common options

All `diff` commands share these options:

| Option | Description | Default |
|--------|-------------|---------|
| `--old-root` | Path to older documentation corpus | required |
| `--new-root` | Path to newer documentation corpus | required |
| `--old-version` | Label for old version | `"9"` |
| `--new-version` | Label for new version | `"10"` |
| `--rename-threshold` | Similarity threshold 0–100 | `85.0` |
| `--allow-overwrite` | Overwrite existing output files | `false` |
| `--allow-symlinks` | Process symlinked files | `false` |
| `--verbose`, `-v` | Enable debug logging | `false` |

`diff scan` and `diff full` also accept:

| Option | Description | Default |
|--------|-------------|---------|
| `--max-docs` | Maximum documents to process semantically | all |
| `--include-modified` | Include modified documents | `true` |
| `--include-renamed` | Include rename candidates | `true` |
