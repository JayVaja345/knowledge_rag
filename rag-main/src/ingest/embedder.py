"""
src/ingest/embedder.py

Generates embeddings for text chunks via OpenRouter.
Model: text-embedding-3-small (1536 dims)
"""
from __future__ import annotations
import os
from openai import OpenAI

EMBED_MODEL = "openai/text-embedding-3-small"
EMBED_DIMS = 1536

_client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
)

def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """
    Takes a list of text chunks.
    Returns a list of 1536-dim float vectors in the same order.
    """
    response = _client.embeddings.create(
        model=EMBED_MODEL,
        input=chunks,
    )
    return [item.embedding for item in response.data]