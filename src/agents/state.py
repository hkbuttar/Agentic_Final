"""Shared state schema threaded through the LangGraph graph: transcript ->
intent (Router) -> plan (Planner) -> evidence (Retriever) -> answer +
citations (Answerer/Critic). See README.md's System Architecture table.
"""
from typing import Optional, TypedDict


class Constraints(TypedDict):
    max_price: Optional[float]
    brand: Optional[str]
    material: Optional[str]


class Intent(TypedDict):
    task: str
    constraints: Constraints
    category: Optional[str]  # one of the catalog's known top-level categories, or None
    wants_live_data: bool
    safety_flags: list[str]


class Plan(TypedDict):
    sources: list[str]  # subset of ["private", "live"]
    fields: list[str]
    criteria: list[str]


class Citation(TypedDict):
    title: str
    doc_id: Optional[str]
    url: Optional[str]


class AgentState(TypedDict, total=False):
    transcript: str
    intent: Intent
    plan: Plan
    evidence: list[dict]
    answer: str
    citations: list[Citation]
    trace: list[str]  # human-readable step log, surfaced in the UI's agent step log
