"""Stage 3: Fact Structuring - Extracts timeline, parties, and evidence from user queries."""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.adaptive_state import (
    AdaptiveAgentState,
    FactStructure,
    TimelineEvent,
    Party,
    Evidence,
)
from app.agents.utils import get_internal_llm_config
from app.config import logger


class TimelineEventOutput(BaseModel):
    """A single event in the timeline."""
    date: Optional[str] = Field(
        default=None,
        description="Date in ISO format (YYYY-MM-DD) or relative description (e.g., '2 weeks ago', 'last month')"
    )
    description: str = Field(description="What happened")
    significance: Literal["critical", "relevant", "background"] = Field(
        description="How important is this event to the legal matter"
    )
    source: Literal["user_stated", "document", "inferred"] = Field(
        default="user_stated",
        description="Where this information came from"
    )


class PartyOutput(BaseModel):
    """A party involved in the legal matter."""
    role: str = Field(description="Role in the matter: tenant, landlord, employer, employee, etc.")
    name: Optional[str] = Field(default=None, description="Name if mentioned")
    is_user: bool = Field(description="Whether this party is the user")
    relationship_to_user: Optional[str] = Field(
        default=None,
        description="How they relate to the user: employer, landlord, ex-spouse, etc."
    )


class EvidenceOutput(BaseModel):
    """An evidence item."""
    type: Literal["document", "witness", "communication", "physical"] = Field(
        description="Type of evidence"
    )
    description: str = Field(description="What the evidence is")
    status: Literal["available", "mentioned", "needed"] = Field(
        description="Whether user has it, mentioned it, or it's needed"
    )
    strength: Literal["strong", "moderate", "weak"] = Field(
        description="How strong this evidence would be"
    )


class FactStructuringOutput(BaseModel):
    """LLM output for fact structuring."""
    timeline: list[TimelineEventOutput] = Field(
        default_factory=list,
        description="Chronological events relevant to the matter"
    )
    parties: list[PartyOutput] = Field(
        default_factory=list,
        description="All parties involved in the matter"
    )
    evidence: list[EvidenceOutput] = Field(
        default_factory=list,
        description="Evidence items available, mentioned, or needed"
    )
    key_facts: list[str] = Field(
        default_factory=list,
        description="Most important factual points (3-7 items)"
    )
    fact_gaps: list[str] = Field(
        default_factory=list,
        description="Information we still need to give proper advice"
    )
    narrative_summary: str = Field(
        description="A 2-3 sentence summary of the situation in plain language"
    )


FACT_STRUCTURING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a legal fact analyst for Australian legal matters. Your task is to extract and structure facts from user queries to support legal analysis.

## Your Goals

1. **Timeline**: Extract chronological events with dates (exact or relative)
2. **Parties**: Identify all people/entities involved and their roles
3. **Evidence**: Catalog what evidence exists, is mentioned, or would be needed
4. **Key Facts**: Summarize the most legally relevant facts
5. **Fact Gaps**: Identify what information is missing for proper legal analysis
6. **Narrative**: Create a clear, factual summary

## Guidelines

### Timeline Events
- Mark significance as:
  - **critical**: Events that directly affect legal rights (signing lease, termination, incident)
  - **relevant**: Events that provide important context (complaints made, responses received)
  - **background**: Events that help understand the situation but aren't legally central

### Parties
- Always include the user as a party with is_user=true
- Identify their legal role (tenant, employee, buyer, etc.)
- Include any other party mentioned (landlord, employer, company, agency, etc.)
- Note relationships between parties

### Evidence
- **document**: Leases, contracts, emails, letters, receipts, photos
- **witness**: People who can corroborate facts
- **communication**: Text messages, call logs, recorded conversations
- **physical**: Objects, property damage, items in dispute

Status:
- **available**: User explicitly has this evidence
- **mentioned**: User referred to it but unclear if they have it
- **needed**: Evidence that would strengthen their case but wasn't mentioned

### Fact Gaps
Think like a lawyer preparing for a case:
- What dates are unclear?
- What amounts are uncertain?
- What was the other party's position?
- What documentation exists?
- What witnesses might exist?

## Current Context

User's query: {query}
Legal area identified: {legal_area}
Sub-category: {sub_category}
User's state/territory: {user_state}
Document uploaded: {has_document}

## Additional Context from Issue Analysis
{issue_context}
"""),
    ("human", "Extract and structure the facts from this legal query. Be thorough but only include facts actually stated or clearly implied.")
])


class FactStructurer:
    """Extracts and structures facts from user queries."""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.chain = FACT_STRUCTURING_PROMPT | self.llm.with_structured_output(
            FactStructuringOutput
        )

    async def structure_facts(
        self,
        state: AdaptiveAgentState,
        config: Optional[RunnableConfig] = None,
    ) -> FactStructure:
        """
        Extract and structure facts from the user's query.

        Args:
            state: Current agent state with query and issue classification
            config: LangGraph config to customize for internal LLM calls

        Returns:
            FactStructure with timeline, parties, evidence, key facts, and gaps
        """
        try:
            # Get issue classification for context
            issue = state.get("issue_classification", {})
            primary = issue.get("primary_issue", {})
            secondary = issue.get("secondary_issues", [])

            # Build issue context string
            issue_context_parts = []
            if primary:
                issue_context_parts.append(
                    f"Primary issue: {primary.get('area', 'unknown')} - {primary.get('description', 'N/A')}"
                )
            if secondary:
                for sec in secondary:
                    issue_context_parts.append(
                        f"Secondary issue: {sec.get('area', 'unknown')} - {sec.get('description', 'N/A')}"
                    )
            issue_context = "\n".join(issue_context_parts) if issue_context_parts else "No prior classification"

            # Use internal config to prevent streaming JSON to frontend
            internal_config = get_internal_llm_config(config)
            result = await self.chain.ainvoke(
                {
                    "query": state.get("current_query", ""),
                    "legal_area": primary.get("area", "unknown"),
                    "sub_category": primary.get("sub_category", "general"),
                    "user_state": state.get("user_state") or "Unknown",
                    "has_document": "Yes" if state.get("uploaded_document_url") else "No",
                    "issue_context": issue_context,
                },
                config=internal_config,
            )

            # Convert Pydantic models to TypedDicts
            timeline: list[TimelineEvent] = [
                {
                    "date": event.date,
                    "description": event.description,
                    "significance": event.significance,
                    "source": event.source,
                }
                for event in result.timeline
            ]

            parties: list[Party] = [
                {
                    "role": party.role,
                    "name": party.name,
                    "is_user": party.is_user,
                    "relationship_to_user": party.relationship_to_user,
                }
                for party in result.parties
            ]

            evidence: list[Evidence] = [
                {
                    "type": ev.type,
                    "description": ev.description,
                    "status": ev.status,
                    "strength": ev.strength,
                }
                for ev in result.evidence
            ]

            fact_structure: FactStructure = {
                "timeline": timeline,
                "parties": parties,
                "evidence": evidence,
                "key_facts": result.key_facts,
                "fact_gaps": result.fact_gaps,
                "narrative_summary": result.narrative_summary,
            }

            logger.info(
                f"Facts structured: {len(timeline)} events, {len(parties)} parties, "
                f"{len(evidence)} evidence items, {len(result.fact_gaps)} gaps identified"
            )

            return fact_structure

        except Exception as e:
            logger.error(f"Fact structuring error: {e}")
            # Return minimal fact structure on error
            return {
                "timeline": [],
                "parties": [{
                    "role": "user",
                    "name": None,
                    "is_user": True,
                    "relationship_to_user": None,
                }],
                "evidence": [],
                "key_facts": ["Unable to extract facts from query"],
                "fact_gaps": ["Complete situation details needed"],
                "narrative_summary": "Unable to structure facts from the provided information.",
            }


# Singleton instance
_fact_structurer: FactStructurer | None = None


def get_fact_structurer() -> FactStructurer:
    """Get or create the singleton FactStructurer instance."""
    global _fact_structurer
    if _fact_structurer is None:
        _fact_structurer = FactStructurer()
    return _fact_structurer


async def fact_structuring_node(state: AdaptiveAgentState, config: RunnableConfig) -> dict:
    """
    Stage 3: Fact structuring node.

    Extracts timeline, parties, evidence, and key facts from the user's query.
    Identifies information gaps that would be needed for complete legal analysis.

    This stage runs only on the COMPLEX path, after issue identification and
    jurisdiction resolution.

    Args:
        state: Current agent state
        config: LangGraph config for controlling LLM streaming

    Returns:
        dict with fact_structure and updated stage tracking
    """
    logger.info("Stage 3: Fact Structuring")

    structurer = get_fact_structurer()
    fact_structure = await structurer.structure_facts(state, config)

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("fact_structuring")

    return {
        "fact_structure": fact_structure,
        "current_stage": "fact_structuring",
        "stages_completed": stages_completed,
    }
