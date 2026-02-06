"""Consolidated deep analysis - single LLM call for facts, risks, and strategy.

This module combines fact_organizer, risk_analyzer, and strategy_advisor into
a single LLM call, reducing latency from ~6 seconds to ~2 seconds.

The LLM reasons through all three steps in-context:
1. Extract and organize facts from conversation
2. Analyze risks based on those facts
3. Recommend strategy based on facts and risks
"""

from typing import Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, ConfigDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.utils import get_internal_llm_config
from app.config import logger


# ============================================
# TypedDict Schemas (for type hints)
# ============================================

class TimelineEvent(TypedDict):
    date: Optional[str]
    description: str
    significance: str  # critical, relevant, background


class Party(TypedDict):
    role: str
    name: Optional[str]
    is_user: bool


class Evidence(TypedDict):
    type: str  # document, witness, communication, physical
    description: str
    status: str  # available, mentioned, needed
    strength: str  # strong, moderate, weak


class RiskFactor(TypedDict):
    description: str
    severity: str  # high, medium, low
    mitigation: Optional[str]


class StrategyOption(TypedDict):
    name: str
    description: str
    pros: list[str]
    cons: list[str]
    estimated_cost: Optional[str]
    estimated_timeline: Optional[str]


class ConsolidatedAnalysis(TypedDict):
    """Complete analysis result from single LLM call."""
    # Facts
    timeline: list[TimelineEvent]
    parties: list[Party]
    evidence: list[Evidence]
    key_facts: list[str]
    fact_gaps: list[str]
    narrative: str
    # Risks
    overall_risk: str
    strengths: list[str]
    weaknesses: list[str]
    risks: list[RiskFactor]
    time_sensitive: Optional[str]
    # Strategy
    recommended: StrategyOption
    alternatives: list[StrategyOption]
    immediate_actions: list[str]


# ============================================
# Pydantic Models (for OpenAI structured output)
# ============================================

class TimelineEventModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: Optional[str] = Field(default=None, description="Date or relative time")
    description: str = Field(description="What happened")
    significance: str = Field(description="critical, relevant, or background")


class PartyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(description="Role in the matter (tenant, landlord, etc.)")
    name: Optional[str] = Field(default=None, description="Name if known")
    is_user: bool = Field(description="Whether this party is the user")


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(description="document, witness, communication, or physical")
    description: str = Field(description="Description of the evidence")
    status: str = Field(description="available, mentioned, or needed")
    strength: str = Field(description="strong, moderate, or weak")


class RiskFactorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(description="Description of the risk")
    severity: str = Field(description="high, medium, or low")
    mitigation: Optional[str] = Field(default=None, description="How to mitigate this risk")


class StrategyOptionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(description="Name of the strategy")
    description: str = Field(description="Description of the strategy")
    pros: list[str] = Field(default_factory=list, description="Advantages")
    cons: list[str] = Field(default_factory=list, description="Disadvantages")
    estimated_cost: Optional[str] = Field(default=None, description="Estimated cost range")
    estimated_timeline: Optional[str] = Field(default=None, description="Estimated timeline")


class ConsolidatedAnalysisOutput(BaseModel):
    """Single LLM output combining facts, risks, and strategy."""
    model_config = ConfigDict(extra="forbid")

    # === FACTS ===
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

    # === RISKS ===
    overall_risk: str = Field(
        description="Overall risk level: high, medium, or low"
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="Strengths in the user's position (3-5 items)"
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Weaknesses or gaps in the user's position (2-4 items)"
    )
    risks: list[RiskFactorModel] = Field(
        default_factory=list,
        description="Specific risk factors with severity and mitigation (2-4 items)"
    )
    time_sensitive: Optional[str] = Field(
        default=None,
        description="Any time-sensitive aspects (deadlines, limitation periods)"
    )

    # === STRATEGY ===
    recommended: StrategyOptionModel = Field(
        description="The primary recommended strategy"
    )
    alternatives: list[StrategyOptionModel] = Field(
        default_factory=list,
        description="1-2 alternative strategies"
    )
    immediate_actions: list[str] = Field(
        default_factory=list,
        description="Concrete next steps the user should take now (3-5 items)"
    )


# ============================================
# Combined Prompt
# ============================================

CONSOLIDATED_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are providing a comprehensive legal analysis in one pass. Analyze the conversation and produce:

## PART 1: ORGANIZE FACTS

Extract and organize all relevant facts:

**Timeline**: Events in chronological order
- Include dates (exact or relative like "2 weeks ago")
- Mark significance: critical (directly affects legal rights), relevant (important context), background

**Parties**: Everyone involved with their role (tenant, landlord, employer, etc.)

**Evidence**: Documents and proof mentioned
- Type: document, witness, communication, physical
- Status: available (user has it), mentioned (unclear), needed (would help)
- Strength: strong, moderate, weak

**Key Facts**: The 3-7 most legally relevant facts

**Fact Gaps**: Information that would help but we don't have

**Narrative**: A clear 2-3 sentence summary

## PART 2: ANALYZE RISKS

Based on the facts you just organized:

**Strengths**: What's in the user's favor? (evidence, facts, legal rights)

**Weaknesses**: What could hurt their case? (missing evidence, unhelpful facts)

**Risks**: Specific things that could go wrong
- Severity: high/medium/low
- Include mitigation for each

**Overall Risk Level**:
- high: Significant evidence gaps, strong defences against them, or time-critical issues
- medium: Some weaknesses but addressable
- low: Strong position with good evidence

**Time Sensitivity**: Any deadlines or urgent matters

## PART 3: RECOMMEND STRATEGY

Based on the facts and risks:

**Recommended Strategy**: The best approach given their situation

**Alternatives**: 1-2 other options

**Immediate Actions**: Concrete next steps (3-5 items)

Strategy types to consider:
- Informal: Direct negotiation, written demand, informal mediation
- Formal dispute: Formal mediation, industry ombudsman (free), community justice centre
- Tribunal/Court: NCAT/QCAT/VCAT ($50-200), Fair Work Commission, small claims
- Self-help: Insurance claims, bond authority, consumer guarantees

Australian cost estimates:
- Self-representation at tribunal: $50-500
- Mediation: $0-2000
- Legal advice session: $300-1000
- Full solicitor representation: $2000-10000+

Always include at least one low-cost option.

---

## User Context
- State/Territory: {user_state}
- Has uploaded document: {has_document}

## Conversation History
{conversation}

---

Be thorough but only include facts actually stated or clearly implied. Be honest but constructive about risks."""),
    ("human", "Provide a complete analysis of this legal situation.")
])


# ============================================
# Main Function
# ============================================

async def run_consolidated_analysis(
    messages: list[BaseMessage],
    user_state: Optional[str] = None,
    has_document: bool = False,
    config: Optional[RunnableConfig] = None,
) -> ConsolidatedAnalysis:
    """
    Run complete deep analysis in a single LLM call.

    This combines fact organization, risk analysis, and strategy recommendation
    into one call, reducing latency from ~6 seconds to ~2 seconds.

    Args:
        messages: Conversation message history
        user_state: User's Australian state/territory
        has_document: Whether user has uploaded a document
        config: LangGraph config for LLM calls

    Returns:
        ConsolidatedAnalysis with facts, risks, and strategy
    """
    try:
        # Format conversation
        conversation = _format_conversation(messages)

        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        chain = CONSOLIDATED_ANALYSIS_PROMPT | llm.with_structured_output(
            ConsolidatedAnalysisOutput
        )

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

        # Convert Pydantic models to TypedDict format
        analysis: ConsolidatedAnalysis = {
            # Facts
            "timeline": [
                {"date": e.date, "description": e.description, "significance": e.significance}
                for e in result.timeline
            ],
            "parties": [
                {"role": p.role, "name": p.name, "is_user": p.is_user}
                for p in result.parties
            ],
            "evidence": [
                {"type": e.type, "description": e.description, "status": e.status, "strength": e.strength}
                for e in result.evidence
            ],
            "key_facts": result.key_facts,
            "fact_gaps": result.fact_gaps,
            "narrative": result.narrative,
            # Risks
            "overall_risk": result.overall_risk,
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            "risks": [
                {"description": r.description, "severity": r.severity, "mitigation": r.mitigation}
                for r in result.risks
            ],
            "time_sensitive": result.time_sensitive,
            # Strategy
            "recommended": {
                "name": result.recommended.name,
                "description": result.recommended.description,
                "pros": result.recommended.pros,
                "cons": result.recommended.cons,
                "estimated_cost": result.recommended.estimated_cost,
                "estimated_timeline": result.recommended.estimated_timeline,
            },
            "alternatives": [
                {
                    "name": alt.name,
                    "description": alt.description,
                    "pros": alt.pros,
                    "cons": alt.cons,
                    "estimated_cost": alt.estimated_cost,
                    "estimated_timeline": alt.estimated_timeline,
                }
                for alt in result.alternatives
            ],
            "immediate_actions": result.immediate_actions,
        }

        logger.info(
            f"Consolidated analysis complete: "
            f"{len(analysis['key_facts'])} facts, "
            f"risk={analysis['overall_risk']}, "
            f"strategy='{analysis['recommended']['name']}'"
        )

        return analysis

    except Exception as e:
        logger.error(f"Consolidated analysis error: {e}")
        return _get_fallback_analysis()


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


def _get_fallback_analysis() -> ConsolidatedAnalysis:
    """Return fallback analysis when LLM call fails."""
    return {
        "timeline": [],
        "parties": [{"role": "user", "name": None, "is_user": True}],
        "evidence": [],
        "key_facts": ["Unable to fully analyze the situation"],
        "fact_gaps": ["Complete details needed for thorough analysis"],
        "narrative": "Unable to complete analysis. Please try again or seek professional advice.",
        "overall_risk": "medium",
        "strengths": [],
        "weaknesses": ["Incomplete analysis"],
        "risks": [{
            "description": "Incomplete risk assessment",
            "severity": "medium",
            "mitigation": "Consult with a legal professional",
        }],
        "time_sensitive": None,
        "recommended": {
            "name": "Seek professional legal advice",
            "description": "Given the analysis issues, we recommend consulting with a qualified solicitor.",
            "pros": ["Expert guidance", "Tailored advice"],
            "cons": ["Cost involved"],
            "estimated_cost": "$300-1000 for consultation",
            "estimated_timeline": "1-2 weeks",
        },
        "alternatives": [{
            "name": "Community legal centre",
            "description": "Free legal advice for eligible individuals.",
            "pros": ["Free service", "Professional advice"],
            "cons": ["May have waitlist"],
            "estimated_cost": "$0",
            "estimated_timeline": "1-3 weeks",
        }],
        "immediate_actions": [
            "Document all relevant facts and gather evidence",
            "Note any upcoming deadlines",
            "Consider seeking professional legal advice",
        ],
    }
