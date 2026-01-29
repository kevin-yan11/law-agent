"""Stage 5: Case Precedent - Identifies relevant case law and outcome patterns."""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.adaptive_state import (
    AdaptiveAgentState,
    PrecedentAnalysis,
    CasePrecedent,
)
from app.agents.schemas.case_precedents import (
    search_cases_by_keywords,
    get_cases_by_subcategory,
    MockCase,
)
from app.agents.utils import get_internal_llm_config
from app.config import logger


class CasePrecedentOutput(BaseModel):
    """LLM output for a single case precedent analysis."""
    case_name: str = Field(description="Name of the case")
    citation: str = Field(description="Legal citation")
    year: int = Field(description="Year of decision")
    jurisdiction: str = Field(description="Jurisdiction (NSW, QLD, FEDERAL, etc.)")
    relevance_score: float = Field(ge=0, le=1, description="How relevant to current matter (0-1)")
    key_holding: str = Field(description="The main legal principle from this case")
    how_it_applies: str = Field(description="How this case applies to the current situation")
    outcome_for_similar_party: Literal["favorable", "unfavorable", "mixed"] = Field(
        description="Whether the outcome was favorable for a party in similar position to user"
    )


class PrecedentAnalysisOutput(BaseModel):
    """LLM output for precedent analysis."""
    analyzed_cases: list[CasePrecedentOutput] = Field(
        default_factory=list,
        description="Cases analyzed for relevance"
    )
    pattern_identified: str | None = Field(
        default=None,
        description="Pattern in how similar cases are typically decided"
    )
    typical_outcome: str | None = Field(
        default=None,
        description="What usually happens in similar cases"
    )
    distinguishing_factors: list[str] = Field(
        default_factory=list,
        description="Factors that could distinguish this case from precedents (for better or worse)"
    )


CASE_PRECEDENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Australian legal researcher analyzing case precedents for relevance to a current matter.

## Your Task

Given a set of potentially relevant cases and the current matter's facts, analyze:
1. How relevant each case is to the current situation
2. What legal principles from each case apply
3. Whether outcomes favor parties in similar positions to the user
4. What patterns emerge across similar cases
5. What factors might distinguish this case from precedents

## Analysis Guidelines

### Relevance Scoring (0-1)
- **0.8-1.0**: Nearly identical facts and legal issues
- **0.6-0.8**: Same legal area with similar key issues
- **0.4-0.6**: Related legal principles, different specific facts
- **0.2-0.4**: Tangentially related, limited applicability
- **0.0-0.2**: Minimal relevance

### Outcome Assessment
- **favorable**: The party in similar position to user won/got favorable outcome
- **unfavorable**: The party in similar position to user lost/got unfavorable outcome
- **mixed**: Split decision or partial success

### Distinguishing Factors
Consider what makes the current case different:
- Stronger or weaker evidence
- Different timeline or urgency
- Additional parties or complications
- Jurisdictional differences
- More recent legislative changes

## Current Matter Context

**Legal Area:** {legal_area}
**Sub-category:** {sub_category}
**Jurisdiction:** {jurisdiction}

**Key Facts:**
{key_facts}

**Elements Analysis Summary:**
{elements_summary}

## Candidate Cases to Analyze

{cases_text}
"""),
    ("human", "Analyze these cases for relevance to the current matter and identify any patterns in outcomes.")
])


class CasePrecedentAnalyzer:
    """Analyzes case precedents for relevance to current matter."""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.chain = CASE_PRECEDENT_PROMPT | self.llm.with_structured_output(
            PrecedentAnalysisOutput
        )

    def _extract_keywords_from_state(self, state: AdaptiveAgentState) -> list[str]:
        """Extract relevant keywords from the state for case search."""
        keywords = []

        # From issue classification
        issue = state.get("issue_classification", {})
        primary = issue.get("primary_issue", {})
        if primary.get("sub_category"):
            # Convert sub_category to keywords (e.g., "bond_refund" -> ["bond", "refund"])
            keywords.extend(primary["sub_category"].replace("_", " ").split())

        # From fact structure
        fact_structure = state.get("fact_structure", {})
        key_facts = fact_structure.get("key_facts", [])
        for fact in key_facts[:5]:  # Limit to avoid too many keywords
            # Extract significant words (simple approach)
            words = fact.lower().split()
            keywords.extend([w for w in words if len(w) > 4])

        # From elements analysis
        elements = state.get("elements_analysis", {})
        for elem in elements.get("elements", [])[:3]:
            if elem.get("element_name"):
                keywords.extend(elem["element_name"].lower().split())

        # Deduplicate and limit
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen and len(kw) > 3:
                seen.add(kw)
                unique_keywords.append(kw)
                if len(unique_keywords) >= 10:
                    break

        return unique_keywords

    def _format_cases_for_prompt(self, cases: list[MockCase]) -> str:
        """Format mock cases into prompt text."""
        if not cases:
            return "No directly matching cases found in database."

        parts = []
        for i, case in enumerate(cases, 1):
            parts.append(f"""
**Case {i}: {case['case_name']}**
- Citation: {case['citation']}
- Year: {case['year']}
- Jurisdiction: {case['jurisdiction']}
- Key Facts: {case['key_facts']}
- Key Holding: {case['key_holding']}
- Outcome: {case['outcome']}
""")
        return "\n".join(parts)

    def _format_elements_summary(self, state: AdaptiveAgentState) -> str:
        """Format elements analysis into summary."""
        elements = state.get("elements_analysis", {})
        if not elements:
            return "No elements analysis available."

        parts = [
            f"Applicable Law: {elements.get('applicable_law', 'Unknown')}",
            f"Viability: {elements.get('viability_assessment', 'Unknown')}",
            f"Elements Satisfied: {elements.get('elements_satisfied', 0)}/{elements.get('elements_total', 0)}",
        ]

        for elem in elements.get("elements", [])[:4]:
            status = elem.get("is_satisfied", "unknown")
            parts.append(f"- {elem.get('element_name', 'Unknown')}: {status}")

        return "\n".join(parts)

    async def analyze_precedents(
        self,
        state: AdaptiveAgentState,
        config: Optional[RunnableConfig] = None,
    ) -> PrecedentAnalysis:
        """
        Analyze relevant case precedents for the current matter.

        Args:
            state: Current agent state with issue, facts, and elements analysis
            config: LangGraph config to customize for internal LLM calls

        Returns:
            PrecedentAnalysis with matching cases and outcome patterns
        """
        try:
            # Get context
            issue = state.get("issue_classification", {})
            primary = issue.get("primary_issue", {})
            legal_area = primary.get("area", "unknown")
            sub_category = primary.get("sub_category", "general")

            jurisdiction = state.get("jurisdiction_result", {})
            primary_jurisdiction = jurisdiction.get("primary_jurisdiction", "FEDERAL")

            fact_structure = state.get("fact_structure", {})
            key_facts = fact_structure.get("key_facts", [])

            # Search for relevant cases
            # First try exact subcategory match
            cases = get_cases_by_subcategory(legal_area, sub_category)

            # If not enough, search by keywords
            if len(cases) < 3:
                keywords = self._extract_keywords_from_state(state)
                keyword_cases = search_cases_by_keywords(keywords, legal_area)
                # Add any cases not already included
                existing_names = {c["case_name"] for c in cases}
                for kc in keyword_cases:
                    if kc["case_name"] not in existing_names:
                        cases.append(kc)
                        if len(cases) >= 5:
                            break

            # Format for prompt
            cases_text = self._format_cases_for_prompt(cases[:5])  # Limit to 5 cases
            elements_summary = self._format_elements_summary(state)
            key_facts_str = "\n".join(f"- {f}" for f in key_facts) if key_facts else "No key facts identified"

            # Use internal config to prevent streaming JSON to frontend
            internal_config = get_internal_llm_config(config)
            result = await self.chain.ainvoke(
                {
                    "legal_area": legal_area,
                    "sub_category": sub_category,
                    "jurisdiction": primary_jurisdiction,
                    "key_facts": key_facts_str,
                    "elements_summary": elements_summary,
                    "cases_text": cases_text,
                },
                config=internal_config,
            )

            # Convert to TypedDicts
            matching_cases: list[CasePrecedent] = [
                {
                    "case_name": case.case_name,
                    "citation": case.citation,
                    "year": case.year,
                    "jurisdiction": case.jurisdiction,
                    "relevance_score": case.relevance_score,
                    "key_holding": case.key_holding,
                    "how_it_applies": case.how_it_applies,
                    "outcome_for_similar_party": case.outcome_for_similar_party,
                }
                for case in result.analyzed_cases
                if case.relevance_score >= 0.4  # Only include reasonably relevant cases
            ]

            analysis: PrecedentAnalysis = {
                "matching_cases": matching_cases,
                "pattern_identified": result.pattern_identified,
                "typical_outcome": result.typical_outcome,
                "distinguishing_factors": result.distinguishing_factors,
            }

            logger.info(
                f"Precedent analysis complete: {len(matching_cases)} relevant cases, "
                f"pattern: {result.pattern_identified[:50] if result.pattern_identified else 'None'}..."
            )

            return analysis

        except Exception as e:
            logger.error(f"Case precedent analysis error: {e}")
            return {
                "matching_cases": [],
                "pattern_identified": None,
                "typical_outcome": None,
                "distinguishing_factors": ["Unable to complete precedent analysis"],
            }


# Singleton instance
_case_precedent_analyzer: CasePrecedentAnalyzer | None = None


def get_case_precedent_analyzer() -> CasePrecedentAnalyzer:
    """Get or create the singleton CasePrecedentAnalyzer instance."""
    global _case_precedent_analyzer
    if _case_precedent_analyzer is None:
        _case_precedent_analyzer = CasePrecedentAnalyzer()
    return _case_precedent_analyzer


async def case_precedent_node(state: AdaptiveAgentState, config: RunnableConfig) -> dict:
    """
    Stage 5: Case precedent analysis node.

    Searches for and analyzes relevant case law to identify:
    - Similar cases and their outcomes
    - Patterns in how courts decide similar matters
    - Factors that could distinguish the current case

    This stage runs only on the COMPLEX path, after legal elements mapping.

    Args:
        state: Current agent state
        config: LangGraph config for controlling LLM streaming

    Returns:
        dict with precedent_analysis and updated stage tracking
    """
    logger.info("Stage 5: Case Precedent Analysis")

    analyzer = get_case_precedent_analyzer()
    precedent_analysis = await analyzer.analyze_precedents(state, config)

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("case_precedent")

    return {
        "precedent_analysis": precedent_analysis,
        "current_stage": "case_precedent",
        "stages_completed": stages_completed,
    }
