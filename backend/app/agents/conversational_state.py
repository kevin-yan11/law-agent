"""Simplified state for conversational mode.

This replaces the complex AdaptiveAgentState with a simpler structure
focused on natural conversation rather than multi-stage analysis pipelines.
"""

from typing import Optional, Literal, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
import operator


class ConversationalState(TypedDict):
    """Simple state for conversational legal assistant.

    Focuses on:
    - Fast, natural conversation
    - Tool usage (RAG, lawyer finder) as needed
    - Quick replies for smooth UX
    - Brief generation only on explicit request
    """

    # ---- Session & Context ----
    session_id: str
    user_state: Optional[str]  # Australian state/territory (NSW, VIC, etc.)
    uploaded_document_url: Optional[str]

    # ---- Conversation ----
    messages: Annotated[list[BaseMessage], operator.add]
    current_query: str

    # ---- Mode Control ----
    mode: Literal["chat", "brief"]  # Current operation mode
    is_first_message: bool  # First message in session (run safety check)

    # ---- Chat Response Metadata ----
    quick_replies: Optional[list[str]]  # Suggested response options
    suggest_brief: bool  # Whether to highlight brief generation option
    suggest_lawyer: bool  # Whether to suggest finding a lawyer

    # ---- Safety ----
    safety_result: Literal["safe", "escalate", "unknown"]
    crisis_resources: Optional[list[dict]]  # If escalation needed

    # ---- Brief Generation (only used in brief mode) ----
    brief_facts_collected: Optional[dict]
    brief_missing_info: Optional[list[str]]
    brief_info_complete: bool
    brief_questions_asked: int

    # ---- CopilotKit Integration ----
    copilotkit: Optional[dict]

    # ---- Error Handling ----
    error: Optional[str]


class ConversationalOutput(TypedDict):
    """Output schema - these fields are streamed to UI via AG-UI protocol.

    The frontend accesses these via useCoAgent hook.
    Note: The quick reply LLM call uses get_internal_llm_config to suppress
    streaming, preventing raw JSON from appearing in the chat.
    """

    messages: Annotated[list[BaseMessage], operator.add]
    quick_replies: Optional[list[str]]
    suggest_brief: bool
    suggest_lawyer: bool
