"""Deep analysis flow nodes for conversational mode.

These nodes handle the optional deep analysis feature:
1. Offering analysis when readiness is high
2. Running the analysis pipeline
3. Formatting results conversationally
"""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.agents.conversational_state import ConversationalState
from app.agents.analysis import organize_facts, analyze_risks, recommend_strategy
from app.config import logger


# Trigger for accepting analysis (sent from frontend or natural language)
ANALYSIS_ACCEPT_TRIGGERS = ["yes", "sure", "ok", "analyze", "do it", "please", "go ahead"]
ANALYSIS_DECLINE_TRIGGERS = ["no", "not now", "skip", "later", "don't", "nope"]


async def analysis_offer_node(state: ConversationalState) -> dict:
    """
    Offer deep analysis to the user.

    This node generates a message asking if the user wants a deeper
    analysis of their situation. The graph then ENDs, waiting for
    the user's response in the next message.
    """
    logger.info("Offering deep analysis to user")

    offer_message = AIMessage(content=(
        "I've gathered quite a bit about your situation. Would you like me to do a "
        "**deeper analysis**? This would organize the facts, identify strengths and "
        "weaknesses in your position, and suggest concrete next steps.\n\n"
        "Just say **yes** to continue, or **no** to keep chatting."
    ))

    return {
        "messages": [offer_message],
        "analysis_offered": True,
        "analysis_pending_response": True,  # Wait for user's response on next message
        "quick_replies": ["Yes, analyze my situation", "No, keep chatting"],
    }


async def deep_analysis_node(
    state: ConversationalState,
    config: RunnableConfig,
) -> dict:
    """
    Run the deep analysis pipeline.

    This executes:
    1. Fact organization (timeline, parties, evidence)
    2. Risk analysis (strengths, weaknesses)
    3. Strategy recommendation
    """
    logger.info("Running deep analysis pipeline")

    messages = state.get("messages", [])
    user_state = state.get("user_state")
    has_document = bool(state.get("uploaded_document_url"))

    try:
        # Step 1: Organize facts from conversation
        facts = await organize_facts(
            messages=messages,
            user_state=user_state,
            has_document=has_document,
            config=config,
        )

        # Step 2: Analyze risks based on facts
        risks = await analyze_risks(
            facts=facts,
            user_state=user_state,
            config=config,
        )

        # Step 3: Recommend strategy
        strategy = await recommend_strategy(
            facts=facts,
            risks=risks,
            user_state=user_state,
            config=config,
        )

        # Combine into analysis result
        analysis_result = {
            "facts": facts,
            "risks": risks,
            "strategy": strategy,
        }

        logger.info(
            f"Deep analysis complete: {len(facts['key_facts'])} key facts, "
            f"risk level={risks['overall_risk']}, "
            f"recommended={strategy['recommended']['name']}"
        )

        return {
            "analysis_result": analysis_result,
            "analysis_accepted": True,
        }

    except Exception as e:
        logger.error(f"Deep analysis error: {e}")
        return {
            "analysis_result": None,
            "analysis_accepted": True,
            "error": f"Analysis error: {str(e)}",
        }


async def analysis_response_node(state: ConversationalState) -> dict:
    """
    Format analysis results as a conversational response.

    Presents findings in a friendly, readable format rather than
    a formal legal document.
    """
    analysis_result = state.get("analysis_result")

    if not analysis_result:
        # Analysis failed
        error_message = AIMessage(content=(
            "I'm sorry, I encountered an issue while analyzing your situation. "
            "Let's continue our conversation - I can still help answer specific questions."
        ))
        return {
            "messages": [error_message],
            "quick_replies": ["What are my options?", "Find me a lawyer"],
        }

    facts = analysis_result.get("facts", {})
    risks = analysis_result.get("risks", {})
    strategy = analysis_result.get("strategy", {})

    # Build response
    response_parts = ["Based on what you've told me, here's my analysis:\n"]

    # Situation summary
    response_parts.append("## Your Situation\n")
    response_parts.append(facts.get("narrative", ""))
    response_parts.append("\n")

    # Key facts
    if facts.get("key_facts"):
        response_parts.append("**Key Facts:**\n")
        for fact in facts["key_facts"][:5]:
            response_parts.append(f"• {fact}\n")
        response_parts.append("\n")

    # Strengths
    if risks.get("strengths"):
        response_parts.append("## What's In Your Favor\n")
        for strength in risks["strengths"][:4]:
            response_parts.append(f"✓ {strength}\n")
        response_parts.append("\n")

    # Weaknesses / Risks
    if risks.get("weaknesses") or risks.get("risks"):
        response_parts.append("## Things to Be Aware Of\n")
        for weakness in risks.get("weaknesses", [])[:3]:
            response_parts.append(f"• {weakness}\n")
        for risk in risks.get("risks", [])[:2]:
            response_parts.append(f"• {risk['description']}")
            if risk.get("mitigation"):
                response_parts.append(f" — *{risk['mitigation']}*")
            response_parts.append("\n")
        response_parts.append("\n")

    # Time sensitivity
    if risks.get("time_sensitive"):
        response_parts.append(f"⏰ **Time Sensitive:** {risks['time_sensitive']}\n\n")

    # Recommended strategy
    recommended = strategy.get("recommended", {})
    if recommended:
        response_parts.append("## Recommended Next Steps\n")
        response_parts.append(f"**{recommended.get('name', 'Strategy')}**\n")
        response_parts.append(f"{recommended.get('description', '')}\n\n")

        if recommended.get("estimated_cost"):
            response_parts.append(f"💰 Estimated cost: {recommended['estimated_cost']}\n")
        if recommended.get("estimated_timeline"):
            response_parts.append(f"📅 Timeline: {recommended['estimated_timeline']}\n")
        response_parts.append("\n")

    # Immediate actions
    if strategy.get("immediate_actions"):
        response_parts.append("**What to do now:**\n")
        for i, action in enumerate(strategy["immediate_actions"][:4], 1):
            response_parts.append(f"{i}. {action}\n")
        response_parts.append("\n")

    # Alternatives
    if strategy.get("alternatives"):
        response_parts.append("**Alternative approaches:**\n")
        for alt in strategy["alternatives"][:2]:
            response_parts.append(f"• **{alt.get('name')}** — {alt.get('description', '')}\n")
        response_parts.append("\n")

    # Closing
    response_parts.append("---\n")
    response_parts.append(
        "Would you like me to help with any of these steps, or would you prefer "
        "a **formal brief** to take to a lawyer?"
    )

    response_content = "".join(response_parts)
    response_message = AIMessage(content=response_content)

    logger.info("Analysis response formatted and ready")

    return {
        "messages": [response_message],
        "quick_replies": [
            "Help with step 1",
            "Find me a lawyer",
            "Generate a brief",
            "Tell me more about risks",
        ],
        "suggest_brief": True,
    }


def route_after_chat(state: ConversationalState) -> str:
    """
    Route after chat response.

    - If analysis readiness is high (>= 0.7) and not yet offered → offer analysis
    - Otherwise → end

    Note: We ONLY use the readiness threshold, not the LLM's suggest_deep_analysis flag,
    because the LLM doesn't reliably follow scoring rules.
    """
    analysis_readiness = state.get("analysis_readiness", 0.0)
    already_offered = state.get("analysis_offered", False)

    # Offer analysis ONLY if readiness threshold is met
    # The readiness score is based on % of checklist items gathered (8 items total)
    # 0.7 = at least 5-6 items known (state, problem type, role, facts, desired outcome, etc.)
    if analysis_readiness >= 0.7 and not already_offered:
        logger.info(f"Routing to analysis offer (readiness={analysis_readiness})")
        return "offer_analysis"

    return "end"


def route_after_analysis_offer(state: ConversationalState) -> str:
    """
    Route based on user's response to analysis offer.

    Called during initialize phase when analysis_pending_response is True.
    Checks the latest message (user's response to the offer) for acceptance/decline.
    """
    messages = state.get("messages", [])

    # Find the latest user message (this is their response to the offer)
    latest_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            latest_user_msg = msg.content.lower().strip()
            break

    # Check for acceptance
    if any(trigger in latest_user_msg for trigger in ANALYSIS_ACCEPT_TRIGGERS):
        logger.info("User accepted analysis offer")
        return "accept"

    # Check for explicit decline
    if any(trigger in latest_user_msg for trigger in ANALYSIS_DECLINE_TRIGGERS):
        logger.info("User declined analysis offer")
        return "decline"

    # Default: if they said something else, treat as decline and continue normal chat
    logger.info("Unclear response to analysis offer, continuing normal chat")
    return "decline"


async def handle_analysis_response_node(state: ConversationalState) -> dict:
    """
    Handle user's response to analysis offer.

    Clears the pending flag and sets accepted status based on routing decision.
    This node is called before deep_analysis (if accepted) or before chat_response (if declined).
    """
    # Clear the pending flag - we've processed the response
    return {
        "analysis_pending_response": False,
    }
