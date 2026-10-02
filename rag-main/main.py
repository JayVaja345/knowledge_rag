"""
Kozy AI — Company Brain API
Endpoints:
  POST /ingest  — Cloudinary PDF URL + company_id -> full ingestion pipeline
  POST /chat    — question + company_id -> grounded answer from graph
  GET  /health  — health check
All endpoints protected by x-endpoint-secret header.
"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel

from src.graph_client import build_graphiti
from src.seed_taxonomy import seed
from src.ingest.loaders import load_cloudinary_file
from src.ingest.ingest import ingest_docs
from src.retrieval.retrieve import ask

load_dotenv()

ENDPOINT_SECRET = os.getenv("ENDPOINT_SECRET", "")

# ---------------------------------------------------------------------------
# App lifespan — seed taxonomy + build Graphiti once at startup
# ---------------------------------------------------------------------------
graphiti = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graphiti
    print("Seeding taxonomy...")
    await seed()
    print("Building Graphiti indices...")
    graphiti = build_graphiti()
    await graphiti.build_indices_and_constraints()
    print("Ready.")
    yield
    await graphiti.close()


app = FastAPI(title="Kozy AI Company Brain", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def verify_secret(x_endpoint_secret: str = Header(...)):
    if not ENDPOINT_SECRET or x_endpoint_secret != ENDPOINT_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class IngestRequest(BaseModel):
    cloudinary_url: str
    company_id: str
    title: str | None = None
    min_confidence: float = 0.0


class IngestResponse(BaseModel):
    episodes: int
    rejected: int


class ChatRequest(BaseModel):
    question: str
    company_id: str


class ChatResponse(BaseModel):
    answer: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse, dependencies=[Depends(verify_secret)])
async def ingest(req: IngestRequest):
    doc = load_cloudinary_file(req.cloudinary_url, company_id=req.company_id, title=req.title)
    if doc is None:
        raise HTTPException(status_code=422, detail="Failed to load or parse PDF.")

    stats = await ingest_docs(
        graphiti=graphiti,
        docs=[doc],
        company_id=req.company_id,
        min_conf=req.min_confidence,
    )
    return IngestResponse(**stats)


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(verify_secret)])
async def chat(req: ChatRequest):
    answer = await ask(
        graphiti=graphiti,
        question=req.question,
        company_id=req.company_id,
    )
    return ChatResponse(answer=answer)