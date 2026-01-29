"""Stage 8: Escalation Brief - Generates structured lawyer handoff package."""

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.adaptive_state import (
    AdaptiveAgentState,
    EscalationBrief,
    LegalIssue,
)
from app.agents.utils import get_internal_llm_config
from app.config import logger


class BriefSummaryOutput(BaseModel):
    """LLM output for brief summary generation."""
    executive_summary: str = Field(
        description="1-2 sentence executive summary of the matter"
    )
    urgency_level: Literal["urgent", "standard", "low_priority"] = Field(
        description="Priority level for lawyer review"
    )
    open_questions: list[str] = Field(
        min_length=1,
        description="Unresolved questions or fact gaps that need clarification"
    )
    suggested_next_steps: list[str] = Field(
        min_length=1,
        description="Recommended next steps for the lawyer to take"
    )


BRIEF_SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are creating an executive summary for a legal brief to be handed off to a lawyer.

## Your Task

Create a concise executive summary that helps a lawyer quickly understand:
1. What this matter is about
2. How urgent it is
3. What questions remain unanswered
4. What they should do next

## Urgency Level Guidelines

### Urgent
- Court/tribunal deadlines within 14 days
- Limitation periods about to expire
- Risk of irreversible harm (eviction, termination taking effect)
- Criminal charges pending
- Family violence or safety concerns
- Child welfare issues

### Standard
- Active disputes requiring resolution
- Deadlines within 1-3 months
- Moderate financial or personal impact
- Complex matters requiring detailed analysis

### Low Priority
- Information gathering stage
- No immediate deadlines
- Preventative advice sought
- Minor disputes

## Matter Context

**Legal Area:** {legal_area}
**Jurisdiction:** {jurisdiction}
**Client Situation:** {client_situation}

**Key Facts:**
{key_facts}

**Fact Gaps:**
{fact_gaps}

**Viability Assessment:** {viability}
**Risk Level:** {risk_level}
**Time Sensitivity:** {time_sensitivity}

**Evidence Available:**
{evidence_summary}

**Primary Strategy Recommended:** {recommended_strategy}

## Output Guidelines

1. Executive summary should be 1-2 sentences max
2. Open questions should focus on factual gaps and ambiguities
3. Suggested next steps should be concrete and actionable
4. Consider both legal and practical considerations
"""),
    ("human", "Generate the brief summary, urgency assessment, open questions, and next steps.")
])


class EscalationBriefGenerator:
    """Generates structured lawyer handoff packages."""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.summary_chain = BRIEF_SUMMARY_PROMPT | self.llm.with_structured_output(
            BriefSummaryOutput
        )

    def _format_key_facts(self, state: AdaptiveAgentState) -> str:
        """Format key facts from state."""
        fact_structure = state.get("fact_structure", {})
        key_facts = fact_structure.get("key_facts", [])

        if not key_facts:
            return "No key facts documented"

        return "\n".join(f"- {fact}" for fact in key_facts)

    def _format_fact_gaps(self, state: AdaptiveAgentState) -> str:
        """Format fact gaps from state."""
        fact_structure = state.get("fact_structure", {})
        fact_gaps = fact_structure.get("fact_gaps", [])

        if not fact_gaps:
            return "No obvious gaps identified"

        return "\n".join(f"- {gap}" for gap in fact_gaps)

    def _format_evidence_summary(self, state: AdaptiveAgentState) -> str:
        """Format evidence inventory."""
        fact_structure = state.get("fact_structure", {})
        evidence = fact_structure.get("evidence", [])

        if not evidence:
            return "No evidence catalogued"

        parts = []
        for ev in evidence:
            status = ev.get("status", "unknown")
            strength = ev.get("strength", "unknown")
            parts.append(f"- [{status}] {ev.get('description', 'Unknown')} ({strength})")

        return "\n".join(parts)

    def _get_client_situation(self, state: AdaptiveAgentState) -> str:
        """Generate client situation narrative."""
        fact_structure = state.get("fact_structure", {})
        narrative = fact_structure.get("narrative_summary", "")

        if narrative:
            return narrative

        # Fallback to query
        return state.get("current_query", "Client situation not documented")

    def _extract_legal_issues(self, state: AdaptiveAgentState) -> list[LegalIssue]:
        """Extract all legal issues from classification."""
        issue_classification = state.get("issue_classification", {})

        issues = []

        # Primary issue
        primary = issue_classification.get("primary_issue")
        if primary:
            issues.append(primary)

        # Secondary issues
        secondary = issue_classification.get("secondary_issues", [])
        issues.extend(secondary)

        return issues

    def _extract_relevant_precedents(self, state: AdaptiveAgentState) -> list[dict]:
        """Extract relevant case precedents."""
        precedent_analysis = state.get("precedent_analysis", {})
        matching_cases = precedent_analysis.get("matching_cases", [])

        # Return top 5 most relevant
        return matching_cases[:5]

    async def generate_brief(
        self,
        state: AdaptiveAgentState,
        config: Optional[RunnableConfig] = None,
    ) -> EscalationBrief:
        """
        Generate a comprehensive escalation brief for lawyer handoff.

        Args:
            state: Current agent state with all previous stage outputs
            config: LangGraph config to customize for internal LLM calls

        Returns:
            EscalationBrief with all structured data for lawyer review
        """
        try:
            # Get context
            issue = state.get("issue_classification", {})
            primary = issue.get("primary_issue", {})
            legal_area = primary.get("area", "unknown")

            jurisdiction = state.get("jurisdiction_result", {})
            primary_jurisdiction = jurisdiction.get("primary_jurisdiction", "FEDERAL")

            elements = state.get("elements_analysis", {})
            viability = elements.get("viability_assessment", "unknown")

            risk_assessment = state.get("risk_assessment", {})
            risk_level = risk_assessment.get("overall_risk_level", "unknown")
            time_sensitivity = risk_assessment.get("time_sensitivity") or "No specific deadlines"

            strategy = state.get("strategy_recommendation", {})
            recommended = strategy.get("recommended_strategy", {})
            recommended_name = recommended.get("name", "See detailed analysis")

            client_situation = self._get_client_situation(state)

            # Use internal config to prevent streaming JSON to frontend
            internal_config = get_internal_llm_config(config)

            # Generate summary using LLM
            summary_result = await self.summary_chain.ainvoke(
                {
                    "legal_area": legal_area,
                    "jurisdiction": primary_jurisdiction,
                    "client_situation": client_situation,
                    "key_facts": self._format_key_facts(state),
                    "fact_gaps": self._format_fact_gaps(state),
                    "viability": viability,
                    "risk_level": risk_level,
                    "time_sensitivity": time_sensitivity,
                    "evidence_summary": self._format_evidence_summary(state),
                    "recommended_strategy": recommended_name,
                },
                config=internal_config,
            )

            # Assemble the brief
            brief: EscalationBrief = {
                "brief_id": str(uuid.uuid4()),
                "generated_at": datetime.now(timezone.utc).isoformat(),

                # Summary
                "executive_summary": summary_result.executive_summary,
                "urgency_level": summary_result.urgency_level,

                # Structured data from previous stages
                "client_situation": client_situation,
                "legal_issues": self._extract_legal_issues(state),
                "jurisdiction": state.get("jurisdiction_result", {
                    "primary_jurisdiction": "FEDERAL",
                    "applicable_jurisdictions": ["FEDERAL"],
                    "jurisdiction_conflicts": [],
                    "fallback_to_federal": True,
                    "reasoning": "Jurisdiction not determined",
                }),
                "facts": state.get("fact_structure", {
                    "timeline": [],
                    "parties": [],
                    "evidence": [],
                    "key_facts": [],
                    "fact_gaps": ["Full fact gathering not completed"],
                    "narrative_summary": client_situation,
                }),
                "legal_analysis": state.get("elements_analysis", {
                    "applicable_law": "Not determined",
                    "elements": [],
                    "elements_satisfied": 0,
                    "elements_total": 0,
                    "viability_assessment": "insufficient_info",
                    "reasoning": "Elements analysis not completed",
                }),
                "relevant_precedents": self._extract_relevant_precedents(state),
                "risk_assessment": state.get("risk_assessment", {
                    "overall_risk_level": "medium",
                    "risks": [],
                    "evidence_weaknesses": [],
                    "possible_defences": [],
                    "counterfactual_scenarios": [],
                    "time_sensitivity": None,
                }),

                # Recommendations
                "recommended_strategy": recommended if recommended else {
                    "name": "Seek professional legal advice",
                    "description": "Professional consultation recommended",
                    "pros": ["Expert guidance"],
                    "cons": ["Cost involved"],
                    "estimated_cost": "Varies",
                    "estimated_timeline": "1-2 weeks",
                    "success_likelihood": "medium",
                    "recommended_for": "All legal matters",
                },
                "open_questions": summary_result.open_questions,
                "suggested_next_steps": summary_result.suggested_next_steps,
            }

            logger.info(
                f"Escalation brief generated: id={brief['brief_id'][:8]}, "
                f"urgency={brief['urgency_level']}, "
                f"{len(brief['open_questions'])} open questions"
            )

            return brief

        except Exception as e:
            logger.error(f"Escalation brief generation error: {e}")

            # Return minimal brief on error
            return {
                "brief_id": str(uuid.uuid4()),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "executive_summary": "Brief generation encountered an error. Manual review required.",
                "urgency_level": "standard",
                "client_situation": state.get("current_query", "Unknown"),
                "legal_issues": self._extract_legal_issues(state) or [{
                    "area": "unknown",
                    "sub_category": "unknown",
                    "confidence": 0.0,
                    "description": "Issue classification not completed",
                }],
                "jurisdiction": state.get("jurisdiction_result", {
                    "primary_jurisdiction": "FEDERAL",
                    "applicable_jurisdictions": ["FEDERAL"],
                    "jurisdiction_conflicts": [],
                    "fallback_to_federal": True,
                    "reasoning": "Jurisdiction not determined",
                }),
                "facts": state.get("fact_structure", {
                    "timeline": [],
                    "parties": [],
                    "evidence": [],
                    "key_facts": [],
                    "fact_gaps": ["Error during fact structuring"],
                    "narrative_summary": "",
                }),
                "legal_analysis": state.get("elements_analysis", {
                    "applicable_law": "Not determined",
                    "elements": [],
                    "elements_satisfied": 0,
                    "elements_total": 0,
                    "viability_assessment": "insufficient_info",
                    "reasoning": "Elements analysis not completed",
                }),
                "relevant_precedents": [],
                "risk_assessment": state.get("risk_assessment", {
                    "overall_risk_level": "medium",
                    "risks": [],
                    "evidence_weaknesses": [],
                    "possible_defences": [],
                    "counterfactual_scenarios": [],
                    "time_sensitivity": None,
                }),
                "recommended_strategy": {
                    "name": "Seek professional legal advice",
                    "description": "Professional consultation recommended due to brief generation error",
                    "pros": ["Expert guidance"],
                    "cons": ["Cost involved"],
                    "estimated_cost": "Varies",
                    "estimated_timeline": "1-2 weeks",
                    "success_likelihood": "medium",
                    "recommended_for": "All legal matters",
                },
                "open_questions": ["All questions require manual review due to processing error"],
                "suggested_next_steps": [
                    "Review the raw query and any uploaded documents",
                    "Conduct manual fact-gathering interview",
                    "Determine applicable legal framework",
                ],
            }


# Singleton instance
_brief_generator: EscalationBriefGenerator | None = None


def get_brief_generator() -> EscalationBriefGenerator:
    """Get or create the singleton EscalationBriefGenerator instance."""
    global _brief_generator
    if _brief_generator is None:
        _brief_generator = EscalationBriefGenerator()
    return _brief_generator


async def escalation_brief_node(state: AdaptiveAgentState, config: RunnableConfig) -> dict:
    """
    Stage 8: Escalation brief node.

    Generates a comprehensive structured brief for lawyer handoff,
    compiling all analysis from previous stages into a professional
    document format.

    This stage runs only on the COMPLEX path as the final stage.

    Args:
        state: Current agent state
        config: LangGraph config for controlling LLM streaming

    Returns:
        dict with escalation_brief and updated stage tracking
    """
    logger.info("Stage 8: Escalation Brief Generation")

    generator = get_brief_generator()
    brief = await generator.generate_brief(state, config)

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("escalation_brief")

    return {
        "escalation_brief": brief,
        "current_stage": "escalation_brief",
        "stages_completed": stages_completed,
    }
