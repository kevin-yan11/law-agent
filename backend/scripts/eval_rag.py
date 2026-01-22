"""
RAG Evaluation Script for AusLaw AI

Evaluates the quality of the legal document retrieval system using
test queries dynamically generated from actual database content.

Usage:
    cd backend
    conda activate law_agent
    python scripts/eval_rag.py              # Auto-generate test cases from DB
    python scripts/eval_rag.py --verbose    # Show detailed results
    python scripts/eval_rag.py --stats      # Show DB statistics first
    python scripts/eval_rag.py --static     # Use hardcoded test cases instead
"""

import argparse
import re
import sys
from pathlib import Path
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.tools.lookup_law import lookup_law
from app.db import supabase


@dataclass
class EvalCase:
    """A single evaluation test case."""
    query: str
    jurisdiction: str
    expected_citations: list[str]  # Partial matches OK
    description: str = ""


def generate_eval_cases_from_db(max_per_jurisdiction: int = 10) -> list[EvalCase]:
    """
    Dynamically generate evaluation cases based on actual legislation in the database.

    Queries the database for random legislation and creates test cases
    using keywords extracted from the citation.

    Args:
        max_per_jurisdiction: Maximum test cases per jurisdiction

    Returns:
        List of EvalCase objects based on current DB content
    """
    cases = []

    for jurisdiction in ["NSW", "QLD", "FEDERAL"]:
        try:
            # Get random sample of legislation from this jurisdiction
            response = supabase.table("legislation_documents") \
                .select("citation") \
                .eq("jurisdiction", jurisdiction) \
                .limit(max_per_jurisdiction) \
                .execute()

            if not response.data:
                continue

            for doc in response.data:
                citation = doc["citation"]
                # Extract keywords from citation for query
                # e.g., "Conveyancers Licensing Act 2003 (NSW)" -> "conveyancers licensing"
                query = _citation_to_query(citation)
                if query:
                    cases.append(EvalCase(
                        query=query,
                        jurisdiction=jurisdiction,
                        expected_citations=[_extract_act_name(citation)],
                        description=f"{jurisdiction}: {citation[:50]}"
                    ))

        except Exception as e:
            print(f"Error fetching {jurisdiction} legislation: {e}")

    return cases


def _citation_to_query(citation: str) -> str:
    """
    Convert a citation to a search query by extracting key terms.

    Args:
        citation: Full citation like "Conveyancers Licensing Act 2003 (NSW)"

    Returns:
        Search query like "conveyancers licensing"
    """
    # Remove year and state suffix
    # "Conveyancers Licensing Act 2003 (NSW)" -> "Conveyancers Licensing Act"
    cleaned = re.sub(r'\s*\d{4}\s*', ' ', citation)  # Remove year
    cleaned = re.sub(r'\s*\([^)]+\)\s*', ' ', cleaned)  # Remove (NSW), (Qld), etc.
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()  # Normalize spaces

    # Remove common suffixes that don't help search
    cleaned = re.sub(r'\s+Act$', '', cleaned, flags=re.IGNORECASE)

    # Take first 3-4 meaningful words
    words = cleaned.split()[:4]

    return ' '.join(words).lower()


def _extract_act_name(citation: str) -> str:
    """
    Extract the Act name without year for partial matching.

    Args:
        citation: Full citation like "Conveyancers Licensing Act 2003 (NSW)"

    Returns:
        Act name like "Conveyancers Licensing Act"
    """
    # Remove year and state
    cleaned = re.sub(r'\s*\d{4}\s*', ' ', citation)
    cleaned = re.sub(r'\s*\([^)]+\)\s*', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


# Static fallback cases (used if DB query fails)
STATIC_EVAL_CASES = [
    EvalCase(
        query="conveyancer licensing requirements",
        jurisdiction="NSW",
        expected_citations=["Conveyancers Licensing Act"],
        description="Conveyancer licensing NSW"
    ),
    EvalCase(
        query="government advertising rules",
        jurisdiction="NSW",
        expected_citations=["Government Advertising Act"],
        description="Government advertising NSW"
    ),
    EvalCase(
        query="education curriculum assessment",
        jurisdiction="QLD",
        expected_citations=["Education", "Curriculum"],
        description="Education curriculum QLD"
    ),
]


@dataclass
class EvalResult:
    """Result of evaluating a single case."""
    case: EvalCase
    success: bool
    retrieved_citations: list[str]
    matched_expected: list[str]
    error: str | None = None


def check_citation_match(retrieved: str, expected_list: list[str]) -> list[str]:
    """
    Check if retrieved citation matches any expected citation (partial match).

    Args:
        retrieved: The citation string from search results
        expected_list: List of expected citation substrings

    Returns:
        List of matched expected citations
    """
    matches = []
    retrieved_lower = retrieved.lower()
    for expected in expected_list:
        if expected.lower() in retrieved_lower:
            matches.append(expected)
    return matches


def evaluate_case(case: EvalCase) -> EvalResult:
    """
    Evaluate a single test case.

    Args:
        case: The evaluation case to test

    Returns:
        EvalResult with success/failure and details
    """
    try:
        # Call the lookup_law tool
        results = lookup_law.invoke({
            "query": case.query,
            "state": case.jurisdiction
        })

        # Handle error string response
        if isinstance(results, str):
            return EvalResult(
                case=case,
                success=False,
                retrieved_citations=[],
                matched_expected=[],
                error=results
            )

        # Filter out note dictionaries (for unsupported states)
        results = [r for r in results if "citation" in r]

        # Extract citations from results
        retrieved_citations = [r.get("citation", "") for r in results]

        # Check which expected citations were found
        all_matches = set()
        for citation in retrieved_citations:
            matches = check_citation_match(citation, case.expected_citations)
            all_matches.update(matches)

        # Success if at least one expected citation was found
        success = len(all_matches) > 0

        return EvalResult(
            case=case,
            success=success,
            retrieved_citations=retrieved_citations,
            matched_expected=list(all_matches)
        )

    except Exception as e:
        return EvalResult(
            case=case,
            success=False,
            retrieved_citations=[],
            matched_expected=[],
            error=str(e)
        )


def run_evaluation(verbose: bool = False, use_static: bool = False) -> dict:
    """
    Run the full evaluation suite.

    Args:
        verbose: Whether to print detailed output per case
        use_static: Use static test cases instead of generating from DB

    Returns:
        Dictionary with evaluation metrics
    """
    print("=" * 60)
    print("AusLaw AI - RAG Evaluation")
    print("=" * 60)

    # Get test cases
    if use_static:
        eval_cases = STATIC_EVAL_CASES
        print("\nUsing static test cases")
    else:
        eval_cases = generate_eval_cases_from_db()
        print(f"\nGenerated {len(eval_cases)} test cases from database")

    print(f"Running {len(eval_cases)} test cases...\n")

    results: list[EvalResult] = []

    for i, case in enumerate(eval_cases, 1):
        result = evaluate_case(case)
        results.append(result)

        # Progress indicator
        status = "PASS" if result.success else "FAIL"
        status_color = "\033[92m" if result.success else "\033[91m"
        reset_color = "\033[0m"

        print(f"[{i:2d}/{len(eval_cases)}] {status_color}{status}{reset_color} | {case.jurisdiction:7s} | {case.query[:45]}")

        if verbose:
            print(f"       Expected: {case.expected_citations}")
            print(f"       Retrieved: {result.retrieved_citations[:3]}")  # Show top 3
            if result.matched_expected:
                print(f"       Matched: {result.matched_expected}")
            if result.error:
                print(f"       Error: {result.error}")
            print()

    # Calculate metrics
    total = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total - passed

    # Group failures by jurisdiction
    failures_by_jurisdiction: dict[str, list[EvalResult]] = {}
    for r in results:
        if not r.success:
            j = r.case.jurisdiction
            if j not in failures_by_jurisdiction:
                failures_by_jurisdiction[j] = []
            failures_by_jurisdiction[j].append(r)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\nTotal:  {total}")
    print(f"Passed: {passed} ({100*passed/total:.1f}%)")
    print(f"Failed: {failed} ({100*failed/total:.1f}%)")

    if failures_by_jurisdiction:
        print(f"\nFailures by jurisdiction:")
        for jurisdiction, failures in sorted(failures_by_jurisdiction.items()):
            print(f"  {jurisdiction}: {len(failures)} failures")
            for f in failures:
                print(f"    - {f.case.query[:50]}")
                if f.error:
                    print(f"      Error: {f.error[:60]}")

    # Metrics dictionary
    metrics = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / total if total > 0 else 0,
        "failures_by_jurisdiction": {
            j: len(f) for j, f in failures_by_jurisdiction.items()
        }
    }

    print("\n" + "=" * 60)

    return metrics


def show_database_stats():
    """Show current database statistics."""
    print("\n" + "=" * 60)
    print("DATABASE STATISTICS")
    print("=" * 60)

    try:
        for jurisdiction in ['NSW', 'QLD', 'FEDERAL']:
            response = supabase.table('legislation_documents') \
                .select('id', count='exact') \
                .eq('jurisdiction', jurisdiction) \
                .execute()
            print(f"{jurisdiction}: {response.count} documents")

        # Total chunks
        response = supabase.table('legislation_chunks') \
            .select('id', count='exact') \
            .execute()
        print(f"\nTotal chunks: {response.count}")

    except Exception as e:
        print(f"Error fetching stats: {e}")

    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality")
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output for each test case"
    )
    parser.add_argument(
        "--static", "-s",
        action="store_true",
        help="Use static test cases instead of generating from DB"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show database statistics before running"
    )
    args = parser.parse_args()

    if args.stats:
        show_database_stats()

    metrics = run_evaluation(verbose=args.verbose, use_static=args.static)

    # Exit with error code if pass rate is below threshold
    if metrics["pass_rate"] < 0.7:
        print("\nWARNING: Pass rate below 70% threshold!")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
