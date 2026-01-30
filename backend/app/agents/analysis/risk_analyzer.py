"""Risk analyzer - identifies strengths, weaknesses, and risks in user's position."""

from typing import Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.utils import get_internal_llm_config
from app.agents.analysis.fact_organizer import FactSummary
from app.config import logger


class RiskFactor(TypedDict):
    """A risk factor in the user's case."""
    description: str
    severity: str  # high, medium, low
    mitigation: Optional[str]


class RiskSummary(TypedDict):
    """Risk analysis summary."""
    overall_risk: str  # high, medium, low
    strengths: list[str]
    weaknesses: list[str]
    risks: list[RiskFactor]
    time_sensitive: Optional[str]


class RiskAnalysisOutput(BaseModel):
    """LLM output for risk analysis."""
    overall_risk: str = Field(
        description="Overall risk level: high, medium, or low"
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="Strengths in the user's position (evidence, facts in their favor)"
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Weaknesses or gaps in the user's position"
    )
    risks: list[dict] = Field(
        default_factory=list,
        description="Specific risk factors with description, severity, and mitigation"
    )
    time_sensitive: Optional[str] = Field(
        default=None,
        description="Any time-sensitive aspects (deadlines, limitation periods)"
    )


RISK_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are analyzing the strengths, weaknesses, and risks in a legal matter.

## Your Task

Based on the organized facts, identify:

1. **Strengths**: What's in the user's favor?
   - Strong evidence they have
   - Facts that support their position
   - Legal rights that apply

2. **Weaknesses**: What could hurt their case?
   - Missing evidence
   - Facts that don't support them
   - Gaps in their story

3. **Risks**: Specific things that could go wrong
   - Include severity (high/medium/low)
   - Suggest how to mitigate each risk

4. **Time Sensitivity**: Any deadlines or urgent matters

## Risk Level Guidelines

- **high**: Significant evidence gaps, strong likely defences against them, or time-critical issues
- **medium**: Some weaknesses but addressable, moderate challenges
- **low**: Strong position with good evidence, limited vulnerabilities

## Organized Facts

**Narrative:** {narrative}

**Key Facts:**
{key_facts}

**Evidence Available:**
{evidence}

**Fact Gaps:**
{fact_gaps}

**Timeline:**
{timeline}

**User's State/Territory:** {user_state}

Be honest but constructive - identify real risks without being unnecessarily alarming."""),
    ("human", "Analyze the strengths, weaknesses, and risks in this situation.")
])


async def analyze_risks(
    facts: FactSummary,
    user_state: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> RiskSummary:
    """
    Analyze risks based on organized facts.

    Args:
        facts: Organized facts from fact_organizer
        user_state: User's Australian state/territory
        config: LangGraph config for LLM calls

    Returns:
        RiskSummary with strengths, weaknesses, and risks
    """
    try:
        # Format inputs
        key_facts_str = "\n".join(f"- {f}" for f in facts["key_facts"]) if facts["key_facts"] else "None identified"
        fact_gaps_str = "\n".join(f"- {g}" for g in facts["fact_gaps"]) if facts["fact_gaps"] else "None identified"

        evidence_parts = []
        for ev in facts["evidence"]:
            evidence_parts.append(f"- [{ev['status']}] {ev['description']} ({ev['strength']} strength)")
        evidence_str = "\n".join(evidence_parts) if evidence_parts else "No evidence catalogued"

        timeline_parts = []
        for event in facts["timeline"]:
            date = event["date"] or "Unknown date"
            timeline_parts.append(f"- {date}: {event['description']} ({event['significance']})")
        timeline_str = "\n".join(timeline_parts) if timeline_parts else "No timeline events"

        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        chain = RISK_ANALYSIS_PROMPT | llm.with_structured_output(RiskAnalysisOutput)

        # Use internal config to prevent streaming
        internal_config = get_internal_llm_config(config)

        result = await chain.ainvoke(
            {
                "narrative": facts["narrative"],
                "key_facts": key_facts_str,
                "evidence": evidence_str,
                "fact_gaps": fact_gaps_str,
                "timeline": timeline_str,
                "user_state": user_state or "Not specified",
            },
            config=internal_config,
        )

        # Convert to TypedDict format
        risk_summary: RiskSummary = {
            "overall_risk": result.overall_risk,
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            "risks": [
                {
                    "description": r.get("description", ""),
                    "severity": r.get("severity", "medium"),
                    "mitigation": r.get("mitigation"),
                }
                for r in result.risks
            ],
            "time_sensitive": result.time_sensitive,
        }

        logger.info(
            f"Risk analysis complete: overall={risk_summary['overall_risk']}, "
            f"{len(risk_summary['strengths'])} strengths, "
            f"{len(risk_summary['weaknesses'])} weaknesses"
        )

        return risk_summary

    except Exception as e:
        logger.error(f"Risk analysis error: {e}")
        return {
            "overall_risk": "medium",
            "strengths": ["Unable to fully assess strengths"],
            "weaknesses": ["Incomplete analysis - consider seeking professional advice"],
            "risks": [{
                "description": "Incomplete risk assessment",
                "severity": "medium",
                "mitigation": "Consult with a legal professional for comprehensive analysis",
            }],
            "time_sensitive": None,
        }
