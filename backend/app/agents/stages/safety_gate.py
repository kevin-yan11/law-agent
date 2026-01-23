"""Stage 0: Safety Gate - Detects high-risk situations requiring escalation."""

from langchain_core.messages import AIMessage

from app.agents.adaptive_state import AdaptiveAgentState
from app.agents.routers.safety_router import get_safety_router
from app.config import logger


async def safety_gate_node(state: AdaptiveAgentState) -> dict:
    """
    Stage 0: Safety assessment.

    This node always runs first to detect high-risk situations that need
    immediate professional help rather than AI legal information.

    High-risk situations include:
    - Criminal charges or police involvement
    - Family violence or personal safety concerns
    - Urgent court deadlines
    - Child welfare emergencies
    - Mental health crises

    Returns:
        dict with safety_assessment and updated stage tracking
    """
    logger.info("Stage 0: Safety Gate - Assessing query for high-risk indicators")

    router = get_safety_router()
    assessment = await router.assess(
        query=state.get("current_query", ""),
        user_state=state.get("user_state"),
    )

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("safety_gate")

    return {
        "safety_assessment": assessment,
        "current_stage": "safety_gate",
        "stages_completed": stages_completed,
    }


def route_after_safety(state: AdaptiveAgentState) -> str:
    """
    Route based on safety assessment result.

    Args:
        state: Current agent state with safety_assessment populated

    Returns:
        "escalate" if high-risk detected, "continue" otherwise
    """
    assessment = state.get("safety_assessment")

    if assessment and assessment.get("requires_escalation"):
        logger.info(
            f"Routing to ESCALATE: {assessment.get('risk_category')} detected"
        )
        return "escalate"

    logger.info("Safety check passed, routing to continue")
    return "continue"


def format_escalation_response(state: AdaptiveAgentState) -> dict:
    """
    Format a response for high-risk escalation scenarios.

    Creates a compassionate, informative message directing the user to
    appropriate crisis resources while acknowledging their situation.

    Returns:
        dict with messages containing the escalation response
    """
    assessment = state.get("safety_assessment", {})
    risk_category = assessment.get("risk_category", "unknown")
    resources = assessment.get("recommended_resources", [])

    # Category-specific opening messages
    category_messages = {
        "criminal": (
            "I understand you may be facing criminal charges or police involvement. "
            "This is a serious matter that requires professional legal representation."
        ),
        "family_violence": (
            "I'm concerned about your safety. If you're experiencing family violence, "
            "please know that help is available and you don't have to face this alone."
        ),
        "urgent_deadline": (
            "I can see you're dealing with an urgent legal deadline. "
            "Time-sensitive legal matters require immediate professional attention."
        ),
        "child_welfare": (
            "Matters involving children's safety and welfare are extremely serious. "
            "It's important to get professional support right away."
        ),
        "suicide_self_harm": (
            "I'm really concerned about what you've shared. Your wellbeing matters, "
            "and there are people who can help you through this difficult time."
        ),
    }

    opening = category_messages.get(
        risk_category,
        "I want to make sure you get the right support for your situation."
    )

    # Format resources
    resource_lines = []
    for resource in resources:
        line = f"**{resource['name']}**"
        if resource.get("phone"):
            line += f" - {resource['phone']}"
        if resource.get("description"):
            line += f"\n  _{resource['description']}_"
        if resource.get("url"):
            line += f"\n  {resource['url']}"
        resource_lines.append(line)

    resources_text = "\n\n".join(resource_lines) if resource_lines else ""

    # Build full message
    message_parts = [
        opening,
        "",
        "**I strongly recommend contacting these services for immediate help:**",
        "",
        resources_text,
        "",
        "---",
        "",
        "These services are free and confidential. They can provide the urgent, "
        "professional support that I, as an AI assistant, cannot offer.",
        "",
        "If you have other legal questions that aren't urgent safety matters, "
        "I'm still here to help with general legal information."
    ]

    message = "\n".join(message_parts)

    stages_completed = state.get("stages_completed", []).copy()
    stages_completed.append("escalation_response")

    return {
        "messages": [AIMessage(content=message)],
        "current_stage": "escalation_response",
        "stages_completed": stages_completed,
    }
