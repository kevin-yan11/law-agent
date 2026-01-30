"""Fact organizer - extracts and structures facts from conversation history."""

from typing import Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, ConfigDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.utils import get_internal_llm_config
from app.config import logger


class TimelineEvent(TypedDict):
    """A single event in the timeline."""
    date: Optional[str]
    description: str
    significance: str  # critical, relevant, background


class Party(TypedDict):
    """A party involved in the matter."""
    role: str
    name: Optional[str]
    is_user: bool


class Evidence(TypedDict):
    """An evidence item."""
    type: str  # document, witness, communication, physical
    description: str
    status: str  # available, mentioned, needed
    strength: str  # strong, moderate, weak


class FactSummary(TypedDict):
    """Organized facts from conversation."""
    timeline: list[TimelineEvent]
    parties: list[Party]
    evidence: list[Evidence]
    key_facts: list[str]
    fact_gaps: list[str]
    narrative: str


# Pydantic models for OpenAI structured output (require additionalProperties: false)
class TimelineEventModel(BaseModel):
    """A single event in the timeline."""
    model_config = ConfigDict(extra="forbid")

    date: Optional[str] = Field(default=None, description="Date or relative time")
    description: str = Field(description="What happened")
    significance: str = Field(description="critical, relevant, or background")


class PartyModel(BaseModel):
    """A party involved in the matter."""
    model_config = ConfigDict(extra="forbid")

    role: str = Field(description="Role in the matter (tenant, landlord, etc.)")
    name: Optional[str] = Field(default=None, description="Name if known")
    is_user: bool = Field(description="Whether this party is the user")


class EvidenceModel(BaseModel):
    """An evidence item."""
    model_config = ConfigDict(extra="forbid")

    type: str = Field(description="document, witness, communication, or physical")
    description: str = Field(description="Description of the evidence")
    status: str = Field(description="available, mentioned, or needed")
    strength: str = Field(description="strong, moderate, or weak")


class FactOrganizationOutput(BaseModel):
    """LLM output for fact organization."""
    model_config = ConfigDict(extra="forbid")

    timeline: list[TimelineEventModel] = Field(
        default_factory=list,
        description="Chronological events with date, description, and significance"
    )
    parties: list[PartyModel] = Field(
        default_factory=list,
        description="Parties involved with role, name (if known), and is_user flag"
    )
    evidence: list[EvidenceModel] = Field(
        default_factory=list,
        description="Evidence items with type, description, status, and strength"
    )
    key_facts: list[str] = Field(
        default_factory=list,
        description="Most important factual points (3-7 items)"
    )
    fact_gaps: list[str] = Field(
        default_factory=list,
        description="Information we don't have but would be helpful"
    )
    narrative: str = Field(
        description="A 2-3 sentence plain language summary of the situation"
    )


FACT_ORGANIZATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are organizing facts from a legal conversation to help with case analysis.

## Your Task

Extract and organize all relevant facts from the conversation into:

1. **Timeline**: Events in chronological order
   - Include dates (exact or relative like "2 weeks ago")
   - Mark significance: critical (directly affects legal rights), relevant (important context), background (helpful but not central)

2. **Parties**: Everyone involved
   - Their role (tenant, landlord, employer, employee, etc.)
   - Name if mentioned
   - Whether they are the user

3. **Evidence**: Documents and proof mentioned
   - Type: document, witness, communication, physical
   - Status: available (user has it), mentioned (unclear if they have it), needed (would help but not mentioned)
   - Strength: strong, moderate, weak

4. **Key Facts**: The most legally relevant facts (3-7 bullet points)

5. **Fact Gaps**: Information that would help but we don't have

6. **Narrative**: A clear 2-3 sentence summary in plain language

## User Context
- State/Territory: {user_state}
- Has uploaded document: {has_document}

## Conversation History
{conversation}

Be thorough but only include facts actually stated or clearly implied."""),
    ("human", "Organize the facts from this conversation.")
])


async def organize_facts(
    messages: list[BaseMessage],
    user_state: Optional[str] = None,
    has_document: bool = False,
    config: Optional[RunnableConfig] = None,
) -> FactSummary:
    """
    Organize facts from conversation history.

    Args:
        messages: Conversation message history
        user_state: User's Australian state/territory
        has_document: Whether user has uploaded a document
        config: LangGraph config for LLM calls

    Returns:
        FactSummary with organized timeline, parties, evidence, etc.
    """
    try:
        # Format conversation for the prompt
        conversation = _format_conversation(messages)

        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        chain = FACT_ORGANIZATION_PROMPT | llm.with_structured_output(FactOrganizationOutput)

        # Use internal config to prevent streaming
        internal_config = get_internal_llm_config(config)

        result = await chain.ainvoke(
            {
                "conversation": conversation,
                "user_state": user_state or "Not specified",
                "has_document": "Yes" if has_document else "No",
            },
            config=internal_config,
        )

        # Convert to TypedDict format
        fact_summary: FactSummary = {
            "timeline": [
                {
                    "date": e.date,
                    "description": e.description,
                    "significance": e.significance,
                }
                for e in result.timeline
            ],
            "parties": [
                {
                    "role": p.role,
                    "name": p.name,
                    "is_user": p.is_user,
                }
                for p in result.parties
            ],
            "evidence": [
                {
                    "type": ev.type,
                    "description": ev.description,
                    "status": ev.status,
                    "strength": ev.strength,
                }
                for ev in result.evidence
            ],
            "key_facts": result.key_facts,
            "fact_gaps": result.fact_gaps,
            "narrative": result.narrative,
        }

        logger.info(
            f"Facts organized: {len(fact_summary['timeline'])} events, "
            f"{len(fact_summary['parties'])} parties, "
            f"{len(fact_summary['evidence'])} evidence items"
        )

        return fact_summary

    except Exception as e:
        logger.error(f"Fact organization error: {e}")
        return {
            "timeline": [],
            "parties": [{"role": "user", "name": None, "is_user": True}],
            "evidence": [],
            "key_facts": ["Unable to extract facts from conversation"],
            "fact_gaps": ["Complete situation details needed"],
            "narrative": "Unable to organize facts from the conversation.",
        }


def _format_conversation(messages: list[BaseMessage]) -> str:
    """Format messages into a readable conversation string."""
    parts = []
    for msg in messages:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        content = msg.content if hasattr(msg, 'content') else str(msg)
        # Truncate very long messages
        if len(content) > 1000:
            content = content[:1000] + "..."
        parts.append(f"{role}: {content}")
    return "\n\n".join(parts)
