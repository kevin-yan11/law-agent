"""Tests for the conversational mode graph."""

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.conversational_state import ConversationalState
from app.agents.conversational_graph import (
    get_conversational_graph,
    route_after_initialize,
)
from app.agents.utils import extract_user_state
from app.agents.stages.safety_check_lite import (
    _check_crisis_keywords,
    _might_be_risky,
)


class TestCrisisKeywordDetection:
    """Test the keyword-based crisis detection."""

    def test_suicide_keywords_detected(self):
        is_crisis, category = _check_crisis_keywords("I want to kill myself")
        assert is_crisis is True
        assert category == "suicide_self_harm"

    def test_family_violence_detected(self):
        is_crisis, category = _check_crisis_keywords("My partner hit me last night")
        assert is_crisis is True
        assert category == "family_violence"

    def test_criminal_detected(self):
        is_crisis, category = _check_crisis_keywords("I was arrested for theft")
        assert is_crisis is True
        assert category == "criminal"

    def test_normal_query_not_flagged(self):
        is_crisis, category = _check_crisis_keywords("What are my tenant rights?")
        assert is_crisis is False
        assert category is None

    def test_employment_not_flagged(self):
        is_crisis, category = _check_crisis_keywords("My boss fired me unfairly")
        assert is_crisis is False
        assert category is None


class TestRiskyKeywordDetection:
    """Test the uncertain keyword detection."""

    def test_court_is_risky(self):
        assert _might_be_risky("I have court tomorrow") is True

    def test_eviction_is_risky(self):
        assert _might_be_risky("I'm being evicted") is True

    def test_normal_query_not_risky(self):
        assert _might_be_risky("What are tenant rights?") is False


class TestRouteAfterInitialize:
    """Test the routing logic after initialization."""

    def test_first_message_always_checks(self):
        state: ConversationalState = {
            "is_first_message": True,
            "current_query": "Hello",
            "messages": [],
            "session_id": "test",
            "user_state": None,
            "uploaded_document_url": None,
            "mode": "chat",
            "quick_replies": None,
            "suggest_brief": False,
            "suggest_lawyer": False,
            "safety_result": "unknown",
            "crisis_resources": None,
            "brief_facts_collected": None,
            "brief_missing_info": None,
            "brief_unknown_info": None,
            "brief_info_complete": False,
            "brief_questions_asked": 0,
            "brief_needs_full_intake": False,
            "copilotkit": None,
            "error": None,
        }
        assert route_after_initialize(state) == "check"

    def test_short_follow_up_skips(self):
        state: ConversationalState = {
            "is_first_message": False,
            "current_query": "Tell me more",
            "messages": [],
            "session_id": "test",
            "user_state": None,
            "uploaded_document_url": None,
            "mode": "chat",
            "quick_replies": None,
            "suggest_brief": False,
            "suggest_lawyer": False,
            "safety_result": "unknown",
            "crisis_resources": None,
            "brief_facts_collected": None,
            "brief_missing_info": None,
            "brief_unknown_info": None,
            "brief_info_complete": False,
            "brief_questions_asked": 0,
            "brief_needs_full_intake": False,
            "copilotkit": None,
            "error": None,
        }
        assert route_after_initialize(state) == "skip"

    def test_emergency_keyword_checks(self):
        state: ConversationalState = {
            "is_first_message": False,
            "current_query": "I need help now",
            "messages": [],
            "session_id": "test",
            "user_state": None,
            "uploaded_document_url": None,
            "mode": "chat",
            "quick_replies": None,
            "suggest_brief": False,
            "suggest_lawyer": False,
            "safety_result": "unknown",
            "crisis_resources": None,
            "brief_facts_collected": None,
            "brief_missing_info": None,
            "brief_unknown_info": None,
            "brief_info_complete": False,
            "brief_questions_asked": 0,
            "brief_needs_full_intake": False,
            "copilotkit": None,
            "error": None,
        }
        assert route_after_initialize(state) == "check"

    def test_brief_mode_routes_to_brief(self):
        state: ConversationalState = {
            "is_first_message": False,
            "current_query": "Generate brief",
            "messages": [],
            "session_id": "test",
            "user_state": None,
            "uploaded_document_url": None,
            "mode": "brief",
            "quick_replies": None,
            "suggest_brief": False,
            "suggest_lawyer": False,
            "safety_result": "unknown",
            "crisis_resources": None,
            "brief_facts_collected": None,
            "brief_missing_info": None,
            "brief_unknown_info": None,
            "brief_info_complete": False,
            "brief_questions_asked": 0,
            "brief_needs_full_intake": False,
            "copilotkit": None,
            "error": None,
        }
        assert route_after_initialize(state) == "brief"


class TestContextExtraction:
    """Test CopilotKit context extraction."""

    def test_extract_user_state_nsw(self):
        state: ConversationalState = {
            "copilotkit": {
                "context": [
                    {"description": "User's state/territory", "value": "NSW"}
                ]
            },
            "messages": [],
            "session_id": "test",
            "current_query": "",
            "user_state": None,
            "uploaded_document_url": None,
            "mode": "chat",
            "is_first_message": True,
            "quick_replies": None,
            "suggest_brief": False,
            "suggest_lawyer": False,
            "safety_result": "unknown",
            "crisis_resources": None,
            "brief_facts_collected": None,
            "brief_missing_info": None,
            "brief_unknown_info": None,
            "brief_info_complete": False,
            "brief_questions_asked": 0,
            "brief_needs_full_intake": False,
            "error": None,
        }
        assert extract_user_state(state) == "NSW"

    def test_extract_user_state_with_quotes(self):
        state: ConversationalState = {
            "copilotkit": {
                "context": [
                    {"description": "User's state/territory", "value": '"VIC"'}
                ]
            },
            "messages": [],
            "session_id": "test",
            "current_query": "",
            "user_state": None,
            "uploaded_document_url": None,
            "mode": "chat",
            "is_first_message": True,
            "quick_replies": None,
            "suggest_brief": False,
            "suggest_lawyer": False,
            "safety_result": "unknown",
            "crisis_resources": None,
            "brief_facts_collected": None,
            "brief_missing_info": None,
            "brief_unknown_info": None,
            "brief_info_complete": False,
            "brief_questions_asked": 0,
            "brief_needs_full_intake": False,
            "error": None,
        }
        assert extract_user_state(state) == "VIC"


class TestConversationalGraphCompiles:
    """Test that the graph compiles correctly."""

    def test_graph_compiles(self):
        graph = get_conversational_graph()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        from app.agents.conversational_graph import build_conversational_graph
        workflow = build_conversational_graph()
        # Check that the expected chat mode nodes exist
        assert "initialize" in workflow.nodes
        assert "safety_check" in workflow.nodes
        assert "chat_response" in workflow.nodes
        assert "escalation_response" in workflow.nodes
        # Check that brief mode nodes exist
        assert "brief_check_info" in workflow.nodes
        assert "brief_ask_questions" in workflow.nodes
        assert "brief_generate" in workflow.nodes
