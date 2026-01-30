"""Reusable analysis modules for deep case analysis.

These modules provide simplified interfaces for:
- Organizing facts from conversation (timeline, parties, evidence)
- Analyzing risks and weaknesses
- Recommending strategies

Used by the conversational graph when users opt into deep analysis.
"""

from .fact_organizer import organize_facts, FactSummary
from .risk_analyzer import analyze_risks, RiskSummary
from .strategy_advisor import recommend_strategy, StrategySummary

__all__ = [
    "organize_facts",
    "FactSummary",
    "analyze_risks",
    "RiskSummary",
    "recommend_strategy",
    "StrategySummary",
]
