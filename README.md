# Knowledge RAG: Enterprise Knowledge Intelligence

Multi-tenant Graph RAG backend that answers questions over company documents. It combines Neo4j vector search with Graphiti graph-based fact retrieval, scoped per company.

A closed-taxonomy gate rejects any content that falls outside a predefined organisational ontology, so the graph cannot grow new categories on its own.

## How it works

**Ingestion** (`POST /ingest`)
1. Download a PDF, DOCX, PPTX or HTML file from a Cloudinary URL.
2. Parse it with Docling (OCR, table structure, image captions via a vision model).
3. Chunk it by markdown headers, falling back to TF-IDF grouping.
4. Classify each chunk into exactly one domain from the fixed ontology. Off-list results are rejected.
5. Embed the chunk (`text-embedding-3-small`, 1536 dims) and store it in Neo4j as a `Chunk` node.
6. Add the chunk to Graphiti as an episode, scoped by `company_id` and domain, to extract facts.

**Retrieval** (`POST /chat`)
1. Classify the question into a domain.
2. Run a Neo4j vector search on chunks and a Graphiti hybrid search on facts, both scoped to that company and domain.
3. Merge the results and have the LLM write an answer grounded only in them, citing the domains used.

`src/validate.py` is an audit script that checks the graph never drifted outside the ontology.

## Stack

Python, FastAPI, Neo4j, Graphiti, Docling, OpenRouter (GPT-4o, GPT-4o-mini), sentence-transformers, scikit-learn, LangChain text splitters.

## Setup

```bash
git clone https://github.com/JayVaja345/knowledge_rag.git
cd knowledge_rag
pip install -r requirements.txt
cp .env.example .env   # then fill in the values
uvicorn main:app --reload
```

### Environment variables

| Variable | Purpose |
| --- | --- |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` | Neo4j connection |
| `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL` | LLM, embeddings and vision calls |
| `LLM_MODEL`, `SMALL_MODEL`, `VLM_MODEL` | Model overrides (defaults: gpt-4o, gpt-4o-mini, qwen2.5-vl-72b) |
| `ENDPOINT_SECRET` | Required in the `x-endpoint-secret` header on all endpoints |
| `STORAGE_ROOT` | Where downloaded files are saved |

## API

```bash
curl -X POST localhost:8000/ingest \
  -H "x-endpoint-secret: $ENDPOINT_SECRET" -H "Content-Type: application/json" \
  -d '{"cloudinary_url": "https://...", "company_id": "acme"}'

curl -X POST localhost:8000/chat \
  -H "x-endpoint-secret: $ENDPOINT_SECRET" -H "Content-Type: application/json" \
  -d '{"question": "What is the recruitment policy?", "company_id": "acme"}'
```

`GET /health` returns `{"status": "ok"}`.
