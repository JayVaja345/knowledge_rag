# """
# CLOSED ONTOLOGY — single source of truth for the Kozy AI graph structure.

# Nothing in this system may create a node category not defined here.
# Classification targets are at TEAM level; department is inferred via PARENT_OF.
# group_id = f"{company_id}_{team_id}" enforces per-company, per-team isolation.
# """
# from __future__ import annotations
# from enum import Enum
# from pydantic import BaseModel, Field

# ORGANIZATION = "Organization"

# # ---------------------------------------------------------------------------
# # FIXED TAXONOMY  (department -> [teams])
# # ---------------------------------------------------------------------------
# TAXONOMY: dict[str, list[str]] = {  
#     "Core": [
#         "Corporate Strategy",
#         "Transformation Office",
#         "M&A (Mergers & Acquisitions)",
#         "Investor Relations / Shareholders",
#         "CEO Office / Chief of Staff",
#     ],
#     "Human Resources": [
#         "Recruitment / Talent Acquisition",
#         "HR Operations",
#         "Performance Management",
#         "Learning & Development (L&D)",
#         "Employee Engagement",
#     ],
#     "Finance & Accounting": [
#         "Accounting",
#         "FP&A (Financial Planning & Analysis)",
#         "Treasury",
#         "Taxation",
#         "Payroll Finance",
#     ],
#     "Legal & Compliance": [
#         "Corporate Legal",
#         "Contract Management",
#         "Compliance & Regulatory",
#         "Intellectual Property (IP)",
#     ],
#     "Administrative Functions": [
#         "Administration & Facilities",
#         "IT (Infrastructure & Support)",
#         "Compliance & Documentation",
#         "Security",
#         "Safety",
#     ],
#     "Sales & Marketing": [
#         "Brand Management",
#         "Market Analysis",
#         "Digital Marketing",
#         "Non-digital / Offline Marketing",
#         "Sales",
#         "Customer Service / Support",
#         "Business Development",
#         "Channel Partner Sales (Distribution)",
#         "Account Management / Customer Success",
#     ],
#     "Operations & Delivery": [
#         "Operations (BizOps)",
#         "Supply Chain & Logistics",
#         "Production / Manufacturing",
#         "Project Management",
#     ],
#     "Technical & Product": [
#         "Engineering / R&D",
#         "DevOps / Infrastructure",
#         "Product Management",
#         "Design",
#         "Data / AI / Business Analysis",
#         "Quality Assurance (QA)",
#     ],
#     "Admin / Facilities": [
#         "Admin / Facilities (General)",
#     ],
#     "Specialized Functions": [
#         "PR / Corporate Communications",
#         "Creative Services",
#         "Market / Business Intelligence",
#         "ESG / Sustainability",
#     ],
# }

# DEPARTMENTS: list[str] = list(TAXONOMY.keys())

# # Classification targets = all teams across all departments.
# CLASSIFICATION_TARGETS: list[str] = [
#     team for teams in TAXONOMY.values() for team in teams
# ]

# # Fast membership check.
# ALLOWED_TARGETS: frozenset[str] = frozenset(CLASSIFICATION_TARGETS)

# # Map every team back to its parent department.
# PARENT_OF: dict[str, str] = {
#     team: dept
#     for dept, teams in TAXONOMY.items()
#     for team in teams
# }


# def is_valid_target(target: str) -> bool:
#     """The ONLY gate that decides whether content may enter the graph."""
#     return target in ALLOWED_TARGETS


# # def team_to_group_id(company_id: str, team: str) -> str:
# #     """Multitenancy key: isolates each company's team data in Graphiti."""
# #     return f"{company_id}__{team}"

# def team_to_group_id(company_id: str, team: str) -> str:
#     """Multitenancy key: isolates each company's team data in Graphiti."""
#     import re
#     safe_team = re.sub(r"[^a-zA-Z0-9\-_]", "_", team)
#     return f"{company_id}__{safe_team}"

# def DepartmentEnum() -> type[Enum]:
#     """Runtime Enum of allowed targets — used to constrain the LLM classifier."""
#     return Enum("TeamTarget", {t: t for t in CLASSIFICATION_TARGETS})


# # ---------------------------------------------------------------------------
# # CLOSED ENTITY TYPES
# # Graphiti extracts ONLY these node types within each team scope.
# # ---------------------------------------------------------------------------
# class Product(BaseModel):
#     """A product, service, or product line offered or discussed."""
#     category: str | None = Field(None, description="High-level product category")


# class Person(BaseModel):
#     """A named individual: employee, executive, candidate, or external contact."""
#     role: str | None = Field(None, description="Their role or title, if stated")


# class Initiative(BaseModel):
#     """A project, program, campaign, or strategic initiative."""


# class Policy(BaseModel):
#     """A policy, regulation, contract clause, SOP, or compliance rule."""


# class Metric(BaseModel):
#     """A quantitative figure: revenue, headcount, KPI, score, price."""
#     unit: str | None = Field(None, description="Unit or currency, if stated")


# class Topic(BaseModel):
#     """A concept, technology, theme, or subject area discussed in the source."""


# ENTITY_TYPES: dict[str, type[BaseModel]] = {
#     "Product":    Product,
#     "Person":     Person,
#     "Initiative": Initiative,
#     "Policy":     Policy,
#     "Metric":     Metric,
#     "Topic":      Topic,
# }

# # ---------------------------------------------------------------------------
# # CLOSED EDGE TYPES
# # ---------------------------------------------------------------------------
# class PRODUCES(BaseModel):
#     """Entity makes, offers, or delivers the target product or service."""


# class RESPONSIBLE_FOR(BaseModel):
#     """A person or team is responsible for the target initiative, product, or area."""


# class COMPETES_WITH(BaseModel):
#     """The two entities compete in the same market or space."""


# class RELATES_TO(BaseModel):
#     """Generic association — used only when no specific edge type fits."""


# EDGE_TYPES: dict[str, type[BaseModel]] = {
#     "PRODUCES":         PRODUCES,
#     "RESPONSIBLE_FOR":  RESPONSIBLE_FOR,
#     "COMPETES_WITH":    COMPETES_WITH,
#     "RELATES_TO":       RELATES_TO,
# }

# EDGE_TYPE_MAP: dict[tuple[str, str], list[str]] = {
#     ("Entity", "Entity"): list(EDGE_TYPES.keys()),
# }

"""
config/ontology.py

CSV-driven ontology for Kozy AI.
Reads Enterprise_KG_SubFunction_NodeType_Mapping.csv at import time.
Dynamically generates Pydantic entity models for all NodeTypes.
Zero hardcoding of domains, subfunctions, or node types.
"""
from __future__ import annotations

import csv
import os
import re
from enum import Enum
from pathlib import Path
from typing import Any
from pydantic import BaseModel, create_model

# ---------------------------------------------------------------------------
# CSV path — sits at project root alongside this config/ folder
# ---------------------------------------------------------------------------
_CSV_PATH = Path(__file__).parent.parent / "t1.csv"


# ---------------------------------------------------------------------------
# Parse CSV once at import time
# ---------------------------------------------------------------------------
def _load_csv() -> list[dict[str, str]]:
    rows = []
    with open(_CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            domain = row["Domain"].strip()
            subfn  = row["Sub-function"].strip()
            nt     = row["Node Type"].strip()
            if domain and subfn and nt:
                rows.append({"domain": domain, "subfn": subfn, "node_type": nt})
    return rows


_ROWS = _load_csv()

# ---------------------------------------------------------------------------
# Derived structures
# ---------------------------------------------------------------------------

# Domain → set of SubFunctions
DOMAIN_TO_SUBFUNCTIONS: dict[str, list[str]] = {}
# SubFunction → set of NodeTypes
SUBFUNCTION_TO_NODETYPES: dict[str, list[str]] = {}
# NodeType → set of Domains (for classification reference)
NODETYPE_TO_DOMAINS: dict[str, set[str]] = {}

_seen_domain_subfn: set[tuple[str, str]] = set()
_seen_subfn_nt: set[tuple[str, str]] = set()

for _r in _ROWS:
    d, s, n = _r["domain"], _r["subfn"], _r["node_type"]

    if d not in DOMAIN_TO_SUBFUNCTIONS:
        DOMAIN_TO_SUBFUNCTIONS[d] = []
    if (d, s) not in _seen_domain_subfn:
        DOMAIN_TO_SUBFUNCTIONS[d].append(s)
        _seen_domain_subfn.add((d, s))

    if s not in SUBFUNCTION_TO_NODETYPES:
        SUBFUNCTION_TO_NODETYPES[s] = []
    if (s, n) not in _seen_subfn_nt:
        SUBFUNCTION_TO_NODETYPES[s].append(n)
        _seen_subfn_nt.add((s, n))

    NODETYPE_TO_DOMAINS.setdefault(n, set()).add(d)

DOMAINS: list[str] = list(DOMAIN_TO_SUBFUNCTIONS.keys())
SUBFUNCTIONS: list[str] = list(SUBFUNCTION_TO_NODETYPES.keys())
NODE_TYPES: list[str] = list({r["node_type"] for r in _ROWS})

# ---------------------------------------------------------------------------
# Classification targets = Domains (top-level classification)
# Graphiti group_id = company_id__sanitized_domain
# ---------------------------------------------------------------------------
CLASSIFICATION_TARGETS: list[str] = DOMAINS
ALLOWED_TARGETS: frozenset[str] = frozenset(DOMAINS)


def is_valid_target(target: str) -> bool:
    return target in ALLOWED_TARGETS


def _sanitize(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9\-_]", "_", s)


def team_to_group_id(company_id: str, domain: str) -> str:
    """Multitenancy key: company_id__sanitized_domain."""
    return f"{company_id}__{_sanitize(domain)}"


def DepartmentEnum() -> type[Enum]:
    """Runtime Enum of allowed classification targets for the LLM classifier."""
    return Enum("DomainTarget", {t: t for t in CLASSIFICATION_TARGETS})


# ---------------------------------------------------------------------------
# Dynamic Pydantic entity models — one per unique NodeType
# ---------------------------------------------------------------------------
def _model_name(node_type: str) -> str:
    """'Opportunity / Deal' → 'Opportunity_Deal'"""
    return re.sub(r"[^a-zA-Z0-9]", "_", node_type).strip("_")


def _make_model(node_type: str) -> type[BaseModel]:
    domains = ", ".join(sorted(NODETYPE_TO_DOMAINS.get(node_type, set())))
    return create_model(
        _model_name(node_type),
        __base__=BaseModel,
        __doc__=f"Entity type: {node_type}. Appears in domains: {domains}.",
        description=(str | None, None),
    )


# Build ENTITY_TYPES dict: model_name → model class
ENTITY_TYPES: dict[str, type[BaseModel]] = {
    _model_name(nt): _make_model(nt)
    for nt in NODE_TYPES
}

# ---------------------------------------------------------------------------
# Edge types — generic, Graphiti infers specifics from content
# ---------------------------------------------------------------------------
class RELATES_TO(BaseModel):
    """Generic association between two entities."""

class BELONGS_TO(BaseModel):
    """Entity belongs to or is part of another entity."""

class INFLUENCES(BaseModel):
    """One entity influences or impacts another."""

class OWNS(BaseModel):
    """One entity owns or is responsible for another."""


EDGE_TYPES: dict[str, type[BaseModel]] = {
    "RELATES_TO":  RELATES_TO,
    "BELONGS_TO":  BELONGS_TO,
    "INFLUENCES":  INFLUENCES,
    "OWNS":        OWNS,
}

EDGE_TYPE_MAP: dict[tuple[str, str], list[str]] = {
    ("Entity", "Entity"): list(EDGE_TYPES.keys()),
}

# ---------------------------------------------------------------------------
# Legacy shim — PARENT_OF equivalent for ingest.py compatibility
# Maps domain → domain (since we're now single-level for classification)
# ---------------------------------------------------------------------------
PARENT_OF: dict[str, str] = {d: d for d in DOMAINS}