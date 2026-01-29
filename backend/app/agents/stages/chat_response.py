"""Chat response node for conversational mode.

Generates natural, helpful responses using tools (lookup_law, find_lawyer)
when needed. Includes quick reply suggestions for smoother conversation flow.
"""

from typing import Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent

from app.agents.conversational_state import ConversationalState
from app.agents.utils import get_internal_llm_config
from app.tools.lookup_law import lookup_law
from app.tools.find_lawyer import find_lawyer
from app.config import logger


# System prompt for natural conversation
SYSTEM_PROMPT = """You are an Australian legal assistant having a natural, helpful conversation.
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

## Tool Usage Guidelines
- Use lookup_law when user asks about specific rights, laws, or legal requirements
- Use find_lawyer when user asks for lawyer recommendations or says they need professional help
- Always pass the user's state to tools

Remember: Your goal is to be helpful and informative while keeping the conversation natural and flowing."""


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
    suggest_lawyer: bool = Field(
        default=False,
        description="True if user should consider consulting a lawyer soon"
    )


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
- "Find me a lawyer"
- "What about costs?"

Also indicate if:
- The situation seems complex enough that a lawyer brief would be helpful
- The user should seriously consider consulting a lawyer

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
            suggest_lawyer=False,
        )


def _create_chat_agent(user_state: str, has_document: bool):
    """Create a ReAct agent with tools for chat."""
    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)

    # Tools available for chat
    tools = [lookup_law, find_lawyer]

    # Create system prompt with user context
    system = SYSTEM_PROMPT.format(
        user_state=user_state or "Not specified",
        has_document="Yes" if has_document else "No",
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

    Args:
        state: Current conversation state
        config: LangGraph config

    Returns:
        dict with messages and quick_replies
    """
    messages = state.get("messages", [])
    user_state = state.get("user_state")
    has_document = bool(state.get("uploaded_document_url"))

    logger.info(f"Chat response: user_state={user_state}, has_document={has_document}")

    try:
        # Create agent with tools
        agent = _create_chat_agent(user_state, has_document)

        # Run agent
        result = await agent.ainvoke(
            {"messages": messages},
            config=config,
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
            "suggest_lawyer": quick_reply_analysis.suggest_lawyer,
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
            "suggest_lawyer": False,
        }
