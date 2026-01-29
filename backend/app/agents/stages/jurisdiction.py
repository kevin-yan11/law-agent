"""Stage 2: Jurisdiction Resolution - Determines applicable laws and forums."""

from typing import Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.adaptive_state import AdaptiveAgentState, JurisdictionResult
from app.agents.utils import get_internal_llm_config
from app.config import logger


# Legal areas that are primarily federal
FEDERAL_AREAS = {
    "employment": ["unfair_dismissal", "redundancy", "general_protections", "workplace_rights"],
    "family": ["divorce", "child_custody", "child_support", "property_settlement"],
    "immigration": True,  # All immigration is federal
    "consumer": ["accc", "competition", "consumer_guarantees"],
}

# Legal areas that are primarily state-based
STATE_AREAS = {
    "tenancy": True,  # All tenancy is state
    "property": ["boundary_disputes", "strata", "conveyancing"],
    "criminal": ["state_offences", "traffic"],
    "wills_estates": True,  # Primarily state
}

# Supported jurisdictions with RAG data
SUPPORTED_RAG_JURISDICTIONS = ["NSW", "QLD", "FEDERAL"]

# All Australian jurisdictions
ALL_JURISDICTIONS = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT", "FEDERAL"]


class JurisdictionOutput(BaseModel):
    """LLM output for jurisdiction resolution."""
    primary_jurisdiction: str = Field(
        description="Primary applicable jurisdiction: NSW, VIC, QLD, SA, WA, TAS, NT, ACT, or FEDERAL"
    )
    applicable_jurisdictions: list[str] = Field(
        default_factory=list,
        description="All jurisdictions that may apply"
    )
    jurisdiction_conflicts: list[str] = Field(
        default_factory=list,
        description="Any conflicts or complexities in jurisdiction"
    )
    reasoning: str = Field(
        description="Explanation of jurisdiction determination"
    )


JURISDICTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Australian legal jurisdiction specialist. Determine which jurisdiction(s) apply to the legal matter.

## Australian Legal System Overview

**Federal Law** applies across all of Australia for:
- Employment (Fair Work Act) - unfair dismissal, redundancy, workplace rights
- Family law (Family Law Act) - divorce, custody, property settlement
- Immigration and citizenship
- Consumer law (Australian Consumer Law) - consumer guarantees
- Corporations law
- Taxation

**State/Territory Law** applies within each state for:
- Tenancy/residential leases (each state has its own Residential Tenancies Act)
- Property and conveyancing
- State criminal offences
- Wills and estates (primarily)
- Local government matters

## Key Legislation by Area

**Tenancy** (State-based):
- NSW: Residential Tenancies Act 2010 (NSW)
- VIC: Residential Tenancies Act 1997 (Vic)
- QLD: Residential Tenancies and Rooming Accommodation Act 2008 (Qld)

**Employment** (Federal):
- Fair Work Act 2009 (Cth)
- Fair Work Regulations

**Family** (Federal):
- Family Law Act 1975 (Cth)

## Current Query Context

User's stated location: {user_state}
Primary legal area: {legal_area}
Sub-category: {sub_category}
Query: {query}

Determine the applicable jurisdiction(s)."""),
    ("human", "What jurisdiction(s) apply to this legal matter?")
])


class JurisdictionResolver:
    """Resolves applicable jurisdictions for legal matters."""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.chain = JURISDICTION_PROMPT | self.llm.with_structured_output(JurisdictionOutput)

    def _quick_resolve(
        self,
        legal_area: str,
        sub_category: str,
        user_state: str | None
    ) -> JurisdictionResult | None:
        """
        Attempt quick resolution without LLM for clear-cut cases.

        Returns None if LLM resolution is needed.
        """
        # Normalize inputs
        area_lower = legal_area.lower()
        sub_lower = sub_category.lower() if sub_category else ""
        state = user_state or "NSW"  # Default to NSW if not specified

        # Check if area is purely federal
        if area_lower in FEDERAL_AREAS:
            federal_rule = FEDERAL_AREAS[area_lower]
            if federal_rule is True or (isinstance(federal_rule, list) and any(s in sub_lower for s in federal_rule)):
                return {
                    "primary_jurisdiction": "FEDERAL",
                    "applicable_jurisdictions": ["FEDERAL", state],
                    "jurisdiction_conflicts": [],
                    "fallback_to_federal": False,
                    "reasoning": f"{legal_area} matters are governed by federal law",
                }

        # Check if area is purely state-based
        if area_lower in STATE_AREAS:
            state_rule = STATE_AREAS[area_lower]
            if state_rule is True or (isinstance(state_rule, list) and any(s in sub_lower for s in state_rule)):
                # Check if we have RAG data for this state
                fallback = state not in SUPPORTED_RAG_JURISDICTIONS
                applicable = [state]
                if fallback:
                    applicable.append("FEDERAL")

                return {
                    "primary_jurisdiction": state,
                    "applicable_jurisdictions": applicable,
                    "jurisdiction_conflicts": [],
                    "fallback_to_federal": fallback,
                    "reasoning": f"{legal_area} matters are governed by {state} state law",
                }

        # Need LLM for complex cases
        return None

    async def resolve(
        self,
        state: AdaptiveAgentState,
        config: Optional[RunnableConfig] = None,
    ) -> JurisdictionResult:
        """
        Resolve applicable jurisdictions for the legal matter.

        Args:
            state: Current agent state with query and issue classification
            config: LangGraph config to customize for internal LLM calls

        Returns:
            JurisdictionResult with applicable jurisdictions
        """
        user_state = state.get("user_state")
        issue_classification = state.get("issue_classification", {})
        primary_issue = issue_classification.get("primary_issue", {})
        legal_area = primary_issue.get("area", "other")
        sub_category = primary_issue.get("sub_category", "")

        # Try quick resolution first
        quick_result = self._quick_resolve(legal_area, sub_category, user_state)
        if quick_result:
            logger.info(
                f"Jurisdiction resolved (quick): {quick_result['primary_jurisdiction']} "
                f"(fallback: {quick_result['fallback_to_federal']})"
            )
            return quick_result

        # Use LLM for complex cases
        try:
            # Use internal config to prevent streaming JSON to frontend
            internal_config = get_internal_llm_config(config)
            result = await self.chain.ainvoke(
                {
                    "user_state": user_state or "Not specified",
                    "legal_area": legal_area,
                    "sub_category": sub_category,
                    "query": state.get("current_query", ""),
                },
                config=internal_config,
            )

            # Validate and normalize jurisdiction
            primary = result.primary_jurisdiction.upper()
            if primary not in ALL_JURISDICTIONS:
                primary = user_state or "NSW"

            # Check if we need to fallback to federal
            fallback = primary not in SUPPORTED_RAG_JURISDICTIONS and primary != "FEDERAL"

            jurisdiction_result: JurisdictionResult = {
                "primary_jurisdiction": primary,
                "applicable_jurisdictions": [j.upper() for j in result.applicable_jurisdictions] or [primary],
                "jurisdiction_conflicts": result.jurisdiction_conflicts,
                "fallback_to_federal": fallback,
                "reasoning": result.reasoning,
            }

            logger.info(
                f"Jurisdiction resolved (LLM): {primary} "
                f"(fallback: {fallback}, conflicts: {len(result.jurisdiction_conflicts)})"
            )

            return jurisdiction_result

        except Exception as e:
            logger.error(f"Jurisdiction resolution error: {e}")
            # Default to user's state or NSW
            default_state = user_state or "NSW"
            return {
                "primary_jurisdiction": default_state,
                "applicable_jurisdictions": [default_state, "FEDERAL"],
                "jurisdiction_conflicts": [],
                "fallback_to_federal": default_state not in SUPPORTED_RAG_JURISDICTIONS,
                "reasoning": f"Defaulting to {default_state} due to resolution error",
            }


# Singleton instance
_jurisdiction_resolver: JurisdictionResolver | None = None


def get_jurisdiction_resolver() -> JurisdictionResolver:
    """Get or create the singleton JurisdictionResolver instance."""
    global _jurisdiction_resolver
    if _jurisdiction_resolver is None:
        _jurisdiction_resolver = JurisdictionResolver()
    return _jurisdiction_resolver


async def jurisdiction_node(state: AdaptiveAgentState, config: RunnableConfig) -> dict:
    """
    Stage 2: Jurisdiction resolution node.

    Determines which Australian jurisdiction(s) apply to the legal matter.
    This affects which legislation will be searched in RAG.

    Args:
        state: Current agent state
        config: LangGraph config for controlling LLM streaming

    Returns:
        dict with jurisdiction_result and updated stage tracking
    """
    logger.info("Stage 2: Jurisdiction Resolution")

    resolver = get_jurisdiction_resolver()
    jurisdiction_result = await resolver.resolve(state, config)

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("jurisdiction")

    return {
        "jurisdiction_result": jurisdiction_result,
        "current_stage": "jurisdiction",
        "stages_completed": stages_completed,
    }
