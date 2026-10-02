#     """
# Classify a chunk of text into EXACTLY ONE existing team.
# Closed-gate: model is shown the fixed list and must return one verbatim.
# Anything off-list is rejected by the caller — no new category can ever be created.
# """
# from __future__ import annotations
# import json
# import os
# from openai import OpenAI
# from config.ontology import CLASSIFICATION_TARGETS, is_valid_target, PARENT_OF

# _client = OpenAI(
#     api_key=os.getenv("OPENROUTER_API_KEY"),
#     base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
# )
# _MODEL = os.getenv("SMALL_MODEL", "openai/gpt-4o-mini")

# _SYSTEM = (
#     "You are a strict classifier for a company knowledge graph. "
#     "You will be given a passage of text. Assign it to EXACTLY ONE team "
#     "from the allowed list. You MUST choose an ID from the list verbatim. "
#     "You may NOT invent new teams. If nothing fits well, choose the single "
#     "closest team. Respond ONLY as JSON: {\"team\": \"<ID>\", \"confidence\": 0.0-1.0}."
# )


# def classify(text: str) -> tuple[str | None, float]:
#     """Return (team_id, confidence) or (None, 0.0) if model went off-list."""
#     allowed = ", ".join(CLASSIFICATION_TARGETS)
#     user = f"Allowed teams: {allowed}\n\nPassage:\n{text[:4000]}"

#     resp = _client.chat.completions.create(
#         model=_MODEL,
#         temperature=0,
#         response_format={"type": "json_object"},
#         messages=[
#             {"role": "system", "content": _SYSTEM},
#             {"role": "user",   "content": user},
#         ],
#     )

#     try:
#         data   = json.loads(resp.choices[0].message.content)
#         target = data.get("team")
#         conf   = float(data.get("confidence", 0.0))
#     except Exception:
#         return None, 0.0

#     # HARD GATE: reject anything not in the closed taxonomy
#     if target and is_valid_target(target):
#         return target, conf
#     return None, 0.0


# def parent_chain(team_id: str) -> list[str]:
#     """[team, department] — used to build scoped group_ids for retrieval."""
#     chain = [team_id]
#     dept = PARENT_OF.get(team_id)
#     if dept:
#         chain.append(dept)
#     return chain

"""
Classify a chunk of text into EXACTLY ONE existing domain.
Closed-gate: model is shown the fixed list and must return one verbatim.
Anything off-list is rejected by the caller — no new category can ever be created.
"""
from __future__ import annotations
import json
import os
from openai import OpenAI
from config.ontology import CLASSIFICATION_TARGETS, is_valid_target, PARENT_OF

_client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
)
_MODEL = os.getenv("SMALL_MODEL", "openai/gpt-4o-mini")

_SYSTEM = (
    "You are a strict classifier for a company knowledge graph. " 
    "You will be given a passage of text. Assign it to EXACTLY ONE domain "
    "from the allowed list. You MUST choose an ID from the list verbatim. "
    "You may NOT invent new domains. If nothing fits well, choose the single "
    "closest domain. Respond ONLY as JSON: {\"team\": \"<ID>\", \"confidence\": 0.0-1.0}."
)


def classify(text: str) -> tuple[str | None, float]:
    """Return (domain_id, confidence) or (None, 0.0) if model went off-list."""
    allowed = ", ".join(CLASSIFICATION_TARGETS)
    user = f"Allowed domains: {allowed}\n\nPassage:\n{text[:4000]}"
    resp = _client.chat.completions.create(
        model=_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": user},
        ],
    )
    try:
        data   = json.loads(resp.choices[0].message.content)
        target = data.get("team")
        conf   = float(data.get("confidence", 0.0))
    except Exception:
        return None, 0.0

    if target and is_valid_target(target):
        return target, conf
    return None, 0.0


def parent_chain(domain_id: str) -> list[str]:
    """[domain] — kept for retrieval compatibility."""
    return [domain_id]