"""Configuration utilities for internal LLM calls in the adaptive agent.

The key insight is that CopilotKit's emit_messages/emit_tool_calls settings must be
in the config that flows through LangGraph's callback system. Creating a standalone
config at module load time doesn't work because the metadata isn't properly propagated
to the LangGraph events.

This module provides a helper to customize the runtime config from LangGraph nodes,
ensuring the emit settings are properly respected.

NOTE: There's a bug in copilotkit's LangGraphAGUIAgent._dispatch_event (line 153) where
it uses `getattr(raw_event, 'metadata', {})` on a dict instead of `.get()`. This means
the prefixed keys (copilotkit:emit-messages) are never found. As a workaround, we also
set the unprefixed keys (emit-messages) which the base AG-UI agent checks correctly.
"""

from typing import Optional
from langchain_core.runnables import RunnableConfig
from copilotkit.langgraph import copilotkit_customize_config


def get_chat_agent_config(config: Optional[RunnableConfig] = None) -> RunnableConfig:
    """
    Get a config for the chat agent that hides tool calls but keeps message streaming.

    This allows the final response to stream naturally while hiding intermediate
    tool call events (which can be confusing when they appear then disappear).

    Note: Intermediate messages like "Let me search..." will appear then disappear
    when the final response arrives. This is a tradeoff for keeping streaming.

    Args:
        config: The current LangGraph config from the node.

    Returns:
        A customized RunnableConfig with emit_messages=True and emit_tool_calls=False.
    """
    customized = copilotkit_customize_config(
        config,
        emit_messages=True,
        emit_tool_calls=False,
    )

    if customized.get("metadata") is None:
        customized["metadata"] = {}
    customized["metadata"]["emit-messages"] = True
    customized["metadata"]["emit-tool-calls"] = False

    return customized


def get_internal_llm_config(config: Optional[RunnableConfig] = None) -> RunnableConfig:
    """
    Get a config for internal LLM calls that suppresses streaming to the frontend.

    This function takes the current LangGraph config (which contains the proper
    callbacks and context) and customizes it to disable message and tool call
    streaming. The customized config should be passed to internal LLM calls
    (e.g., safety classification, issue identification) so their JSON output
    doesn't appear in the chat.

    Args:
        config: The current LangGraph config from the node. If None, creates
                a new config (but this won't work as well for suppressing streams).

    Returns:
        A customized RunnableConfig with emit_messages=False and emit_tool_calls=False.

    Example:
        async def my_node(state: AdaptiveAgentState, config: RunnableConfig) -> dict:
            internal_config = get_internal_llm_config(config)
            result = await self.chain.ainvoke({"query": ...}, config=internal_config)
            ...
    """
    # Use copilotkit's helper to set the prefixed metadata keys
    customized = copilotkit_customize_config(
        config,
        emit_messages=False,
        emit_tool_calls=False,
    )

    # WORKAROUND: Also set unprefixed keys that base AG-UI agent checks correctly.
    # The copilotkit SDK has a bug where it uses getattr() on dict instead of .get(),
    # so the prefixed keys (copilotkit:emit-messages) are never found. The base
    # ag-ui-langgraph agent checks unprefixed keys with event["metadata"].get().
    if customized.get("metadata") is None:
        customized["metadata"] = {}
    customized["metadata"]["emit-messages"] = False
    customized["metadata"]["emit-tool-calls"] = False

    return customized
