# """
# Seed the FIXED organizational skeleton into Neo4j using plain Cypher.
# Idempotent (MERGE) — safe to re-run. No LLM involved.
# This is the ONLY place Department and Team nodes are created.

# Structure seeded:
#   (:Organization)-[:HAS_DEPARTMENT]->(:Department)-[:HAS_TEAM]->(:Team)
# """
# from __future__ import annotations
# import asyncio
# from neo4j import AsyncGraphDatabase
# from src.graph_client import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE
# from config.ontology import ORGANIZATION, TAXONOMY

# CONSTRAINTS = [
#     "CREATE CONSTRAINT org_name  IF NOT EXISTS FOR (o:Organization) REQUIRE o.name IS UNIQUE",
#     "CREATE CONSTRAINT dept_id   IF NOT EXISTS FOR (d:Department)   REQUIRE d.id   IS UNIQUE",
#     "CREATE CONSTRAINT team_id   IF NOT EXISTS FOR (t:Team)         REQUIRE t.id   IS UNIQUE",
# ]

# SEED = """
# MERGE (org:Organization {name: $org})
# WITH org
# UNWIND $tree AS branch
#   MERGE (dept:Department {id: branch.department})
#     ON CREATE SET dept.name = branch.department
#   MERGE (org)-[:HAS_DEPARTMENT]->(dept)
#   WITH org, dept, branch
#   UNWIND branch.teams AS teamName
#     MERGE (team:Team {id: teamName})
#       ON CREATE SET team.name = teamName
#     MERGE (dept)-[:HAS_TEAM]->(team)
# """


# async def seed() -> None:
#     tree = [
#         {"department": dept, "teams": teams}
#         for dept, teams in TAXONOMY.items()
#     ]
#     driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
#     try:
#         async with driver.session(database=NEO4J_DATABASE) as session:
#             for c in CONSTRAINTS:
#                 await session.run(c)
#             await session.run(SEED, {"org": ORGANIZATION, "tree": tree})
#             result = await session.run(
#                 """
#                 MATCH (d:Department) WITH count(d) AS depts
#                 MATCH (t:Team) RETURN depts, count(t) AS teams
#                 """
#             )
#             rec = await result.single()
#             print(f"Skeleton ready: {rec['depts']} departments, {rec['teams']} teams.")
#     finally:
#         await driver.close()


# if __name__ == "__main__":
#     asyncio.run(seed())

"""
scripts/seed_taxonomy.py

Seeds the Neo4j Schema layer from CSV.
Creates: (:Schema:Domain)-[:HAS]->(:Schema:SubFunction)-[:HAS]->(:Schema:NodeType)
Safe to re-run — all writes use MERGE.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph_client import raw_async_driver, NEO4J_DATABASE
from config.ontology import DOMAIN_TO_SUBFUNCTIONS, SUBFUNCTION_TO_NODETYPES

MERGE_DOMAIN = """
MERGE (d:Schema:Domain {key: $key})
SET d.name = $name
"""

MERGE_SUBFN = """
MATCH (d:Schema:Domain {key: $domain_key})
MERGE (s:Schema:SubFunction {key: $key})
SET s.name = $name
MERGE (d)-[:HAS]->(s)
"""

MERGE_NT = """
MATCH (s:Schema:SubFunction {key: $subfn_key})
MERGE (n:Schema:NodeType {key: $key})
SET n.name = $name
MERGE (s)-[:HAS]->(n)
"""


def _key(s: str) -> str:
    return s.lower().replace(" ", "_").replace("/", "_").replace("&", "and")


async def seed():
    driver = raw_async_driver()
    counts = {"domains": 0, "subfunctions": 0, "node_types": 0}

    try:
        async with driver.session(database=NEO4J_DATABASE) as session:

            # 1. Domains
            for domain, subfns in DOMAIN_TO_SUBFUNCTIONS.items():
                await session.run(MERGE_DOMAIN, key=_key(domain), name=domain)
                counts["domains"] += 1

                # 2. SubFunctions
                for subfn in subfns:
                    await session.run(
                        MERGE_SUBFN,
                        domain_key=_key(domain),
                        key=_key(subfn),
                        name=subfn,
                    )
                    counts["subfunctions"] += 1

                    # 3. NodeTypes
                    for nt in SUBFUNCTION_TO_NODETYPES.get(subfn, []):
                        await session.run(
                            MERGE_NT,
                            subfn_key=_key(subfn),
                            key=_key(nt),
                            name=nt,
                        )
                        counts["node_types"] += 1

    finally:
        await driver.close()

    print(f"[seed] Done.")
    print(f"  Domains:      {counts['domains']}")
    print(f"  SubFunctions: {counts['subfunctions']}") 
    print(f"  NodeTypes:    {counts['node_types']}")


if __name__ == "__main__":
    asyncio.run(seed())