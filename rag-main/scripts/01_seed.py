"""
scripts/01_seed.py

Step 1 — seed the fixed skeleton + build Graphiti indices + create Neo4j vector index.
Run once.
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.seed_taxonomy import seed
from src.graph_client import build_graphiti, raw_async_driver, NEO4J_DATABASE

CREATE_VECTOR_INDEX = """
CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }
}
"""

async def main():
    print("Seeding fixed domain/subfunction/nodetype taxonomy...")
    await seed()

    print("Creating Neo4j vector index for chunks...")
    driver = raw_async_driver()
    try:
        async with driver.session(database=NEO4J_DATABASE) as session:
            await session.run(CREATE_VECTOR_INDEX)
        print("Vector index ready.")
    finally:
        await driver.close()

    print("Building Graphiti indices and constraints...")
    g = build_graphiti()
    try:
        await g.build_indices_and_constraints()
        print("Graphiti indices ready.")
    finally:
        await g.close()

if __name__ == "__main__":
    asyncio.run(main())