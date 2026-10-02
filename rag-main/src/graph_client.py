# 
"""
Connection factory.
Builds a configured Graphiti instance and a raw Neo4j async driver.
Every other module imports from here — no connection logic lives elsewhere.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
from sentence_transformers import SentenceTransformer
from graphiti_core import Graphiti
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

load_dotenv()

# Neo4j
NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# OpenRouter
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL           = os.getenv("LLM_MODEL",   "openai/gpt-4o")
SMALL_MODEL         = os.getenv("SMALL_MODEL", "openai/gpt-4o-mini")

# Local embeddings
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
EMBED_DIM   = int(os.getenv("EMBED_DIM", "384"))


# class SentenceTransformerEmbedder(EmbedderClient):
#     """Local embedder using sentence-transformers. No API key needed."""

#     def __init__(self, model_name: str = EMBED_MODEL):
#         self._model = SentenceTransformer(model_name)

#     async def create(self, input_data) -> list[float]:
#         if isinstance(input_data, str):
#             return self._model.encode(input_data).tolist()
#         return self._model.encode(list(input_data))[0].tolist()

class SentenceTransformerEmbedder(EmbedderClient):
    """Local embedder using sentence-transformers. No API key needed."""

    def __init__(self, model_name: str = EMBED_MODEL):
        self._model = SentenceTransformer(model_name)

    async def create(self, input_data) -> list[float]:
        if isinstance(input_data, str):
            return self._model.encode(input_data).tolist()
        return self._model.encode(list(input_data))[0].tolist()

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        return self._model.encode(input_data_list).tolist()


def build_graphiti() -> Graphiti:
    llm_config = LLMConfig(
        model=LLM_MODEL,
        small_model=SMALL_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
    )
    llm_client    = OpenAIClient(config=llm_config)
    embedder      = SentenceTransformerEmbedder()
    cross_encoder = OpenAIRerankerClient(client=llm_client, config=llm_config)
    graph_driver  = Neo4jDriver(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE,
    )

    return Graphiti(
        graph_driver=graph_driver,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder,
    )


def raw_async_driver():
    return AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
    )