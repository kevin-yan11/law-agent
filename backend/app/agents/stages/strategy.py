"""Stage 7: Strategy Recommendation - Generates strategic pathways with pros/cons."""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.adaptive_state import (
    AdaptiveAgentState,
    StrategyRecommendation,
    StrategyOption,
)
from app.agents.utils import get_internal_llm_config
from app.config import logger


class StrategyOptionOutput(BaseModel):
    """LLM output for a single strategy option."""
    name: str = Field(description="Short name for the strategy (e.g., 'Negotiate directly')")
    description: str = Field(description="Detailed description of the strategy approach")
    pros: list[str] = Field(
        min_length=1,
        description="Advantages of this strategy"
    )
    cons: list[str] = Field(
        min_length=1,
        description="Disadvantages or risks of this strategy"
    )
    estimated_cost: str | None = Field(
        default=None,
        description="Estimated cost range (e.g., '$0-500', '$1000-5000')"
    )
    estimated_timeline: str | None = Field(
        default=None,
        description="Estimated timeline (e.g., '2-4 weeks', '3-6 months')"
    )
    success_likelihood: Literal["high", "medium", "low"] = Field(
        description="Likelihood of success with this strategy"
    )
    recommended_for: str = Field(
        description="When this strategy makes the most sense"
    )


class StrategyRecommendationOutput(BaseModel):
    """LLM output for strategy recommendations."""
    recommended_strategy: StrategyOptionOutput = Field(
        description="The primary recommended strategy"
    )
    alternative_strategies: list[StrategyOptionOutput] = Field(
        min_length=1,
        max_length=3,
        description="Alternative strategies to consider (1-3 options)"
    )
    immediate_actions: list[str] = Field(
        min_length=1,
        description="Immediate next steps the user should take"
    )
    decision_factors: list[str] = Field(
        min_length=1,
        description="Key factors the user should consider when choosing a strategy"
    )


STRATEGY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Australian legal strategist providing practical strategy recommendations for a legal matter.

## Your Task

Based on the comprehensive analysis provided, recommend strategic pathways for resolving this matter. You should:

1. Recommend the BEST strategy as the primary recommendation
2. Provide 1-3 alternative strategies for different circumstances
3. List immediate action items
4. Identify key decision factors

## Strategy Types to Consider

### Informal Resolution
- Direct negotiation with other party
- Written demand letters
- Informal mediation
- Settlement discussions

### Formal Dispute Resolution
- Formal mediation
- Conciliation
- Industry ombudsman schemes
- Community justice centres

### Tribunal/Court Action
- Small claims/minor civil claims
- State tribunals (NCAT, QCAT, VCAT, etc.)
- Fair Work Commission
- Court proceedings

### Self-Help Remedies (where legally available)
- Insurance claims
- Bond authority claims
- Statutory warranties
- Consumer guarantees

## Strategy Assessment Guidelines

### Success Likelihood
- **high**: Strong legal position, good evidence, favorable precedents
- **medium**: Reasonable position but some risks or uncertainties
- **low**: Weak position, significant challenges, but worth considering in certain circumstances

### Cost Estimates (Australian context)
- Self-representation at tribunal: $0-500 (filing fees only)
- Mediation services: $0-2000
- Legal advice only: $300-1000
- Solicitor representation (tribunal): $2000-10000
- Court proceedings: $5000-50000+

### Timeline Estimates
- Direct negotiation: 1-4 weeks
- Tribunal matters: 2-6 months
- Court proceedings: 6-24 months

## Current Matter Context

**Legal Area:** {legal_area}
**Sub-category:** {sub_category}
**Jurisdiction:** {jurisdiction}

**Case Summary:**
{narrative_summary}

**Key Facts:**
{key_facts}

**Legal Position Viability:** {viability}

**Risk Level:** {risk_level}
**Key Risks:**
{risks_summary}

**Relevant Precedents:**
{precedent_summary}

**Time Constraints:**
{time_sensitivity}

**User Position:** {user_position}

## Important Guidelines

1. Be practical and realistic about costs, timelines, and success likelihood
2. Consider the user's position (plaintiff/defendant) when recommending strategies
3. Always include at least one low-cost option if available
4. Consider emotional and practical factors, not just legal merits
5. Recommend professional legal advice for complex or high-stakes matters
6. Be mindful of limitation periods and urgent deadlines
7. Consider the other party's likely response to each strategy
"""),
    ("human", "Provide strategic recommendations for this matter, starting with the best overall strategy.")
])


class StrategyRecommender:
    """Generates strategic recommendations based on comprehensive analysis."""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1)  # Slight temperature for creativity
        self.chain = STRATEGY_PROMPT | self.llm.with_structured_output(
            StrategyRecommendationOutput
        )

    def _format_key_facts(self, state: AdaptiveAgentState) -> str:
        """Format key facts from fact structure."""
        fact_structure = state.get("fact_structure", {})
        key_facts = fact_structure.get("key_facts", [])

        if not key_facts:
            return "No key facts identified"

        return "\n".join(f"- {fact}" for fact in key_facts[:10])

    def _format_risks_summary(self, state: AdaptiveAgentState) -> str:
        """Format risk summary from risk assessment."""
        risk_assessment = state.get("risk_assessment", {})
        risks = risk_assessment.get("risks", [])

        if not risks:
            return "No specific risks identified"

        parts = []
        for risk in risks[:5]:
            severity = risk.get("severity", "unknown")
            likelihood = risk.get("likelihood", "unknown")
            parts.append(f"- [{severity}/{likelihood}] {risk.get('description', 'Unknown')}")

        return "\n".join(parts)

    def _format_precedent_summary(self, state: AdaptiveAgentState) -> str:
        """Format precedent summary."""
        precedents = state.get("precedent_analysis", {})

        if not precedents:
            return "No relevant precedents identified"

        parts = []

        if precedents.get("pattern_identified"):
            parts.append(f"Pattern: {precedents['pattern_identified']}")

        if precedents.get("typical_outcome"):
            parts.append(f"Typical outcome: {precedents['typical_outcome']}")

        cases = precedents.get("matching_cases", [])
        if cases:
            favorable = sum(1 for c in cases if c.get("outcome_for_similar_party") == "favorable")
            unfavorable = sum(1 for c in cases if c.get("outcome_for_similar_party") == "unfavorable")
            if favorable or unfavorable:
                parts.append(f"Case outcomes: {favorable} favorable, {unfavorable} unfavorable")

        return "\n".join(parts) if parts else "No relevant precedents identified"

    def _determine_user_position(self, state: AdaptiveAgentState) -> str:
        """Determine user's position in the dispute."""
        fact_structure = state.get("fact_structure", {})
        narrative = fact_structure.get("narrative_summary", "")
        query = state.get("current_query", "")

        combined = f"{narrative} {query}".lower()

        if any(word in combined for word in ["sued", "accused", "charged", "respondent", "defend", "being taken"]):
            return "defendant/respondent (being pursued by other party)"
        else:
            return "plaintiff/applicant (pursuing action against other party)"

    async def recommend_strategy(
        self,
        state: AdaptiveAgentState,
        config: Optional[RunnableConfig] = None,
    ) -> StrategyRecommendation:
        """
        Generate strategic recommendations based on all previous analysis.

        Args:
            state: Current agent state with all previous stage outputs
            config: LangGraph config to customize for internal LLM calls

        Returns:
            StrategyRecommendation with recommended and alternative strategies
        """
        try:
            # Get context from previous stages
            issue = state.get("issue_classification", {})
            primary = issue.get("primary_issue", {})
            legal_area = primary.get("area", "unknown")
            sub_category = primary.get("sub_category", "general")

            jurisdiction = state.get("jurisdiction_result", {})
            primary_jurisdiction = jurisdiction.get("primary_jurisdiction", "FEDERAL")

            fact_structure = state.get("fact_structure", {})
            narrative_summary = fact_structure.get("narrative_summary", "No narrative available")

            elements = state.get("elements_analysis", {})
            viability = elements.get("viability_assessment", "unknown")

            risk_assessment = state.get("risk_assessment", {})
            risk_level = risk_assessment.get("overall_risk_level", "unknown")
            time_sensitivity = risk_assessment.get("time_sensitivity") or "No specific time constraints identified"

            # Use internal config to prevent streaming JSON to frontend
            internal_config = get_internal_llm_config(config)
            result = await self.chain.ainvoke(
                {
                    "legal_area": legal_area,
                    "sub_category": sub_category,
                    "jurisdiction": primary_jurisdiction,
                    "narrative_summary": narrative_summary,
                    "key_facts": self._format_key_facts(state),
                    "viability": viability,
                    "risk_level": risk_level,
                    "risks_summary": self._format_risks_summary(state),
                    "precedent_summary": self._format_precedent_summary(state),
                    "time_sensitivity": time_sensitivity,
                    "user_position": self._determine_user_position(state),
                },
                config=internal_config,
            )

            # Convert to TypedDicts
            def option_to_typed_dict(option: StrategyOptionOutput) -> StrategyOption:
                return {
                    "name": option.name,
                    "description": option.description,
                    "pros": option.pros,
                    "cons": option.cons,
                    "estimated_cost": option.estimated_cost,
                    "estimated_timeline": option.estimated_timeline,
                    "success_likelihood": option.success_likelihood,
                    "recommended_for": option.recommended_for,
                }

            recommendation: StrategyRecommendation = {
                "recommended_strategy": option_to_typed_dict(result.recommended_strategy),
                "alternative_strategies": [
                    option_to_typed_dict(alt) for alt in result.alternative_strategies
                ],
                "immediate_actions": result.immediate_actions,
                "decision_factors": result.decision_factors,
            }

            logger.info(
                f"Strategy recommendation complete: primary='{result.recommended_strategy.name}', "
                f"{len(result.alternative_strategies)} alternatives, "
                f"{len(result.immediate_actions)} immediate actions"
            )

            return recommendation

        except Exception as e:
            logger.error(f"Strategy recommendation error: {e}")
            return {
                "recommended_strategy": {
                    "name": "Seek professional legal advice",
                    "description": "Given the complexity of this matter, we recommend consulting with a qualified solicitor who can provide tailored advice based on the full details of your situation.",
                    "pros": ["Expert guidance", "Tailored to your specific circumstances", "Can identify issues we may have missed"],
                    "cons": ["Cost involved", "Takes time to arrange"],
                    "estimated_cost": "$300-1000 for initial consultation",
                    "estimated_timeline": "1-2 weeks to arrange",
                    "success_likelihood": "high",
                    "recommended_for": "All situations where legal rights are at stake",
                },
                "alternative_strategies": [{
                    "name": "Community legal centre consultation",
                    "description": "Free legal advice is available through community legal centres for eligible individuals.",
                    "pros": ["Free service", "Professional advice", "No obligation"],
                    "cons": ["May have waitlist", "Limited appointment times", "Income eligibility may apply"],
                    "estimated_cost": "$0",
                    "estimated_timeline": "1-3 weeks to get appointment",
                    "success_likelihood": "medium",
                    "recommended_for": "Those who meet income eligibility criteria",
                }],
                "immediate_actions": [
                    "Document all relevant facts and gather supporting evidence",
                    "Note any upcoming deadlines or limitation periods",
                    "Consider seeking professional legal advice",
                ],
                "decision_factors": [
                    "The financial stakes involved",
                    "Your available time and resources",
                    "The strength of your evidence",
                    "Your relationship with the other party",
                ],
            }


# Singleton instance
_strategy_recommender: StrategyRecommender | None = None


def get_strategy_recommender() -> StrategyRecommender:
    """Get or create the singleton StrategyRecommender instance."""
    global _strategy_recommender
    if _strategy_recommender is None:
        _strategy_recommender = StrategyRecommender()
    return _strategy_recommender


async def strategy_node(state: AdaptiveAgentState, config: RunnableConfig) -> dict:
    """
    Stage 7: Strategy recommendation node.

    Generates strategic recommendations based on comprehensive analysis
    from all previous stages. Provides a primary strategy, alternatives,
    immediate actions, and decision factors.

    This stage runs on both SIMPLE (abbreviated) and COMPLEX (full) paths,
    but with different depths of analysis available.

    Args:
        state: Current agent state
        config: LangGraph config for controlling LLM streaming

    Returns:
        dict with strategy_recommendation and updated stage tracking
    """
    logger.info("Stage 7: Strategy Recommendation")

    recommender = get_strategy_recommender()
    strategy = await recommender.recommend_strategy(state, config)

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("strategy")

    return {
        "strategy_recommendation": strategy,
        "current_stage": "strategy",
        "stages_completed": stages_completed,
    }
