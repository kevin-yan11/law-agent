"""Tests for Phase 3: Fact Structuring and Legal Elements Mapping."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.stages.fact_structuring import (
    FactStructurer,
    FactStructuringOutput,
    TimelineEventOutput,
    PartyOutput,
    EvidenceOutput,
    fact_structuring_node,
)
from app.agents.stages.legal_elements import (
    LegalElementsAnalyzer,
    ElementsAnalysisOutput,
    LegalElementOutput,
    legal_elements_node,
)
from app.agents.schemas.legal_elements import (
    get_element_schema,
    get_areas_with_schemas,
    ELEMENT_SCHEMAS,
)


# ============================================
# Fact Structuring Tests
# ============================================


class TestFactStructurer:
    """Test fact structuring functionality."""

    @pytest.fixture
    def mock_fact_output(self):
        """Create mock fact structuring output."""
        def _create(
            timeline: list = None,
            parties: list = None,
            evidence: list = None,
            key_facts: list = None,
            fact_gaps: list = None,
            narrative: str = "Test narrative"
        ):
            return FactStructuringOutput(
                timeline=timeline or [
                    TimelineEventOutput(
                        date="2024-01-15",
                        description="Lease signed",
                        significance="critical",
                        source="user_stated"
                    ),
                    TimelineEventOutput(
                        date="2024-06-01",
                        description="Moved out",
                        significance="critical",
                        source="user_stated"
                    ),
                ],
                parties=parties or [
                    PartyOutput(role="tenant", name=None, is_user=True, relationship_to_user=None),
                    PartyOutput(role="landlord", name="John", is_user=False, relationship_to_user="landlord"),
                ],
                evidence=evidence or [
                    EvidenceOutput(type="document", description="Lease agreement", status="available", strength="strong"),
                ],
                key_facts=key_facts or ["Tenant paid bond", "Lease ended"],
                fact_gaps=fact_gaps or ["Exit condition report status unknown"],
                narrative_summary=narrative,
            )
        return _create

    @pytest.mark.asyncio
    async def test_structures_tenancy_facts(self, mock_fact_output):
        """Should structure facts from tenancy query."""
        structurer = FactStructurer()

        with patch.object(structurer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_fact_output())

            state = {
                "current_query": "My landlord won't return my bond. I moved out in June.",
                "user_state": "NSW",
                "uploaded_document_url": None,
                "issue_classification": {
                    "primary_issue": {
                        "area": "tenancy",
                        "sub_category": "bond_refund",
                        "description": "Bond refund dispute",
                    },
                    "secondary_issues": [],
                },
            }

            result = await structurer.structure_facts(state)

            assert len(result["timeline"]) == 2
            assert len(result["parties"]) == 2
            assert len(result["evidence"]) == 1
            assert result["parties"][0]["is_user"] is True

    @pytest.mark.asyncio
    async def test_identifies_parties_correctly(self, mock_fact_output):
        """Should identify user and other parties."""
        structurer = FactStructurer()

        parties = [
            PartyOutput(role="employee", name=None, is_user=True, relationship_to_user=None),
            PartyOutput(role="employer", name="ABC Corp", is_user=False, relationship_to_user="employer"),
            PartyOutput(role="manager", name="Jane", is_user=False, relationship_to_user="supervisor"),
        ]

        with patch.object(structurer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_fact_output(parties=parties))

            state = {
                "current_query": "I was fired by my manager Jane at ABC Corp",
                "user_state": "VIC",
                "uploaded_document_url": None,
                "issue_classification": {
                    "primary_issue": {"area": "employment", "sub_category": "unfair_dismissal"},
                    "secondary_issues": [],
                },
            }

            result = await structurer.structure_facts(state)

            user_parties = [p for p in result["parties"] if p["is_user"]]
            other_parties = [p for p in result["parties"] if not p["is_user"]]

            assert len(user_parties) == 1
            assert len(other_parties) == 2
            assert user_parties[0]["role"] == "employee"

    @pytest.mark.asyncio
    async def test_extracts_timeline_with_significance(self, mock_fact_output):
        """Should extract timeline with significance levels."""
        structurer = FactStructurer()

        timeline = [
            TimelineEventOutput(
                date="2024-01-01",
                description="Started job",
                significance="background",
                source="user_stated"
            ),
            TimelineEventOutput(
                date="2024-06-15",
                description="Received verbal warning",
                significance="relevant",
                source="user_stated"
            ),
            TimelineEventOutput(
                date="2024-07-01",
                description="Terminated without notice",
                significance="critical",
                source="user_stated"
            ),
        ]

        with patch.object(structurer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_fact_output(timeline=timeline))

            state = {
                "current_query": "I was fired without notice",
                "user_state": "NSW",
                "uploaded_document_url": None,
                "issue_classification": {
                    "primary_issue": {"area": "employment", "sub_category": "unfair_dismissal"},
                    "secondary_issues": [],
                },
            }

            result = await structurer.structure_facts(state)

            critical_events = [e for e in result["timeline"] if e["significance"] == "critical"]
            assert len(critical_events) == 1
            assert "Terminated" in critical_events[0]["description"]

    @pytest.mark.asyncio
    async def test_catalogs_evidence_with_status(self, mock_fact_output):
        """Should catalog evidence with availability status."""
        structurer = FactStructurer()

        evidence = [
            EvidenceOutput(type="document", description="Employment contract", status="available", strength="strong"),
            EvidenceOutput(type="communication", description="Termination email", status="available", strength="strong"),
            EvidenceOutput(type="witness", description="Colleague who witnessed", status="mentioned", strength="moderate"),
            EvidenceOutput(type="document", description="Performance reviews", status="needed", strength="strong"),
        ]

        with patch.object(structurer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_fact_output(evidence=evidence))

            state = {
                "current_query": "I have my contract and the termination email. My colleague saw what happened.",
                "user_state": "QLD",
                "uploaded_document_url": None,
                "issue_classification": {
                    "primary_issue": {"area": "employment", "sub_category": "unfair_dismissal"},
                    "secondary_issues": [],
                },
            }

            result = await structurer.structure_facts(state)

            available = [e for e in result["evidence"] if e["status"] == "available"]
            needed = [e for e in result["evidence"] if e["status"] == "needed"]

            assert len(available) == 2
            assert len(needed) == 1

    @pytest.mark.asyncio
    async def test_identifies_fact_gaps(self, mock_fact_output):
        """Should identify missing information."""
        structurer = FactStructurer()

        fact_gaps = [
            "Exact date of termination unknown",
            "Reason given for dismissal unclear",
            "Employment period not specified",
        ]

        with patch.object(structurer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_fact_output(fact_gaps=fact_gaps))

            state = {
                "current_query": "I was fired recently",
                "user_state": "NSW",
                "uploaded_document_url": None,
                "issue_classification": {
                    "primary_issue": {"area": "employment", "sub_category": "unfair_dismissal"},
                    "secondary_issues": [],
                },
            }

            result = await structurer.structure_facts(state)

            assert len(result["fact_gaps"]) == 3
            assert any("date" in gap.lower() for gap in result["fact_gaps"])

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Should return minimal structure on error."""
        structurer = FactStructurer()

        with patch.object(structurer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("API error"))

            state = {
                "current_query": "Test query",
                "user_state": "NSW",
                "issue_classification": {},
            }

            result = await structurer.structure_facts(state)

            # Should return default structure, not raise
            assert result["timeline"] == []
            assert len(result["parties"]) == 1  # At least user party
            assert result["parties"][0]["is_user"] is True

    @pytest.mark.asyncio
    async def test_includes_issue_context(self, mock_fact_output):
        """Should pass issue classification context to LLM."""
        structurer = FactStructurer()

        with patch.object(structurer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_fact_output())

            state = {
                "current_query": "Bond dispute with landlord",
                "user_state": "NSW",
                "uploaded_document_url": None,
                "issue_classification": {
                    "primary_issue": {
                        "area": "tenancy",
                        "sub_category": "bond_refund",
                        "description": "Tenant seeking bond refund",
                    },
                    "secondary_issues": [
                        {"area": "contract", "description": "Lease dispute"},
                    ],
                },
            }

            await structurer.structure_facts(state)

            # Verify issue context was included in LLM call
            call_args = mock_chain.ainvoke.call_args[0][0]
            assert call_args["legal_area"] == "tenancy"
            assert call_args["sub_category"] == "bond_refund"
            assert "tenancy" in call_args["issue_context"]


class TestFactStructuringNode:
    """Test fact structuring node execution."""

    @pytest.mark.asyncio
    async def test_node_updates_state(self):
        """Node should update state with fact structure."""
        mock_fact_structure = {
            "timeline": [{"date": "2024-01-01", "description": "Event", "significance": "critical", "source": "user_stated"}],
            "parties": [{"role": "tenant", "name": None, "is_user": True, "relationship_to_user": None}],
            "evidence": [],
            "key_facts": ["Test fact"],
            "fact_gaps": ["Missing info"],
            "narrative_summary": "Test narrative",
        }

        with patch('app.agents.stages.fact_structuring.get_fact_structurer') as mock_get:
            mock_structurer = MagicMock()
            mock_structurer.structure_facts = AsyncMock(return_value=mock_fact_structure)
            mock_get.return_value = mock_structurer

            state = {
                "current_query": "Test query",
                "user_state": "NSW",
                "issue_classification": {},
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction"],
            }

            result = await fact_structuring_node(state, {})

            assert result["fact_structure"] == mock_fact_structure
            assert "fact_structuring" in result["stages_completed"]
            assert result["current_stage"] == "fact_structuring"


# ============================================
# Legal Elements Schema Tests
# ============================================


class TestLegalElementSchemas:
    """Test legal element schema definitions."""

    def test_tenancy_bond_schema_exists(self):
        """Tenancy bond refund schema should exist."""
        schema = get_element_schema("tenancy", "bond_refund")
        assert schema is not None
        assert schema["area"] == "tenancy"
        assert len(schema["elements"]) >= 3

    def test_employment_unfair_dismissal_schema_exists(self):
        """Employment unfair dismissal schema should exist."""
        schema = get_element_schema("employment", "unfair_dismissal")
        assert schema is not None
        assert schema["area"] == "employment"
        assert len(schema["elements"]) >= 4

    def test_schema_has_required_fields(self):
        """All schemas should have required fields."""
        for key, schema in ELEMENT_SCHEMAS.items():
            assert "area" in schema, f"Schema {key} missing 'area'"
            assert "sub_category" in schema, f"Schema {key} missing 'sub_category'"
            assert "claim_type" in schema, f"Schema {key} missing 'claim_type'"
            assert "elements" in schema, f"Schema {key} missing 'elements'"
            assert "relevant_legislation" in schema, f"Schema {key} missing 'relevant_legislation'"

    def test_element_definitions_complete(self):
        """Element definitions should have all required fields."""
        for key, schema in ELEMENT_SCHEMAS.items():
            for i, elem in enumerate(schema["elements"]):
                assert "name" in elem, f"Schema {key} element {i} missing 'name'"
                assert "description" in elem, f"Schema {key} element {i} missing 'description'"
                assert "typical_evidence" in elem, f"Schema {key} element {i} missing 'typical_evidence'"

    def test_alias_mappings_work(self):
        """Alias mappings should point to same schema."""
        bond_refund = get_element_schema("tenancy", "bond_refund")
        bond_dispute = get_element_schema("tenancy", "bond_dispute")
        assert bond_refund == bond_dispute

    def test_get_areas_with_schemas(self):
        """Should return list of available schemas."""
        areas = get_areas_with_schemas()
        assert len(areas) > 0
        assert "tenancy/bond_refund" in areas
        assert "employment/unfair_dismissal" in areas

    def test_nonexistent_schema_returns_none(self):
        """Unknown area/sub_category should return None."""
        schema = get_element_schema("unknown", "nonexistent")
        assert schema is None


# ============================================
# Legal Elements Analyzer Tests
# ============================================


class TestLegalElementsAnalyzer:
    """Test legal elements analysis functionality."""

    @pytest.fixture
    def mock_elements_output(self):
        """Create mock elements analysis output."""
        def _create(
            applicable_law: str = "Test Act s.1",
            elements: list = None,
            viability: str = "moderate",
            reasoning: str = "Test reasoning"
        ):
            return ElementsAnalysisOutput(
                applicable_law=applicable_law,
                elements=elements or [
                    LegalElementOutput(
                        element_name="Valid agreement",
                        description="A valid agreement existed",
                        is_satisfied="yes",
                        supporting_facts=["Contract signed"],
                        missing_facts=[],
                    ),
                    LegalElementOutput(
                        element_name="Breach occurred",
                        description="The agreement was breached",
                        is_satisfied="partial",
                        supporting_facts=["Bond not returned"],
                        missing_facts=["Written demand unclear"],
                    ),
                ],
                viability_assessment=viability,
                reasoning=reasoning,
            )
        return _create

    @pytest.mark.asyncio
    async def test_analyzes_with_predefined_schema(self, mock_elements_output):
        """Should use predefined schema when available."""
        analyzer = LegalElementsAnalyzer()

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_elements_output(
                applicable_law="Residential Tenancies Act 2010 (NSW) s.63"
            ))

            state = {
                "current_query": "My landlord won't return my bond",
                "user_state": "NSW",
                "issue_classification": {
                    "primary_issue": {
                        "area": "tenancy",
                        "sub_category": "bond_refund",
                    },
                },
                "jurisdiction_result": {
                    "primary_jurisdiction": "NSW",
                },
                "fact_structure": {
                    "timeline": [],
                    "parties": [],
                    "evidence": [],
                    "key_facts": ["Bond was paid", "Lease ended properly"],
                    "fact_gaps": [],
                    "narrative_summary": "Tenant seeking bond refund",
                },
            }

            result = await analyzer.analyze_elements(state)

            # Verify predefined schema chain was used (not fallback)
            mock_chain.ainvoke.assert_called_once()
            assert "Residential Tenancies" in result["applicable_law"]

    @pytest.mark.asyncio
    async def test_uses_fallback_for_unknown_schema(self, mock_elements_output):
        """Should use fallback LLM when no predefined schema."""
        analyzer = LegalElementsAnalyzer()

        with patch.object(analyzer, 'fallback_chain') as mock_fallback:
            mock_fallback.ainvoke = AsyncMock(return_value=mock_elements_output(
                applicable_law="Relevant legislation determined by LLM"
            ))

            state = {
                "current_query": "Unusual legal question",
                "user_state": "NSW",
                "issue_classification": {
                    "primary_issue": {
                        "area": "other",
                        "sub_category": "unusual_matter",
                    },
                },
                "jurisdiction_result": {
                    "primary_jurisdiction": "NSW",
                },
                "fact_structure": {
                    "timeline": [],
                    "parties": [],
                    "evidence": [],
                    "key_facts": [],
                    "fact_gaps": [],
                    "narrative_summary": "Unusual matter",
                },
            }

            result = await analyzer.analyze_elements(state)

            mock_fallback.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculates_satisfaction_stats(self, mock_elements_output):
        """Should calculate element satisfaction statistics."""
        analyzer = LegalElementsAnalyzer()

        elements = [
            LegalElementOutput(element_name="E1", description="D1", is_satisfied="yes", supporting_facts=[], missing_facts=[]),
            LegalElementOutput(element_name="E2", description="D2", is_satisfied="partial", supporting_facts=[], missing_facts=[]),
            LegalElementOutput(element_name="E3", description="D3", is_satisfied="no", supporting_facts=[], missing_facts=[]),
            LegalElementOutput(element_name="E4", description="D4", is_satisfied="unknown", supporting_facts=[], missing_facts=[]),
        ]

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_elements_output(elements=elements))

            state = {
                "current_query": "Test",
                "user_state": "NSW",
                "issue_classification": {
                    "primary_issue": {"area": "tenancy", "sub_category": "bond_refund"},
                },
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {
                    "timeline": [], "parties": [], "evidence": [],
                    "key_facts": [], "fact_gaps": [], "narrative_summary": "Test",
                },
            }

            result = await analyzer.analyze_elements(state)

            # yes and partial count as satisfied
            assert result["elements_satisfied"] == 2
            assert result["elements_total"] == 4

    @pytest.mark.asyncio
    async def test_viability_assessment_levels(self, mock_elements_output):
        """Should return correct viability assessment."""
        analyzer = LegalElementsAnalyzer()

        for viability in ["strong", "moderate", "weak", "insufficient_info"]:
            with patch.object(analyzer, 'chain') as mock_chain:
                mock_chain.ainvoke = AsyncMock(return_value=mock_elements_output(viability=viability))

                state = {
                    "current_query": "Test",
                    "user_state": "NSW",
                    "issue_classification": {
                        "primary_issue": {"area": "tenancy", "sub_category": "bond_refund"},
                    },
                    "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                    "fact_structure": {
                        "timeline": [], "parties": [], "evidence": [],
                        "key_facts": [], "fact_gaps": [], "narrative_summary": "Test",
                    },
                }

                result = await analyzer.analyze_elements(state)
                assert result["viability_assessment"] == viability

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Should return minimal analysis on error."""
        analyzer = LegalElementsAnalyzer()

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("API error"))

            state = {
                "current_query": "Test",
                "user_state": "NSW",
                "issue_classification": {
                    "primary_issue": {"area": "tenancy", "sub_category": "bond_refund"},
                },
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {},
            }

            result = await analyzer.analyze_elements(state)

            assert result["viability_assessment"] == "insufficient_info"
            assert result["elements_total"] == 0

    @pytest.mark.asyncio
    async def test_formats_facts_summary(self, mock_elements_output):
        """Should format fact structure into readable summary."""
        analyzer = LegalElementsAnalyzer()

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_elements_output())

            state = {
                "current_query": "Test",
                "user_state": "NSW",
                "issue_classification": {
                    "primary_issue": {"area": "tenancy", "sub_category": "bond_refund"},
                },
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {
                    "timeline": [
                        {"date": "2024-01-15", "description": "Lease signed", "significance": "critical", "source": "user_stated"},
                    ],
                    "parties": [
                        {"role": "tenant", "name": None, "is_user": True, "relationship_to_user": None},
                    ],
                    "evidence": [
                        {"type": "document", "description": "Lease", "status": "available", "strength": "strong"},
                    ],
                    "key_facts": ["Paid $1000 bond"],
                    "fact_gaps": ["Exit report missing"],
                    "narrative_summary": "Tenant paid bond, seeking refund",
                },
            }

            await analyzer.analyze_elements(state)

            call_args = mock_chain.ainvoke.call_args[0][0]
            # Verify facts_summary contains timeline info
            assert "Timeline" in call_args["facts_summary"] or "Lease signed" in call_args["facts_summary"]


class TestLegalElementsNode:
    """Test legal elements node execution."""

    @pytest.mark.asyncio
    async def test_node_updates_state(self):
        """Node should update state with elements analysis."""
        mock_analysis = {
            "applicable_law": "Test Act s.1",
            "elements": [
                {
                    "element_name": "Test element",
                    "description": "Test description",
                    "is_satisfied": "yes",
                    "supporting_facts": [],
                    "missing_facts": [],
                }
            ],
            "elements_satisfied": 1,
            "elements_total": 1,
            "viability_assessment": "strong",
            "reasoning": "Test reasoning",
        }

        with patch('app.agents.stages.legal_elements.get_legal_elements_analyzer') as mock_get:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_elements = AsyncMock(return_value=mock_analysis)
            mock_get.return_value = mock_analyzer

            state = {
                "current_query": "Test query",
                "user_state": "NSW",
                "issue_classification": {},
                "jurisdiction_result": {},
                "fact_structure": {},
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction", "fact_structuring"],
            }

            result = await legal_elements_node(state, {})

            assert result["elements_analysis"] == mock_analysis
            assert "legal_elements" in result["stages_completed"]
            assert result["current_stage"] == "legal_elements"


# ============================================
# Integration Tests (State Flow)
# ============================================


class TestPhase3StateFlow:
    """Test state flows through Phase 3 stages."""

    @pytest.mark.asyncio
    async def test_fact_structuring_receives_issue_context(self):
        """Fact structuring should receive issue classification from state."""
        with patch('app.agents.stages.fact_structuring.get_fact_structurer') as mock_get:
            mock_structurer = MagicMock()
            mock_structurer.structure_facts = AsyncMock(return_value={
                "timeline": [], "parties": [], "evidence": [],
                "key_facts": [], "fact_gaps": [], "narrative_summary": "Test",
            })
            mock_get.return_value = mock_structurer

            state = {
                "current_query": "Bond issue",
                "user_state": "NSW",
                "issue_classification": {
                    "primary_issue": {"area": "tenancy", "sub_category": "bond_refund"},
                    "secondary_issues": [],
                },
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction"],
            }

            await fact_structuring_node(state, {})

            # Verify structure_facts received full state
            mock_structurer.structure_facts.assert_called_once()
            called_state = mock_structurer.structure_facts.call_args[0][0]
            assert called_state["issue_classification"]["primary_issue"]["area"] == "tenancy"

    @pytest.mark.asyncio
    async def test_legal_elements_receives_fact_structure(self):
        """Legal elements should receive fact structure from state."""
        with patch('app.agents.stages.legal_elements.get_legal_elements_analyzer') as mock_get:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_elements = AsyncMock(return_value={
                "applicable_law": "Test",
                "elements": [],
                "elements_satisfied": 0,
                "elements_total": 0,
                "viability_assessment": "insufficient_info",
                "reasoning": "Test",
            })
            mock_get.return_value = mock_analyzer

            state = {
                "current_query": "Bond issue",
                "user_state": "NSW",
                "issue_classification": {
                    "primary_issue": {"area": "tenancy", "sub_category": "bond_refund"},
                },
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {
                    "timeline": [{"date": "2024-01-01", "description": "Event", "significance": "critical", "source": "user_stated"}],
                    "parties": [],
                    "evidence": [],
                    "key_facts": ["Important fact"],
                    "fact_gaps": ["Missing info"],
                    "narrative_summary": "Test narrative",
                },
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction", "fact_structuring"],
            }

            await legal_elements_node(state, {})

            # Verify analyze_elements received state with fact_structure
            mock_analyzer.analyze_elements.assert_called_once()
            called_state = mock_analyzer.analyze_elements.call_args[0][0]
            assert called_state["fact_structure"]["key_facts"] == ["Important fact"]
