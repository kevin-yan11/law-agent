"""
Case Law Search Tool using AustLII

Searches the Australian Legal Information Institute (AustLII) for
court decisions and tribunal rulings across all Australian jurisdictions.
"""

import asyncio
from langchain_core.tools import tool
from app.services.austlii_search import get_austlii_searcher
from app.config import logger


@tool
def search_case_law(query: str, state: str) -> str | list[dict]:
    """
    Search for Australian case law (court decisions, tribunal rulings).

    Searches AustLII for relevant court cases across all Australian jurisdictions.
    Use this when the user asks about court cases, legal precedents, or how
    courts have ruled on specific issues.

    Args:
        query: Case topic or legal issue (e.g., 'unfair dismissal wrongful termination',
               'landlord failure to repair rental property', 'bond refund dispute').
        state: Australian state/territory code - REQUIRED. Use the user's selected
               state (NSW, QLD, VIC, SA, WA, TAS, NT, ACT, or FEDERAL).

    Returns:
        List of relevant cases with citations and source URLs,
        or message if no cases found.
    """
    try:
        logger.info(f"search_case_law: query='{query}', state='{state}'")

        searcher = get_austlii_searcher()
        results = asyncio.run(
            searcher.search_cases(query, state, max_results=5)
        )

        if not results:
            return (
                f"No case law found for '{query}' in {state} on AustLII. "
                f"Try different keywords or broaden the search terms."
            )

        formatted = []
        formatted.append({
            "note": f"Case law results from AustLII for {state}. "
                    f"Verify details via the source links provided."
        })

        for item in results:
            # Build a summary from available metadata
            summary_parts = [item["title"]]
            if item.get("court"):
                summary_parts.append(f"Court: {item['court']}")
            if item.get("date"):
                summary_parts.append(f"Date: {item['date']}")

            formatted.append({
                "content": " | ".join(summary_parts),
                "citation": item.get("citation", item["title"]),
                "jurisdiction": state,
                "source_url": item["url"],
                "court": item.get("court", ""),
                "date": item.get("date", ""),
                "confidence": "web_search",
                "source": "austlii_case",
            })

        formatted.append({"result_quality": "austlii_case_search"})

        logger.info(
            f"search_case_law returned {len(results)} cases for '{query}' in {state}"
        )
        return formatted

    except Exception as e:
        logger.error(f"Error in search_case_law: {e}")
        return "Sorry, I couldn't search for case law at this time. Please try again later."
