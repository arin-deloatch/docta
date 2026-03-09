# Vector Database Deployment Guide (Version 2)

## Overview

This document explains how to deploy a vector database for retrieval augmented generation (RAG) workflows. The system stores embeddings created from documentation and supports semantic similarity search.

## Requirements

- Python 3.11+
- Docker 24+
- Minimum 8 GB RAM
- Internet access for downloading embedding models

## Installation

### 1. Clone the repository

```bash
git clone https://example.com/vector-db.git
cd vector-db
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Launch the service

```bash
docker compose up -d
```

## Embedding Generation

Embeddings are generated using the `nomic-embed-text-v1` model.

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("nomic-ai/nomic-embed-text-v1")
embedding = model.encode("Example sentence")
```

## Querying the Database

Queries use cosine similarity to compare vector embeddings.

```python
results = vector_store.similarity_search("How do I deploy the system?")
```

## Troubleshooting

If the service does not start:

- Check Docker container logs
- Confirm required ports are open
- Verify all dependencies are installed