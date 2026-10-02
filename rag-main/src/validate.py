"""
Audit guard — proves the graph never drifted outside the closed ontology.
Run after ingestion. Fails loudly if:
  - any Department node exists that isn't in the taxonomy
  - any Team node exists that isn't in the taxonomy
  - any Episodic node has a group_id that doesn't match a known team+company pattern
"""
from __future__ import annotations
import asyncio
from neo4j import AsyncGraphDatabase
from src.graph_client import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE
from config.ontology import DEPARTMENTS, CLASSIFICATION_TARGETS, ALLOWED_TARGETS

CHECK_DEPARTMENTS = "MATCH (d:Department) RETURN collect(d.id) AS ids"
CHECK_TEAMS       = "MATCH (t:Team)       RETURN collect(t.id) AS ids"
CHECK_GROUPS      = "MATCH (n:Episodic)   RETURN collect(DISTINCT n.group_id) AS ids"


async def validate() -> bool:
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    ok = True
    try:
        async with driver.session(database=NEO4J_DATABASE) as s:
            depts  = (await (await s.run(CHECK_DEPARTMENTS)).single())["ids"]
            teams  = (await (await s.run(CHECK_TEAMS)).single())["ids"]
            groups = (await (await s.run(CHECK_GROUPS)).single())["ids"]

        bad_depts = set(depts) - set(DEPARTMENTS)
        bad_teams = set(teams) - set(CLASSIFICATION_TARGETS)

        # group_id format: "{company_id}__{team_id}"
        # extract team part and check against allowed targets
        bad_groups = set()
        for g in groups:
            if not g:
                continue
            parts = g.split("__", 1)
            if len(parts) != 2 or parts[1] not in ALLOWED_TARGETS:
                bad_groups.add(g)

        if bad_depts:
            ok = False
            print(f"FAIL  unexpected departments: {bad_depts}")
        if bad_teams:
            ok = False
            print(f"FAIL  unexpected teams: {bad_teams}")
        if bad_groups:
            ok = False
            print(f"FAIL  episodes with off-taxonomy group_id: {bad_groups}")
        if ok:
            print("PASS  graph conforms to closed taxonomy. No new categories created.")
    finally:
        await driver.close()
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(validate()) else 1)