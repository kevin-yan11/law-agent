"""Tests for Phase 4: Case Precedent and Risk Analysis."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.stages.case_precedent import (
    CasePrecedentAnalyzer,
    PrecedentAnalysisOutput,
    CasePrecedentOutput,
    case_precedent_node,
)
from app.agents.stages.risk_analysis import (
    RiskAnalyzer,
    RiskAnalysisOutput,
    RiskFactorOutput,
    DefenceAnalysisOutput,
    risk_analysis_node,
)
from app.agents.schemas.case_precedents import (
    get_cases_by_area,
    get_cases_by_subcategory,
    search_cases_by_keywords,
    get_case_by_name,
    ALL_CASES,
    TENANCY_CASES,
    EMPLOYMENT_CASES,
)


# ============================================
# Case Precedent Schema Tests
# ============================================


class TestCasePrecedentSchemas:
    """Test case precedent database functions."""

    def test_all_cases_populated(self):
        """Should have cases in the database."""
        assert len(ALL_CASES) > 10

    def test_get_cases_by_area_tenancy(self):
        """Should return tenancy cases."""
        cases = get_cases_by_area("tenancy")
        assert len(cases) >= 3
        assert all(c["legal_area"] == "tenancy" for c in cases)

    def test_get_cases_by_area_employment(self):
        """Should return employment cases."""
        cases = get_cases_by_area("employment")
        assert len(cases) >= 3
        assert all(c["legal_area"] == "employment" for c in cases)

    def test_get_cases_by_subcategory(self):
        """Should filter by subcategory."""
        cases = get_cases_by_subcategory("tenancy", "bond_refund")
        assert len(cases) >= 1
        assert all("bond_refund" in c["sub_categories"] for c in cases)

    def test_search_by_keywords(self):
        """Should find cases by keywords."""
        cases = search_cases_by_keywords(["bond", "cleaning"])
        assert len(cases) >= 1
        # First result should be most relevant
        assert any(
            "bond" in kw.lower()
            for kw in cases[0]["relevance_keywords"]
        )

    def test_search_by_keywords_with_area_filter(self):
        """Should filter search by legal area."""
        cases = search_cases_by_keywords(["dismissal"], legal_area="employment")
        assert len(cases) >= 1
        assert all(c["legal_area"] == "employment" for c in cases)

    def test_get_case_by_name(self):
        """Should find specific case by name."""
        case = get_case_by_name("Shields v Westpac Banking Corp")
        assert case is not None
        assert case["legal_area"] == "tenancy"

    def test_get_case_by_name_not_found(self):
        """Should return None for unknown case."""
        case = get_case_by_name("Nonexistent v Case")
        assert case is None

    def test_case_has_required_fields(self):
        """All cases should have required fields."""
        required_fields = [
            "case_name", "citation", "year", "jurisdiction",
            "legal_area", "sub_categories", "key_facts",
            "key_holding", "outcome", "relevance_keywords"
        ]
        for case in ALL_CASES:
            for field in required_fields:
                assert field in case, f"Case {case.get('case_name', 'Unknown')} missing {field}"


# ============================================
# Case Precedent Analyzer Tests
# ============================================


class TestCasePrecedentAnalyzer:
    """Test case precedent analysis functionality."""

    @pytest.fixture
    def mock_precedent_output(self):
        """Create mock precedent analysis output."""
        def _create(
            cases: list = None,
            pattern: str = None,
            typical_outcome: str = None,
            distinguishing: list = None
        ):
            return PrecedentAnalysisOutput(
                analyzed_cases=cases or [
                    CasePrecedentOutput(
                        case_name="Test Case v Respondent",
                        citation="[2023] TEST 123",
                        year=2023,
                        jurisdiction="NSW",
                        relevance_score=0.8,
                        key_holding="Test holding",
                        how_it_applies="Applies because of similar facts",
                        outcome_for_similar_party="favorable",
                    ),
                ],
                pattern_identified=pattern or "Courts typically favor tenants in bond disputes",
                typical_outcome=typical_outcome or "Bond returned in full in most cases",
                distinguishing_factors=distinguishing or ["Strong evidence available"],
            )
        return _create

    @pytest.mark.asyncio
    async def test_analyzes_tenancy_precedents(self, mock_precedent_output):
        """Should analyze tenancy case precedents."""
        analyzer = CasePrecedentAnalyzer()

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_precedent_output())

            state = {
                "current_query": "My landlord won't return my bond",
                "user_state": "NSW",
                "issue_classification": {
                    "primary_issue": {
                        "area": "tenancy",
                        "sub_category": "bond_refund",
                    },
                },
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {
                    "key_facts": ["Paid $2000 bond", "Left property clean"],
                    "evidence": [],
                    "timeline": [],
                    "parties": [],
                    "fact_gaps": [],
                    "narrative_summary": "Bond dispute",
                },
                "elements_analysis": {
                    "applicable_law": "Residential Tenancies Act 2010 (NSW)",
                    "viability_assessment": "moderate",
                    "elements_satisfied": 3,
                    "elements_total": 5,
                    "elements": [],
                },
            }

            result = await analyzer.analyze_precedents(state)

            assert len(result["matching_cases"]) >= 1
            assert result["pattern_identified"] is not None

    @pytest.mark.asyncio
    async def test_extracts_keywords_from_state(self):
        """Should extract relevant keywords for case search."""
        analyzer = CasePrecedentAnalyzer()

        state = {
            "issue_classification": {
                "primary_issue": {
                    "area": "employment",
                    "sub_category": "unfair_dismissal",
                },
            },
            "fact_structure": {
                "key_facts": ["Employed for 5 years", "Terminated without warning"],
            },
            "elements_analysis": {
                "elements": [
                    {"element_name": "Employment relationship"},
                    {"element_name": "Procedural fairness"},
                ],
            },
        }

        keywords = analyzer._extract_keywords_from_state(state)

        assert len(keywords) > 0
        assert "unfair" in keywords or "dismissal" in keywords

    @pytest.mark.asyncio
    async def test_filters_low_relevance_cases(self, mock_precedent_output):
        """Should filter out cases with low relevance scores."""
        analyzer = CasePrecedentAnalyzer()

        cases = [
            CasePrecedentOutput(
                case_name="Relevant Case",
                citation="[2023] TEST 1",
                year=2023,
                jurisdiction="NSW",
                relevance_score=0.8,
                key_holding="Relevant holding",
                how_it_applies="Directly applies",
                outcome_for_similar_party="favorable",
            ),
            CasePrecedentOutput(
                case_name="Irrelevant Case",
                citation="[2023] TEST 2",
                year=2023,
                jurisdiction="NSW",
                relevance_score=0.2,  # Below threshold
                key_holding="Not relevant",
                how_it_applies="Tangentially related",
                outcome_for_similar_party="mixed",
            ),
        ]

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_precedent_output(cases=cases))

            state = {
                "current_query": "Test query",
                "issue_classification": {
                    "primary_issue": {"area": "tenancy", "sub_category": "bond_refund"},
                },
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {"key_facts": [], "evidence": [], "timeline": [], "parties": [], "fact_gaps": [], "narrative_summary": ""},
                "elements_analysis": {},
            }

            result = await analyzer.analyze_precedents(state)

            # Should only include cases with relevance >= 0.4
            assert len(result["matching_cases"]) == 1
            assert result["matching_cases"][0]["case_name"] == "Relevant Case"

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Should return empty analysis on error."""
        analyzer = CasePrecedentAnalyzer()

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("API error"))

            state = {
                "current_query": "Test",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {},
                "elements_analysis": {},
            }

            result = await analyzer.analyze_precedents(state)

            assert result["matching_cases"] == []
            assert "Unable to complete" in result["distinguishing_factors"][0]


class TestCasePrecedentNode:
    """Test case precedent node execution."""

    @pytest.mark.asyncio
    async def test_node_updates_state(self):
        """Node should update state with precedent analysis."""
        mock_analysis = {
            "matching_cases": [
                {
                    "case_name": "Test Case",
                    "citation": "[2023] TEST 1",
                    "year": 2023,
                    "jurisdiction": "NSW",
                    "relevance_score": 0.8,
                    "key_holding": "Test holding",
                    "how_it_applies": "Test application",
                    "outcome_for_similar_party": "favorable",
                }
            ],
            "pattern_identified": "Test pattern",
            "typical_outcome": "Favorable for tenants",
            "distinguishing_factors": ["Strong evidence"],
        }

        with patch('app.agents.stages.case_precedent.get_case_precedent_analyzer') as mock_get:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_precedents = AsyncMock(return_value=mock_analysis)
            mock_get.return_value = mock_analyzer

            state = {
                "current_query": "Test",
                "issue_classification": {},
                "jurisdiction_result": {},
                "fact_structure": {},
                "elements_analysis": {},
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction", "fact_structuring", "legal_elements"],
            }

            result = await case_precedent_node(state)

            assert result["precedent_analysis"] == mock_analysis
            assert "case_precedent" in result["stages_completed"]
            assert result["current_stage"] == "case_precedent"


# ============================================
# Risk Analysis Tests
# ============================================


class TestRiskAnalyzer:
    """Test risk analysis functionality."""

    @pytest.fixture
    def mock_risk_output(self):
        """Create mock risk analysis output."""
        def _create(
            overall_level: str = "medium",
            risks: list = None,
            evidence_weaknesses: list = None,
            defences: list = None,
            counterfactuals: list = None,
            time_sensitivity: str = None
        ):
            return RiskAnalysisOutput(
                overall_risk_level=overall_level,
                risks=risks or [
                    RiskFactorOutput(
                        description="Lack of written documentation",
                        severity="medium",
                        likelihood="possible",
                        mitigation="Gather any available evidence",
                    ),
                ],
                evidence_weaknesses=evidence_weaknesses or ["No exit condition report"],
                possible_defences=defences or [
                    DefenceAnalysisOutput(
                        defence_type="Property damage claim",
                        likelihood_of_use=0.6,
                        strength="moderate",
                        counter_strategy="Present photos of property condition",
                    ),
                ],
                counterfactual_scenarios=counterfactuals or ["What if landlord claims cleaning costs?"],
                time_sensitivity=time_sensitivity,
            )
        return _create

    @pytest.mark.asyncio
    async def test_analyzes_risks(self, mock_risk_output):
        """Should analyze risks for the matter."""
        analyzer = RiskAnalyzer()

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_risk_output())

            state = {
                "current_query": "My landlord won't return my bond",
                "user_state": "NSW",
                "issue_classification": {
                    "primary_issue": {"area": "tenancy", "sub_category": "bond_refund"},
                },
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {
                    "key_facts": ["Bond was $2000", "Moved out last week"],
                    "fact_gaps": ["Exit condition report missing"],
                    "evidence": [
                        {"description": "Photos", "status": "available", "strength": "moderate"},
                    ],
                    "timeline": [],
                    "parties": [],
                    "narrative_summary": "Bond dispute",
                },
                "elements_analysis": {
                    "viability_assessment": "moderate",
                    "elements_satisfied": 3,
                    "elements_total": 5,
                    "elements": [],
                },
                "precedent_analysis": {
                    "matching_cases": [],
                    "pattern_identified": None,
                    "typical_outcome": None,
                    "distinguishing_factors": [],
                },
            }

            result = await analyzer.analyze_risks(state)

            assert result["overall_risk_level"] in ["high", "medium", "low"]
            assert len(result["risks"]) >= 1
            assert len(result["possible_defences"]) >= 1

    @pytest.mark.asyncio
    async def test_identifies_evidence_weaknesses(self, mock_risk_output):
        """Should identify evidence weaknesses."""
        analyzer = RiskAnalyzer()

        weaknesses = ["No written lease", "Missing receipts", "No witnesses"]

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_risk_output(
                evidence_weaknesses=weaknesses
            ))

            state = {
                "current_query": "Test",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {"key_facts": [], "fact_gaps": [], "evidence": [], "timeline": [], "parties": [], "narrative_summary": ""},
                "elements_analysis": {},
                "precedent_analysis": {},
            }

            result = await analyzer.analyze_risks(state)

            assert result["evidence_weaknesses"] == weaknesses

    @pytest.mark.asyncio
    async def test_analyzes_defences(self, mock_risk_output):
        """Should analyze possible defences."""
        analyzer = RiskAnalyzer()

        defences = [
            DefenceAnalysisOutput(
                defence_type="Valid reason defence",
                likelihood_of_use=0.8,
                strength="strong",
                counter_strategy="Challenge the validity of the stated reason",
            ),
            DefenceAnalysisOutput(
                defence_type="Procedural compliance",
                likelihood_of_use=0.5,
                strength="moderate",
                counter_strategy="Document procedural failures",
            ),
        ]

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_risk_output(defences=defences))

            state = {
                "current_query": "I was unfairly dismissed",
                "issue_classification": {"primary_issue": {"area": "employment", "sub_category": "unfair_dismissal"}},
                "jurisdiction_result": {"primary_jurisdiction": "FEDERAL"},
                "fact_structure": {"key_facts": [], "fact_gaps": [], "evidence": [], "timeline": [], "parties": [], "narrative_summary": ""},
                "elements_analysis": {},
                "precedent_analysis": {},
            }

            result = await analyzer.analyze_risks(state)

            assert len(result["possible_defences"]) == 2
            assert result["possible_defences"][0]["likelihood_of_use"] == 0.8

    @pytest.mark.asyncio
    async def test_generates_counterfactuals(self, mock_risk_output):
        """Should generate counterfactual scenarios."""
        analyzer = RiskAnalyzer()

        counterfactuals = [
            "What if the employer claims misconduct?",
            "What if there were prior verbal warnings?",
        ]

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_risk_output(
                counterfactuals=counterfactuals
            ))

            state = {
                "current_query": "Test",
                "issue_classification": {"primary_issue": {"area": "employment", "sub_category": "unfair_dismissal"}},
                "jurisdiction_result": {"primary_jurisdiction": "FEDERAL"},
                "fact_structure": {"key_facts": [], "fact_gaps": [], "evidence": [], "timeline": [], "parties": [], "narrative_summary": ""},
                "elements_analysis": {},
                "precedent_analysis": {},
            }

            result = await analyzer.analyze_risks(state)

            assert result["counterfactual_scenarios"] == counterfactuals

    @pytest.mark.asyncio
    async def test_identifies_time_sensitivity(self, mock_risk_output):
        """Should identify time-sensitive factors."""
        analyzer = RiskAnalyzer()

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(return_value=mock_risk_output(
                time_sensitivity="21-day deadline to lodge unfair dismissal claim"
            ))

            state = {
                "current_query": "I was fired yesterday",
                "issue_classification": {"primary_issue": {"area": "employment", "sub_category": "unfair_dismissal"}},
                "jurisdiction_result": {"primary_jurisdiction": "FEDERAL"},
                "fact_structure": {"key_facts": [], "fact_gaps": [], "evidence": [], "timeline": [], "parties": [], "narrative_summary": ""},
                "elements_analysis": {},
                "precedent_analysis": {},
            }

            result = await analyzer.analyze_risks(state)

            assert "21-day" in result["time_sensitivity"]

    @pytest.mark.asyncio
    async def test_determines_user_position(self):
        """Should determine user's position (plaintiff/defendant)."""
        analyzer = RiskAnalyzer()

        # Plaintiff/applicant case
        state_plaintiff = {
            "current_query": "I want to sue my employer",
            "fact_structure": {"narrative_summary": "Employee seeking compensation"},
        }
        assert "plaintiff" in analyzer._determine_user_position(state_plaintiff)

        # Defendant/respondent case
        state_defendant = {
            "current_query": "I've been sued by my tenant",
            "fact_structure": {"narrative_summary": "Landlord being sued"},
        }
        assert "defendant" in analyzer._determine_user_position(state_defendant)

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Should return default assessment on error."""
        analyzer = RiskAnalyzer()

        with patch.object(analyzer, 'chain') as mock_chain:
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("API error"))

            state = {
                "current_query": "Test",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {},
                "elements_analysis": {},
                "precedent_analysis": {},
            }

            result = await analyzer.analyze_risks(state)

            assert result["overall_risk_level"] == "medium"
            assert len(result["risks"]) >= 1
            assert "Unable to complete" in result["risks"][0]["description"]


class TestRiskAnalysisNode:
    """Test risk analysis node execution."""

    @pytest.mark.asyncio
    async def test_node_updates_state(self):
        """Node should update state with risk assessment."""
        mock_assessment = {
            "overall_risk_level": "medium",
            "risks": [
                {
                    "description": "Test risk",
                    "severity": "medium",
                    "likelihood": "possible",
                    "mitigation": "Test mitigation",
                }
            ],
            "evidence_weaknesses": ["Test weakness"],
            "possible_defences": [],
            "counterfactual_scenarios": ["What if X?"],
            "time_sensitivity": None,
        }

        with patch('app.agents.stages.risk_analysis.get_risk_analyzer') as mock_get:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_risks = AsyncMock(return_value=mock_assessment)
            mock_get.return_value = mock_analyzer

            state = {
                "current_query": "Test",
                "issue_classification": {},
                "jurisdiction_result": {},
                "fact_structure": {},
                "elements_analysis": {},
                "precedent_analysis": {},
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction", "fact_structuring", "legal_elements", "case_precedent"],
            }

            result = await risk_analysis_node(state)

            assert result["risk_assessment"] == mock_assessment
            assert "risk_analysis" in result["stages_completed"]
            assert result["current_stage"] == "risk_analysis"


# ============================================
# Integration Tests (State Flow)
# ============================================


class TestPhase4StateFlow:
    """Test state flows through Phase 4 stages."""

    @pytest.mark.asyncio
    async def test_case_precedent_receives_elements_analysis(self):
        """Case precedent should receive elements analysis from state."""
        with patch('app.agents.stages.case_precedent.get_case_precedent_analyzer') as mock_get:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_precedents = AsyncMock(return_value={
                "matching_cases": [],
                "pattern_identified": None,
                "typical_outcome": None,
                "distinguishing_factors": [],
            })
            mock_get.return_value = mock_analyzer

            state = {
                "current_query": "Bond issue",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {"key_facts": ["Test fact"], "evidence": [], "timeline": [], "parties": [], "fact_gaps": [], "narrative_summary": ""},
                "elements_analysis": {
                    "applicable_law": "RTA 2010 s.63",
                    "viability_assessment": "strong",
                    "elements_satisfied": 4,
                    "elements_total": 5,
                    "elements": [],
                },
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction", "fact_structuring", "legal_elements"],
            }

            await case_precedent_node(state)

            called_state = mock_analyzer.analyze_precedents.call_args[0][0]
            assert called_state["elements_analysis"]["viability_assessment"] == "strong"

    @pytest.mark.asyncio
    async def test_risk_analysis_receives_precedent_analysis(self):
        """Risk analysis should receive precedent analysis from state."""
        with patch('app.agents.stages.risk_analysis.get_risk_analyzer') as mock_get:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze_risks = AsyncMock(return_value={
                "overall_risk_level": "low",
                "risks": [],
                "evidence_weaknesses": [],
                "possible_defences": [],
                "counterfactual_scenarios": [],
                "time_sensitivity": None,
            })
            mock_get.return_value = mock_analyzer

            state = {
                "current_query": "Bond issue",
                "issue_classification": {"primary_issue": {"area": "tenancy", "sub_category": "bond_refund"}},
                "jurisdiction_result": {"primary_jurisdiction": "NSW"},
                "fact_structure": {"key_facts": [], "fact_gaps": [], "evidence": [], "timeline": [], "parties": [], "narrative_summary": ""},
                "elements_analysis": {},
                "precedent_analysis": {
                    "matching_cases": [{"case_name": "Test v Case", "outcome_for_similar_party": "favorable"}],
                    "pattern_identified": "Courts favor tenants",
                    "typical_outcome": "Bond returned",
                    "distinguishing_factors": [],
                },
                "stages_completed": ["safety_gate", "issue_identification", "jurisdiction", "fact_structuring", "legal_elements", "case_precedent"],
            }

            await risk_analysis_node(state)

            called_state = mock_analyzer.analyze_risks.call_args[0][0]
            assert called_state["precedent_analysis"]["pattern_identified"] == "Courts favor tenants"
