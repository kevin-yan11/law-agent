"""
Legal Document Lookup Tool using RAG

Provides hybrid search (vector + keyword) with reranking for
retrieving relevant Australian legislation.
"""

import asyncio
from langchain_core.tools import tool
from app.db import supabase
from app.services.hybrid_retriever import get_hybrid_retriever
from app.services.reranker import get_reranker
from app.config import logger


# State code to jurisdiction mapping
STATE_TO_JURISDICTION = {
    "NSW": "NSW",
    "QLD": "QLD",
    "FEDERAL": "FEDERAL",
    "ACT": "FEDERAL",  # ACT uses federal law primarily
}

# States not yet supported (no data in corpus)
UNSUPPORTED_STATES = ["VIC", "SA", "WA", "TAS", "NT"]


@tool
def lookup_law(query: str, state: str = "VIC") -> str | list[dict]:
    """
    Search for Australian laws/acts using advanced RAG retrieval.

    Uses hybrid search (vector similarity + keyword matching) combined
    with neural reranking for high-quality legal document retrieval.

    Args:
        query: Legal question or keywords (e.g., 'rent increase notice period',
               'tenant bond refund rights', 'criminal sentencing guidelines').
        state: Australian state/territory code (NSW, QLD, FEDERAL supported).
               For unsupported states (VIC, SA, WA, TAS, NT), falls back to
               showing relevant Federal law.

    Returns:
        List of matching legal passages with citations and source URLs,
        or error message if search fails.
    """
    try:
        # Map state to jurisdiction
        jurisdiction = STATE_TO_JURISDICTION.get(state)
        is_unsupported = state in UNSUPPORTED_STATES

        if is_unsupported:
            jurisdiction = "FEDERAL"  # Fallback

        logger.info(f"lookup_law: query='{query}', state='{state}', jurisdiction='{jurisdiction}'")

        # Run async search in sync context
        results = asyncio.run(_search_and_rerank(query, jurisdiction))

        if not results:
            msg = f"No legislation found for '{query}'"
            if jurisdiction:
                msg += f" in {state if not is_unsupported else 'Federal law'}"
            return msg + ". Try different keywords or check another jurisdiction."

        # Batch fetch all parent contents (single query instead of N queries)
        parent_contents = _get_parent_contents_batch(results)

        formatted_results = []
        for chunk in results:
            parent_id = chunk.get("parent_chunk_id")
            parent_content = parent_contents.get(parent_id) if parent_id else None

            result = {
                "content": parent_content or chunk.get("content", ""),
                "citation": chunk.get("citation", "Unknown"),
                "jurisdiction": chunk.get("jurisdiction", state),
                "source_url": chunk.get("source_url", ""),
                "relevance_score": round(
                    chunk.get("rerank_score", chunk.get("rrf_score", 0)),
                    3
                ),
            }
            formatted_results.append(result)

        # Add note if showing federal law for unsupported state
        if is_unsupported and formatted_results:
            formatted_results.insert(0, {
                "note": f"Note: {state} legislation is not yet available in our database. "
                        f"Showing relevant Federal law instead. For state-specific advice, "
                        f"please consult a legal professional."
            })

        return formatted_results

    except Exception as e:
        logger.error(f"Error in lookup_law: {e}")
        return "Sorry, I couldn't search the legal database at this time. Please try again later."


async def _search_and_rerank(query: str, jurisdiction: str | None) -> list[dict]:
    """
    Execute hybrid search and reranking pipeline.

    Args:
        query: The search query
        jurisdiction: Jurisdiction filter (FEDERAL, NSW, QLD) or None

    Returns:
        List of reranked document chunks
    """
    retriever = get_hybrid_retriever()
    reranker = get_reranker()

    # Hybrid search (vector + keyword with RRF)
    results = await retriever.search(
        query=query,
        jurisdiction=jurisdiction,
        top_k=20
    )

    if not results:
        return []

    # Rerank for final precision
    reranked = await reranker.rerank(
        query=query,
        documents=results,
        top_n=10  # Get more candidates before deduplication
    )

    # Deduplicate by parent chunk to ensure diversity
    deduplicated = _deduplicate_by_parent(reranked)

    return deduplicated[:5]  # Return top 5 unique parents


def _deduplicate_by_parent(results: list[dict]) -> list[dict]:
    """
    Keep only the top-scoring chunk per parent/document.

    This ensures diversity in results - we don't want 3 chunks from
    the same Act when we could show 3 different relevant Acts.

    Args:
        results: List of chunks, already sorted by score (highest first)

    Returns:
        Deduplicated list with one chunk per parent
    """
    seen_parents = set()
    deduplicated = []

    for chunk in results:
        # Use parent_chunk_id if exists, otherwise document_id (for parent-only chunks)
        key = chunk.get("parent_chunk_id") or chunk.get("document_id")
        if key and key not in seen_parents:
            seen_parents.add(key)
            deduplicated.append(chunk)
        elif not key:
            # No parent or document ID - include it anyway
            deduplicated.append(chunk)

    return deduplicated


def _get_parent_contents_batch(chunks: list[dict]) -> dict[str, str]:
    """
    Fetch all parent chunk contents in a single batch query.

    When we retrieve child chunks (small, precise), we often want
    to return the parent chunks (larger, more context) to the user.
    This function batches all parent lookups into one query to avoid N+1.

    Args:
        chunks: List of retrieved chunk dicts

    Returns:
        Dict mapping parent_chunk_id -> content
    """
    parent_ids = [c.get("parent_chunk_id") for c in chunks if c.get("parent_chunk_id")]

    if not parent_ids:
        return {}

    try:
        response = supabase.table("legislation_chunks") \
            .select("id, content") \
            .in_("id", parent_ids) \
            .execute()

        if response.data:
            return {row["id"]: row["content"] for row in response.data}
    except Exception as e:
        logger.warning(f"Failed to batch fetch parent chunks: {e}")

    return {}


# Keep backward compatibility - also export as function
def search_law(query: str, state: str = "VIC") -> str | list[dict]:
    """Alias for lookup_law for backward compatibility."""
    return lookup_law.invoke({"query": query, "state": state})
