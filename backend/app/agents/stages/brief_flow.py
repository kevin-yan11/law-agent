"""Brief generation flow for conversational mode.

User-triggered brief generation that:
1. Analyzes conversation to extract facts and identify gaps
2. Asks targeted follow-up questions if info is missing
3. Generates a comprehensive lawyer brief when ready

This is Phase 3 of conversational mode - activated when user clicks "Generate Brief".
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.agents.conversational_state import ConversationalState
from app.agents.utils import get_internal_llm_config
from app.config import logger


# ============================================
# Skip Response Detection
# ============================================

SKIP_PHRASES = [
    "i don't know",
    "i dont know",
    "not sure",
    "skip",
    "i'm not certain",
    "im not certain",
    "no idea",
    "unsure",
    "don't know",
    "dont know",
    "can't remember",
    "cant remember",
    "not certain",
]


def _detect_skip_response(message: str) -> bool:
    """Check if the user's message indicates they want to skip/don't know."""
    if not message:
        return False
    message_lower = message.lower().strip()
    return any(phrase in message_lower for phrase in SKIP_PHRASES)


def _detect_generate_now(message: str) -> bool:
    """Check if user wants to generate the brief immediately."""
    if not message:
        return False
    message_lower = message.lower().strip()
    generate_phrases = ["generate brief now", "generate now", "just generate", "skip all"]
    return any(phrase in message_lower for phrase in generate_phrases)


# ============================================
# Schemas for LLM Structured Output
# ============================================

class ExtractedFacts(BaseModel):
    """Facts extracted from conversation history."""
    legal_area: str = Field(
        description="Primary legal area (tenancy, employment, family, consumer, criminal, general)"
    )
    situation_summary: str = Field(
        description="Brief summary of the user's legal situation"
    )
    key_facts: list[str] = Field(
        default_factory=list,
        description="Key facts established in the conversation"
    )
    parties_involved: list[str] = Field(
        default_factory=list,
        description="Parties mentioned (landlord, employer, spouse, etc.)"
    )
    timeline_events: list[str] = Field(
        default_factory=list,
        description="Timeline of events if mentioned"
    )
    documents_mentioned: list[str] = Field(
        default_factory=list,
        description="Any documents or evidence mentioned"
    )
    user_goals: list[str] = Field(
        default_factory=list,
        description="What the user wants to achieve"
    )
    missing_critical_info: list[str] = Field(
        default_factory=list,
        description="Critical information still missing to provide a useful brief"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in understanding the situation (0.0-1.0)"
    )


class FollowUpQuestions(BaseModel):
    """Targeted questions to fill information gaps."""
    questions: list[str] = Field(
        min_length=1,
        max_length=3,
        description="1-3 targeted questions to ask the user"
    )
    question_context: str = Field(
        description="Brief explanation of why these questions are needed"
    )


class ConversationalBrief(BaseModel):
    """Comprehensive lawyer brief generated from conversation."""
    executive_summary: str = Field(
        description="1-2 sentence summary of the matter"
    )
    legal_area: str = Field(
        description="Primary legal area this falls under"
    )
    jurisdiction: str = Field(
        description="Relevant Australian jurisdiction"
    )
    situation_narrative: str = Field(
        description="Clear narrative of the client's situation"
    )
    key_facts: list[str] = Field(
        description="Established facts"
    )
    fact_gaps: list[str] = Field(
        description="Information still unknown or unclear"
    )
    parties: list[str] = Field(
        description="Parties involved"
    )
    documents_evidence: list[str] = Field(
        description="Documents or evidence available or mentioned"
    )
    client_goals: list[str] = Field(
        description="What the client wants to achieve"
    )
    potential_issues: list[str] = Field(
        description="Legal issues the lawyer should consider"
    )
    questions_for_lawyer: list[str] = Field(
        description="Specific questions the client should discuss with lawyer"
    )
    urgency_level: Literal["urgent", "standard", "low_priority"] = Field(
        description="How urgently the client should see a lawyer"
    )
    urgency_reason: str = Field(
        description="Brief explanation of urgency level"
    )


# ============================================
# Prompts
# ============================================

FACT_EXTRACTION_PROMPT = """You are analyzing a conversation between a user and a legal assistant to extract facts for a lawyer brief.

## Your Task

Extract all relevant facts from the conversation that would help a lawyer understand:
1. What the legal situation is
2. Who is involved
3. What happened and when
4. What documents or evidence exist
5. What the user wants

## Critical Info That Must Be Known

For a useful lawyer brief, we need at minimum:
- The general nature of the legal problem
- The user's role in the situation
- What outcome the user wants
- Any urgent deadlines or time pressures

If these are unclear, list them in missing_critical_info.

## Conversation History

{conversation}

## User's State/Territory

{user_state}

Extract the facts carefully. If something is implied but not stated, note it as uncertain."""


FOLLOW_UP_PROMPT = """Based on the conversation analysis, you need to ask the user some follow-up questions before generating their lawyer brief.

## What We Know

{situation_summary}

## Missing Information

{missing_info}

## Your Task

Generate 1-3 targeted questions that will:
1. Fill the most critical gaps
2. Be conversational and not feel like an interrogation
3. Help generate a useful lawyer brief

Keep questions focused and practical. Don't ask about irrelevant details.

Ask the questions naturally, as a helpful assistant would."""


BRIEF_GENERATION_PROMPT = """You are generating a comprehensive lawyer brief based on the conversation between a user and a legal assistant.

## User's State/Territory
{user_state}

## Conversation History
{conversation}

## Extracted Facts
{extracted_facts}

## Your Task

Generate a professional, structured brief that a lawyer can use to quickly understand:
1. What this case is about
2. Key facts and timeline
3. Who is involved
4. What documents exist
5. What the client wants
6. What questions the client should discuss with the lawyer

## Urgency Guidelines

**Urgent:**
- Court/tribunal deadlines within 14 days
- Limitation periods about to expire
- Risk of eviction, termination, or harm
- Criminal charges pending
- Family violence or safety concerns

**Standard:**
- Active disputes requiring resolution
- Deadlines within 1-3 months
- Complex matters needing analysis

**Low Priority:**
- Information gathering stage
- No immediate deadlines
- Preventative advice sought

Be thorough but concise. The brief should help a lawyer quickly understand the situation without reading the entire conversation."""


# ============================================
# Required Info by Legal Area
# ============================================

REQUIRED_INFO_BY_AREA = {
    "tenancy": [
        "type of tenancy (residential, commercial)",
        "lease status (signed, verbal, expired)",
        "issue (rent, repairs, eviction, bond, etc.)",
        "other party (landlord, agent, roommate)",
    ],
    "employment": [
        "employment type (full-time, part-time, casual, contractor)",
        "issue (dismissal, wages, discrimination, injury, etc.)",
        "employer relationship (current, former, potential)",
        "length of employment if relevant",
    ],
    "family": [
        "relationship type (marriage, de facto, etc.)",
        "issue (separation, children, property, violence)",
        "children involved (yes/no)",
        "current living situation",
    ],
    "consumer": [
        "product or service involved",
        "issue (refund, warranty, scam, etc.)",
        "value of transaction",
        "business or seller involved",
    ],
    "criminal": [
        "type of matter (charged, accused, victim, witness)",
        "nature of alleged offense",
        "court involvement (yes/no, stage)",
        "representation status",
    ],
    "general": [
        "nature of legal issue",
        "desired outcome",
        "any deadlines or urgency",
    ],
}


# ============================================
# Node Functions
# ============================================

async def brief_check_info_node(
    state: ConversationalState,
    config: RunnableConfig,
) -> dict:
    """
    Analyze conversation to extract facts and identify information gaps.

    This node handles multiple scenarios:
    1. Initial brief trigger - analyze conversation, identify gaps
    2. User answered a question - check if more pending questions, else re-analyze
    3. User said "I don't know" - skip current question, continue with next
    4. User said "Generate now" - mark complete to generate with available info
    5. Empty conversation - start full intake flow

    Args:
        state: Current conversation state
        config: LangGraph config

    Returns:
        dict with brief_facts_collected, brief_missing_info, brief_unknown_info, brief_info_complete
    """
    messages = state.get("messages", [])
    user_state = state.get("user_state", "Not specified")
    current_query = state.get("current_query", "")
    existing_missing = state.get("brief_missing_info") or []
    existing_unknown = state.get("brief_unknown_info") or []
    pending_questions = state.get("brief_pending_questions") or []

    logger.info(f"Brief check: analyzing {len(messages)} messages, pending_questions={len(pending_questions)}")

    # Check if user wants to generate immediately
    if _detect_generate_now(current_query):
        logger.info("User requested immediate brief generation")
        return {
            "brief_info_complete": True,
            "brief_pending_questions": [],  # Clear pending questions
        }

    # Check if user said "I don't know" to the previous question
    if _detect_skip_response(current_query):
        # If we have pending questions, just continue to next one
        # If we have missing info tracked, move first item to unknown
        if existing_missing:
            skipped_item = existing_missing[0]
            new_missing = existing_missing[1:]
            new_unknown = existing_unknown + [skipped_item]
            logger.info(f"User skipped question, moved '{skipped_item}' to unknown")
        else:
            new_missing = existing_missing
            new_unknown = existing_unknown

        # Check if there are more pending questions
        if pending_questions:
            # More questions to ask - don't mark complete yet
            logger.info(f"Skipped, but {len(pending_questions)} questions still pending")
            return {
                "brief_missing_info": new_missing,
                "brief_unknown_info": new_unknown,
                "brief_info_complete": False,
            }
        else:
            # No more pending questions - check if we need to re-analyze
            is_complete = len(new_missing) == 0
            return {
                "brief_missing_info": new_missing,
                "brief_unknown_info": new_unknown,
                "brief_info_complete": is_complete,
            }

    # If there are still pending questions from previous round, continue asking
    # (user answered the last question, just move to next one)
    if pending_questions:
        logger.info(f"User answered question, {len(pending_questions)} questions still pending")
        return {
            "brief_info_complete": False,
            # Keep existing state - brief_ask_questions_node will use pending_questions
        }

    # No pending questions - need to analyze conversation to extract facts
    # Count substantive messages (excluding brief trigger)
    substantive_messages = [
        m for m in messages
        if isinstance(m, HumanMessage) and "[GENERATE_BRIEF]" not in m.content
    ]
    is_empty_conversation = len(substantive_messages) < 2

    # Format conversation for analysis
    conversation = _format_conversation(messages)

    try:
        # Use internal config to suppress streaming
        internal_config = get_internal_llm_config(config)

        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        structured_llm = llm.with_structured_output(ExtractedFacts)

        facts = await structured_llm.ainvoke(
            FACT_EXTRACTION_PROMPT.format(
                conversation=conversation,
                user_state=user_state,
            ),
            config=internal_config,
        )

        # Determine if we have enough info
        missing_critical = facts.missing_critical_info
        has_enough_info = (
            facts.confidence >= 0.6
            and len(missing_critical) == 0
            and facts.legal_area != "unknown"
            and len(facts.key_facts) >= 2
        )

        logger.info(
            f"Brief facts extracted: area={facts.legal_area}, "
            f"confidence={facts.confidence:.2f}, "
            f"missing={len(missing_critical)}, complete={has_enough_info}, "
            f"empty_conversation={is_empty_conversation}"
        )

        return {
            "brief_facts_collected": facts.model_dump(),
            "brief_missing_info": missing_critical,
            "brief_unknown_info": existing_unknown,  # Preserve unknown items
            "brief_info_complete": has_enough_info,
            "brief_needs_full_intake": is_empty_conversation,
            "brief_pending_questions": [],  # Clear for fresh question generation
            "brief_current_question_index": 0,
            "brief_total_questions": 0,
        }

    except Exception as e:
        logger.error(f"Brief fact extraction error: {e}")
        return {
            "brief_facts_collected": {
                "legal_area": "general",
                "situation_summary": "Could not fully analyze conversation",
                "key_facts": [],
                "parties_involved": [],
                "timeline_events": [],
                "documents_mentioned": [],
                "user_goals": [],
                "missing_critical_info": ["Full conversation analysis failed"],
                "confidence": 0.3,
            },
            "brief_missing_info": ["Unable to complete analysis - proceeding with available info"],
            "brief_info_complete": True,  # Proceed anyway with what we have
            "brief_pending_questions": [],
        }


async def brief_ask_questions_node(
    state: ConversationalState,
    config: RunnableConfig,
) -> dict:
    """
    Ask targeted questions to fill information gaps - ONE AT A TIME.

    Called when brief_info_complete is False. Continues asking until:
    - All info gathered (or marked as unknown)
    - User requests early generation

    Questions are asked one by one with a progress indicator (e.g., "Question 1/3").

    Args:
        state: Current conversation state
        config: LangGraph config

    Returns:
        dict with messages (single question) and question tracking state
    """
    facts = state.get("brief_facts_collected", {})
    missing_info = state.get("brief_missing_info", [])
    questions_asked = state.get("brief_questions_asked", 0)
    needs_full_intake = state.get("brief_needs_full_intake", False)
    pending_questions = state.get("brief_pending_questions") or []
    current_index = state.get("brief_current_question_index", 0)
    total_questions = state.get("brief_total_questions", 0)

    logger.info(
        f"Brief questions: pending={len(pending_questions)}, "
        f"current_index={current_index}, total={total_questions}"
    )

    try:
        # If no pending questions, generate new ones
        if not pending_questions:
            # Use internal config to suppress streaming
            internal_config = get_internal_llm_config(config)

            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
            structured_llm = llm.with_structured_output(FollowUpQuestions)

            result = await structured_llm.ainvoke(
                FOLLOW_UP_PROMPT.format(
                    situation_summary=facts.get("situation_summary", "User needs legal help"),
                    missing_info="\n".join(f"- {item}" for item in missing_info[:5]),
                ),
                config=internal_config,
            )

            pending_questions = result.questions
            total_questions = len(pending_questions)
            current_index = 0

            logger.info(f"Generated {total_questions} questions for brief intake")

        # Get the next question (always index 0 since pending_questions only has remaining)
        if pending_questions:
            question = pending_questions[0]
            remaining_questions = pending_questions[1:]

            # Build the message with progress indicator
            # current_index tracks which question we're on in the original sequence
            progress = f"**Question {current_index + 1}/{total_questions}**"

            if needs_full_intake and questions_asked == 0 and current_index == 0:
                # First question with empty conversation - add friendly intro
                question_text = (
                    "I need a bit more information to prepare your brief. "
                    "I'll ask you a few questions - feel free to say \"I don't know\" if you're unsure.\n\n"
                    f"{progress}\n\n{question}"
                )
            else:
                question_text = f"{progress}\n\n{question}"

            return {
                "messages": [AIMessage(content=question_text)],
                "brief_questions_asked": questions_asked + 1,
                "brief_pending_questions": remaining_questions,
                "brief_current_question_index": current_index + 1,
                "brief_total_questions": total_questions,
                "quick_replies": ["I don't know", "Generate brief now"],
            }
        else:
            # No more questions - should not reach here normally
            logger.warning("No more questions but brief_ask_questions_node called")
            return {
                "brief_info_complete": True,
                "brief_pending_questions": [],
            }

    except Exception as e:
        logger.error(f"Brief question generation error: {e}")
        # If question generation fails, proceed with brief generation
        return {
            "messages": [AIMessage(content="I'll prepare your brief with the information we have.")],
            "brief_questions_asked": questions_asked + 1,
            "brief_info_complete": True,  # Force completion
            "brief_pending_questions": [],
        }


async def brief_generate_node(
    state: ConversationalState,
    config: RunnableConfig,
) -> dict:
    """
    Generate the comprehensive lawyer brief.

    Called when we have enough information (brief_info_complete=True)
    or after maximum question rounds.

    Args:
        state: Current conversation state
        config: LangGraph config

    Returns:
        dict with messages (formatted brief) and mode reset to "chat"
    """
    messages = state.get("messages", [])
    user_state = state.get("user_state", "Not specified")
    facts = state.get("brief_facts_collected", {})
    unknown_info = state.get("brief_unknown_info") or []

    logger.info(f"Brief generation: creating comprehensive brief, unknown_items={len(unknown_info)}")

    # Format conversation and facts
    conversation = _format_conversation(messages)
    facts_text = _format_facts_for_prompt(facts)

    try:
        # Use internal config to suppress streaming
        internal_config = get_internal_llm_config(config)

        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        structured_llm = llm.with_structured_output(ConversationalBrief)

        brief = await structured_llm.ainvoke(
            BRIEF_GENERATION_PROMPT.format(
                user_state=user_state,
                conversation=conversation,
                extracted_facts=facts_text,
            ),
            config=internal_config,
        )

        # Format brief as readable message (include unknown items)
        formatted_brief = _format_brief_as_message(brief, user_state, unknown_info)

        logger.info(
            f"Brief generated: area={brief.legal_area}, "
            f"urgency={brief.urgency_level}"
        )

        return {
            "messages": [AIMessage(content=formatted_brief)],
            "mode": "chat",  # Return to chat mode
            "quick_replies": [
                "Find me a lawyer",
                "What should I ask the lawyer?",
                "Explain the urgency",
            ],
            "suggest_lawyer": True,
        }

    except Exception as e:
        logger.error(f"Brief generation error: {e}")
        return {
            "messages": [AIMessage(
                content="I apologize, but I encountered an issue generating your brief. "
                "Please try again, or I can help you find a lawyer directly."
            )],
            "mode": "chat",
            "quick_replies": ["Find me a lawyer", "Try again", "What can you help with?"],
        }


# ============================================
# Helper Functions
# ============================================

def _format_conversation(messages: list, max_messages: int = 20) -> str:
    """Format conversation messages for LLM context."""
    formatted = []
    for msg in messages[-max_messages:]:
        if isinstance(msg, HumanMessage):
            formatted.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            formatted.append(f"Assistant: {msg.content}")
    return "\n\n".join(formatted)


def _format_facts_for_prompt(facts: dict) -> str:
    """Format extracted facts for the brief generation prompt."""
    parts = []

    if facts.get("legal_area"):
        parts.append(f"**Legal Area:** {facts['legal_area']}")

    if facts.get("situation_summary"):
        parts.append(f"**Summary:** {facts['situation_summary']}")

    if facts.get("key_facts"):
        parts.append("**Key Facts:**")
        for fact in facts["key_facts"]:
            parts.append(f"- {fact}")

    if facts.get("parties_involved"):
        parts.append(f"**Parties:** {', '.join(facts['parties_involved'])}")

    if facts.get("timeline_events"):
        parts.append("**Timeline:**")
        for event in facts["timeline_events"]:
            parts.append(f"- {event}")

    if facts.get("documents_mentioned"):
        parts.append(f"**Documents:** {', '.join(facts['documents_mentioned'])}")

    if facts.get("user_goals"):
        parts.append("**User Goals:**")
        for goal in facts["user_goals"]:
            parts.append(f"- {goal}")

    return "\n".join(parts)


def _format_brief_as_message(
    brief: ConversationalBrief,
    user_state: str,
    unknown_info: list[str] | None = None,
) -> str:
    """Format the brief as a readable chat message.

    Args:
        brief: The generated brief
        user_state: User's Australian state/territory
        unknown_info: Items the user explicitly said they don't know
    """
    urgency_emoji = {
        "urgent": "🔴",
        "standard": "🟡",
        "low_priority": "🟢",
    }

    lines = [
        "# Lawyer Brief",
        "",
        f"## Summary",
        f"{brief.executive_summary}",
        "",
        f"**Urgency:** {urgency_emoji.get(brief.urgency_level, '⚪')} {brief.urgency_level.replace('_', ' ').title()}",
        f"*{brief.urgency_reason}*",
        "",
        f"**Legal Area:** {brief.legal_area.title()}",
        f"**Jurisdiction:** {brief.jurisdiction or user_state or 'Australia'}",
        "",
        "---",
        "",
        "## Your Situation",
        brief.situation_narrative,
        "",
    ]

    if brief.key_facts:
        lines.append("## Key Facts")
        for fact in brief.key_facts:
            lines.append(f"- {fact}")
        lines.append("")

    if brief.parties:
        lines.append(f"**Parties Involved:** {', '.join(brief.parties)}")
        lines.append("")

    if brief.documents_evidence:
        lines.append("## Documents & Evidence")
        for doc in brief.documents_evidence:
            lines.append(f"- {doc}")
        lines.append("")

    if brief.client_goals:
        lines.append("## Your Goals")
        for goal in brief.client_goals:
            lines.append(f"- {goal}")
        lines.append("")

    # Show items user explicitly said they don't know
    if unknown_info:
        lines.append("## Information Not Provided")
        lines.append("*You indicated you don't know these details - the lawyer may need to discuss:*")
        for item in unknown_info:
            lines.append(f"- {item}")
        lines.append("")

    if brief.fact_gaps:
        lines.append("## Information to Gather")
        lines.append("*These are things the lawyer may ask about:*")
        for gap in brief.fact_gaps:
            lines.append(f"- {gap}")
        lines.append("")

    if brief.potential_issues:
        lines.append("## Potential Legal Issues")
        for issue in brief.potential_issues:
            lines.append(f"- {issue}")
        lines.append("")

    if brief.questions_for_lawyer:
        lines.append("## Questions for Your Lawyer")
        for q in brief.questions_for_lawyer:
            lines.append(f"- {q}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "*This brief summarizes our conversation. Share it with a lawyer for professional advice.*",
    ])

    return "\n".join(lines)
