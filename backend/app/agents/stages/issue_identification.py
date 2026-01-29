"""Stage 1: Issue Identification - Classifies legal issues from user queries."""

from typing import Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.adaptive_state import AdaptiveAgentState, LegalIssue, IssueClassification
from app.agents.utils import get_internal_llm_config
from app.config import logger


class SecondaryIssue(BaseModel):
    """A secondary legal issue identified."""
    area: str = Field(description="Legal area")
    sub_category: str = Field(description="Specific sub-category")
    confidence: float = Field(ge=0, le=1, description="Confidence score")
    description: str = Field(description="Brief description")


class IssueIdentificationOutput(BaseModel):
    """LLM output for issue identification."""
    primary_area: str = Field(
        description="Primary legal area: tenancy, employment, family, criminal, contract, immigration, property, wills_estates, injury, debt, administrative, consumer, other"
    )
    primary_sub_category: str = Field(
        description="Specific sub-category (e.g., bond_dispute, unfair_dismissal, rent_increase)"
    )
    primary_confidence: float = Field(
        ge=0, le=1,
        description="Confidence in primary classification"
    )
    primary_description: str = Field(
        description="Brief description of the primary issue"
    )

    secondary_issues: list[SecondaryIssue] = Field(
        default_factory=list,
        description="Additional legal issues identified (if any)"
    )

    complexity_score: float = Field(
        ge=0, le=1,
        description="Overall complexity: 0=very simple, 1=very complex"
    )
    involves_multiple_jurisdictions: bool = Field(
        default=False,
        description="Whether multiple states/territories or federal law involved"
    )
    requires_document_analysis: bool = Field(
        default=False,
        description="Whether document analysis would be helpful"
    )


ISSUE_IDENTIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Australian legal issue classifier. Your task is to identify and categorize legal issues from user queries.

## Legal Areas (choose one as primary)

- **tenancy**: Rental agreements, lease issues, bond disputes, eviction, repairs, rent increases, break lease
- **employment**: Unfair dismissal, wages/underpayment, workplace rights, redundancy, workplace bullying, discrimination at work
- **family**: Divorce, child custody, property settlement, domestic violence orders (DVO/AVO), child support
- **criminal**: Criminal charges, arrests, police matters, traffic offences, court appearances
- **contract**: Contract disputes, breaches, consumer guarantees, refunds, warranty claims
- **immigration**: Visas, citizenship, deportation, migration issues
- **property**: Buying/selling property, boundary disputes, strata/body corporate, easements
- **wills_estates**: Inheritance, probate, power of attorney, contested wills, estate planning
- **injury**: Personal injury, workers compensation, public liability, medical negligence
- **debt**: Bankruptcy, debt collection, credit issues, financial hardship
- **administrative**: Government decisions, tribunal appeals, FOI requests, licensing
- **consumer**: Product issues, service complaints, ACCC matters, scams
- **other**: Anything not fitting above categories

## Sub-categories (be specific)

Use descriptive sub-categories like:
- tenancy: bond_refund, rent_increase, eviction_notice, repairs_maintenance, break_lease, subletting
- employment: unfair_dismissal, underpayment, redundancy, workplace_bullying, discrimination, contract_termination
- family: divorce, child_custody, property_settlement, domestic_violence_order, child_support
- etc.

## Complexity Scoring

Consider these factors when scoring complexity (0-1):

**Low complexity (0.0-0.3)**:
- Single, clear legal question
- One party relationship
- General information request
- Common, well-documented issue

**Medium complexity (0.4-0.6)**:
- Some ambiguity in facts
- Multiple related issues
- Time pressure mentioned
- Needs specific advice

**High complexity (0.7-1.0)**:
- Multiple interrelated legal areas
- Multiple parties with conflicting interests
- Ongoing dispute or litigation
- Document analysis needed
- Emotionally charged situation
- Potential for significant consequences

## Current Query Context

User's query: {query}
User's Australian state/territory: {user_state}
User has uploaded document: {has_document}
"""),
    ("human", "Identify and classify the legal issues in this query.")
])


class IssueIdentifier:
    """Identifies and classifies legal issues from user queries."""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.chain = ISSUE_IDENTIFICATION_PROMPT | self.llm.with_structured_output(
            IssueIdentificationOutput
        )

    async def identify(
        self,
        state: AdaptiveAgentState,
        config: Optional[RunnableConfig] = None,
    ) -> IssueClassification:
        """
        Identify legal issues from the user's query.

        Args:
            state: Current agent state with query and context
            config: LangGraph config to customize for internal LLM calls

        Returns:
            IssueClassification with primary issue, secondary issues, and complexity score
        """
        try:
            # Use internal config to prevent streaming JSON to frontend
            internal_config = get_internal_llm_config(config)
            result = await self.chain.ainvoke(
                {
                    "query": state.get("current_query", ""),
                    "user_state": state.get("user_state") or "Unknown",
                    "has_document": "Yes" if state.get("uploaded_document_url") else "No",
                },
                config=internal_config,
            )

            # Build primary issue
            primary_issue: LegalIssue = {
                "area": result.primary_area,
                "sub_category": result.primary_sub_category,
                "confidence": result.primary_confidence,
                "description": result.primary_description,
            }

            # Build secondary issues
            secondary_issues: list[LegalIssue] = [
                {
                    "area": issue.area,
                    "sub_category": issue.sub_category,
                    "confidence": issue.confidence,
                    "description": issue.description,
                }
                for issue in result.secondary_issues
            ]

            classification: IssueClassification = {
                "primary_issue": primary_issue,
                "secondary_issues": secondary_issues,
                "complexity_score": result.complexity_score,
                "involves_multiple_jurisdictions": result.involves_multiple_jurisdictions,
                "requires_document_analysis": result.requires_document_analysis,
            }

            logger.info(
                f"Issue identified: {primary_issue['area']}/{primary_issue['sub_category']} "
                f"(complexity: {result.complexity_score:.2f}, "
                f"secondary issues: {len(secondary_issues)})"
            )

            return classification

        except Exception as e:
            logger.error(f"Issue identification error: {e}")
            # Return a default classification on error
            return {
                "primary_issue": {
                    "area": "other",
                    "sub_category": "general_inquiry",
                    "confidence": 0.5,
                    "description": "Unable to classify - treating as general inquiry",
                },
                "secondary_issues": [],
                "complexity_score": 0.5,
                "involves_multiple_jurisdictions": False,
                "requires_document_analysis": False,
            }


# Singleton instance
_issue_identifier: IssueIdentifier | None = None


def get_issue_identifier() -> IssueIdentifier:
    """Get or create the singleton IssueIdentifier instance."""
    global _issue_identifier
    if _issue_identifier is None:
        _issue_identifier = IssueIdentifier()
    return _issue_identifier


async def issue_identification_node(state: AdaptiveAgentState, config: RunnableConfig) -> dict:
    """
    Stage 1: Issue identification node.

    Classifies the user's query into legal areas and assesses complexity.
    This determines whether to use the simple or complex analysis path.

    Args:
        state: Current agent state
        config: LangGraph config for controlling LLM streaming

    Returns:
        dict with issue_classification and updated stage tracking
    """
    logger.info("Stage 1: Issue Identification")

    identifier = get_issue_identifier()
    classification = await identifier.identify(state, config)

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("issue_identification")

    return {
        "issue_classification": classification,
        "current_stage": "issue_identification",
        "stages_completed": stages_completed,
    }
