"""Tests for lookup_law RAG tool."""

import pytest


class TestLookupLaw:
    """Test the lookup_law tool functionality."""

    def test_state_to_jurisdiction_mapping(self):
        """Test that state codes map to correct jurisdictions."""
        from app.tools.lookup_law import STATE_TO_JURISDICTION

        assert STATE_TO_JURISDICTION.get("NSW") == "NSW"
        assert STATE_TO_JURISDICTION.get("QLD") == "QLD"
        assert STATE_TO_JURISDICTION.get("FEDERAL") == "FEDERAL"
        assert STATE_TO_JURISDICTION.get("ACT") == "FEDERAL"  # ACT uses federal

    def test_unsupported_states_defined(self):
        """Test that unsupported states are correctly identified."""
        from app.tools.lookup_law import UNSUPPORTED_STATES

        assert "VIC" in UNSUPPORTED_STATES
        assert "SA" in UNSUPPORTED_STATES
        assert "WA" in UNSUPPORTED_STATES
        assert "TAS" in UNSUPPORTED_STATES
        assert "NT" in UNSUPPORTED_STATES
        # Supported states should not be in unsupported list
        assert "NSW" not in UNSUPPORTED_STATES
        assert "QLD" not in UNSUPPORTED_STATES

    def test_lookup_law_tool_exists(self):
        """Test that lookup_law tool is properly defined."""
        from app.tools.lookup_law import lookup_law

        assert hasattr(lookup_law, "invoke")
        assert hasattr(lookup_law, "name")

    def test_search_law_alias_exists(self):
        """Test that search_law alias function exists."""
        from app.tools.lookup_law import search_law

        assert callable(search_law)


class TestHybridRetriever:
    """Test the hybrid retriever service."""

    def test_retriever_singleton(self):
        """Test that retriever uses singleton pattern."""
        from app.services.hybrid_retriever import get_hybrid_retriever

        retriever1 = get_hybrid_retriever()
        retriever2 = get_hybrid_retriever()

        assert retriever1 is retriever2

    def test_rrf_constant_is_reasonable(self):
        """Test that RRF constant is within expected range."""
        from app.services.hybrid_retriever import HybridRetriever

        # RRF_K is a class attribute
        assert hasattr(HybridRetriever, "RRF_K")
        # RRF_K is typically 60 in literature
        assert 1 <= HybridRetriever.RRF_K <= 100

    def test_retriever_has_search_method(self):
        """Test that retriever has async search method."""
        from app.services.hybrid_retriever import get_hybrid_retriever

        retriever = get_hybrid_retriever()
        assert hasattr(retriever, "search")
        assert hasattr(retriever, "search_sync")


class TestEmbeddingService:
    """Test the embedding service."""

    def test_embedding_service_singleton(self):
        """Test that embedding service uses singleton pattern."""
        from app.services.embedding_service import get_embedding_service

        service1 = get_embedding_service()
        service2 = get_embedding_service()

        assert service1 is service2
