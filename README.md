# lexio

Enterprise document intelligence platform. Ingest internal documents, build a searchable knowledge base, and answer natural-language queries using retrieval-augmented generation.

Built for teams that need to query internal runbooks, compliance policies, incident reports, and technical documentation without exposing data to third-party services.

## What it does

- Accepts PDF, DOCX, and plain-text uploads via REST API
- Chunks and embeds documents using sentence-transformers (all-MiniLM-L6-v2)
- Stores embeddings in PostgreSQL with pgvector for efficient cosine similarity search
- Retrieves the top-k relevant chunks and synthesises an answer using a configurable LLM
- Exposes source attribution so every answer can be traced back to the originating document and chunk
- Supports namespace-based collection isolation (e.g. per-team or per-project knowledge bases)
- Ships with async ingestion via Celery and Redis so large document batches do not block the API

## Architecture

```
HTTP client
    |
FastAPI (app/)
    |-- /api/v1/documents   upload, status, delete
    |-- /api/v1/ingest      trigger / status
    |-- /api/v1/search      semantic search
    |-- /api/v1/query       RAG question answering
    |-- /api/v1/health      liveness + readiness
    |
Services (app/services/)
    |-- ingestion.py        parse -> chunk -> embed -> store
    |-- retrieval.py        embed query -> cosine search -> rerank
    |-- generation.py       prompt assembly -> LLM call -> response
    |-- document.py         CRUD over documents table
    |
Infrastructure
    |-- PostgreSQL + pgvector   document metadata + embeddings
    |-- Redis + Celery          async ingestion workers
    |-- sentence-transformers   local embedding model (no API key needed)
    |-- LangChain               LLM abstraction (Ollama / OpenAI / Azure)
```

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.111, Pydantic v2, Uvicorn |
| ORM | SQLAlchemy 2.0 async |
| Database | PostgreSQL 15 + pgvector 0.7 |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 |
| RAG framework | LangChain 0.2 |
| LLM backend | Ollama (default) / OpenAI-compatible |
| Async workers | Celery 5 + Redis 7 |
| Document parsing | pypdf, python-docx, unstructured |
| Observability | structlog, Prometheus metrics endpoint |
| Containers | Docker, Docker Compose |
| CI | GitHub Actions |

## Getting started

### Prerequisites

- Docker and Docker Compose
- Ollama running locally with `llama3.2` pulled, or an OpenAI-compatible endpoint

### Run with Docker Compose

```bash
git clone https://github.com/preetham0810/lexio.git
cd lexio
cp .env.example .env
# edit .env if you want to point at a different LLM endpoint
docker compose up --build
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# start dependencies only
docker compose up postgres redis -d

# run migrations
alembic upgrade head

# start the API
uvicorn app.main:app --reload --port 8000

# start a Celery worker (separate terminal)
celery -A app.worker.celery_app worker --loglevel=info
```

## API reference

### Upload a document

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@runbook.pdf" \
  -F "collection=ops-runbooks" \
  -F "title=K8s Incident Runbook"
```

### Query the knowledge base

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the escalation path for a P1 database outage?",
    "collection": "ops-runbooks",
    "top_k": 5
  }'
```

### Semantic search (no generation)

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "database failover procedure", "collection": "ops-runbooks", "top_k": 8}'
```

### Response format

```json
{
  "answer": "For a P1 database outage, the escalation path is...",
  "sources": [
    {
      "document_id": "d3f1a2b4",
      "title": "K8s Incident Runbook",
      "chunk_index": 4,
      "score": 0.91,
      "excerpt": "P1 incidents require immediate page to on-call DBA..."
    }
  ],
  "latency_ms": 843
}
```

## Configuration

All configuration is environment-based. See `.env.example` for the full list.

Key variables:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | see compose | PostgreSQL async DSN |
| `REDIS_URL` | see compose | Redis DSN for Celery |
| `EMBEDDING_MODEL` | all-MiniLM-L6-v2 | HuggingFace model name |
| `LLM_PROVIDER` | ollama | ollama / openai / azure |
| `LLM_MODEL` | llama3.2 | Model name passed to provider |
| `OPENAI_API_KEY` | — | Required only if LLM_PROVIDER=openai |
| `CHUNK_SIZE` | 512 | Token target per chunk |
| `CHUNK_OVERLAP` | 64 | Overlap between adjacent chunks |
| `RETRIEVAL_TOP_K` | 5 | Chunks retrieved per query |

## Running tests

```bash
pytest tests/ -v --tb=short
```

Integration tests spin up a temporary PostgreSQL container via testcontainers. Unit tests mock all external I/O.

## Sample data

`scripts/seed_sample_data.py` loads three sample documents into the `demo` collection:

- `data/samples/incident_response_runbook.txt` — incident classification and escalation procedures
- `data/samples/api_security_policy.txt` — internal API authentication and rate-limiting policy
- `data/samples/deployment_checklist.txt` — pre/post deployment verification steps

```bash
python scripts/seed_sample_data.py
```

## Project structure

```
lexio/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── documents.py
│   │       ├── ingest.py
│   │       ├── query.py
│   │       ├── search.py
│   │       └── health.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── logging.py
│   ├── models/
│   │   ├── document.py
│   │   └── chunk.py
│   ├── schemas/
│   │   ├── document.py
│   │   ├── query.py
│   │   └── search.py
│   ├── services/
│   │   ├── document.py
│   │   ├── ingestion.py
│   │   ├── retrieval.py
│   │   └── generation.py
│   ├── worker/
│   │   ├── celery_app.py
│   │   └── tasks.py
│   └── main.py
├── alembic/
│   └── versions/
├── data/
│   └── samples/
├── scripts/
│   └── seed_sample_data.py
├── tests/
│   ├── unit/
│   └── integration/
├── .env.example
├── .github/
│   └── workflows/
│       └── ci.yml
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── requirements.txt
└── README.md
```

## Deployment notes

The service is stateless at the API layer. For production:

- Run the FastAPI app behind an NGINX reverse proxy or an application load balancer
- Scale Celery workers horizontally; they share the same Redis broker and PostgreSQL backend
- Use a managed PostgreSQL service (RDS, Cloud SQL, Azure Database) with the pgvector extension enabled
- The embedding model is downloaded at container startup; pin the model version in `.env` and pre-warm via the `/health/ready` probe

## License

MIT
