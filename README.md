# RAG PoC L3

Full-stack Retrieval-Augmented Generation app: JWT auth, document ingestion, semantic search (Qdrant) and chat powered by a local LLM (Ollama).

## Stack

- **Backend:** FastAPI, SQLite, LlamaIndex, JWT (`python-jose`), bcrypt
- **Vector DB:** Qdrant
- **LLM / Embeddings:** Ollama (local)
- **Frontend:** Vanilla HTML/CSS/JS

## Structure

```
rag-poc-l3/
├── back-end/            # FastAPI API
│   ├── core_endpoints/  # auth, chat, admin, rag routes
│   ├── services/        # SQLite + RAG helpers
│   ├── config.py        # env vars, CORS, auth setup
│   ├── models.py        # Pydantic schemas
│   ├── main.py          # app entrypoint + route wiring
│   └── requirements.txt
└── front-end/           # Static UI
    ├── login/ chat/ admin/ stats/
    ├── assets/ lib/
    └── config.js        # API base URL
```

## Features

- **Auth:** JWT (HS256), bcrypt hashing, role claim, server-side token revocation
- **Chat:** multi-turn sessions and messages persisted in SQLite, LLM-generated titles, 50-message context
- **RAG:** ingest `.txt`, `.md`, `.pdf`, `.docx`; semantic search via Qdrant; generation via Ollama
- **Admin panel (`/admin`):** manage personas, users (promote/demote) and the knowledge base (ingest text / reset)

## Quick Start

Prerequisites: Python 3.13, [Ollama](https://ollama.com) running locally and [Docker](https://docs.docker.com/get-docker/) for Qdrant.

### Qdrant (one command)

```bash
docker run -d --name rag-poc-qdrant -p 6333:6333 -p 6334:6334 \
  -v "$(pwd)/qdrant_storage:/qdrant/storage" qdrant/qdrant
```

Windows (PowerShell):

```powershell
docker run -d --name rag-poc-qdrant -p 6333:6333 -p 6334:6334 -v "${PWD}/qdrant_storage:/qdrant/storage" qdrant/qdrant
```

### Backend (macOS / Linux)

```bash
cd back-end
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python check_versions.py  # optional: check Python + JS dependency versions
cp .env.example .env      # then fill in secrets
python main.py            # http://127.0.0.1:8000
```

### Backend (Windows)

```powershell
cd back-end
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python check_versions.py
copy .env.example .env
python main.py
```

### Environment

| Variable | Default | Notes |
| --- | --- | --- |
| `SECRET_KEY` | — | Required. JWT signing key. |
| `ADMIN_SECRET` | — | Required to register an admin. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `OLLAMA_MODEL` | `lfm2.5-thinking` | |
| `OLLAMA_EMBEDDING_MODEL` | `embeddinggemma` | |
| `QDRANT_URL` | `http://localhost:6333` | |
| `QDRANT_COLLECTION_NAME` | `documents` | |

## Ingesting data

Supported files: `.txt`, `.md`, `.pdf`, `.docx` (max 20 MB each). Content is split
into chunks, embedded with Ollama (`embeddinggemma`) and stored in Qdrant — make
sure Ollama and Qdrant are running first.

### From the UI

- **Chat page** — click the paperclip button and pick a file (any logged-in user).
- **Admin → Base de connaissances** — paste raw text and click *Ingérer*; use
  *Réinitialiser la base* to clear everything.

### From the API

```bash
# Log in and capture a token (use your own credentials)
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"YOUR_USER","password":"YOUR_PASSWORD"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Upload a file (any authenticated user)
curl -X POST http://127.0.0.1:8000/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./docs/handbook.pdf"

# Ingest raw text (admin only)
curl -X POST http://127.0.0.1:8000/ingest \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"documents":["RAG PoC L3 ingests text and documents."]}'

# Check how many vectors are stored (admin only)
curl http://127.0.0.1:8000/collection-info -H "Authorization: Bearer $TOKEN"

# Query the knowledge base (authenticated)
curl -X POST http://127.0.0.1:8000/query \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"What is RAG PoC L3?"}'
```

### Bulk import a folder

```bash
for f in ./data/*.pdf ./data/*.docx ./data/*.txt ./data/*.md; do
  [ -e "$f" ] || continue
  curl -s -X POST http://127.0.0.1:8000/upload \
    -H "Authorization: Bearer $TOKEN" -F "file=@$f" > /dev/null
  echo "ingested $f"
done
```

### Reset the knowledge base (admin only)

```bash
curl -X POST http://127.0.0.1:8000/reset-collection -H "Authorization: Bearer $TOKEN"
```

> No account yet? Register one with
> `curl -X POST http://127.0.0.1:8000/register -H 'Content-Type: application/json' -d '{"full_name":"Demo","username":"demo"}'`
> — the generated password is returned once in the response.

## Docs

- [back-end/backend.md](back-end/backend.md) — API routes, schema, config, RAG pipeline
- [front-end/frontend.md](front-end/frontend.md) — pages, API usage, dev setup
