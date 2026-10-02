"""
retrieval/retrieve.py

Hybrid retrieval + answer.
Flow:
  1. Classify the question into a domain using the same closed classifier.
  2. Embed the question via OpenRouter.
  3. Neo4j vector search on (:Chunk) nodes scoped to domain.
  4. Graphiti hybrid search on facts/edges scoped to domain.
  5. Merge chunk text + graph facts into one context.
  6. Synthesize a grounded answer via OpenRouter LLM.
"""
from __future__ import annotations
import os
from openai import OpenAI
from src.ingest.classify import classify, parent_chain
from src.ingest.embedder import embed_chunks
from src.graph_client import raw_async_driver, NEO4J_DATABASE
from config.ontology import team_to_group_id, CLASSIFICATION_TARGETS

_client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
)
_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o")
_SYSTEM = (
    "You answer strictly from the provided knowledge-graph facts and document chunks. "
    "Each item is tagged with its source type and team/domain. "
    "If the facts are insufficient, say so plainly. Do not invent anything. "
    "Cite the team(s)/domain(s) you used."
)

VECTOR_SEARCH = """
CALL db.index.vector.queryNodes('chunk_embeddings', $top_k, $query_embedding)
YIELD node, score
WHERE node.group_id IN $group_ids
RETURN node.text AS text, node.group_id AS group_id, node.file_path AS file_path, score
"""

async def retrieve_chunks(
    question_embedding: list[float],
    group_ids: list[str],
    top_k: int = 8,
) -> list[dict]:
    """Neo4j native vector search scoped to group_ids."""
    driver = raw_async_driver()
    try:
        async with driver.session(database=NEO4J_DATABASE) as s:
            result = await s.run(VECTOR_SEARCH, {
                "top_k": top_k * 3,  # over-fetch, then filter by group_id in Cypher
                "query_embedding": question_embedding,
                "group_ids": group_ids,
            })
            records = await result.data()
        return [
            {"text": r["text"], "team": r["group_id"], "file_path": r["file_path"], "score": r["score"]}
            for r in records[:top_k]
        ]
    finally:
        await driver.close()

async def retrieve_facts(
    graphiti,
    question: str,
    group_ids: list[str],
    per_team: int = 8,
) -> list[dict]:
    """Graphiti hybrid search. Returns fact dicts with provenance."""
    results = await graphiti.search(
        query=question,
        group_ids=group_ids,
        num_results=per_team,
    )
    facts = []
    for edge in results:
        facts.append({
            "fact":       getattr(edge, "fact",     str(edge)),
            "team":       getattr(edge, "group_id", "unknown"),
            "valid_at":   str(getattr(edge, "valid_at",   "") or ""),
            "invalid_at": str(getattr(edge, "invalid_at", "") or ""),
        })
    return facts

def synthesize(question: str, facts: list[dict], chunks: list[dict]) -> str:
    if not facts and not chunks:
        return "No facts or chunks found for that question."

    lines = []
    for f in facts:
        temporal = ""
        if f["valid_at"]:
            temporal = f" (valid from {f['valid_at']}" + (
                f", superseded {f['invalid_at']})" if f["invalid_at"] else ")"
            )
        lines.append(f"- [FACT][{f['team']}] {f['fact']}{temporal}")

    for c in chunks:
        lines.append(f"- [CHUNK][{c['team']}] {c['text']} (score={c['score']:.3f})")

    context = "\n".join(lines)
    user = (
        f"Knowledge:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer (with team citations):"
    )
    resp = _client.chat.completions.create(
        model=_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content

async def ask(graphiti, question: str, company_id: str) -> str:
    domain, conf = classify(question)
    if domain:
        group_ids = [team_to_group_id(company_id, d) for d in parent_chain(domain)]
    else:
        group_ids = [team_to_group_id(company_id, d) for d in CLASSIFICATION_TARGETS]

    print(f"  [debug] question classified -> domain={domain} conf={conf}")
    print(f"  [debug] searching group_ids={group_ids}")

    question_embedding = embed_chunks([question])[0]

    facts  = await retrieve_facts(graphiti, question, group_ids)
    chunks = await retrieve_chunks(question_embedding, group_ids)

    print(f"  [debug] facts={len(facts)} chunks={len(chunks)}")

    return synthesize(question, facts, chunks)