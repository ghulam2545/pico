## Pico

**Pico is a document-focused Retrieval-Augmented Generation (RAG) application.** Upload your documents, retrieve relevant passages, and ask questions through a streaming chat interface. Answers are grounded in retrieved document context, with source information emitted alongside the response.

### Features

- **Workspace isolation** — organize documents and conversations by workspace.
- **API-key authentication** — workspace keys are generated at creation time; only a hash is stored in the database.
- **Document ingestion** — upload Markdown, plain-text, and PDF files through the API.
- **Content-aware chunking** — split Markdown by headings, keep code blocks intact during chunking, and configure chunk size and overlap.
- **Hybrid retrieval** — retrieve candidates with pgvector similarity search, re-rank them with BM25, and combine rankings using Reciprocal Rank Fusion (RRF).
- **Streaming RAG chat** — stream model output as Server-Sent Events (SSE), with source metadata sent at the end of the stream.
- **Conversation memory** — store recent chat history in Redis with a configurable TTL.
- **API documentation** — interactive Swagger UI and ReDoc pages are provided by FastAPI.

> **Format note:** `.md`, `.markdown`, `.txt`, and `.pdf` are implemented by the current loaders. `.docx` is not ready to rely on.

### How it works

1. A document is uploaded to a workspace.
2. Pico detects the format, checks for duplicates, extracts text, and splits it into chunks.
3. An Ollama embedding model converts the chunks into vectors, which are stored in PostgreSQL using pgvector.
4. When a question arrives, Pico performs dense retrieval, re-ranks the candidates with BM25, and combines the rankings with RRF.
5. The retrieved context and recent conversation history are sent to the configured Ollama Cloud chat model.
6. The generated answer is streamed to the client, followed by source metadata.

### Tech stack

| Component | Technology |
| --- | --- |
| API | Python, FastAPI, Uvicorn |
| RAG orchestration | LangChain |
| Embeddings | Ollama, default model `nomic-embed-text` |
| Chat model | Ollama Cloud's OpenAI-compatible API |
| Vector search | PostgreSQL, pgvector |
| Re-ranking | BM25 and Reciprocal Rank Fusion (RRF) |
| Relational data | SQLAlchemy, asyncpg |
| Conversation memory | Redis |
| Settings | Pydantic Settings (`.env`) |
| Logging | structlog |

### Requirements

- Python 3.11 or newer recommended
- [uv](https://docs.astral.sh/uv/) for Python dependency management
- PostgreSQL with the **pgvector** extension installed
- Redis 7 or compatible
- [Ollama](https://ollama.com/) running locally for embeddings
- An Ollama Cloud API key and a chat model available to your account

### Quick start

#### 1. Clone the repository and install dependencies

```bash
git clone https://github.com/ghulam2545/pico.git
cd pico
uv sync --no-install-project
```

#### 2. Configure environment variables

Create a `.env` file in the project root:

```dotenv
# PostgreSQL
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=pico
DATABASE_USER=postgres
DATABASE_PASSWORD=change-this-password

# Redis (the supplied Compose file exposes Redis on host port 6380)
REDIS_URL=redis://localhost:6380/0

# Local Ollama embeddings
OLLAMA_LOCAL_URL=http://localhost:11434
EMBED_MODEL=nomic-embed-text

# Ollama Cloud chat model
OLLAMA_CLOUD_URL=https://api.ollama.com/v1
OLLAMA_API_KEY=your-ollama-api-key
LLM_MODEL=your-cloud-model
LLM_TEMPERATURE=0.1

# Retrieval
TOP_K_DENSE=15
TOP_K_FINAL=6
RRF_K=50

# Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
MIN_CHUNK_LENGTH=50

# Conversation memory
REDIS_TTL_HOURS=24
REDIS_MAX_MESSAGES=20

# Application
API_PREFIX=/pico/api
CORS_ORIGINS=["http://localhost:8000"]
MAX_DOCUMENT_COUNT=30
MAX_CONVERSATION_COUNT=30
```

Replace the database credentials, API key, and model name with values for your setup. The names in `.env` correspond to the settings defined in `src/config/settings.py`.

#### 3. Start Redis

The repository includes a Compose service for Redis. It maps host port `6380` to Redis's container port `6379`, matching the default `REDIS_URL` above.

```bash
docker compose up -d redis
```

#### 4. Prepare PostgreSQL

Create a database named `pico` (or use the database name configured in `.env`) and enable pgvector. For a local PostgreSQL installation, for example:

```bash
createdb -h localhost -U postgres pico
psql -h localhost -U postgres -d pico -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

The current application code does not create its relational tables automatically at startup. Once `.env` is configured, create the tables defined by the SQLAlchemy models:

```bash
PYTHONPATH=src uv run --no-sync python - <<'PY'
import asyncio
from db.session import get_engine
from models.db import Base

async def main():
    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()

asyncio.run(main())
PY
```

The pgvector extension must be installed on the PostgreSQL server before this step. The vector-store tables are managed by LangChain's PGVector integration.

#### 5. Start Ollama

Make sure the Ollama service is running and pull the configured embedding model:

```bash
ollama pull nomic-embed-text
```

Configure `OLLAMA_API_KEY` and `LLM_MODEL` for a chat model available through Ollama Cloud. Pico uses local Ollama for embeddings and the Ollama Cloud-compatible endpoint for chat generation.

#### 6. Run Pico

From the repository root:

```bash
PYTHONPATH=src uv run --no-sync uvicorn main:app --reload
```

The application will be available at:

- Web interface: <http://localhost:8000/>
- Swagger API docs: <http://localhost:8000/api/docs>
- ReDoc: <http://localhost:8000/api/redoc>
- Health endpoint: <http://localhost:8000/pico/api/health>

The health endpoint checks PostgreSQL, Redis, local Ollama, and the configured Ollama Cloud endpoint.

### API overview

The default API prefix is `/pico/api`. Protected workspace-scoped endpoints expect the workspace key in the `X-API-Key` header.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/pico/api/health` | Check dependencies |
| `POST` | `/pico/api/workspaces` | Create a workspace and generate an API key |
| `GET` | `/pico/api/workspaces` | List workspaces |
| `DELETE` | `/pico/api/workspaces/{identifier}` | Delete a workspace and associated data |
| `POST` | `/pico/api/ingest/upload` | Upload one document (`multipart/form-data`) |
| `POST` | `/pico/api/ingest/bulk` | Upload multiple documents |
| `GET` | `/pico/api/documents` | List documents, with pagination and an optional user filter |
| `DELETE` | `/pico/api/documents/{doc_id}` | Delete a document and its vectors |
| `GET` | `/pico/api/conversations?user_id=...` | List a user's conversations |
| `POST` | `/pico/api/conversations` | Create a conversation |
| `PATCH` | `/pico/api/conversations/{convo_id}` | Rename or pin a conversation |
| `DELETE` | `/pico/api/conversations/{convo_id}` | Delete a conversation and its Redis history |
| `POST` | `/pico/api/chat` | Ask a question and stream the answer as SSE |

See Swagger UI for request and response schemas.

#### Create a workspace

```bash
curl -X POST http://localhost:8000/pico/api/workspaces \
  -H 'Content-Type: application/json' \
  -d '{"name":"Engineering Docs","identifier":"engineering"}'
```

The response includes an `api_key`. **Save it when the workspace is created:** the raw key is returned only once.

#### Upload a document

```bash
export PICO_API_KEY='paste-your-workspace-api-key-here'

curl -X POST http://localhost:8000/pico/api/ingest/upload \
  -H "X-API-Key: $PICO_API_KEY" \
  -F 'file=@./docs/overview.md' \
  -F 'user_id=user-123'
```

Add `-F 'is_public=true'` to set the document's public flag. Uploading the same file content for the same workspace and user is detected as a duplicate.

#### Create a conversation

```bash
curl -X POST http://localhost:8000/pico/api/conversations \
  -H "X-API-Key: $PICO_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user-123","name":"Documentation Q&A"}'
```

Use the returned conversation `id` in the chat request.

#### Ask a question

```bash
curl -N -X POST http://localhost:8000/pico/api/chat \
  -H "X-API-Key: $PICO_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id":"<conversation-id-from-the-previous-step>",
    "query":"Summarize the main ideas in my document.",
    "user_id":"user-123"
  }'
```

The response is an SSE stream containing token events, a final `[SOURCES]` event, and a `[DONE]` sentinel. You can optionally pass `document_filter` with a `user_id` and/or `filename` to narrow the retrieval scope.

### Configuration reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_HOST` | `localhost` | PostgreSQL host |
| `DATABASE_PORT` | `5432` | PostgreSQL port |
| `DATABASE_NAME` | empty | Database name; set this before running |
| `DATABASE_USER` | empty | Database username; set this before running |
| `DATABASE_PASSWORD` | empty | Database password; set this before running |
| `REDIS_URL` | `redis://localhost:6380/0` | Redis connection URL |
| `OLLAMA_LOCAL_URL` | `http://localhost:11434` | Local Ollama URL |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model name |
| `OLLAMA_CLOUD_URL` | `https://api.ollama.com/v1` | OpenAI-compatible chat endpoint |
| `OLLAMA_API_KEY` | empty | Ollama Cloud API key |
| `LLM_MODEL` | empty | Chat model name |
| `LLM_TEMPERATURE` | `0.1` | Chat generation temperature |
| `TOP_K_DENSE` | `15` | Number of dense-retrieval candidates |
| `TOP_K_FINAL` | `6` | Number of final retrieved chunks |
| `RRF_K` | `50` | RRF ranking constant |
| `CHUNK_SIZE` | `1000` | Target chunk size |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `MIN_CHUNK_LENGTH` | `50` | Ignore chunks shorter than this length |
| `REDIS_TTL_HOURS` | `24` | Conversation-history TTL in hours |
| `REDIS_MAX_MESSAGES` | `20` | Maximum recent messages considered |
| `API_PREFIX` | `/pico/api` | Prefix for API routes |
| `CORS_ORIGINS` | `["http://localhost:8000"]` | Allowed browser origins; provide a JSON array |
| `MAX_DOCUMENT_COUNT` | `30` | Configured document-count limit |
| `MAX_CONVERSATION_COUNT` | `30` | Configured conversation-count limit |

### Project structure

```text
pico/
├── main.py                 # FastAPI application entry point
├── compose.yml             # Redis service for local development
├── pyproject.toml          # Project metadata and dependencies
├── uv.lock                 # Locked dependency versions
└── src/
    ├── api/                # Health, workspace, document, ingest, chat APIs
    ├── config/             # Settings and FastAPI dependencies
    ├── core/               # Loaders, chunking, embeddings, retrieval, RAG chain
    ├── db/                 # PostgreSQL engine and session management
    ├── models/              # SQLAlchemy models and request/response schemas
    ├── pages/               # HTML page routes
    ├── service/             # Ingestion, vector store, workspace, chat, Redis services
    ├── static/              # Static assets
    └── templates/           # HTML pages
```

### Security notes

- Treat workspace API keys as secrets. The raw key is returned only when a workspace is created.
- In the current code, workspace management routes (`POST`, `GET`, and `DELETE /workspaces`) are not protected by the workspace API-key dependency. Add administrative authentication and authorization before exposing these routes on a public network.
- Keep `.env` out of version control and use strong database credentials.

### Current limitations

- DOCX ingestion is not fully implemented yet.
- PostgreSQL's relational tables must be initialized manually; application startup does not run migrations or create them automatically.
- Configure both local Ollama embeddings and the Ollama Cloud chat model before testing the full RAG flow.
