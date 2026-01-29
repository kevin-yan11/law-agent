"""Stage 4: Legal Elements Mapping - Maps facts to legal elements for viability assessment."""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.adaptive_state import (
    AdaptiveAgentState,
    ElementsAnalysis,
    LegalElement,
)
from app.agents.schemas.legal_elements import get_element_schema, LegalAreaElements
from app.agents.utils import get_internal_llm_config
from app.config import logger


class LegalElementOutput(BaseModel):
    """LLM output for a single legal element assessment."""
    element_name: str = Field(description="Name of the legal element")
    description: str = Field(description="What this element requires")
    is_satisfied: Literal["yes", "no", "partial", "unknown"] = Field(
        description="Whether the facts satisfy this element"
    )
    supporting_facts: list[str] = Field(
        default_factory=list,
        description="Facts from the case that support this element being satisfied"
    )
    missing_facts: list[str] = Field(
        default_factory=list,
        description="Facts that would be needed to fully satisfy this element"
    )


class ElementsAnalysisOutput(BaseModel):
    """LLM output for legal elements analysis."""
    applicable_law: str = Field(
        description="The specific law/statute that applies (e.g., 'Residential Tenancies Act 2010 (NSW) s.63')"
    )
    elements: list[LegalElementOutput] = Field(
        description="Assessment of each legal element"
    )
    viability_assessment: Literal["strong", "moderate", "weak", "insufficient_info"] = Field(
        description="Overall viability of the legal position"
    )
    reasoning: str = Field(
        description="Explanation of the viability assessment (2-3 sentences)"
    )


LEGAL_ELEMENTS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Australian legal analyst assessing whether facts satisfy legal elements for a claim or defence.

## Your Task

Given the facts of a case and the relevant legal elements, assess:
1. Which elements are satisfied by the available facts
2. What facts support each element
3. What facts are missing for each element
4. Overall viability of the legal position

## Element Assessment Criteria

- **yes**: The element is clearly satisfied by stated facts
- **partial**: Some supporting facts exist but gaps remain
- **no**: Facts suggest element cannot be satisfied
- **unknown**: Insufficient information to assess

## Viability Assessment

- **strong**: Most elements satisfied, few gaps, good evidence
- **moderate**: Key elements satisfied but some gaps or uncertainties
- **weak**: Significant elements unsatisfied or major evidence gaps
- **insufficient_info**: Too many unknowns to assess viability

## Current Case Context

**Legal Area:** {legal_area}
**Sub-category:** {sub_category}
**Jurisdiction:** {jurisdiction}

**Legal Framework:**
{legal_framework}

**Structured Facts:**
{facts_summary}

**Key Facts:**
{key_facts}

**Identified Fact Gaps:**
{fact_gaps}

**Available Evidence:**
{evidence_summary}
"""),
    ("human", "Assess each legal element against the facts and provide an overall viability assessment. Be thorough but realistic about the strength of the case based on available information.")
])


# Fallback prompt when no predefined schema exists
FALLBACK_ELEMENTS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Australian legal analyst. The user has a legal issue for which we don't have a predefined elements framework.

## Your Task

1. Identify the most likely applicable law for this situation in {jurisdiction}
2. Determine what legal elements would typically need to be satisfied
3. Assess whether the available facts satisfy those elements
4. Provide an overall viability assessment

## Guidelines

- Focus on the most relevant legal framework for the situation
- Identify 3-6 key legal elements that would need to be established
- Be realistic about what the facts do and don't support

## Current Case Context

**Legal Area:** {legal_area}
**Sub-category:** {sub_category}
**Jurisdiction:** {jurisdiction}

**User's Query:**
{query}

**Structured Facts:**
{facts_summary}

**Key Facts:**
{key_facts}

**Fact Gaps:**
{fact_gaps}

**Evidence Available:**
{evidence_summary}
"""),
    ("human", "Identify the relevant legal elements for this situation and assess the facts against them.")
])


class LegalElementsAnalyzer:
    """Analyzes facts against legal elements to assess case viability."""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.chain = LEGAL_ELEMENTS_PROMPT | self.llm.with_structured_output(
            ElementsAnalysisOutput
        )
        self.fallback_chain = FALLBACK_ELEMENTS_PROMPT | self.llm.with_structured_output(
            ElementsAnalysisOutput
        )

    def _format_facts_summary(self, state: AdaptiveAgentState) -> str:
        """Format the fact structure into a readable summary."""
        fact_structure = state.get("fact_structure", {})
        parts = []

        # Timeline
        timeline = fact_structure.get("timeline", [])
        if timeline:
            parts.append("**Timeline:**")
            for event in timeline:
                date = event.get("date", "Unknown date")
                desc = event.get("description", "")
                sig = event.get("significance", "relevant")
                parts.append(f"- [{sig.upper()}] {date}: {desc}")

        # Parties
        parties = fact_structure.get("parties", [])
        if parties:
            parts.append("\n**Parties:**")
            for party in parties:
                role = party.get("role", "unknown")
                name = party.get("name") or "unnamed"
                is_user = " (USER)" if party.get("is_user") else ""
                parts.append(f"- {role}: {name}{is_user}")

        # Narrative
        narrative = fact_structure.get("narrative_summary", "")
        if narrative:
            parts.append(f"\n**Summary:** {narrative}")

        return "\n".join(parts) if parts else "No structured facts available"

    def _format_evidence_summary(self, state: AdaptiveAgentState) -> str:
        """Format the evidence inventory."""
        fact_structure = state.get("fact_structure", {})
        evidence = fact_structure.get("evidence", [])

        if not evidence:
            return "No evidence catalogued"

        parts = []
        for ev in evidence:
            ev_type = ev.get("type", "unknown")
            desc = ev.get("description", "")
            status = ev.get("status", "unknown")
            strength = ev.get("strength", "unknown")
            parts.append(f"- [{status.upper()}] {ev_type}: {desc} (strength: {strength})")

        return "\n".join(parts)

    def _format_legal_framework(self, schema: LegalAreaElements) -> str:
        """Format the legal framework from schema."""
        parts = [f"**Claim Type:** {schema['claim_type']}", ""]

        parts.append("**Elements to Establish:**")
        for i, elem in enumerate(schema["elements"], 1):
            parts.append(f"{i}. **{elem['name']}**: {elem['description']}")
            if elem.get("typical_evidence"):
                parts.append(f"   Typical evidence: {', '.join(elem['typical_evidence'])}")

        parts.append(f"\n**Relevant Legislation:** {', '.join(schema['relevant_legislation'])}")
        parts.append(f"\n**Possible Defences/Counterarguments:** {', '.join(schema['key_defences'])}")

        return "\n".join(parts)

    async def analyze_elements(
        self,
        state: AdaptiveAgentState,
        config: Optional[RunnableConfig] = None,
    ) -> ElementsAnalysis:
        """
        Analyze facts against legal elements.

        Args:
            state: Current agent state with issue classification, jurisdiction, and facts
            config: LangGraph config to customize for internal LLM calls

        Returns:
            ElementsAnalysis with element satisfaction assessment and viability
        """
        try:
            # Get context from previous stages
            issue = state.get("issue_classification", {})
            primary = issue.get("primary_issue", {})
            area = primary.get("area", "unknown")
            sub_category = primary.get("sub_category", "general")

            jurisdiction = state.get("jurisdiction_result", {})
            primary_jurisdiction = jurisdiction.get("primary_jurisdiction", "FEDERAL")

            fact_structure = state.get("fact_structure", {})
            key_facts = fact_structure.get("key_facts", [])
            fact_gaps = fact_structure.get("fact_gaps", [])

            # Format context strings
            facts_summary = self._format_facts_summary(state)
            evidence_summary = self._format_evidence_summary(state)
            key_facts_str = "\n".join(f"- {f}" for f in key_facts) if key_facts else "No key facts identified"
            fact_gaps_str = "\n".join(f"- {g}" for g in fact_gaps) if fact_gaps else "No gaps identified"

            # Check if we have a predefined schema for this issue type
            schema = get_element_schema(area, sub_category)

            # Use internal config to prevent streaming JSON to frontend
            internal_config = get_internal_llm_config(config)

            if schema:
                # Use schema-guided analysis
                legal_framework = self._format_legal_framework(schema)
                result = await self.chain.ainvoke(
                    {
                        "legal_area": area,
                        "sub_category": sub_category,
                        "jurisdiction": primary_jurisdiction,
                        "legal_framework": legal_framework,
                        "facts_summary": facts_summary,
                        "key_facts": key_facts_str,
                        "fact_gaps": fact_gaps_str,
                        "evidence_summary": evidence_summary,
                    },
                    config=internal_config,
                )
                logger.info(f"Legal elements analyzed using predefined schema: {area}/{sub_category}")
            else:
                # Use fallback LLM-generated elements
                result = await self.fallback_chain.ainvoke(
                    {
                        "legal_area": area,
                        "sub_category": sub_category,
                        "jurisdiction": primary_jurisdiction,
                        "query": state.get("current_query", ""),
                        "facts_summary": facts_summary,
                        "key_facts": key_facts_str,
                        "fact_gaps": fact_gaps_str,
                        "evidence_summary": evidence_summary,
                    },
                    config=internal_config,
                )
                logger.info(f"Legal elements analyzed using LLM fallback for: {area}/{sub_category}")

            # Convert Pydantic to TypedDict
            elements: list[LegalElement] = [
                {
                    "element_name": elem.element_name,
                    "description": elem.description,
                    "is_satisfied": elem.is_satisfied,
                    "supporting_facts": elem.supporting_facts,
                    "missing_facts": elem.missing_facts,
                }
                for elem in result.elements
            ]

            # Calculate satisfaction stats
            elements_satisfied = sum(
                1 for e in elements
                if e["is_satisfied"] in ("yes", "partial")
            )

            analysis: ElementsAnalysis = {
                "applicable_law": result.applicable_law,
                "elements": elements,
                "elements_satisfied": elements_satisfied,
                "elements_total": len(elements),
                "viability_assessment": result.viability_assessment,
                "reasoning": result.reasoning,
            }

            logger.info(
                f"Elements analysis complete: {elements_satisfied}/{len(elements)} satisfied, "
                f"viability: {result.viability_assessment}"
            )

            return analysis

        except Exception as e:
            logger.error(f"Legal elements analysis error: {e}")
            # Return minimal analysis on error
            return {
                "applicable_law": "Unable to determine applicable law",
                "elements": [],
                "elements_satisfied": 0,
                "elements_total": 0,
                "viability_assessment": "insufficient_info",
                "reasoning": "Unable to complete legal elements analysis due to an error.",
            }


# Singleton instance
_legal_elements_analyzer: LegalElementsAnalyzer | None = None


def get_legal_elements_analyzer() -> LegalElementsAnalyzer:
    """Get or create the singleton LegalElementsAnalyzer instance."""
    global _legal_elements_analyzer
    if _legal_elements_analyzer is None:
        _legal_elements_analyzer = LegalElementsAnalyzer()
    return _legal_elements_analyzer


async def legal_elements_node(state: AdaptiveAgentState, config: RunnableConfig) -> dict:
    """
    Stage 4: Legal elements mapping node.

    Maps the structured facts to legal elements required for the identified
    legal issue. Assesses which elements are satisfied, partially satisfied,
    or unmet, providing an overall viability assessment.

    This stage runs only on the COMPLEX path, after fact structuring.

    Args:
        state: Current agent state
        config: LangGraph config for controlling LLM streaming

    Returns:
        dict with elements_analysis and updated stage tracking
    """
    logger.info("Stage 4: Legal Elements Mapping")

    analyzer = get_legal_elements_analyzer()
    elements_analysis = await analyzer.analyze_elements(state, config)

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("legal_elements")

    return {
        "elements_analysis": elements_analysis,
        "current_stage": "legal_elements",
        "stages_completed": stages_completed,
    }
