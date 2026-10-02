"""
src/ingest/ingest.py

Ingestion orchestrator.
For each chunk:
  1. Classify into one EXISTING domain (closed gate).        -> reject if off-list
  2. Embed chunk via OpenRouter text-embedding-3-small.      -> 1536-dim vector
  3. Store chunk + embedding as (:Chunk) node in Neo4j.      -> vector searchable
  4. Add as Graphiti episode with group_id = company_id__domain -> fact extraction
  5. Link Graphiti nodes to Schema Domain/SubFunction nodes.  -> connects skeleton + content
  6. Tag Episodic nodes with file_path.                       -> file retrieval later
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from graphiti_core.nodes import EpisodeType
from src.graph_client import build_graphiti, raw_async_driver, NEO4J_DATABASE
from src.ingest.chunker import chunk
from src.ingest.classify import classify
from src.ingest.embedder import embed_chunks
from config.ontology import ENTITY_TYPES, EDGE_TYPES, EDGE_TYPE_MAP, PARENT_OF, team_to_group_id
from src.ingest.loaders import TextDoc, load_cloudinary_file

CHECK_CHUNK_EXISTS = """
MATCH (c:Chunk {id: $id}) RETURN count(c) AS exists
"""

STORE_CHUNK = """
MERGE (c:Chunk {id: $id})
SET c.text       = $text,
    c.embedding  = $embedding,
    c.group_id   = $group_id,
    c.file_path  = $file_path,
    c.source     = $source,
    c.domain     = $domain,
    c.created_at = $created_at
"""

LINK_CHUNK_TO_SCHEMA = """
MATCH (c:Chunk {id: $id})
MATCH (d:Schema:Domain {key: $domain_key})
MERGE (c)-[:BELONGS_TO_DOMAIN]->(d)
"""

LINK_TO_SKELETON = """
MATCH (n {group_id: $group_id})
WHERE n:Episodic OR n:Entity
MATCH (d:Schema:Domain {key: $domain_key})
MERGE (d)-[:HAS_CONTENT]->(n)
"""

TAG_FILE_PATH = """
MATCH (n:Episodic {group_id: $group_id, name: $name})
SET n.file_path = $file_path, n.source_url = $source_url
"""

def _domain_key(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "_", s).lower()

async def ingest_docs(
    graphiti,
    docs: list[TextDoc],
    company_id: str,
    min_conf: float = 0.0,
) -> dict:
    stats = {"episodes": 0, "rejected": 0}
    link_driver = raw_async_driver()
    try:
        for doc in docs:
            chunks = chunk(doc.text)
            if not chunks:
                continue

            embeddings = embed_chunks(chunks)
            print(f"  [debug] embeddings: count={len(embeddings)} dim={len(embeddings[0]) if embeddings else 0}")

            for i, (piece, embedding) in enumerate(zip(chunks, embeddings)):
                domain, conf = classify(piece)
                if domain is None or conf < min_conf:
                    stats["rejected"] += 1
                    print(f"  [reject] off-taxonomy or low confidence: {doc.source} #{i}")
                    continue

                group_id     = team_to_group_id(company_id, domain)
                chunk_id     = f"{company_id}__{doc.title}__{i}"
                episode_name = f"{doc.title} #{i}"
                created_at   = datetime.now(timezone.utc).isoformat()

                # resume: skip already ingested chunks
                async with link_driver.session(database=NEO4J_DATABASE) as s:
                    result = await s.run(CHECK_CHUNK_EXISTS, {"id": chunk_id})
                    record = await result.single()
                    if record and record["exists"] > 0:
                        print(f"  [skip] already ingested: {chunk_id}")
                        stats["episodes"] += 1
                        continue

                # store chunk + embedding
                async with link_driver.session(database=NEO4J_DATABASE) as s:
                    await s.run(STORE_CHUNK, {
                        "id":         chunk_id,
                        "text":       piece,
                        "embedding":  embedding,
                        "group_id":   group_id,
                        "file_path":  doc.file_path,
                        "source":     doc.source,
                        "domain":     domain,
                        "created_at": created_at,
                    })
                    await s.run(LINK_CHUNK_TO_SCHEMA, {
                        "id":         chunk_id,
                        "domain_key": _domain_key(domain),
                    })

                # graphiti fact extraction
                await graphiti.add_episode(
                    name=episode_name,
                    episode_body=piece,
                    source=EpisodeType.text,
                    source_description=doc.source,
                    reference_time=datetime.now(timezone.utc),
                    group_id=group_id,
                    entity_types=ENTITY_TYPES,
                    edge_types=EDGE_TYPES,
                    edge_type_map=EDGE_TYPE_MAP,
                )

                # link to schema + tag file path
                async with link_driver.session(database=NEO4J_DATABASE) as s:
                    await s.run(LINK_TO_SKELETON, {
                        "group_id":   group_id,
                        "domain_key": _domain_key(domain),
                    })
                    await s.run(TAG_FILE_PATH, {
                        "group_id":   group_id,
                        "name":       episode_name,
                        "file_path":  doc.file_path,
                        "source_url": doc.source,
                    })

                stats["episodes"] += 1
                print(f"  [ok] {doc.source} #{i} -> {domain} (conf={conf:.2f})")

    finally:
        await link_driver.close()
    return stats