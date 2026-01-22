"""
RAG Evaluation Script for AusLaw AI

Evaluates the quality of the legal document retrieval system using
a curated set of test queries with expected citations.

Usage:
    cd backend
    conda activate law_agent
    python scripts/eval_rag.py
    python scripts/eval_rag.py --verbose  # Show detailed results
"""

import argparse
import asyncio
import sys
from pathlib import Path
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.tools.lookup_law import lookup_law
from app.config import logger


@dataclass
class EvalCase:
    """A single evaluation test case."""
    query: str
    jurisdiction: str
    expected_citations: list[str]  # Partial matches OK (e.g., "Residential Tenancies" matches "Residential Tenancies Act 2010")
    description: str = ""


# Evaluation dataset - add more cases as you discover edge cases
EVAL_CASES = [
    # NSW Tenancy
    EvalCase(
        query="tenant bond refund timeframe",
        jurisdiction="NSW",
        expected_citations=["Residential Tenancies"],
        description="Bond refund rules in NSW"
    ),
    EvalCase(
        query="landlord notice period to end tenancy",
        jurisdiction="NSW",
        expected_citations=["Residential Tenancies"],
        description="Termination notice requirements NSW"
    ),
    EvalCase(
        query="rent increase notice requirements",
        jurisdiction="NSW",
        expected_citations=["Residential Tenancies"],
        description="Rent increase rules NSW"
    ),

    # QLD Tenancy
    EvalCase(
        query="bond refund dispute resolution",
        jurisdiction="QLD",
        expected_citations=["Residential Tenancies", "Rooming Accommodation"],
        description="Bond disputes in QLD"
    ),
    EvalCase(
        query="tenant rights for repairs",
        jurisdiction="QLD",
        expected_citations=["Residential Tenancies", "Rooming Accommodation"],
        description="Repair obligations QLD"
    ),

    # Federal - Family Law
    EvalCase(
        query="child custody arrangements divorce",
        jurisdiction="FEDERAL",
        expected_citations=["Family Law"],
        description="Custody under federal family law"
    ),
    EvalCase(
        query="property settlement after separation",
        jurisdiction="FEDERAL",
        expected_citations=["Family Law"],
        description="Property division federal"
    ),

    # Federal - Criminal
    EvalCase(
        query="fraud criminal penalties",
        jurisdiction="FEDERAL",
        expected_citations=["Criminal Code", "Crimes Act"],
        description="Federal fraud offences"
    ),

    # NSW Criminal
    EvalCase(
        query="assault charges and penalties",
        jurisdiction="NSW",
        expected_citations=["Crimes Act"],
        description="Assault offences NSW"
    ),

    # Employment
    EvalCase(
        query="unfair dismissal claim requirements",
        jurisdiction="FEDERAL",
        expected_citations=["Fair Work"],
        description="Unfair dismissal federal"
    ),
    EvalCase(
        query="minimum wage requirements",
        jurisdiction="FEDERAL",
        expected_citations=["Fair Work"],
        description="Minimum wage federal"
    ),

    # Consumer Protection
    EvalCase(
        query="consumer refund rights faulty product",
        jurisdiction="FEDERAL",
        expected_citations=["Consumer Law", "Competition and Consumer"],
        description="Consumer guarantees federal"
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


def evaluate_case(case: EvalCase, verbose: bool = False) -> EvalResult:
    """
    Evaluate a single test case.

    Args:
        case: The evaluation case to test
        verbose: Whether to print detailed output

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


def run_evaluation(verbose: bool = False) -> dict:
    """
    Run the full evaluation suite.

    Args:
        verbose: Whether to print detailed output per case

    Returns:
        Dictionary with evaluation metrics
    """
    print("=" * 60)
    print("AusLaw AI - RAG Evaluation")
    print("=" * 60)
    print(f"\nRunning {len(EVAL_CASES)} test cases...\n")

    results: list[EvalResult] = []

    for i, case in enumerate(EVAL_CASES, 1):
        result = evaluate_case(case, verbose)
        results.append(result)

        # Progress indicator
        status = "PASS" if result.success else "FAIL"
        status_color = "\033[92m" if result.success else "\033[91m"
        reset_color = "\033[0m"

        print(f"[{i:2d}/{len(EVAL_CASES)}] {status_color}{status}{reset_color} | {case.jurisdiction:7s} | {case.query[:45]}")

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


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality")
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output for each test case"
    )
    args = parser.parse_args()

    metrics = run_evaluation(verbose=args.verbose)

    # Exit with error code if pass rate is below threshold
    if metrics["pass_rate"] < 0.7:
        print("\nWARNING: Pass rate below 70% threshold!")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
