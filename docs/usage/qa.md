# QA Generation

Generate question-answer pairs from documentation changes using [RAGAS](https://docs.ragas.io/). Useful for creating test datasets to evaluate RAG systems and documentation understanding.

## Installation

Install QA generation dependencies:

```bash
uv sync --extra qa
```

This adds approximately 50 packages including:

- `ragas>=0.4.3` — QA generation framework
- `litellm` — multi-provider LLM support
- `instructor` — structured output from LLMs
- `pyyaml` — YAML configuration support

---

## Quick start

### 1. Set up an API key

```bash
# Google Gemini
export GOOGLE_API_KEY="your-api-key"

# OpenAI
export OPENAI_API_KEY="your-api-key"
```

### 2. Generate QA pairs

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

---

## Configuration

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

---

## How it works

QA generation uses two parallel ingestion paths:

1. **Modified Documents** → extract text snippets from semantic diff changes
2. **Added Documents** → extract sections from full document structure

Both paths feed into RAGAS synthesizers which generate:

- Question (various types: factual, reasoning, comparative)
- Ground truth answer
- Source metadata (location, version, change type)

---

## Output format

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

---

## Error handling

The pipeline includes automatic error recovery:

- **Batch processing fallback** — if content causes parsing errors, falls back to batch processing automatically
- **Problematic content skipping** — documents that fail after retries are logged and skipped
- **Detailed logging** — failed documents tracked by topic and index

---

## Command options

All `qa` commands share these options:

| Option | Description | Default |
|--------|-------------|---------|
| `--config`, `-c` | Path to YAML configuration file | none |
| `--testset-size`, `-n` | Number of QA pairs to generate | config value |
| `--num-documents`, `-d` | Limit number of source documents | all |
| `--format`, `-f` | Output format: `json`, `yaml`, or `auto` | `auto` |
| `--overwrite` | Allow overwriting existing output | `false` |
| `--verbose`, `-v` | Enable verbose logging | `false` |

`qa unified` takes three positional arguments: `delta_report_path`, `semantic_diff_report_path`, `output_path`.

`qa generate` and `qa from-added` take two positional arguments: the input report path and `output_path`.

---

## Best practices

### Command selection

| Goal | Command |
|------|---------|
| QA focused on what changed | `qa generate` |
| QA covering all new content | `qa from-added` |
| Complete coverage (recommended) | `qa unified` |

### Performance tips

- Start with `--testset-size 10` to validate configuration before scaling up
- Use `--num-documents` to limit processing during development
- Use `--verbose` to monitor extraction statistics
- If seeing frequent errors, reduce `max_text_length` in the config or switch to `gpt-4o`

### Supported LLM providers

| Provider | Package | Environment variable |
|----------|---------|----------------------|
| Google Gemini | `langchain-google-genai` | `GOOGLE_API_KEY` |
| Google Vertex AI | `langchain-google-vertexai` | (service account) |
| OpenAI | `langchain-openai` | `OPENAI_API_KEY` |
