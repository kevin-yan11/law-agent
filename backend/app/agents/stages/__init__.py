"""Stage implementations for adaptive legal agent workflow."""

from app.agents.stages.safety_gate import (
    safety_gate_node,
    route_after_safety,
    format_escalation_response,
)
from app.agents.stages.issue_identification import (
    issue_identification_node,
    get_issue_identifier,
)
from app.agents.stages.jurisdiction import (
    jurisdiction_node,
    get_jurisdiction_resolver,
)
from app.agents.stages.fact_structuring import (
    fact_structuring_node,
    get_fact_structurer,
)
from app.agents.stages.legal_elements import (
    legal_elements_node,
    get_legal_elements_analyzer,
)
from app.agents.stages.case_precedent import (
    case_precedent_node,
    get_case_precedent_analyzer,
)
from app.agents.stages.risk_analysis import (
    risk_analysis_node,
    get_risk_analyzer,
)

__all__ = [
    # Stage 0: Safety Gate
    "safety_gate_node",
    "route_after_safety",
    "format_escalation_response",
    # Stage 1: Issue Identification
    "issue_identification_node",
    "get_issue_identifier",
    # Stage 2: Jurisdiction
    "jurisdiction_node",
    "get_jurisdiction_resolver",
    # Stage 3: Fact Structuring
    "fact_structuring_node",
    "get_fact_structurer",
    # Stage 4: Legal Elements
    "legal_elements_node",
    "get_legal_elements_analyzer",
    # Stage 5: Case Precedent
    "case_precedent_node",
    "get_case_precedent_analyzer",
    # Stage 6: Risk Analysis
    "risk_analysis_node",
    "get_risk_analyzer",
]
