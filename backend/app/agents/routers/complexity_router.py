"""Complexity router for adaptive depth - routes queries to simple or complex paths."""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.adaptive_state import AdaptiveAgentState
from app.agents.utils import get_internal_llm_config
from app.config import logger


class ComplexityClassification(BaseModel):
    """LLM output for complexity classification."""
    path: Literal["simple", "complex"] = Field(
        description="Whether to use simple or complex analysis path"
    )
    reasoning: str = Field(
        description="Brief explanation of classification"
    )
    confidence: float = Field(
        ge=0, le=1,
        description="Confidence in classification"
    )


# Heuristic thresholds for fast classification
COMPLEXITY_THRESHOLDS = {
    "max_secondary_issues_for_simple": 1,
    "complexity_score_threshold": 0.4,
    "max_query_length_for_simple": 250,  # characters
}

# Simple query patterns (lowercase)
SIMPLE_QUERY_PATTERNS = [
    "what are my rights",
    "what is the law",
    "how do i",
    "can my landlord",
    "can my employer",
    "what is the",
    "how much notice",
    "am i entitled",
    "is it legal",
    "do i have to",
    "what happens if",
    "how long do i have",
]

# Complex query indicators (lowercase)
COMPLEX_QUERY_INDICATORS = [
    "dispute",
    "sued",
    "court",
    "tribunal",
    "lawyer",
    "legal action",
    "they're claiming",
    "i'm being",
    "unfair dismissal",
    "domestic violence",
    "child custody",
    "property settlement",
    "multiple",
    "complicated",
    "complex",
]


def classify_complexity_heuristic(
    state: AdaptiveAgentState
) -> Literal["simple", "complex", "uncertain"]:
    """
    Fast heuristic classification without LLM calls.

    Returns "uncertain" for borderline cases that need LLM classification.

    Args:
        state: Current agent state with query and issue classification

    Returns:
        "simple", "complex", or "uncertain"
    """
    query = state.get("current_query", "").lower()
    has_document = bool(state.get("uploaded_document_url"))
    issue_classification = state.get("issue_classification")

    # ===== DEFINITE COMPLEX INDICATORS =====

    # Document uploaded always needs full analysis
    if has_document:
        logger.debug("Complexity heuristic: COMPLEX (document uploaded)")
        return "complex"

    # Check issue classification if available
    if issue_classification:
        # Multiple secondary issues → complex
        secondary_count = len(issue_classification.get("secondary_issues", []))
        if secondary_count > COMPLEXITY_THRESHOLDS["max_secondary_issues_for_simple"]:
            logger.debug(f"Complexity heuristic: COMPLEX ({secondary_count} secondary issues)")
            return "complex"

        # High complexity score → complex
        complexity_score = issue_classification.get("complexity_score", 0)
        if complexity_score > COMPLEXITY_THRESHOLDS["complexity_score_threshold"]:
            logger.debug(f"Complexity heuristic: COMPLEX (score {complexity_score:.2f})")
            return "complex"

        # Multiple jurisdictions → complex
        if issue_classification.get("involves_multiple_jurisdictions"):
            logger.debug("Complexity heuristic: COMPLEX (multiple jurisdictions)")
            return "complex"

        # Document analysis recommended → complex
        if issue_classification.get("requires_document_analysis"):
            logger.debug("Complexity heuristic: COMPLEX (document analysis recommended)")
            return "complex"

    # Check for complex query indicators
    for indicator in COMPLEX_QUERY_INDICATORS:
        if indicator in query:
            logger.debug(f"Complexity heuristic: COMPLEX (indicator: '{indicator}')")
            return "complex"

    # ===== DEFINITE SIMPLE INDICATORS =====

    # Short queries matching simple patterns
    if len(query) < COMPLEXITY_THRESHOLDS["max_query_length_for_simple"]:
        for pattern in SIMPLE_QUERY_PATTERNS:
            if pattern in query:
                logger.debug(f"Complexity heuristic: SIMPLE (pattern: '{pattern}')")
                return "simple"

    # Low complexity score with no secondary issues
    if issue_classification:
        complexity_score = issue_classification.get("complexity_score", 0.5)
        secondary_count = len(issue_classification.get("secondary_issues", []))
        if complexity_score <= 0.3 and secondary_count == 0:
            logger.debug(f"Complexity heuristic: SIMPLE (low score {complexity_score:.2f}, no secondary)")
            return "simple"

    # ===== UNCERTAIN - NEEDS LLM =====
    logger.debug("Complexity heuristic: UNCERTAIN (needs LLM)")
    return "uncertain"


COMPLEXITY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You classify legal queries as either "simple" or "complex" for analysis depth.

## SIMPLE Path (quick response, ~3k tokens)
Use for:
- Single, clear legal question
- General rights/information requests
- One party relationship (tenant-landlord, employee-employer)
- Common, well-documented issues
- No documents to analyze
- No time-sensitive deadlines

Examples:
- "What notice period does my landlord need to give for rent increase?"
- "Can my employer make me work overtime?"
- "What are my rights if a product is faulty?"

## COMPLEX Path (full analysis, ~9k tokens)
Use for:
- Multiple interrelated legal issues
- Disputes with unclear or contested facts
- Multiple parties involved
- Documents requiring detailed analysis
- Potential litigation or formal processes
- Time-sensitive matters with deadlines
- Emotionally charged situations (family, employment termination)
- Matters with significant financial/personal consequences

Examples:
- "My landlord is trying to evict me and I think it's retaliation for complaining about repairs"
- "I was made redundant but I think it was actually unfair dismissal because of my pregnancy"
- "My ex won't let me see my kids and I need to understand my options"

## Current Query Context

Query: {query}
Issue classification: {issue_summary}
Has uploaded document: {has_document}
Complexity score from classification: {complexity_score}

Choose the appropriate path and explain briefly."""),
    ("human", "Classify this legal query as simple or complex.")
])


class ComplexityRouter:
    """Routes queries to simple or complex analysis paths."""

    def __init__(self):
        # Use GPT-4o-mini for cost efficiency
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.chain = COMPLEXITY_PROMPT | self.llm.with_structured_output(
            ComplexityClassification
        )

    async def classify(
        self,
        state: AdaptiveAgentState,
        config: Optional[RunnableConfig] = None,
    ) -> Literal["simple", "complex"]:
        """
        Classify query complexity using heuristics first, LLM for uncertain cases.

        Args:
            state: Current agent state with query and issue classification
            config: LangGraph config to customize for internal LLM calls

        Returns:
            "simple" or "complex"
        """
        # Try heuristics first (fast, no API cost)
        heuristic_result = classify_complexity_heuristic(state)

        if heuristic_result != "uncertain":
            logger.info(f"Complexity classification: {heuristic_result} (heuristic)")
            return heuristic_result

        # Use LLM for uncertain cases
        try:
            issue_classification = state.get("issue_classification")
            issue_summary = "Not classified"
            complexity_score = "Unknown"

            if issue_classification:
                primary = issue_classification.get("primary_issue", {})
                secondary_count = len(issue_classification.get("secondary_issues", []))
                issue_summary = (
                    f"Primary: {primary.get('area', 'unknown')} - "
                    f"{primary.get('sub_category', 'unknown')}. "
                    f"Secondary issues: {secondary_count}"
                )
                complexity_score = str(issue_classification.get("complexity_score", "Unknown"))

            # Use internal config to prevent streaming JSON to frontend
            internal_config = get_internal_llm_config(config)
            result = await self.chain.ainvoke(
                {
                    "query": state.get("current_query", ""),
                    "issue_summary": issue_summary,
                    "has_document": "Yes" if state.get("uploaded_document_url") else "No",
                    "complexity_score": complexity_score,
                },
                config=internal_config,
            )

            logger.info(
                f"Complexity classification: {result.path} "
                f"(LLM, confidence: {result.confidence:.2f}, reason: {result.reasoning})"
            )
            return result.path

        except Exception as e:
            logger.error(f"Complexity router LLM error: {e}")
            # Default to simple on error to avoid over-processing
            return "simple"


# Singleton instance
_complexity_router: ComplexityRouter | None = None


def get_complexity_router() -> ComplexityRouter:
    """Get or create the singleton ComplexityRouter instance."""
    global _complexity_router
    if _complexity_router is None:
        _complexity_router = ComplexityRouter()
    return _complexity_router


async def route_by_complexity(
    state: AdaptiveAgentState,
    config: Optional[RunnableConfig] = None,
) -> Literal["simple", "complex"]:
    """
    Route to simple or complex path based on complexity analysis.

    This is the main entry point for complexity-based routing.

    Args:
        state: Current agent state
        config: LangGraph config to customize for internal LLM calls

    Returns:
        "simple" or "complex"
    """
    router = get_complexity_router()
    return await router.classify(state, config)
