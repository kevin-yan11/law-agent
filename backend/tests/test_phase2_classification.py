"""Tests for Phase 2: Issue Identification, Complexity Router, and Jurisdiction."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.routers.complexity_router import (
    classify_complexity_heuristic,
    ComplexityRouter,
    ComplexityClassification,
    SIMPLE_QUERY_PATTERNS,
    COMPLEX_QUERY_INDICATORS,
)
from app.agents.stages.issue_identification import (
    IssueIdentifier,
    IssueIdentificationOutput,
    SecondaryIssue,
    issue_identification_node,
)
from app.agents.stages.jurisdiction import (
    JurisdictionResolver,
    jurisdiction_node,
    SUPPORTED_RAG_JURISDICTIONS,
)


class TestComplexityHeuristics:
    """Test complexity classification heuristics."""

    def test_document_uploaded_forces_complex(self):
        """Uploaded document should always route to complex."""
        state = {
            "current_query": "What are my rights?",
            "uploaded_document_url": "https://example.com/lease.pdf",
            "issue_classification": None,
        }
        result = classify_complexity_heuristic(state)
        assert result == "complex"

    def test_multiple_secondary_issues_forces_complex(self):
        """Multiple secondary issues should route to complex."""
        state = {
            "current_query": "I have multiple problems",
            "uploaded_document_url": None,
            "issue_classification": {
                "primary_issue": {"area": "tenancy"},
                "secondary_issues": [
                    {"area": "contract"},
                    {"area": "consumer"},
                ],
                "complexity_score": 0.3,
            },
        }
        result = classify_complexity_heuristic(state)
        assert result == "complex"

    def test_high_complexity_score_forces_complex(self):
        """High complexity score should route to complex."""
        state = {
            "current_query": "Complicated situation",
            "uploaded_document_url": None,
            "issue_classification": {
                "primary_issue": {"area": "employment"},
                "secondary_issues": [],
                "complexity_score": 0.7,
            },
        }
        result = classify_complexity_heuristic(state)
        assert result == "complex"

    def test_multiple_jurisdictions_forces_complex(self):
        """Multiple jurisdictions should route to complex."""
        state = {
            "current_query": "Issue across states",
            "uploaded_document_url": None,
            "issue_classification": {
                "primary_issue": {"area": "property"},
                "secondary_issues": [],
                "complexity_score": 0.3,
                "involves_multiple_jurisdictions": True,
            },
        }
        result = classify_complexity_heuristic(state)
        assert result == "complex"

    def test_simple_pattern_matches_simple(self):
        """Simple query patterns should route to simple."""
        for pattern in SIMPLE_QUERY_PATTERNS[:3]:  # Test first few patterns
            state = {
                "current_query": f"{pattern} in NSW?",
                "uploaded_document_url": None,
                "issue_classification": {
                    "primary_issue": {"area": "tenancy"},
                    "secondary_issues": [],
                    "complexity_score": 0.2,
                },
            }
            result = classify_complexity_heuristic(state)
            assert result == "simple", f"Pattern '{pattern}' should be simple"

    def test_complex_indicator_forces_complex(self):
        """Complex indicators in query should route to complex."""
        for indicator in ["dispute", "court", "tribunal"]:
            state = {
                "current_query": f"I have a {indicator} with my landlord",
                "uploaded_document_url": None,
                "issue_classification": {
                    "primary_issue": {"area": "tenancy"},
                    "secondary_issues": [],
                    "complexity_score": 0.3,
                },
            }
            result = classify_complexity_heuristic(state)
            assert result == "complex", f"Indicator '{indicator}' should be complex"

    def test_low_score_no_secondary_is_simple(self):
        """Low complexity score with no secondary issues should be simple."""
        state = {
            "current_query": "General question about something",
            "uploaded_document_url": None,
            "issue_classification": {
                "primary_issue": {"area": "tenancy"},
                "secondary_issues": [],
                "complexity_score": 0.2,
            },
        }
        result = classify_complexity_heuristic(state)
        assert result == "simple"

    def test_uncertain_for_borderline_cases(self):
        """Borderline cases should return uncertain."""
        state = {
            "current_query": "A moderately detailed question about my situation that doesn't match patterns",
            "uploaded_document_url": None,
            "issue_classification": {
                "primary_issue": {"area": "other"},
                "secondary_issues": [],
                "complexity_score": 0.35,  # Just under threshold
            },
        }
        result = classify_complexity_heuristic(state)
        assert result == "uncertain"


class TestComplexityRouter:
    """Test complexity router with LLM fallback."""

    @pytest.fixture
    def mock_llm_response(self):
        """Create mock LLM response."""
        def _create(path: str, confidence: float = 0.8):
            return ComplexityClassification(
                path=path,
                reasoning="Test reasoning",
                confidence=confidence
            )
        return _create

    @pytest.mark.asyncio
    async def test_uses_heuristic_when_certain(self, mock_llm_response):
        """Should use heuristic result when not uncertain."""
        router = ComplexityRouter()

        state = {
            "current_query": "What are my rights as a tenant?",
            "uploaded_document_url": None,
            "issue_classification": {
                "primary_issue": {"area": "tenancy"},
                "secondary_issues": [],
                "complexity_score": 0.2,
            },
        }

        # Should not call LLM since heuristic is certain
        with patch.object(router, 'chain') as mock_chain:
            result = await router.classify(state)
            mock_chain.ainvoke.assert_not_called()
            assert result == "simple"

    @pytest.mark.asyncio
    async def test_uses_llm_when_uncertain(self, mock_llm_response):
        """Should use LLM when heuristic is uncertain."""
        router = ComplexityRouter()

        state = {
            "current_query": "A borderline case that needs LLM classification",
            "uploaded_document_url": None,
            "issue_classification": {
                "primary_issue": {"area": "other"},
                "secondary_issues": [],
                "complexity_score": 0.35,
            },
        }

        with patch.object(router, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_llm_response("complex"))
            result = await router.classify(state)
            mock_chain.ainvoke.assert_called_once()
            assert result == "complex"

    @pytest.mark.asyncio
    async def test_defaults_to_simple_on_error(self):
        """Should default to simple on LLM error."""
        router = ComplexityRouter()

        state = {
            "current_query": "Uncertain query",
            "uploaded_document_url": None,
            "issue_classification": {
                "primary_issue": {"area": "other"},
                "secondary_issues": [],
                "complexity_score": 0.35,
            },
        }

        with patch.object(router, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("API error"))
            result = await router.classify(state)
            assert result == "simple"


class TestIssueIdentifier:
    """Test issue identification."""

    @pytest.fixture
    def mock_identification_output(self):
        """Create mock issue identification output."""
        def _create(
            area: str = "tenancy",
            sub_category: str = "bond_dispute",
            complexity: float = 0.3,
            secondary: list = None
        ):
            return IssueIdentificationOutput(
                primary_area=area,
                primary_sub_category=sub_category,
                primary_confidence=0.9,
                primary_description="Test description",
                secondary_issues=secondary or [],
                complexity_score=complexity,
                involves_multiple_jurisdictions=False,
                requires_document_analysis=False,
            )
        return _create

    @pytest.mark.asyncio
    async def test_identifies_tenancy_issue(self, mock_identification_output):
        """Should identify tenancy issues correctly."""
        identifier = IssueIdentifier()

        with patch.object(identifier, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_identification_output(
                area="tenancy",
                sub_category="bond_refund"
            ))

            state = {
                "current_query": "My landlord won't return my bond",
                "user_state": "NSW",
                "uploaded_document_url": None,
            }

            result = await identifier.identify(state)

            assert result["primary_issue"]["area"] == "tenancy"
            assert result["primary_issue"]["sub_category"] == "bond_refund"

    @pytest.mark.asyncio
    async def test_identifies_secondary_issues(self, mock_identification_output):
        """Should identify secondary issues."""
        identifier = IssueIdentifier()

        with patch.object(identifier, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_identification_output(
                area="employment",
                sub_category="unfair_dismissal",
                secondary=[
                    SecondaryIssue(
                        area="discrimination",
                        sub_category="pregnancy_discrimination",
                        confidence=0.7,
                        description="Possible discrimination"
                    )
                ]
            ))

            state = {
                "current_query": "I was fired after announcing my pregnancy",
                "user_state": "VIC",
                "uploaded_document_url": None,
            }

            result = await identifier.identify(state)

            assert result["primary_issue"]["area"] == "employment"
            assert len(result["secondary_issues"]) == 1
            assert result["secondary_issues"][0]["area"] == "discrimination"

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Should return default classification on error."""
        identifier = IssueIdentifier()

        with patch.object(identifier, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("API error"))

            state = {
                "current_query": "Test query",
                "user_state": "NSW",
            }

            result = await identifier.identify(state)

            assert result["primary_issue"]["area"] == "other"
            assert result["complexity_score"] == 0.5


class TestIssueIdentificationNode:
    """Test issue identification node execution."""

    @pytest.mark.asyncio
    async def test_node_updates_state(self):
        """Node should update state with classification."""
        mock_classification = {
            "primary_issue": {
                "area": "tenancy",
                "sub_category": "rent_increase",
                "confidence": 0.9,
                "description": "Rent increase query",
            },
            "secondary_issues": [],
            "complexity_score": 0.3,
            "involves_multiple_jurisdictions": False,
            "requires_document_analysis": False,
        }

        with patch('app.agents.stages.issue_identification.get_issue_identifier') as mock_get:
            mock_identifier = MagicMock()
            mock_identifier.identify = AsyncMock(return_value=mock_classification)
            mock_get.return_value = mock_identifier

            state = {
                "current_query": "Can my landlord increase rent?",
                "user_state": "NSW",
                "stages_completed": ["safety_gate"],
            }

            result = await issue_identification_node(state, {})

            assert result["issue_classification"] == mock_classification
            assert "issue_identification" in result["stages_completed"]


class TestJurisdictionResolver:
    """Test jurisdiction resolution."""

    def test_quick_resolve_tenancy_nsw(self):
        """Tenancy should resolve to state jurisdiction quickly."""
        resolver = JurisdictionResolver()

        result = resolver._quick_resolve(
            legal_area="tenancy",
            sub_category="bond_dispute",
            user_state="NSW"
        )

        assert result is not None
        assert result["primary_jurisdiction"] == "NSW"
        assert result["fallback_to_federal"] is False

    def test_quick_resolve_tenancy_vic_fallback(self):
        """VIC tenancy should have fallback flag (no RAG data)."""
        resolver = JurisdictionResolver()

        result = resolver._quick_resolve(
            legal_area="tenancy",
            sub_category="eviction",
            user_state="VIC"
        )

        assert result is not None
        assert result["primary_jurisdiction"] == "VIC"
        assert result["fallback_to_federal"] is True  # VIC not in SUPPORTED_RAG_JURISDICTIONS

    def test_quick_resolve_employment_federal(self):
        """Employment should resolve to federal."""
        resolver = JurisdictionResolver()

        result = resolver._quick_resolve(
            legal_area="employment",
            sub_category="unfair_dismissal",
            user_state="NSW"
        )

        assert result is not None
        assert result["primary_jurisdiction"] == "FEDERAL"

    def test_quick_resolve_family_federal(self):
        """Family law should resolve to federal."""
        resolver = JurisdictionResolver()

        result = resolver._quick_resolve(
            legal_area="family",
            sub_category="divorce",
            user_state="QLD"
        )

        assert result is not None
        assert result["primary_jurisdiction"] == "FEDERAL"

    def test_quick_resolve_returns_none_for_complex(self):
        """Complex cases should return None (need LLM)."""
        resolver = JurisdictionResolver()

        result = resolver._quick_resolve(
            legal_area="other",
            sub_category="unknown",
            user_state="NSW"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_uses_quick_when_possible(self):
        """Should use quick resolution when possible."""
        resolver = JurisdictionResolver()

        state = {
            "current_query": "Tenant rights question",
            "user_state": "NSW",
            "issue_classification": {
                "primary_issue": {
                    "area": "tenancy",
                    "sub_category": "bond_refund",
                },
            },
        }

        with patch.object(resolver, 'chain') as mock_chain:
            result = await resolver.resolve(state)
            mock_chain.ainvoke.assert_not_called()
            assert result["primary_jurisdiction"] == "NSW"


class TestJurisdictionNode:
    """Test jurisdiction node execution."""

    @pytest.mark.asyncio
    async def test_node_updates_state(self):
        """Node should update state with jurisdiction result."""
        mock_result = {
            "primary_jurisdiction": "FEDERAL",
            "applicable_jurisdictions": ["FEDERAL", "NSW"],
            "jurisdiction_conflicts": [],
            "fallback_to_federal": False,
            "reasoning": "Employment is federal",
        }

        with patch('app.agents.stages.jurisdiction.get_jurisdiction_resolver') as mock_get:
            mock_resolver = MagicMock()
            mock_resolver.resolve = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_resolver

            state = {
                "current_query": "Unfair dismissal question",
                "user_state": "NSW",
                "issue_classification": {
                    "primary_issue": {"area": "employment", "sub_category": "unfair_dismissal"},
                },
                "stages_completed": ["safety_gate", "issue_identification"],
            }

            result = await jurisdiction_node(state, {})

            assert result["jurisdiction_result"] == mock_result
            assert "jurisdiction" in result["stages_completed"]


class TestSupportedJurisdictions:
    """Test jurisdiction support configuration."""

    def test_supported_rag_jurisdictions(self):
        """Verify supported RAG jurisdictions are correct."""
        assert "NSW" in SUPPORTED_RAG_JURISDICTIONS
        assert "QLD" in SUPPORTED_RAG_JURISDICTIONS
        assert "FEDERAL" in SUPPORTED_RAG_JURISDICTIONS
        assert "VIC" not in SUPPORTED_RAG_JURISDICTIONS  # No VIC data in corpus
