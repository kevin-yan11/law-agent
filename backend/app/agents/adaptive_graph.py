"""Adaptive depth legal workflow graph using LangGraph.

This module implements the 8-stage professional legal workflow with adaptive depth
routing - simple queries stay fast, complex queries get full analysis.

Architecture:
┌─────────────────────────────────────────────────────────────┐
│  [0] SAFETY GATE (always runs)                              │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         ESCALATE        SIMPLE PATH     COMPLEX PATH
        (high-risk)      (~3k tokens)    (~9k tokens)
              │               │               │
              ▼               ▼               ▼
         Crisis           [1] Issue ID    [1] Issue ID
         Resources        [2] Jurisdiction [2] Jurisdiction
                          [7] Strategy    [3] Fact Structure
                                          [4] Elements Map
                                          [5] Case Precedent
                                          [6] Risk Analysis
                                          [7] Strategy
                                          [8] Escalation Brief
"""

import uuid
from typing import Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.adaptive_state import AdaptiveAgentState, RoutingDecision
from app.agents.stages import (
    safety_gate_node,
    route_after_safety,
    format_escalation_response,
    issue_identification_node,
    jurisdiction_node,
    fact_structuring_node,
    legal_elements_node,
    case_precedent_node,
    risk_analysis_node,
)
from app.agents.stages.strategy import strategy_node
from app.agents.stages.escalation_brief import escalation_brief_node
from app.agents.routers.complexity_router import route_by_complexity
from app.config import logger


# ============================================
# Response Generation
# ============================================

SIMPLE_RESPONSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are AusLaw AI, an Australian legal assistant. Generate a helpful response based on the analysis provided.

## Guidelines
1. Be clear, concise, and professional
2. Use plain language accessible to non-lawyers
3. Structure your response with clear headings where appropriate
4. Include specific recommendations from the strategy analysis
5. Always end with the disclaimer about seeking professional legal advice

## Analysis Context

**Legal Area:** {legal_area}
**Jurisdiction:** {jurisdiction}

**Issue Summary:**
{issue_summary}

**Recommended Strategy:**
{strategy_summary}

**Immediate Actions:**
{immediate_actions}

**Key Decision Factors:**
{decision_factors}

## User's Original Question
{query}
"""),
    ("human", "Generate a helpful, conversational response based on the analysis above.")
])

COMPLEX_RESPONSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are AusLaw AI, an Australian legal assistant. Generate a comprehensive response based on the detailed analysis provided.

## Guidelines
1. Be thorough but clear and professional
2. Use plain language accessible to non-lawyers
3. Structure your response with clear headings
4. Reference key facts, legal elements, and precedents where relevant
5. Highlight risks and important considerations
6. Include specific recommendations from the strategy analysis
7. Always end with the disclaimer about seeking professional legal advice

## Comprehensive Analysis Context

**Legal Area:** {legal_area} ({sub_category})
**Jurisdiction:** {jurisdiction}

**Case Summary:**
{narrative_summary}

**Key Facts:**
{key_facts}

**Legal Position:**
- Viability: {viability}
- Elements satisfied: {elements_status}
- Applicable law: {applicable_law}

**Risk Assessment:**
- Overall risk level: {risk_level}
- Key risks: {risks}
- Time sensitivity: {time_sensitivity}

**Relevant Precedents:**
{precedent_summary}

**Recommended Strategy:**
{strategy_summary}

**Alternative Options:**
{alternatives}

**Immediate Actions:**
{immediate_actions}

## User's Original Question
{query}
"""),
    ("human", "Generate a comprehensive, well-structured response based on the analysis above.")
])


class ResponseGenerator:
    """Generates final user-facing responses from analysis."""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
        self.simple_chain = SIMPLE_RESPONSE_PROMPT | self.llm
        self.complex_chain = COMPLEX_RESPONSE_PROMPT | self.llm

    async def generate_simple_response(self, state: AdaptiveAgentState) -> str:
        """Generate response for simple path."""
        issue = state.get("issue_classification", {})
        primary = issue.get("primary_issue", {})

        jurisdiction = state.get("jurisdiction_result", {})

        strategy = state.get("strategy_recommendation", {})
        recommended = strategy.get("recommended_strategy", {})
        immediate_actions = strategy.get("immediate_actions", [])
        decision_factors = strategy.get("decision_factors", [])

        result = await self.simple_chain.ainvoke({
            "legal_area": primary.get("area", "general"),
            "jurisdiction": jurisdiction.get("primary_jurisdiction", "Australian"),
            "issue_summary": primary.get("description", "Legal matter"),
            "strategy_summary": f"{recommended.get('name', 'N/A')}: {recommended.get('description', 'N/A')}",
            "immediate_actions": "\n".join(f"- {a}" for a in immediate_actions) or "No specific actions identified",
            "decision_factors": "\n".join(f"- {f}" for f in decision_factors) or "Consider seeking professional advice",
            "query": state.get("current_query", ""),
        })

        return result.content

    async def generate_complex_response(self, state: AdaptiveAgentState) -> str:
        """Generate response for complex path."""
        issue = state.get("issue_classification", {})
        primary = issue.get("primary_issue", {})

        jurisdiction = state.get("jurisdiction_result", {})

        fact_structure = state.get("fact_structure", {})
        key_facts = fact_structure.get("key_facts", [])

        elements = state.get("elements_analysis", {})

        risk = state.get("risk_assessment", {})
        risks = risk.get("risks", [])

        precedents = state.get("precedent_analysis", {})
        matching_cases = precedents.get("matching_cases", [])

        strategy = state.get("strategy_recommendation", {})
        recommended = strategy.get("recommended_strategy", {})
        alternatives = strategy.get("alternative_strategies", [])
        immediate_actions = strategy.get("immediate_actions", [])

        # Format precedents
        precedent_summary = "No relevant precedents found"
        if matching_cases:
            lines = []
            for case in matching_cases[:3]:
                outcome = case.get("outcome_for_similar_party", "unknown")
                lines.append(f"- {case.get('case_name', 'Unknown')} ({case.get('year', 'N/A')}): {outcome} - {case.get('key_holding', 'N/A')[:100]}")
            precedent_summary = "\n".join(lines)

        # Format risks
        risks_summary = "No significant risks identified"
        if risks:
            risks_summary = "\n".join(f"- [{r.get('severity', 'N/A')}/{r.get('likelihood', 'N/A')}] {r.get('description', 'N/A')}" for r in risks[:5])

        # Format alternatives
        alternatives_summary = "No alternatives provided"
        if alternatives:
            alternatives_summary = "\n".join(f"- {a.get('name', 'N/A')}: {a.get('description', 'N/A')[:100]}" for a in alternatives[:3])

        result = await self.complex_chain.ainvoke({
            "legal_area": primary.get("area", "general"),
            "sub_category": primary.get("sub_category", "general"),
            "jurisdiction": jurisdiction.get("primary_jurisdiction", "Australian"),
            "narrative_summary": fact_structure.get("narrative_summary", "No summary available"),
            "key_facts": "\n".join(f"- {f}" for f in key_facts[:10]) or "No key facts identified",
            "viability": elements.get("viability_assessment", "unknown"),
            "elements_status": f"{elements.get('elements_satisfied', 0)}/{elements.get('elements_total', 0)}",
            "applicable_law": elements.get("applicable_law", "Not determined"),
            "risk_level": risk.get("overall_risk_level", "unknown"),
            "risks": risks_summary,
            "time_sensitivity": risk.get("time_sensitivity") or "No specific deadlines identified",
            "precedent_summary": precedent_summary,
            "strategy_summary": f"**{recommended.get('name', 'N/A')}**: {recommended.get('description', 'N/A')}\n- Success likelihood: {recommended.get('success_likelihood', 'N/A')}\n- Estimated cost: {recommended.get('estimated_cost', 'N/A')}\n- Timeline: {recommended.get('estimated_timeline', 'N/A')}",
            "alternatives": alternatives_summary,
            "immediate_actions": "\n".join(f"- {a}" for a in immediate_actions) or "No specific actions identified",
            "query": state.get("current_query", ""),
        })

        return result.content


# Singleton
_response_generator: ResponseGenerator | None = None


def get_response_generator() -> ResponseGenerator:
    """Get or create singleton ResponseGenerator."""
    global _response_generator
    if _response_generator is None:
        _response_generator = ResponseGenerator()
    return _response_generator


# ============================================
# Graph Nodes
# ============================================

async def initialize_node(state: AdaptiveAgentState) -> dict:
    """Initialize state with session ID and extract query from messages."""
    messages = state.get("messages", [])
    current_query = ""

    # Extract the latest human message as the current query
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            current_query = msg.content
            break

    session_id = state.get("session_id") or str(uuid.uuid4())

    logger.info(f"Initializing adaptive agent: session={session_id[:8]}, query_length={len(current_query)}")

    return {
        "session_id": session_id,
        "current_query": current_query,
        "current_stage": "initialize",
        "stages_completed": ["initialize"],
    }


async def complexity_routing_node(state: AdaptiveAgentState) -> dict:
    """Determine whether to use simple or complex path."""
    complexity = await route_by_complexity(state)

    routing: RoutingDecision = {
        "path": complexity,
        "reasoning": f"Classified as {complexity} based on query analysis",
        "skip_stages": [] if complexity == "complex" else [
            "fact_structuring",
            "legal_elements",
            "case_precedent",
            "risk_analysis",
            "escalation_brief",
        ],
    }

    logger.info(f"Complexity routing: {complexity}")

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("complexity_routing")

    return {
        "routing_decision": routing,
        "current_stage": "complexity_routing",
        "stages_completed": stages_completed,
    }


def route_by_path(state: AdaptiveAgentState) -> Literal["simple", "complex"]:
    """Route based on complexity decision."""
    routing = state.get("routing_decision", {})
    return routing.get("path", "simple")


async def simple_response_node(state: AdaptiveAgentState) -> dict:
    """Generate response for simple path."""
    logger.info("Generating simple path response")

    generator = get_response_generator()
    response = await generator.generate_simple_response(state)

    # Add disclaimer
    response += "\n\n---\n\n_This is general information, not legal advice. Please consult a qualified lawyer for your specific situation._"

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("simple_response")

    return {
        "simple_response": response,
        "messages": [AIMessage(content=response)],
        "current_stage": "simple_response",
        "stages_completed": stages_completed,
    }


async def complex_response_node(state: AdaptiveAgentState) -> dict:
    """Generate response for complex path."""
    logger.info("Generating complex path response")

    generator = get_response_generator()
    response = await generator.generate_complex_response(state)

    # Add disclaimer
    response += "\n\n---\n\n_This is general information, not legal advice. For your specific situation, consider consulting a qualified lawyer. You can use the 'Find Lawyer' feature to search for specialists in your area._"

    # Reference the escalation brief if generated
    brief = state.get("escalation_brief")
    if brief:
        response += f"\n\n_A detailed brief (ID: {brief.get('brief_id', 'N/A')[:8]}) has been prepared that can be shared with a lawyer for faster consultation._"

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("complex_response")

    return {
        "messages": [AIMessage(content=response)],
        "current_stage": "complex_response",
        "stages_completed": stages_completed,
    }


# ============================================
# Graph Definition
# ============================================

def build_adaptive_graph():
    """Build the adaptive depth legal workflow graph."""
    workflow = StateGraph(AdaptiveAgentState)

    # Add all nodes
    workflow.add_node("initialize", initialize_node)
    workflow.add_node("safety_gate", safety_gate_node)
    workflow.add_node("escalation_response", format_escalation_response)
    workflow.add_node("issue_identification", issue_identification_node)
    workflow.add_node("complexity_routing", complexity_routing_node)
    workflow.add_node("jurisdiction", jurisdiction_node)

    # Simple path nodes
    workflow.add_node("simple_strategy", strategy_node)
    workflow.add_node("simple_response", simple_response_node)

    # Complex path nodes
    workflow.add_node("fact_structuring", fact_structuring_node)
    workflow.add_node("legal_elements", legal_elements_node)
    workflow.add_node("case_precedent", case_precedent_node)
    workflow.add_node("risk_analysis", risk_analysis_node)
    workflow.add_node("complex_strategy", strategy_node)
    workflow.add_node("escalation_brief", escalation_brief_node)
    workflow.add_node("complex_response", complex_response_node)

    # Define edges
    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "safety_gate")

    # Safety gate routing
    workflow.add_conditional_edges(
        "safety_gate",
        route_after_safety,
        {
            "escalate": "escalation_response",
            "continue": "issue_identification",
        }
    )
    workflow.add_edge("escalation_response", END)

    # Issue identification to complexity routing
    workflow.add_edge("issue_identification", "complexity_routing")

    # Complexity routing determines path
    workflow.add_conditional_edges(
        "complexity_routing",
        route_by_path,
        {
            "simple": "jurisdiction",
            "complex": "jurisdiction",
        }
    )

    # After jurisdiction, split by path
    def route_after_jurisdiction(state: AdaptiveAgentState) -> Literal["simple_path", "complex_path"]:
        routing = state.get("routing_decision", {})
        path = routing.get("path", "simple")
        return "simple_path" if path == "simple" else "complex_path"

    workflow.add_conditional_edges(
        "jurisdiction",
        route_after_jurisdiction,
        {
            "simple_path": "simple_strategy",
            "complex_path": "fact_structuring",
        }
    )

    # Simple path
    workflow.add_edge("simple_strategy", "simple_response")
    workflow.add_edge("simple_response", END)

    # Complex path
    workflow.add_edge("fact_structuring", "legal_elements")
    workflow.add_edge("legal_elements", "case_precedent")
    workflow.add_edge("case_precedent", "risk_analysis")
    workflow.add_edge("risk_analysis", "complex_strategy")
    workflow.add_edge("complex_strategy", "escalation_brief")
    workflow.add_edge("escalation_brief", "complex_response")
    workflow.add_edge("complex_response", END)

    return workflow


def create_adaptive_agent():
    """Create the compiled adaptive agent graph with memory."""
    workflow = build_adaptive_graph()
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# Singleton compiled graph
_adaptive_graph = None


def get_adaptive_graph():
    """Get or create the singleton adaptive graph."""
    global _adaptive_graph
    if _adaptive_graph is None:
        _adaptive_graph = create_adaptive_agent()
    return _adaptive_graph
