"""Safety router for detecting high-risk legal situations."""

from typing import Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.adaptive_state import SafetyAssessment
from app.agents.schemas.emergency_resources import get_resources_for_risk
from app.agents.utils import get_internal_llm_config
from app.config import logger


class SafetyClassification(BaseModel):
    """LLM output for safety classification."""
    is_high_risk: bool = Field(
        description="Whether this is a high-risk situation requiring immediate resources"
    )
    risk_category: str | None = Field(
        default=None,
        description="Category if high risk: criminal, family_violence, urgent_deadline, child_welfare, suicide_self_harm"
    )
    risk_indicators: list[str] = Field(
        default_factory=list,
        description="Specific phrases or facts indicating risk"
    )
    reasoning: str = Field(
        description="Brief explanation of the classification"
    )


SAFETY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a safety classifier for a legal assistance AI in Australia.
Your job is to identify HIGH-RISK situations that need immediate professional help, not just AI advice.

## HIGH-RISK Categories (require escalation):

**criminal** - Accused of crime, police investigation, arrest, facing criminal charges
- Examples: "I've been charged with assault", "Police want to question me", "I was arrested"

**family_violence** - Domestic violence, AVO/DVO, threats of harm, stalking
- Examples: "My partner hit me", "I'm scared to go home", "I need an AVO"

**urgent_deadline** - Court date within 7 days, eviction notice expiring soon, limitation periods
- Examples: "My court date is next Tuesday", "I have 3 days to respond", "The deadline is tomorrow"

**child_welfare** - Child custody emergency, child protection involvement, child abuse
- Examples: "Child services took my kids", "My ex won't return the children", "I suspect child abuse"

**suicide_self_harm** - Mentions of self-harm, suicide, hopelessness
- Examples: "I can't go on", "I want to end it", "Life isn't worth living"

## LOW/MEDIUM Risk (handle normally):

- General rights questions ("What are my tenant rights?")
- Tenancy disputes (non-urgent eviction, bond disputes)
- Employment queries (unfair dismissal, wages)
- Contract reviews
- General legal information requests

## Important Guidelines:

1. Be sensitive but not over-cautious
2. Not every mention of a topic is high-risk (e.g., "I read about criminal law" is not high-risk)
3. Context matters - look for actual danger, urgency, or distress
4. When in doubt about safety (especially family violence, self-harm), err on the side of caution

User's message: {query}
User's Australian state/territory: {user_state}"""),
    ("human", "Assess the risk level of this query. Be thorough but not paranoid.")
])


class SafetyRouter:
    """Detects high-risk situations requiring escalation to crisis resources."""

    def __init__(self):
        # Use GPT-4o-mini for cost efficiency - safety classification is straightforward
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.chain = SAFETY_PROMPT | self.llm.with_structured_output(SafetyClassification)

    async def assess(
        self,
        query: str,
        user_state: str | None,
        config: Optional[RunnableConfig] = None,
    ) -> SafetyAssessment:
        """
        Assess a query for high-risk indicators.

        Args:
            query: The user's message/question
            user_state: Australian state/territory code (e.g., "NSW", "VIC")
            config: LangGraph config to customize for internal LLM calls

        Returns:
            SafetyAssessment with risk level, category, and recommended resources
        """
        try:
            # Use internal config to prevent streaming JSON to frontend
            internal_config = get_internal_llm_config(config)
            result = await self.chain.ainvoke(
                {"query": query, "user_state": user_state or "Unknown"},
                config=internal_config,
            )

            # Get relevant resources if high-risk
            resources = []
            risk_category = None

            if result.is_high_risk and result.risk_category:
                # Validate and normalize risk category
                valid_categories = [
                    "criminal",
                    "family_violence",
                    "urgent_deadline",
                    "child_welfare",
                    "suicide_self_harm"
                ]
                if result.risk_category in valid_categories:
                    risk_category = result.risk_category
                    resources = get_resources_for_risk(risk_category, user_state)

            assessment: SafetyAssessment = {
                "is_high_risk": result.is_high_risk,
                "risk_category": risk_category,
                "risk_indicators": result.risk_indicators,
                "recommended_resources": resources,
                "requires_escalation": result.is_high_risk,
                "reasoning": result.reasoning,
            }

            if result.is_high_risk:
                logger.warning(
                    f"HIGH-RISK detected: category={risk_category}, "
                    f"indicators={result.risk_indicators}, "
                    f"reasoning={result.reasoning}"
                )
            else:
                logger.info(f"Safety check passed: {result.reasoning[:100]}...")

            return assessment

        except Exception as e:
            logger.error(f"Safety router error: {e}")
            # On error, return safe default (not high-risk) but log for monitoring
            return {
                "is_high_risk": False,
                "risk_category": None,
                "risk_indicators": [],
                "recommended_resources": [],
                "requires_escalation": False,
                "reasoning": f"Safety check encountered an error: {str(e)}",
            }


# Singleton instance
_safety_router: SafetyRouter | None = None


def get_safety_router() -> SafetyRouter:
    """Get or create the singleton SafetyRouter instance."""
    global _safety_router
    if _safety_router is None:
        _safety_router = SafetyRouter()
    return _safety_router
