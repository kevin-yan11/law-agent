"""Stage 6: Risk Analysis - Identifies risks, defences, and counterfactual scenarios."""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.agents.adaptive_state import (
    AdaptiveAgentState,
    RiskAssessment,
    RiskFactor,
    DefenceAnalysis,
)
from app.agents.utils import get_internal_llm_config
from app.config import logger


class RiskFactorOutput(BaseModel):
    """LLM output for a risk factor."""
    description: str = Field(description="Description of the risk")
    severity: Literal["high", "medium", "low"] = Field(
        description="How serious is this risk if it materializes"
    )
    likelihood: Literal["likely", "possible", "unlikely"] = Field(
        description="How likely is this risk to materialize"
    )
    mitigation: str | None = Field(
        default=None,
        description="How this risk could be mitigated or addressed"
    )


class DefenceAnalysisOutput(BaseModel):
    """LLM output for defence/counterclaim analysis."""
    defence_type: str = Field(description="Type of defence or counterclaim")
    likelihood_of_use: float = Field(
        ge=0, le=1,
        description="How likely is the other party to raise this defence (0-1)"
    )
    strength: Literal["strong", "moderate", "weak"] = Field(
        description="How strong would this defence be if raised"
    )
    counter_strategy: str = Field(
        description="How to respond to or preempt this defence"
    )


class RiskAnalysisOutput(BaseModel):
    """LLM output for risk analysis."""
    overall_risk_level: Literal["high", "medium", "low"] = Field(
        description="Overall risk level for the user's position"
    )
    risks: list[RiskFactorOutput] = Field(
        default_factory=list,
        description="Specific risk factors identified"
    )
    evidence_weaknesses: list[str] = Field(
        default_factory=list,
        description="Weaknesses in the user's evidence or documentation"
    )
    possible_defences: list[DefenceAnalysisOutput] = Field(
        default_factory=list,
        description="Defences or counterclaims the other party might raise"
    )
    counterfactual_scenarios: list[str] = Field(
        default_factory=list,
        description="'What if' scenarios to consider (e.g., 'What if they claim X?')"
    )
    time_sensitivity: str | None = Field(
        default=None,
        description="Any time-sensitive aspects (limitation periods, deadlines)"
    )


RISK_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Australian legal risk analyst. Your task is to identify potential risks, weaknesses, and challenges in the user's legal position.

## Your Task

Conduct a thorough risk analysis considering:
1. Weaknesses in the user's position
2. Evidence gaps and documentation issues
3. Defences the other party might raise
4. Time-sensitive factors
5. "What if" scenarios

## Risk Assessment Guidelines

### Overall Risk Level
- **high**: Significant gaps in evidence, strong likely defences, or time-critical issues
- **medium**: Some weaknesses but addressable, moderate defence possibilities
- **low**: Strong position with good evidence, limited viable defences

### Risk Severity
- **high**: Could significantly harm the case or result in adverse outcome
- **medium**: Notable concern but manageable with proper preparation
- **low**: Minor issue that should be noted but unlikely to be decisive

### Risk Likelihood
- **likely**: Probable to occur based on typical patterns
- **possible**: Could happen but not certain
- **unlikely**: Improbable but worth considering

### Evidence Weaknesses
Think critically about:
- Missing documentation
- Gaps in timeline
- Hearsay vs direct evidence
- Witness availability/credibility
- Contradictory information

### Possible Defences
Consider what the opposing party might argue:
- Complete defences (negating liability entirely)
- Partial defences (reducing damages/responsibility)
- Procedural objections
- Counterclaims

## Current Matter Context

**Legal Area:** {legal_area}
**Sub-category:** {sub_category}
**Jurisdiction:** {jurisdiction}
**User's Position:** {user_position}

**Key Facts:**
{key_facts}

**Fact Gaps Identified:**
{fact_gaps}

**Evidence Inventory:**
{evidence_summary}

**Elements Analysis:**
{elements_summary}

**Relevant Precedents:**
{precedent_summary}

**Applicable Defences from Law:**
{known_defences}
"""),
    ("human", "Conduct a comprehensive risk analysis for this matter. Be thorough but realistic - identify genuine risks without being unnecessarily alarmist.")
])


class RiskAnalyzer:
    """Analyzes risks, defences, and counterfactual scenarios."""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.chain = RISK_ANALYSIS_PROMPT | self.llm.with_structured_output(
            RiskAnalysisOutput
        )

    def _format_evidence_summary(self, state: AdaptiveAgentState) -> str:
        """Format evidence inventory from fact structure."""
        fact_structure = state.get("fact_structure", {})
        evidence = fact_structure.get("evidence", [])

        if not evidence:
            return "No evidence catalogued"

        parts = []
        for ev in evidence:
            status = ev.get("status", "unknown")
            strength = ev.get("strength", "unknown")
            parts.append(f"- [{status}] {ev.get('description', 'Unknown')} (strength: {strength})")

        return "\n".join(parts)

    def _format_elements_summary(self, state: AdaptiveAgentState) -> str:
        """Format elements analysis summary."""
        elements = state.get("elements_analysis", {})
        if not elements:
            return "No elements analysis available"

        parts = [
            f"Viability: {elements.get('viability_assessment', 'Unknown')}",
            f"Elements: {elements.get('elements_satisfied', 0)}/{elements.get('elements_total', 0)} satisfied",
        ]

        # Include unsatisfied/partial elements as they represent risk areas
        for elem in elements.get("elements", []):
            status = elem.get("is_satisfied", "unknown")
            if status in ("no", "partial", "unknown"):
                missing = elem.get("missing_facts", [])
                missing_str = f" (missing: {', '.join(missing[:2])})" if missing else ""
                parts.append(f"- {elem.get('element_name', 'Unknown')}: {status}{missing_str}")

        return "\n".join(parts)

    def _format_precedent_summary(self, state: AdaptiveAgentState) -> str:
        """Format precedent analysis summary."""
        precedents = state.get("precedent_analysis", {})
        if not precedents:
            return "No precedent analysis available"

        parts = []

        # Pattern and typical outcome
        if precedents.get("pattern_identified"):
            parts.append(f"Pattern: {precedents['pattern_identified']}")
        if precedents.get("typical_outcome"):
            parts.append(f"Typical outcome: {precedents['typical_outcome']}")

        # Cases with unfavorable outcomes (risk indicators)
        cases = precedents.get("matching_cases", [])
        unfavorable = [c for c in cases if c.get("outcome_for_similar_party") == "unfavorable"]
        if unfavorable:
            parts.append("Cases with unfavorable outcomes for similar parties:")
            for case in unfavorable[:2]:
                parts.append(f"- {case.get('case_name', 'Unknown')}: {case.get('key_holding', 'N/A')[:100]}")

        # Distinguishing factors
        dist_factors = precedents.get("distinguishing_factors", [])
        if dist_factors:
            parts.append(f"Distinguishing factors: {', '.join(dist_factors[:3])}")

        return "\n".join(parts) if parts else "No relevant precedents identified"

    def _get_known_defences(self, state: AdaptiveAgentState) -> str:
        """Get known defences from legal element schemas if available."""
        # This would ideally pull from the legal_elements schema
        # For now, provide based on legal area
        issue = state.get("issue_classification", {})
        primary = issue.get("primary_issue", {})
        area = primary.get("area", "")

        defences_by_area = {
            "tenancy": [
                "Property damage beyond fair wear and tear",
                "Outstanding rent or utility payments",
                "Breach of lease terms by tenant",
                "Proper notice was provided",
            ],
            "employment": [
                "Valid reason for dismissal existed",
                "Proper procedures were followed",
                "Genuine redundancy",
                "Small business fair dismissal code compliance",
                "Serious misconduct by employee",
            ],
            "family": [
                "Safety concerns about other party",
                "Child's expressed wishes (if appropriate age)",
                "Practical impossibility of proposed arrangement",
                "Non-disclosure of assets",
            ],
            "consumer": [
                "Damage caused by consumer",
                "Issue disclosed before purchase",
                "Not a consumer transaction",
                "Reasonable time for remedy not given",
            ],
        }

        defences = defences_by_area.get(area, ["Defences specific to this area not catalogued"])
        return "\n".join(f"- {d}" for d in defences)

    def _determine_user_position(self, state: AdaptiveAgentState) -> str:
        """Determine user's position (plaintiff/defendant/applicant/respondent)."""
        fact_structure = state.get("fact_structure", {})
        narrative = fact_structure.get("narrative_summary", "")
        query = state.get("current_query", "")

        combined = f"{narrative} {query}".lower()

        if any(word in combined for word in ["sued", "accused", "charged", "respondent", "defend"]):
            return "defendant/respondent"
        else:
            return "plaintiff/applicant"

    async def analyze_risks(
        self,
        state: AdaptiveAgentState,
        config: Optional[RunnableConfig] = None,
    ) -> RiskAssessment:
        """
        Analyze risks, defences, and counterfactual scenarios.

        Args:
            state: Current agent state with all previous stage outputs
            config: LangGraph config to customize for internal LLM calls

        Returns:
            RiskAssessment with identified risks, defences, and scenarios
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
            fact_gaps = fact_structure.get("fact_gaps", [])

            # Format all summaries
            key_facts_str = "\n".join(f"- {f}" for f in key_facts) if key_facts else "No key facts identified"
            fact_gaps_str = "\n".join(f"- {g}" for g in fact_gaps) if fact_gaps else "No gaps identified"
            evidence_summary = self._format_evidence_summary(state)
            elements_summary = self._format_elements_summary(state)
            precedent_summary = self._format_precedent_summary(state)
            known_defences = self._get_known_defences(state)
            user_position = self._determine_user_position(state)

            # Use internal config to prevent streaming JSON to frontend
            internal_config = get_internal_llm_config(config)
            result = await self.chain.ainvoke(
                {
                    "legal_area": legal_area,
                    "sub_category": sub_category,
                    "jurisdiction": primary_jurisdiction,
                    "user_position": user_position,
                    "key_facts": key_facts_str,
                    "fact_gaps": fact_gaps_str,
                    "evidence_summary": evidence_summary,
                    "elements_summary": elements_summary,
                    "precedent_summary": precedent_summary,
                    "known_defences": known_defences,
                },
                config=internal_config,
            )

            # Convert to TypedDicts
            risks: list[RiskFactor] = [
                {
                    "description": risk.description,
                    "severity": risk.severity,
                    "likelihood": risk.likelihood,
                    "mitigation": risk.mitigation,
                }
                for risk in result.risks
            ]

            possible_defences: list[DefenceAnalysis] = [
                {
                    "defence_type": defence.defence_type,
                    "likelihood_of_use": defence.likelihood_of_use,
                    "strength": defence.strength,
                    "counter_strategy": defence.counter_strategy,
                }
                for defence in result.possible_defences
            ]

            assessment: RiskAssessment = {
                "overall_risk_level": result.overall_risk_level,
                "risks": risks,
                "evidence_weaknesses": result.evidence_weaknesses,
                "possible_defences": possible_defences,
                "counterfactual_scenarios": result.counterfactual_scenarios,
                "time_sensitivity": result.time_sensitivity,
            }

            logger.info(
                f"Risk analysis complete: overall level={result.overall_risk_level}, "
                f"{len(risks)} risks, {len(possible_defences)} defences identified"
            )

            return assessment

        except Exception as e:
            logger.error(f"Risk analysis error: {e}")
            return {
                "overall_risk_level": "medium",
                "risks": [{
                    "description": "Unable to complete full risk analysis",
                    "severity": "medium",
                    "likelihood": "possible",
                    "mitigation": "Seek professional legal advice for comprehensive risk assessment",
                }],
                "evidence_weaknesses": ["Risk analysis incomplete - evidence assessment unavailable"],
                "possible_defences": [],
                "counterfactual_scenarios": [],
                "time_sensitivity": None,
            }


# Singleton instance
_risk_analyzer: RiskAnalyzer | None = None


def get_risk_analyzer() -> RiskAnalyzer:
    """Get or create the singleton RiskAnalyzer instance."""
    global _risk_analyzer
    if _risk_analyzer is None:
        _risk_analyzer = RiskAnalyzer()
    return _risk_analyzer


async def risk_analysis_node(state: AdaptiveAgentState, config: RunnableConfig) -> dict:
    """
    Stage 6: Risk analysis node.

    Identifies potential risks, evidence weaknesses, likely defences,
    and counterfactual scenarios to help the user understand vulnerabilities
    in their position.

    This stage runs only on the COMPLEX path, after case precedent analysis.

    Args:
        state: Current agent state
        config: LangGraph config for controlling LLM streaming

    Returns:
        dict with risk_assessment and updated stage tracking
    """
    logger.info("Stage 6: Risk Analysis")

    analyzer = get_risk_analyzer()
    risk_assessment = await analyzer.analyze_risks(state, config)

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("risk_analysis")

    return {
        "risk_assessment": risk_assessment,
        "current_stage": "risk_analysis",
        "stages_completed": stages_completed,
    }
