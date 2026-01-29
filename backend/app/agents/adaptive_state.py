"""Extended state definition for adaptive depth legal workflow."""

from typing import Optional, Literal, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
import operator


# ============================================
# Stage 0: Safety Gate
# ============================================
class SafetyAssessment(TypedDict):
    """Output from safety gate stage."""
    is_high_risk: bool
    risk_category: Optional[Literal[
        "criminal",
        "family_violence",
        "urgent_deadline",
        "child_welfare",
        "suicide_self_harm"
    ]]
    risk_indicators: list[str]
    recommended_resources: list[dict]  # [{name, phone, url, description}]
    requires_escalation: bool
    reasoning: str


# ============================================
# Stage 1: Issue Identification
# ============================================
class LegalIssue(TypedDict):
    """A single identified legal issue."""
    area: str  # e.g., "tenancy", "employment", "family"
    sub_category: str  # e.g., "bond_dispute", "unfair_dismissal"
    confidence: float
    description: str


class IssueClassification(TypedDict):
    """Output from issue identification stage."""
    primary_issue: LegalIssue
    secondary_issues: list[LegalIssue]
    complexity_score: float  # 0-1, used for routing
    involves_multiple_jurisdictions: bool
    requires_document_analysis: bool


# ============================================
# Stage 2: Jurisdiction Resolution
# ============================================
class JurisdictionResult(TypedDict):
    """Output from jurisdiction resolution stage."""
    primary_jurisdiction: str  # "NSW", "QLD", "FEDERAL", etc.
    applicable_jurisdictions: list[str]
    jurisdiction_conflicts: list[str]
    fallback_to_federal: bool
    reasoning: str


# ============================================
# Stage 3: Fact Structuring
# ============================================
class TimelineEvent(TypedDict):
    """A single event in the timeline."""
    date: Optional[str]  # ISO format or relative ("2 weeks ago")
    description: str
    significance: Literal["critical", "relevant", "background"]
    source: Literal["user_stated", "document", "inferred"]


class Party(TypedDict):
    """A party involved in the legal matter."""
    role: str  # "tenant", "landlord", "employer", etc.
    name: Optional[str]
    is_user: bool
    relationship_to_user: Optional[str]


class Evidence(TypedDict):
    """Evidence item."""
    type: Literal["document", "witness", "communication", "physical"]
    description: str
    status: Literal["available", "mentioned", "needed"]
    strength: Literal["strong", "moderate", "weak"]


class FactStructure(TypedDict):
    """Output from fact structuring stage."""
    timeline: list[TimelineEvent]
    parties: list[Party]
    evidence: list[Evidence]
    key_facts: list[str]
    fact_gaps: list[str]  # Information we still need
    narrative_summary: str


# ============================================
# Stage 4: Legal Elements Mapping
# ============================================
class LegalElement(TypedDict):
    """A legal element that must be satisfied."""
    element_name: str
    description: str
    is_satisfied: Literal["yes", "no", "partial", "unknown"]
    supporting_facts: list[str]
    missing_facts: list[str]


class ElementsAnalysis(TypedDict):
    """Output from legal elements mapping stage."""
    applicable_law: str  # e.g., "Residential Tenancies Act 1997 (Vic) s.44"
    elements: list[LegalElement]
    elements_satisfied: int
    elements_total: int
    viability_assessment: Literal["strong", "moderate", "weak", "insufficient_info"]
    reasoning: str


# ============================================
# Stage 5: Case Precedent
# ============================================
class CasePrecedent(TypedDict):
    """A relevant case precedent."""
    case_name: str
    citation: str
    year: int
    jurisdiction: str
    relevance_score: float
    key_holding: str
    how_it_applies: str
    outcome_for_similar_party: Literal["favorable", "unfavorable", "mixed"]


class PrecedentAnalysis(TypedDict):
    """Output from case precedent stage."""
    matching_cases: list[CasePrecedent]
    pattern_identified: Optional[str]
    typical_outcome: Optional[str]
    distinguishing_factors: list[str]


# ============================================
# Stage 6: Risk Analysis
# ============================================
class RiskFactor(TypedDict):
    """A single risk factor."""
    description: str
    severity: Literal["high", "medium", "low"]
    likelihood: Literal["likely", "possible", "unlikely"]
    mitigation: Optional[str]


class DefenceAnalysis(TypedDict):
    """Analysis of potential defences/counterclaims."""
    defence_type: str
    likelihood_of_use: float
    strength: Literal["strong", "moderate", "weak"]
    counter_strategy: str


class RiskAssessment(TypedDict):
    """Output from risk analysis stage."""
    overall_risk_level: Literal["high", "medium", "low"]
    risks: list[RiskFactor]
    evidence_weaknesses: list[str]
    possible_defences: list[DefenceAnalysis]
    counterfactual_scenarios: list[str]  # "What if X..."
    time_sensitivity: Optional[str]


# ============================================
# Stage 7: Strategy Recommendation
# ============================================
class StrategyOption(TypedDict):
    """A single strategy option."""
    name: str
    description: str
    pros: list[str]
    cons: list[str]
    estimated_cost: Optional[str]
    estimated_timeline: Optional[str]
    success_likelihood: Literal["high", "medium", "low"]
    recommended_for: str  # When this option makes sense


class StrategyRecommendation(TypedDict):
    """Output from strategy recommendation stage."""
    recommended_strategy: StrategyOption
    alternative_strategies: list[StrategyOption]
    immediate_actions: list[str]
    decision_factors: list[str]  # What user should consider


# ============================================
# Stage 8: Escalation Brief
# ============================================
class EscalationBrief(TypedDict):
    """Structured handoff package for lawyers."""
    brief_id: str
    generated_at: str  # ISO timestamp

    # Summary
    executive_summary: str
    urgency_level: Literal["urgent", "standard", "low_priority"]

    # Structured data
    client_situation: str
    legal_issues: list[LegalIssue]
    jurisdiction: JurisdictionResult
    facts: FactStructure
    legal_analysis: ElementsAnalysis
    relevant_precedents: list[CasePrecedent]
    risk_assessment: RiskAssessment

    # Recommendations
    recommended_strategy: StrategyOption
    open_questions: list[str]
    suggested_next_steps: list[str]


# ============================================
# Routing Control
# ============================================
class RoutingDecision(TypedDict):
    """Routing decision for adaptive depth."""
    path: Literal["escalate", "simple", "complex"]
    reasoning: str
    skip_stages: list[str]  # Stages to skip in simple path


# ============================================
# Main State (Extended)
# ============================================
class AdaptiveAgentState(TypedDict):
    """Extended state for adaptive depth workflow."""

    # ---- Session & Context ----
    session_id: str
    user_state: Optional[str]  # Australian state/territory
    uploaded_document_url: Optional[str]

    # ---- Conversation ----
    messages: Annotated[list[BaseMessage], operator.add]
    current_query: str

    # ---- Routing Control ----
    routing_decision: Optional[RoutingDecision]
    current_stage: str
    stages_completed: list[str]

    # ---- Stage Outputs ----
    safety_assessment: Optional[SafetyAssessment]
    issue_classification: Optional[IssueClassification]
    jurisdiction_result: Optional[JurisdictionResult]
    fact_structure: Optional[FactStructure]
    elements_analysis: Optional[ElementsAnalysis]
    precedent_analysis: Optional[PrecedentAnalysis]
    risk_assessment: Optional[RiskAssessment]
    strategy_recommendation: Optional[StrategyRecommendation]
    escalation_brief: Optional[EscalationBrief]

    # ---- RAG Results (for simple path) ----
    rag_results: Optional[list[dict]]
    simple_response: Optional[str]

    # ---- Error Handling ----
    error: Optional[str]

    # ---- CopilotKit Integration ----
    copilotkit: Optional[dict]  # Inherited context from CopilotKitState


# ============================================
# Output State (limits what gets streamed to UI)
# ============================================
class AdaptiveAgentOutput(TypedDict):
    """
    Output state schema - only these fields are included in StateSnapshotEvents.

    This prevents intermediate analysis data (safety_assessment, issue_classification, etc.)
    from being shown as raw JSON to users during processing.
    """
    messages: Annotated[list[BaseMessage], operator.add]
