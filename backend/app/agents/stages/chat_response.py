"""Chat response node for conversational mode.

Generates natural, helpful responses using tools (lookup_law, find_lawyer)
when needed. Includes quick reply suggestions for smoother conversation flow.
"""

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent

from app.agents.conversational_state import ConversationalState
from app.agents.utils import get_internal_llm_config, get_chat_agent_config
from app.tools.lookup_law import lookup_law
from app.tools.find_lawyer import find_lawyer
from app.tools.analyze_document import analyze_document
from app.tools.search_case_law import search_case_law
from app.config import logger


# System prompt for CHAT MODE - natural conversation, casual Q&A
CHAT_MODE_PROMPT = """You are an Australian legal assistant having a natural, helpful conversation.
You're like a knowledgeable friend who happens to understand law - approachable, clear, and never condescending.

## How to Respond

1. **Be conversational**: Write like you're talking to a friend, not drafting a legal document. Use plain language.

2. **Be concise**: Answer the immediate question. Don't dump everything you know. If they want more detail, they'll ask.

3. **Ask follow-up questions**: If you need more info to help properly, ask ONE clear question. Don't interrogate.

4. **ALWAYS use tools for legal info**: When you need to reference specific laws, legislation, or legal information, you MUST use the lookup_law tool. NEVER make up legal information or rely on general knowledge - always verify with the database.

5. **Know your limits**: If something needs a real lawyer, say so gently. Don't pretend to give advice you're not qualified to give.

## What NOT to Do

- Don't produce lengthy analysis unless explicitly asked
- Don't use legal jargon without explaining it
- Don't be robotic or formulaic
- NEVER make up legal information - if lookup_law doesn't find it, say "I couldn't find specific legislation on this, but generally..."
- Don't overwhelm with information - keep it focused

## User Context
- State/Territory: {user_state}
- Has uploaded document: {has_document}
- Document URL: {document_url}

## Important: Ask User to Select State if Unknown
If the user's state/territory shows as "Not specified", ask them to select their state from the dropdown menu at the top of the chat. This is important because laws vary significantly between states. Say something like: "I noticed you haven't selected your state yet. Could you pick your state or territory from the dropdown at the top? Laws can vary quite a bit between states, so this helps me give you accurate information."

## Tool Usage Guidelines
- Use lookup_law when user asks about specific rights, laws, or legal requirements
- Use search_case_law when user asks about court cases, legal precedents, or how courts have ruled on specific issues
- Use find_lawyer when user asks for lawyer recommendations or says they need professional help
- Use analyze_document when the user has uploaded a document and asks you to review, analyze, or explain it. You MUST call this tool to read the document content - you cannot see the document without it. IMPORTANT: Always use the exact Document URL shown above - NEVER make up or guess a URL.
- Always pass the user's state to tools (if known)
- When results come from AustLII (source "austlii" or "austlii_case"), cite the source URL and note the user should verify on the official site

Remember: Your goal is to be helpful and informative while keeping the conversation natural and flowing."""


# System prompt for ANALYSIS MODE - natural lawyer consultation flow
ANALYSIS_MODE_PROMPT = """You are a friendly Australian legal assistant having a consultation with someone about their legal situation. Think of yourself as a knowledgeable paralegal doing an initial intake - thorough, warm, and methodical.

## How to Conduct the Consultation

### Phase 1: Understand Their Situation First
When someone describes a legal issue:
- DON'T immediately give legal advice or explain the law
- DO ask clarifying questions to fully understand:
  • What exactly happened? (specific events, dates, amounts)
  • Who is involved? (names, relationships)
  • What outcome are they hoping for?
  • What evidence or documents do they have?
- After gathering enough information, summarize: "Let me make sure I understand correctly..."
- Confirm your understanding is accurate before proceeding
- Ask ONE question at a time - don't overwhelm

### Phase 2: Explain the Law (When You Understand the Situation)
Once you have a clear picture:
- Explain what the law says in PLAIN ENGLISH - no legal jargon
- Use the lookup_law tool to find relevant legislation
- Use the search_case_law tool to find relevant court decisions and precedents
- Explain what the law says AND how courts have applied it in practice
- Reference specific cases when they strengthen or clarify the user's position
- Explain their rights and obligations clearly
- Point out the strengths in their position
- Honestly discuss weaknesses and risks they should know about
- Note any time-sensitive deadlines (e.g., limitation periods)

### Phase 3: Options & Strategy (When Asked or Natural)
Offer options when:
- User asks "what can I do?", "what are my options?", "what should I do?"
- You've explained the law and it's natural to discuss next steps
- Don't force this - let it flow from the conversation

When suggesting options, PRIORITIZE in this order:
1. FREE options first: ombudsmen, fair trading, community legal centres
2. Low-cost tribunals: NCAT (NSW), VCAT (VIC), QCAT (QLD), etc.
3. Self-help resources and guides
4. Paid lawyer ONLY when truly necessary:
   - Criminal charges involved
   - Court litigation unavoidable
   - Amount at stake > $50,000
   - Safety concerns

## Important Guidelines

**NEVER make "consult a lawyer" your default or frequent recommendation.**
It's annoying and unhelpful. Most issues can be resolved without expensive lawyers.
Only suggest professional legal help when the situation genuinely requires it.

**State/Territory is Critical**
If state/territory shows as "Not specified", ask them to select their state first.
Laws vary significantly between Australian states.

## User Context
- State/Territory: {user_state}
- Has uploaded document: {has_document}
- Document URL: {document_url}

## Tool Usage Guidelines
- Use lookup_law when you need to reference specific laws or legislation
- Use search_case_law to find relevant court decisions, tribunal rulings, and case precedents that support or clarify the legal analysis
- Use find_lawyer when user needs professional legal help
- Use analyze_document when the user has uploaded a document and asks you to review, analyze, or explain it. You MUST call this tool to read the document content - you cannot see the document without it. IMPORTANT: Always use the exact Document URL shown above - NEVER make up or guess a URL.
- When results come from AustLII (source "austlii" or "austlii_case"), cite the source URL and note the user should verify on the official site

## Your Tone
- Warm and approachable, not formal or intimidating
- Explain things like you would to a friend
- Be honest about weaknesses, but encouraging
- Empathetic - they're dealing with a real problem"""


class QuickReplyAnalysis(BaseModel):
    """Analyze the conversation to suggest quick replies."""
    quick_replies: list[str] = Field(
        default_factory=list,
        description="2-4 natural follow-up questions or responses the user might want to say"
    )
    suggest_brief: bool = Field(
        default=False,
        description="True if user's situation is complex enough to benefit from a lawyer brief"
    )


# Quick reply prompt - used for both chat and analysis modes
QUICK_REPLY_PROMPT = """Based on this conversation, suggest 2-4 quick reply options that would be natural for the user to say next.

Make them:
- Short (2-6 words each)
- Natural and conversational
- Useful for moving the conversation forward
- Diverse (different types of follow-ups)

Examples of good quick replies:
- "What are my options?"
- "How do I do that?"
- "What happens next?"
- "Can you explain more?"
- "What about costs?"
- "Generate a brief"

Also indicate if the situation seems complex enough that a formal lawyer brief would be helpful.

Current conversation:
{conversation}

Assistant's response:
{response}"""


async def generate_quick_replies(
    messages: list,
    response_content: str,
    config: RunnableConfig,
) -> QuickReplyAnalysis:
    """Generate quick reply suggestions based on conversation context."""
    try:
        # Format conversation for analysis
        conversation = ""
        for msg in messages[-6:]:  # Last 6 messages for context
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            content = msg.content if hasattr(msg, 'content') else str(msg)
            conversation += f"{role}: {content}\n"

        # Use internal config to suppress streaming (prevents raw JSON in chat)
        internal_config = get_internal_llm_config(config)

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
        structured_llm = llm.with_structured_output(QuickReplyAnalysis)

        result = await structured_llm.ainvoke(
            QUICK_REPLY_PROMPT.format(
                conversation=conversation,
                response=response_content
            ),
            config=internal_config,
        )

        return result

    except Exception as e:
        logger.warning(f"Failed to generate quick replies: {e}")
        return QuickReplyAnalysis(
            quick_replies=["Tell me more", "What are my options?"],
            suggest_brief=False,
        )


def _create_chat_agent(user_state: str, has_document: bool, document_url: str = "", ui_mode: str = "chat"):
    """Create a ReAct agent with tools for chat.

    Args:
        user_state: User's Australian state/territory
        has_document: Whether user has uploaded a document
        document_url: Actual URL of uploaded document (for analyze_document tool)
        ui_mode: "chat" for casual Q&A, "analysis" for guided intake
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)

    # Tools available for chat
    tools = [lookup_law, find_lawyer, analyze_document, search_case_law]

    # Select system prompt based on UI mode
    if ui_mode == "analysis":
        system_template = ANALYSIS_MODE_PROMPT
    else:
        system_template = CHAT_MODE_PROMPT

    # Create system prompt with user context
    system = system_template.format(
        user_state=user_state or "Not specified",
        has_document="Yes" if has_document else "No",
        document_url=document_url or "None",
    )

    # Create ReAct agent
    agent = create_react_agent(
        llm,
        tools,
        prompt=system,
    )

    return agent


async def chat_response_node(
    state: ConversationalState,
    config: RunnableConfig,
) -> dict:
    """
    Generate a natural conversational response.

    Uses ReAct agent pattern to naturally incorporate tool usage
    (lookup_law, find_lawyer) when helpful.

    In analysis mode, uses guided intake prompts and lower analysis threshold.

    Args:
        state: Current conversation state
        config: LangGraph config

    Returns:
        dict with messages and quick_replies
    """
    messages = state.get("messages", [])
    user_state = state.get("user_state")
    uploaded_document_url = state.get("uploaded_document_url", "")
    has_document = bool(uploaded_document_url)
    ui_mode = state.get("ui_mode", "chat")

    logger.info(f"Chat response: user_state={user_state}, has_document={has_document}, document_url={uploaded_document_url}, ui_mode={ui_mode}")

    try:
        # Create agent with tools (mode-specific prompts)
        agent = _create_chat_agent(user_state, has_document, uploaded_document_url, ui_mode)

        # Use config that hides tool calls but keeps message streaming
        # This prevents confusing UX where tool calls appear then disappear
        chat_config = get_chat_agent_config(config)

        # Run agent
        result = await agent.ainvoke(
            {"messages": messages},
            config=chat_config,
        )

        # Extract the final response
        agent_messages = result.get("messages", [])
        if agent_messages:
            # Get the last AI message (the final response)
            final_message = agent_messages[-1]
            response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
        else:
            response_content = "I'm sorry, I couldn't generate a response. Could you rephrase your question?"
            final_message = AIMessage(content=response_content)

        # Generate quick replies based on the conversation
        quick_reply_analysis = await generate_quick_replies(
            messages,
            response_content,
            config,
        )

        return {
            "messages": [final_message],
            "quick_replies": quick_reply_analysis.quick_replies,
            "suggest_brief": quick_reply_analysis.suggest_brief,
        }

    except Exception as e:
        logger.error(f"Chat response error: {e}")
        error_message = (
            "I encountered an issue processing your request. "
            "Could you try rephrasing your question?"
        )
        return {
            "messages": [AIMessage(content=error_message)],
            "quick_replies": ["What can you help with?", "Tell me about tenant rights"],
            "suggest_brief": False,
        }
