"""Shared state definition for all LangGraph sub-graphs."""

from typing import TypedDict, Optional, Literal, Annotated
from langchain_core.messages import BaseMessage
import operator


class ChecklistStep(TypedDict):
    """A single step in an action checklist."""
    order: int
    title: str
    description: str
    action_type: Literal["info", "upload", "external_link", "wait"]
    status: Literal["pending", "in_progress", "completed", "skipped"]
    details: Optional[str]


class ResearchResult(TypedDict):
    """Output from research sub-graph."""
    answer: str
    citations: list[dict]  # [{source, section, snippet}]


class AusLawState(TypedDict):
    """Main state shared across all sub-graphs."""

    # Session info
    session_id: str
    user_state: Optional[str]  # "VIC", "NSW", "QLD", etc.

    # Conversation
    messages: Annotated[list[BaseMessage], operator.add]
    current_query: str

    # Routing
    intent: Optional[Literal["research", "action", "match", "clarify", "general"]]

    # Research branch outputs
    research_result: Optional[ResearchResult]

    # Action branch outputs
    active_template_id: Optional[str]
    checklist: Optional[list[ChecklistStep]]
    current_step_index: int

    # Control flow
    error: Optional[str]
