"""Deep analysis module for comprehensive legal case analysis.

Provides a single consolidated LLM call that performs:
- Organizing facts from conversation (timeline, parties, evidence)
- Analyzing risks and weaknesses
- Recommending strategies

Used by the conversational graph when users opt into deep analysis.
"""

from .deep_analysis import run_consolidated_analysis, ConsolidatedAnalysis

__all__ = [
    "run_consolidated_analysis",
    "ConsolidatedAnalysis",
]
