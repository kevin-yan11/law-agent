"""Tests for Phase 5: Strategy Recommendation and Escalation Brief."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.agents.stages.strategy import (
    StrategyRecommender,
    StrategyRecommendationOutput,
    StrategyOptionOutput,
    strategy_node,
)
from app.agents.stages.escalation_brief import (
    EscalationBriefGenerator,
    BriefSummaryOutput,
    escalation_brief_node,
)
from app.agents.adaptive_graph import (
    build_adaptive_graph,
    get_response_generator,
    ResponseGenerator,
)


# ============================================
# Strategy Recommender Tests
# ============================================


class TestStrategyRecommender:
    """Test strategy recommendation functionality."""

    @pytest.fixture
    def mock_strategy_output(self):
        """Create mock strategy recommendation output."""
        def _create(
            recommended_name: str = "Negotiate directly",
            recommended_desc: str = "Negotiate with the other party",
            alternatives: int = 2,
            immediate_actions: list = None,
            decision_factors: list = None,
        ):
            return StrategyRecommendationOutput(
                recommended_strategy=StrategyOptionOutput(
                    name=recommended_name,
                    description=recommended_desc,
                    pros=["Cost-effective", "Preserves relationship"],
                    cons=["May not work", "Requires cooperation"],
                    estimated_cost="$0-500",
                    estimated_timeline="2-4 weeks",
                    success_likelihood="medium",
                    recommended_for="Disputes where parties are willing to communicate",
                ),
                alternative_strategies=[
                    StrategyOptionOutput(
                        name=f"Alternative {i+1}",
                        description=f"Alternative strategy {i+1}",
                        pros=["Pro 1"],
                        cons=["Con 1"],
                        estimated_cost="$500-2000",
                        estimated_timeline="1-3 months",
                        success_likelihood="medium",
                        recommended_for="When negotiation fails",
                    )
                    for i in range(alternatives)
                ],
                immediate_actions=immediate_actions or [
                    "Gather all documentation",
                    "Write a formal demand letter",
                    "Set a deadline for response",
                ],
                decision_factors=decision_factors or [
                    "Your available time and resources",
                    "The amount in dispute",
                    "Your relationship with the other party",
                ],
            )
        return _create

    @pytest.mark.asyncio
    async def test_recommends_strategy_for_tenancy(self, mock_strategy_output):
        """Should recommend strategy for tenancy matters."""
        recommender = StrategyRecommender()

        with patch.object(recommender, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_strategy_output(
                recommended_name="Apply to tribunal",
                recommended_desc="Lodge application with NCAT for bond dispute",
            ))

            state = {
                "current_query": "My landlord won't return my bond",
                "user_state": "NSW",
                "issue_classification": {
                    "primary_issue": {
                        "area": "tenancy",
                        "sub_category": "bond_refund",
                        "confidence": 0.9,
                        "description": "Bond refund dispute",
                    },
                    "secondary_issues": [],
                },
                "jurisdiction_result": {
                    "primary_jurisdiction": "NSW",
                },
                "fact_structure": {
                    "key_facts": ["Bond was $2000", "Moved out 2 weeks ago"],
                    "narrative_summary": "Tenant seeking bond refund",
                    "evidence": [],
                    "timeline": [],
                    "parties": [],
                    "fact_gaps": [],
                },
                "elements_analysis": {
                    "viability_assessment": "moderate",
                },
                "risk_assessment": {
                    "overall_risk_level": "low",
                    "risks": [],
                    "time_sensitivity": None,
                },
                "precedent_analysis": {
                    "matching_cases": [],
                },
            }

            result = await recommender.recommend_strategy(state)

            assert result["recommended_strategy"]["name"] == "Apply to tribunal"
            assert len(result["alternative_strategies"]) >= 1
            assert len(result["immediate_actions"]) >= 1
            assert len(result["decision_factors"]) >= 1

    @pytest.mark.asyncio
    async def test_includes_cost_and_timeline(self, mock_strategy_output):
        """Should include cost and timeline estimates."""
        recommender = StrategyRecommender()

        with patch.object(recommender, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_strategy_output())

            state = {
                "current_query": "Test",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {"key_facts": [], "narrative_summary": "", "evidence": [], "timeline": [], "parties": [], "fact_gaps": []},
                "elements_analysis": {},
                "risk_assessment": {},
                "precedent_analysis": {},
            }

            result = await recommender.recommend_strategy(state)

            assert result["recommended_strategy"]["estimated_cost"] is not None
            assert result["recommended_strategy"]["estimated_timeline"] is not None
            assert result["recommended_strategy"]["success_likelihood"] in ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_provides_alternative_strategies(self, mock_strategy_output):
        """Should provide multiple alternative strategies."""
        recommender = StrategyRecommender()

        with patch.object(recommender, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_strategy_output(alternatives=3))

            state = {
                "current_query": "Complex employment dispute",
                "issue_classification": {"primary_issue": {"area": "employment", "sub_category": "unfair_dismissal"}},
                "jurisdiction_result": {"primary_jurisdiction": "FEDERAL"},
                "fact_structure": {"key_facts": [], "narrative_summary": "", "evidence": [], "timeline": [], "parties": [], "fact_gaps": []},
                "elements_analysis": {},
                "risk_assessment": {},
                "precedent_analysis": {},
            }

            result = await recommender.recommend_strategy(state)

            assert len(result["alternative_strategies"]) == 3
            for alt in result["alternative_strategies"]:
                assert "name" in alt
                assert "pros" in alt
                assert "cons" in alt

    @pytest.mark.asyncio
    async def test_considers_risk_level(self, mock_strategy_output):
        """Should consider risk level in strategy formulation."""
        recommender = StrategyRecommender()

        with patch.object(recommender, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_strategy_output())

            state = {
                "current_query": "High risk matter",
                "issue_classification": {"primary_issue": {"area": "employment", "sub_category": "unfair_dismissal"}},
                "jurisdiction_result": {"primary_jurisdiction": "FEDERAL"},
                "fact_structure": {"key_facts": ["Fired without warning"], "narrative_summary": "Unfair dismissal", "evidence": [], "timeline": [], "parties": [], "fact_gaps": []},
                "elements_analysis": {"viability_assessment": "weak"},
                "risk_assessment": {
                    "overall_risk_level": "high",
                    "risks": [
                        {"description": "Weak evidence", "severity": "high", "likelihood": "likely"},
                    ],
                    "time_sensitivity": "21-day deadline approaching",
                },
                "precedent_analysis": {},
            }

            result = await recommender.recommend_strategy(state)

            # Should still produce a recommendation even with high risk
            assert result["recommended_strategy"] is not None
            mock_chain.ainvoke.assert_called_once()
            call_args = mock_chain.ainvoke.call_args[0][0]
            assert "high" in call_args["risk_level"]

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Should return default strategy on error."""
        recommender = StrategyRecommender()

        with patch.object(recommender, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("API error"))

            state = {
                "current_query": "Test",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {},
                "elements_analysis": {},
                "risk_assessment": {},
                "precedent_analysis": {},
            }

            result = await recommender.recommend_strategy(state)

            assert "Seek professional legal advice" in result["recommended_strategy"]["name"]
            assert len(result["immediate_actions"]) >= 1


class TestStrategyNode:
    """Test strategy node execution."""

    @pytest.mark.asyncio
    async def test_node_updates_state(self):
        """Node should update state with strategy recommendation."""
        mock_recommendation = {
            "recommended_strategy": {
                "name": "Test strategy",
                "description": "Test description",
                "pros": ["Pro 1"],
                "cons": ["Con 1"],
                "estimated_cost": "$100",
                "estimated_timeline": "1 week",
                "success_likelihood": "high",
                "recommended_for": "Testing",
            },
            "alternative_strategies": [],
            "immediate_actions": ["Action 1"],
            "decision_factors": ["Factor 1"],
        }

        with patch('app.agents.stages.strategy.get_strategy_recommender') as mock_get:
            mock_recommender = MagicMock()
            mock_recommender.recommend_strategy = AsyncMock(return_value=mock_recommendation)
            mock_get.return_value = mock_recommender

            state = {
                "current_query": "Test",
                "issue_classification": {},
                "jurisdiction_result": {},
                "fact_structure": {},
                "elements_analysis": {},
                "risk_assessment": {},
                "precedent_analysis": {},
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction", "fact_structuring", "legal_elements", "case_precedent", "risk_analysis"],
            }

            result = await strategy_node(state)

            assert result["strategy_recommendation"] == mock_recommendation
            assert "strategy" in result["stages_completed"]
            assert result["current_stage"] == "strategy"


# ============================================
# Escalation Brief Tests
# ============================================


class TestEscalationBriefGenerator:
    """Test escalation brief generation functionality."""

    @pytest.fixture
    def mock_brief_summary(self):
        """Create mock brief summary output."""
        def _create(
            executive_summary: str = "Bond dispute in NSW requiring tribunal application",
            urgency_level: str = "standard",
            open_questions: list = None,
            next_steps: list = None,
        ):
            return BriefSummaryOutput(
                executive_summary=executive_summary,
                urgency_level=urgency_level,
                open_questions=open_questions or [
                    "Was a condition report completed at move-in?",
                    "Are there photos of the property condition?",
                ],
                suggested_next_steps=next_steps or [
                    "Review tenancy agreement terms",
                    "Gather all communication with landlord",
                    "Prepare tribunal application",
                ],
            )
        return _create

    @pytest.mark.asyncio
    async def test_generates_brief_with_all_sections(self, mock_brief_summary):
        """Should generate brief with all required sections."""
        generator = EscalationBriefGenerator()

        with patch.object(generator, 'summary_chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_brief_summary())

            state = {
                "current_query": "My landlord won't return my bond",
                "issue_classification": {
                    "primary_issue": {
                        "area": "tenancy",
                        "sub_category": "bond_refund",
                        "confidence": 0.9,
                        "description": "Bond refund dispute",
                    },
                    "secondary_issues": [],
                },
                "jurisdiction_result": {
                    "primary_jurisdiction": "NSW",
                    "applicable_jurisdictions": ["NSW"],
                    "jurisdiction_conflicts": [],
                    "fallback_to_federal": False,
                    "reasoning": "NSW tenancy law applies",
                },
                "fact_structure": {
                    "key_facts": ["Bond was $2000"],
                    "fact_gaps": ["Condition report status unknown"],
                    "evidence": [],
                    "timeline": [],
                    "parties": [],
                    "narrative_summary": "Tenant seeking bond refund",
                },
                "elements_analysis": {
                    "applicable_law": "Residential Tenancies Act 2010 (NSW)",
                    "viability_assessment": "moderate",
                    "elements_satisfied": 3,
                    "elements_total": 5,
                    "elements": [],
                    "reasoning": "Good position overall",
                },
                "precedent_analysis": {
                    "matching_cases": [],
                    "pattern_identified": None,
                    "typical_outcome": None,
                    "distinguishing_factors": [],
                },
                "risk_assessment": {
                    "overall_risk_level": "low",
                    "risks": [],
                    "evidence_weaknesses": [],
                    "possible_defences": [],
                    "counterfactual_scenarios": [],
                    "time_sensitivity": None,
                },
                "strategy_recommendation": {
                    "recommended_strategy": {
                        "name": "Apply to NCAT",
                        "description": "Lodge application with tribunal",
                        "pros": ["Formal process"],
                        "cons": ["Takes time"],
                        "estimated_cost": "$50",
                        "estimated_timeline": "2-3 months",
                        "success_likelihood": "high",
                        "recommended_for": "Bond disputes",
                    },
                    "alternative_strategies": [],
                    "immediate_actions": [],
                    "decision_factors": [],
                },
            }

            result = await generator.generate_brief(state)

            # Check all required fields
            assert "brief_id" in result
            assert "generated_at" in result
            assert "executive_summary" in result
            assert "urgency_level" in result
            assert "client_situation" in result
            assert "legal_issues" in result
            assert "jurisdiction" in result
            assert "facts" in result
            assert "legal_analysis" in result
            assert "relevant_precedents" in result
            assert "risk_assessment" in result
            assert "recommended_strategy" in result
            assert "open_questions" in result
            assert "suggested_next_steps" in result

    @pytest.mark.asyncio
    async def test_assigns_urgency_level(self, mock_brief_summary):
        """Should assign appropriate urgency level."""
        generator = EscalationBriefGenerator()

        # Test urgent case
        with patch.object(generator, 'summary_chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_brief_summary(
                urgency_level="urgent"
            ))

            state = {
                "current_query": "Court date in 3 days",
                "issue_classification": {"primary_issue": {"area": "civil", "sub_category": "general"}},
                "jurisdiction_result": {},
                "fact_structure": {"key_facts": [], "fact_gaps": [], "evidence": [], "timeline": [], "parties": [], "narrative_summary": ""},
                "elements_analysis": {},
                "risk_assessment": {"time_sensitivity": "Court date in 3 days"},
                "strategy_recommendation": {"recommended_strategy": {}},
            }

            result = await generator.generate_brief(state)
            assert result["urgency_level"] == "urgent"

    @pytest.mark.asyncio
    async def test_includes_open_questions(self, mock_brief_summary):
        """Should include open questions for lawyer."""
        generator = EscalationBriefGenerator()

        questions = [
            "Did the tenant breach any lease terms?",
            "What was the property condition at move-out?",
            "Has the bond authority been contacted?",
        ]

        with patch.object(generator, 'summary_chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_brief_summary(
                open_questions=questions
            ))

            state = {
                "current_query": "Bond dispute",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {},
                "fact_structure": {"key_facts": [], "fact_gaps": ["Condition unknown"], "evidence": [], "timeline": [], "parties": [], "narrative_summary": ""},
                "elements_analysis": {},
                "risk_assessment": {},
                "strategy_recommendation": {"recommended_strategy": {}},
            }

            result = await generator.generate_brief(state)

            assert result["open_questions"] == questions

    @pytest.mark.asyncio
    async def test_extracts_legal_issues(self, mock_brief_summary):
        """Should extract all legal issues from classification."""
        generator = EscalationBriefGenerator()

        with patch.object(generator, 'summary_chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_brief_summary())

            state = {
                "current_query": "Multiple issues",
                "issue_classification": {
                    "primary_issue": {
                        "area": "tenancy",
                        "sub_category": "bond_refund",
                        "confidence": 0.9,
                        "description": "Bond dispute",
                    },
                    "secondary_issues": [
                        {
                            "area": "consumer",
                            "sub_category": "unfair_terms",
                            "confidence": 0.6,
                            "description": "Unfair lease terms",
                        },
                    ],
                },
                "jurisdiction_result": {},
                "fact_structure": {"key_facts": [], "fact_gaps": [], "evidence": [], "timeline": [], "parties": [], "narrative_summary": ""},
                "elements_analysis": {},
                "risk_assessment": {},
                "strategy_recommendation": {"recommended_strategy": {}},
            }

            result = await generator.generate_brief(state)

            assert len(result["legal_issues"]) == 2
            assert result["legal_issues"][0]["area"] == "tenancy"
            assert result["legal_issues"][1]["area"] == "consumer"

    @pytest.mark.asyncio
    async def test_generates_unique_brief_id(self, mock_brief_summary):
        """Should generate unique brief IDs."""
        generator = EscalationBriefGenerator()

        with patch.object(generator, 'summary_chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_brief_summary())

            state = {
                "current_query": "Test",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {},
                "fact_structure": {"key_facts": [], "fact_gaps": [], "evidence": [], "timeline": [], "parties": [], "narrative_summary": ""},
                "elements_analysis": {},
                "risk_assessment": {},
                "strategy_recommendation": {"recommended_strategy": {}},
            }

            result1 = await generator.generate_brief(state)
            result2 = await generator.generate_brief(state)

            assert result1["brief_id"] != result2["brief_id"]

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Should return minimal brief on error."""
        generator = EscalationBriefGenerator()

        with patch.object(generator, 'summary_chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("API error"))

            state = {
                "current_query": "Test",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {},
                "fact_structure": {},
                "elements_analysis": {},
                "risk_assessment": {},
                "strategy_recommendation": {},
            }

            result = await generator.generate_brief(state)

            assert result["brief_id"] is not None
            assert "error" in result["executive_summary"].lower() or "manual review" in result["executive_summary"].lower()


class TestEscalationBriefNode:
    """Test escalation brief node execution."""

    @pytest.mark.asyncio
    async def test_node_updates_state(self):
        """Node should update state with escalation brief."""
        mock_brief = {
            "brief_id": "test-123",
            "generated_at": datetime.now().isoformat(),
            "executive_summary": "Test summary",
            "urgency_level": "standard",
            "client_situation": "Test situation",
            "legal_issues": [],
            "jurisdiction": {},
            "facts": {},
            "legal_analysis": {},
            "relevant_precedents": [],
            "risk_assessment": {},
            "recommended_strategy": {},
            "open_questions": ["Question 1"],
            "suggested_next_steps": ["Step 1"],
        }

        with patch('app.agents.stages.escalation_brief.get_brief_generator') as mock_get:
            mock_generator = MagicMock()
            mock_generator.generate_brief = AsyncMock(return_value=mock_brief)
            mock_get.return_value = mock_generator

            state = {
                "current_query": "Test",
                "issue_classification": {},
                "jurisdiction_result": {},
                "fact_structure": {},
                "elements_analysis": {},
                "risk_assessment": {},
                "strategy_recommendation": {},
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction", "fact_structuring", "legal_elements", "case_precedent", "risk_analysis", "strategy"],
            }

            result = await escalation_brief_node(state)

            assert result["escalation_brief"] == mock_brief
            assert "escalation_brief" in result["stages_completed"]
            assert result["current_stage"] == "escalation_brief"


# ============================================
# Adaptive Graph Tests
# ============================================


class TestAdaptiveGraph:
    """Test adaptive graph construction and routing."""

    def test_graph_builds_successfully(self):
        """Should build graph without errors."""
        workflow = build_adaptive_graph()
        assert workflow is not None

    def test_graph_has_all_nodes(self):
        """Should have all required nodes."""
        workflow = build_adaptive_graph()

        # Check node names
        node_names = list(workflow.nodes.keys())

        expected_nodes = [
            "initialize",
            "safety_gate",
            "escalation_response",
            "issue_identification",
            "complexity_routing",
            "jurisdiction",
            "simple_strategy",
            "simple_response",
            "fact_structuring",
            "legal_elements",
            "case_precedent",
            "risk_analysis",
            "complex_strategy",
            "escalation_brief",
            "complex_response",
        ]

        for node in expected_nodes:
            assert node in node_names, f"Missing node: {node}"


class TestResponseGenerator:
    """Test response generation functionality."""

    @pytest.mark.asyncio
    async def test_generates_simple_response(self):
        """Should generate response for simple path."""
        generator = ResponseGenerator()

        with patch.object(generator, 'simple_chain') as mock_chain:
            mock_response = MagicMock()
            mock_response.content = "Here is your legal information about bond refunds in NSW."
            mock_chain.ainvoke = AsyncMock(return_value=mock_response)

            state = {
                "current_query": "What are my rights for bond refund?",
                "issue_classification": {
                    "primary_issue": {
                        "area": "tenancy",
                        "sub_category": "bond_refund",
                        "description": "Bond refund rights",
                    },
                },
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "strategy_recommendation": {
                    "recommended_strategy": {"name": "Apply to tribunal", "description": "Lodge application"},
                    "immediate_actions": ["Gather evidence"],
                    "decision_factors": ["Amount in dispute"],
                },
            }

            result = await generator.generate_simple_response(state)

            assert "bond refunds" in result.lower() or "legal information" in result.lower()

    @pytest.mark.asyncio
    async def test_generates_complex_response(self):
        """Should generate response for complex path."""
        generator = ResponseGenerator()

        with patch.object(generator, 'complex_chain') as mock_chain:
            mock_response = MagicMock()
            mock_response.content = "Based on the comprehensive analysis of your unfair dismissal claim..."
            mock_chain.ainvoke = AsyncMock(return_value=mock_response)

            state = {
                "current_query": "I was unfairly dismissed",
                "issue_classification": {
                    "primary_issue": {
                        "area": "employment",
                        "sub_category": "unfair_dismissal",
                        "description": "Unfair dismissal claim",
                    },
                },
                "jurisdiction_result": {"primary_jurisdiction": "FEDERAL"},
                "fact_structure": {
                    "key_facts": ["Employed for 5 years", "No warnings given"],
                    "narrative_summary": "Employee dismissed without cause",
                },
                "elements_analysis": {
                    "viability_assessment": "strong",
                    "elements_satisfied": 4,
                    "elements_total": 5,
                    "applicable_law": "Fair Work Act 2009",
                },
                "risk_assessment": {
                    "overall_risk_level": "low",
                    "risks": [],
                    "time_sensitivity": "21-day deadline",
                },
                "precedent_analysis": {
                    "matching_cases": [
                        {
                            "case_name": "Test v Employer",
                            "year": 2023,
                            "outcome_for_similar_party": "favorable",
                            "key_holding": "Procedural fairness required",
                        }
                    ],
                },
                "strategy_recommendation": {
                    "recommended_strategy": {
                        "name": "Lodge FWC application",
                        "description": "Apply to Fair Work Commission",
                        "success_likelihood": "high",
                        "estimated_cost": "$75",
                        "estimated_timeline": "3-6 months",
                    },
                    "alternative_strategies": [
                        {"name": "Negotiate", "description": "Direct negotiation"},
                    ],
                    "immediate_actions": ["Lodge application before deadline"],
                },
            }

            result = await generator.generate_complex_response(state)

            assert "unfair dismissal" in result.lower() or "comprehensive" in result.lower()


# ============================================
# Integration Tests (State Flow)
# ============================================


class TestPhase5StateFlow:
    """Test state flows through Phase 5 stages."""

    @pytest.mark.asyncio
    async def test_strategy_receives_risk_assessment(self):
        """Strategy should receive risk assessment from state."""
        with patch('app.agents.stages.strategy.get_strategy_recommender') as mock_get:
            mock_recommender = MagicMock()
            mock_recommender.recommend_strategy = AsyncMock(return_value={
                "recommended_strategy": {"name": "Test", "description": "Test"},
                "alternative_strategies": [],
                "immediate_actions": [],
                "decision_factors": [],
            })
            mock_get.return_value = mock_recommender

            state = {
                "current_query": "Test",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {"key_facts": [], "narrative_summary": "", "evidence": [], "timeline": [], "parties": [], "fact_gaps": []},
                "elements_analysis": {"viability_assessment": "strong"},
                "risk_assessment": {
                    "overall_risk_level": "low",
                    "risks": [{"description": "Minor risk", "severity": "low", "likelihood": "unlikely"}],
                    "time_sensitivity": "No deadline",
                },
                "precedent_analysis": {},
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction", "fact_structuring", "legal_elements", "case_precedent", "risk_analysis"],
            }

            await strategy_node(state)

            called_state = mock_recommender.recommend_strategy.call_args[0][0]
            assert called_state["risk_assessment"]["overall_risk_level"] == "low"

    @pytest.mark.asyncio
    async def test_brief_receives_strategy(self):
        """Escalation brief should receive strategy from state."""
        with patch('app.agents.stages.escalation_brief.get_brief_generator') as mock_get:
            mock_generator = MagicMock()
            mock_generator.generate_brief = AsyncMock(return_value={
                "brief_id": "test",
                "generated_at": datetime.now().isoformat(),
                "executive_summary": "Test",
                "urgency_level": "standard",
                "client_situation": "Test",
                "legal_issues": [],
                "jurisdiction": {},
                "facts": {},
                "legal_analysis": {},
                "relevant_precedents": [],
                "risk_assessment": {},
                "recommended_strategy": {},
                "open_questions": [],
                "suggested_next_steps": [],
            })
            mock_get.return_value = mock_generator

            state = {
                "current_query": "Test",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {"key_facts": [], "fact_gaps": [], "evidence": [], "timeline": [], "parties": [], "narrative_summary": ""},
                "elements_analysis": {},
                "risk_assessment": {},
                "strategy_recommendation": {
                    "recommended_strategy": {
                        "name": "Apply to NCAT",
                        "description": "Lodge tribunal application",
                    },
                },
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction", "fact_structuring", "legal_elements", "case_precedent", "risk_analysis", "strategy"],
            }

            await escalation_brief_node(state)

            called_state = mock_generator.generate_brief.call_args[0][0]
            assert called_state["strategy_recommendation"]["recommended_strategy"]["name"] == "Apply to NCAT"
