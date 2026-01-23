"""Tests for safety gate and safety router."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.routers.safety_router import SafetyRouter, SafetyClassification
from app.agents.stages.safety_gate import (
    safety_gate_node,
    route_after_safety,
    format_escalation_response,
)
from app.agents.schemas.emergency_resources import get_resources_for_risk


class TestEmergencyResources:
    """Test emergency resources schema."""

    def test_get_national_resources_family_violence(self):
        """National resources should be returned for family violence."""
        resources = get_resources_for_risk("family_violence")
        assert len(resources) > 0
        # Should include 1800RESPECT
        names = [r["name"] for r in resources]
        assert "1800RESPECT" in names

    def test_get_state_specific_resources(self):
        """State-specific resources should be included when state is provided."""
        resources = get_resources_for_risk("family_violence", "NSW")
        names = [r["name"] for r in resources]
        # Should include both national and NSW-specific
        assert "1800RESPECT" in names
        assert "NSW Domestic Violence Line" in names

    def test_get_resources_criminal_nsw(self):
        """Criminal resources should include Legal Aid NSW."""
        resources = get_resources_for_risk("criminal", "NSW")
        names = [r["name"] for r in resources]
        assert "Legal Aid NSW" in names

    def test_get_resources_suicide_self_harm(self):
        """Suicide/self-harm should return mental health resources."""
        resources = get_resources_for_risk("suicide_self_harm")
        names = [r["name"] for r in resources]
        assert "Lifeline" in names
        assert "Beyond Blue" in names

    def test_resources_have_required_fields(self):
        """All resources should have name, description, and at least phone or url."""
        for category in ["criminal", "family_violence", "suicide_self_harm"]:
            resources = get_resources_for_risk(category)
            for resource in resources:
                assert "name" in resource
                assert "description" in resource
                assert resource.get("phone") or resource.get("url")


class TestSafetyRouter:
    """Test safety router classification."""

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM response."""
        def _create_response(is_high_risk: bool, category: str | None = None, indicators: list[str] = None):
            return SafetyClassification(
                is_high_risk=is_high_risk,
                risk_category=category,
                risk_indicators=indicators or [],
                reasoning="Test reasoning"
            )
        return _create_response

    @pytest.mark.asyncio
    async def test_normal_query_not_flagged(self, mock_llm_response):
        """Normal legal queries should not be flagged as high-risk."""
        router = SafetyRouter()

        with patch.object(router, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_llm_response(
                is_high_risk=False
            ))

            result = await router.assess(
                query="What are my rights as a tenant regarding rent increases?",
                user_state="NSW"
            )

            assert result["is_high_risk"] is False
            assert result["requires_escalation"] is False
            assert result["risk_category"] is None

    @pytest.mark.asyncio
    async def test_criminal_query_flagged(self, mock_llm_response):
        """Criminal charges should be flagged."""
        router = SafetyRouter()

        with patch.object(router, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_llm_response(
                is_high_risk=True,
                category="criminal",
                indicators=["charged with assault"]
            ))

            result = await router.assess(
                query="I've been charged with assault and my court date is next week",
                user_state="NSW"
            )

            assert result["is_high_risk"] is True
            assert result["requires_escalation"] is True
            assert result["risk_category"] == "criminal"
            assert len(result["recommended_resources"]) > 0

    @pytest.mark.asyncio
    async def test_family_violence_flagged(self, mock_llm_response):
        """Family violence should be flagged."""
        router = SafetyRouter()

        with patch.object(router, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_llm_response(
                is_high_risk=True,
                category="family_violence",
                indicators=["partner hit me", "scared to go home"]
            ))

            result = await router.assess(
                query="My partner hit me last night and I'm scared to go home",
                user_state="VIC"
            )

            assert result["is_high_risk"] is True
            assert result["risk_category"] == "family_violence"
            # Should include VIC-specific resources
            resource_names = [r["name"] for r in result["recommended_resources"]]
            assert "1800RESPECT" in resource_names

    @pytest.mark.asyncio
    async def test_error_handling_returns_safe_default(self):
        """On error, should return safe default (not high-risk)."""
        router = SafetyRouter()

        with patch.object(router, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("API error"))

            result = await router.assess(
                query="Test query",
                user_state="NSW"
            )

            assert result["is_high_risk"] is False
            assert result["requires_escalation"] is False
            assert "error" in result["reasoning"].lower()


class TestSafetyGateNode:
    """Test safety gate node execution."""

    @pytest.mark.asyncio
    async def test_safety_gate_node_updates_state(self):
        """Safety gate should update state with assessment."""
        mock_assessment = {
            "is_high_risk": False,
            "risk_category": None,
            "risk_indicators": [],
            "recommended_resources": [],
            "requires_escalation": False,
            "reasoning": "Normal query"
        }

        with patch('app.agents.stages.safety_gate.get_safety_router') as mock_get_router:
            mock_router = MagicMock()
            mock_router.assess = AsyncMock(return_value=mock_assessment)
            mock_get_router.return_value = mock_router

            state = {
                "current_query": "What are tenant rights?",
                "user_state": "NSW",
                "stages_completed": []
            }

            result = await safety_gate_node(state)

            assert result["safety_assessment"] == mock_assessment
            assert result["current_stage"] == "safety_gate"
            assert "safety_gate" in result["stages_completed"]


class TestRouteAfterSafety:
    """Test routing logic after safety assessment."""

    def test_route_escalate_when_high_risk(self):
        """Should route to escalate when high-risk is detected."""
        state = {
            "safety_assessment": {
                "is_high_risk": True,
                "requires_escalation": True,
                "risk_category": "criminal"
            }
        }
        result = route_after_safety(state)
        assert result == "escalate"

    def test_route_continue_when_safe(self):
        """Should route to continue when no high-risk detected."""
        state = {
            "safety_assessment": {
                "is_high_risk": False,
                "requires_escalation": False,
                "risk_category": None
            }
        }
        result = route_after_safety(state)
        assert result == "continue"

    def test_route_continue_when_no_assessment(self):
        """Should route to continue when assessment is missing."""
        state = {"safety_assessment": None}
        result = route_after_safety(state)
        assert result == "continue"


class TestFormatEscalationResponse:
    """Test escalation response formatting."""

    def test_format_criminal_escalation(self):
        """Criminal escalation should have appropriate message."""
        state = {
            "safety_assessment": {
                "risk_category": "criminal",
                "recommended_resources": [
                    {
                        "name": "Legal Aid NSW",
                        "phone": "1300 888 529",
                        "url": "https://www.legalaid.nsw.gov.au",
                        "description": "Free legal advice"
                    }
                ]
            },
            "stages_completed": ["safety_gate"]
        }

        result = format_escalation_response(state)

        assert len(result["messages"]) == 1
        message_content = result["messages"][0].content

        # Should mention criminal matters
        assert "criminal" in message_content.lower() or "charges" in message_content.lower()
        # Should include resource
        assert "Legal Aid NSW" in message_content
        assert "1300 888 529" in message_content

    def test_format_family_violence_escalation(self):
        """Family violence escalation should be compassionate."""
        state = {
            "safety_assessment": {
                "risk_category": "family_violence",
                "recommended_resources": [
                    {
                        "name": "1800RESPECT",
                        "phone": "1800 737 732",
                        "url": "https://www.1800respect.org.au",
                        "description": "24/7 helpline"
                    }
                ]
            },
            "stages_completed": ["safety_gate"]
        }

        result = format_escalation_response(state)
        message_content = result["messages"][0].content

        # Should be compassionate
        assert "safety" in message_content.lower() or "concerned" in message_content.lower()
        # Should include resource
        assert "1800RESPECT" in message_content

    def test_escalation_updates_stages(self):
        """Escalation response should update stages_completed."""
        state = {
            "safety_assessment": {
                "risk_category": "urgent_deadline",
                "recommended_resources": []
            },
            "stages_completed": ["safety_gate"]
        }

        result = format_escalation_response(state)

        assert "escalation_response" in result["stages_completed"]
        assert result["current_stage"] == "escalation_response"
