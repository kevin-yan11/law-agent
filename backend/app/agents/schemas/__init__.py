"""Schemas for adaptive legal agent."""

from app.agents.schemas.emergency_resources import EMERGENCY_RESOURCES, get_resources_for_risk
from app.agents.schemas.legal_elements import (
    get_element_schema,
    get_areas_with_schemas,
    ELEMENT_SCHEMAS,
    LegalAreaElements,
    ElementDefinition,
)
from app.agents.schemas.case_precedents import (
    get_cases_by_area,
    get_cases_by_subcategory,
    search_cases_by_keywords,
    get_case_by_name,
    ALL_CASES,
    MockCase,
)

__all__ = [
    # Emergency resources
    "EMERGENCY_RESOURCES",
    "get_resources_for_risk",
    # Legal elements
    "get_element_schema",
    "get_areas_with_schemas",
    "ELEMENT_SCHEMAS",
    "LegalAreaElements",
    "ElementDefinition",
    # Case precedents
    "get_cases_by_area",
    "get_cases_by_subcategory",
    "search_cases_by_keywords",
    "get_case_by_name",
    "ALL_CASES",
    "MockCase",
]
