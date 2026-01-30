"""Strategy advisor - recommends actions based on facts and risks."""

from typing import Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.utils import get_internal_llm_config
from app.agents.analysis.fact_organizer import FactSummary
from app.agents.analysis.risk_analyzer import RiskSummary
from app.config import logger


class StrategyOption(TypedDict):
    """A strategy option."""
    name: str
    description: str
    pros: list[str]
    cons: list[str]
    estimated_cost: Optional[str]
    estimated_timeline: Optional[str]


class StrategySummary(TypedDict):
    """Strategy recommendation summary."""
    recommended: StrategyOption
    alternatives: list[StrategyOption]
    immediate_actions: list[str]


class StrategyOutput(BaseModel):
    """LLM output for strategy recommendations."""
    recommended: dict = Field(
        description="The primary recommended strategy with name, description, pros, cons, estimated_cost, estimated_timeline"
    )
    alternatives: list[dict] = Field(
        default_factory=list,
        description="1-2 alternative strategies"
    )
    immediate_actions: list[str] = Field(
        default_factory=list,
        description="Concrete next steps the user should take now"
    )


STRATEGY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are providing practical strategy recommendations for a legal matter.

## Your Task

Based on the facts and risk analysis, recommend:

1. **Primary Strategy**: The best approach given their situation
2. **Alternatives**: 1-2 other options to consider
3. **Immediate Actions**: Concrete next steps they should take now

## Strategy Types to Consider

**Informal Resolution**
- Direct negotiation with other party
- Written demand letter
- Informal mediation

**Formal Dispute Resolution**
- Formal mediation
- Industry ombudsman (free)
- Community justice centre (free/low cost)

**Tribunal/Court**
- State tribunals (NCAT, QCAT, VCAT) - usually $50-200 filing
- Fair Work Commission (employment matters)
- Small claims court

**Self-Help Remedies**
- Insurance claims
- Bond authority claims
- Consumer guarantee claims

## Cost Estimates (Australia)

- Self-representation at tribunal: $50-500 (filing fees)
- Mediation: $0-2000
- Legal advice session: $300-1000
- Full solicitor representation: $2000-10000+

## Timeline Estimates

- Direct negotiation: 1-4 weeks
- Tribunal matters: 2-6 months
- Court proceedings: 6-24 months

## Current Situation

**Narrative:** {narrative}

**Key Facts:**
{key_facts}

**Strengths:**
{strengths}

**Weaknesses:**
{weaknesses}

**Risk Level:** {risk_level}

**Time Sensitive:** {time_sensitive}

**User's State/Territory:** {user_state}

Be practical - consider their time, money, and emotional capacity. Always include at least one low-cost option."""),
    ("human", "What strategy do you recommend for this situation?")
])


async def recommend_strategy(
    facts: FactSummary,
    risks: RiskSummary,
    user_state: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> StrategySummary:
    """
    Recommend strategies based on facts and risk analysis.

    Args:
        facts: Organized facts from fact_organizer
        risks: Risk analysis from risk_analyzer
        user_state: User's Australian state/territory
        config: LangGraph config for LLM calls

    Returns:
        StrategySummary with recommended strategy, alternatives, and immediate actions
    """
    try:
        # Format inputs
        key_facts_str = "\n".join(f"- {f}" for f in facts["key_facts"]) if facts["key_facts"] else "None identified"
        strengths_str = "\n".join(f"- {s}" for s in risks["strengths"]) if risks["strengths"] else "None identified"
        weaknesses_str = "\n".join(f"- {w}" for w in risks["weaknesses"]) if risks["weaknesses"] else "None identified"

        llm = ChatOpenAI(model="gpt-4o", temperature=0.1)  # Slight creativity
        chain = STRATEGY_PROMPT | llm.with_structured_output(StrategyOutput)

        # Use internal config to prevent streaming
        internal_config = get_internal_llm_config(config)

        result = await chain.ainvoke(
            {
                "narrative": facts["narrative"],
                "key_facts": key_facts_str,
                "strengths": strengths_str,
                "weaknesses": weaknesses_str,
                "risk_level": risks["overall_risk"],
                "time_sensitive": risks["time_sensitive"] or "No specific deadlines",
                "user_state": user_state or "Not specified",
            },
            config=internal_config,
        )

        # Convert to TypedDict format
        def to_strategy_option(data: dict) -> StrategyOption:
            return {
                "name": data.get("name", "Unknown"),
                "description": data.get("description", ""),
                "pros": data.get("pros", []),
                "cons": data.get("cons", []),
                "estimated_cost": data.get("estimated_cost"),
                "estimated_timeline": data.get("estimated_timeline"),
            }

        strategy_summary: StrategySummary = {
            "recommended": to_strategy_option(result.recommended),
            "alternatives": [to_strategy_option(alt) for alt in result.alternatives],
            "immediate_actions": result.immediate_actions,
        }

        logger.info(
            f"Strategy recommendation: '{strategy_summary['recommended']['name']}', "
            f"{len(strategy_summary['alternatives'])} alternatives, "
            f"{len(strategy_summary['immediate_actions'])} actions"
        )

        return strategy_summary

    except Exception as e:
        logger.error(f"Strategy recommendation error: {e}")
        return {
            "recommended": {
                "name": "Seek professional legal advice",
                "description": "Given the complexity, we recommend consulting with a qualified solicitor.",
                "pros": ["Expert guidance", "Tailored advice"],
                "cons": ["Cost involved"],
                "estimated_cost": "$300-1000 for consultation",
                "estimated_timeline": "1-2 weeks",
            },
            "alternatives": [{
                "name": "Community legal centre",
                "description": "Free legal advice for eligible individuals.",
                "pros": ["Free service", "Professional advice"],
                "cons": ["May have waitlist", "Income eligibility may apply"],
                "estimated_cost": "$0",
                "estimated_timeline": "1-3 weeks",
            }],
            "immediate_actions": [
                "Document all relevant facts and gather evidence",
                "Note any upcoming deadlines",
                "Consider seeking professional legal advice",
            ],
        }
