"""Mock case precedent database for Australian legal matters.

This provides representative case examples for the case precedent stage.
In production, this would be replaced with a proper case law database or API.

Note: These are simplified educational examples based on well-known Australian
cases. They should not be cited as legal authority.
"""

from typing import TypedDict, Literal


class MockCase(TypedDict):
    """A mock case record."""
    case_name: str
    citation: str
    year: int
    jurisdiction: str
    legal_area: str
    sub_categories: list[str]
    key_facts: str
    key_holding: str
    outcome: Literal["plaintiff", "defendant", "mixed", "settled"]
    relevance_keywords: list[str]


# ============================================
# Tenancy Cases
# ============================================

TENANCY_CASES: list[MockCase] = [
    {
        "case_name": "Shields v Westpac Banking Corp",
        "citation": "[2019] NSWCATCD 70",
        "year": 2019,
        "jurisdiction": "NSW",
        "legal_area": "tenancy",
        "sub_categories": ["bond_refund", "fair_wear_tear"],
        "key_facts": "Tenant disputed bond deductions for carpet cleaning and minor wall marks after 3-year tenancy.",
        "key_holding": "Marks consistent with normal use over tenancy period constitute fair wear and tear. Landlord cannot claim for routine cleaning without evidence of damage beyond normal use.",
        "outcome": "plaintiff",
        "relevance_keywords": ["bond", "cleaning", "fair wear", "carpet", "marks", "deduction"],
    },
    {
        "case_name": "Commissioner for Fair Trading v Rixon",
        "citation": "[2020] NSWCATAP 138",
        "year": 2020,
        "jurisdiction": "NSW",
        "legal_area": "tenancy",
        "sub_categories": ["eviction_notice", "retaliatory_eviction"],
        "key_facts": "Landlord issued no-grounds termination notice shortly after tenant complained about repairs.",
        "key_holding": "Termination notice issued in response to tenant exercising legal rights may constitute retaliatory conduct under the Act.",
        "outcome": "plaintiff",
        "relevance_keywords": ["eviction", "retaliation", "repairs", "notice", "termination"],
    },
    {
        "case_name": "Martin v Housing NSW",
        "citation": "[2018] NSWCATAP 288",
        "year": 2018,
        "jurisdiction": "NSW",
        "legal_area": "tenancy",
        "sub_categories": ["repairs_maintenance", "urgent_repairs"],
        "key_facts": "Social housing tenant waited 8 months for hot water system repair despite multiple requests.",
        "key_holding": "Landlord's duty to maintain premises in reasonable repair applies regardless of property ownership. Extended delay in urgent repairs may entitle tenant to compensation.",
        "outcome": "plaintiff",
        "relevance_keywords": ["repairs", "hot water", "urgent", "maintenance", "delay", "compensation"],
    },
    {
        "case_name": "Singh v Johnson Property Management",
        "citation": "[2021] QCAT 412",
        "year": 2021,
        "jurisdiction": "QLD",
        "legal_area": "tenancy",
        "sub_categories": ["bond_refund", "end_of_lease"],
        "key_facts": "Tenant left property clean but landlord claimed bond for professional cleaning not in lease.",
        "key_holding": "Unless specifically required by lease agreement, landlords cannot require professional cleaning. Property must be returned in similar condition allowing for fair wear and tear.",
        "outcome": "plaintiff",
        "relevance_keywords": ["bond", "cleaning", "professional", "lease terms", "condition"],
    },
    {
        "case_name": "Thompson v Ace Realty",
        "citation": "[2022] NSWCATCD 156",
        "year": 2022,
        "jurisdiction": "NSW",
        "legal_area": "tenancy",
        "sub_categories": ["rent_increase", "excessive_increase"],
        "key_facts": "Landlord sought 35% rent increase mid-lease citing market conditions.",
        "key_holding": "Rent increases during fixed term require lease provision. Increases must not be excessive having regard to market rent and condition of premises.",
        "outcome": "plaintiff",
        "relevance_keywords": ["rent increase", "excessive", "fixed term", "market rent"],
    },
]


# ============================================
# Employment Cases
# ============================================

EMPLOYMENT_CASES: list[MockCase] = [
    {
        "case_name": "Selvachandran v Peteron Plastics",
        "citation": "[2021] FWC 4892",
        "year": 2021,
        "jurisdiction": "FEDERAL",
        "legal_area": "employment",
        "sub_categories": ["unfair_dismissal", "procedural_fairness"],
        "key_facts": "Employee dismissed for alleged misconduct without opportunity to respond to allegations.",
        "key_holding": "Procedural fairness requires employee be given opportunity to respond to allegations before dismissal. Failure to afford this opportunity weighs heavily in favour of finding dismissal unfair.",
        "outcome": "plaintiff",
        "relevance_keywords": ["unfair dismissal", "procedural fairness", "misconduct", "respond", "allegations"],
    },
    {
        "case_name": "Chen v Australian Tech Solutions",
        "citation": "[2022] FWC 1876",
        "year": 2022,
        "jurisdiction": "FEDERAL",
        "legal_area": "employment",
        "sub_categories": ["unfair_dismissal", "redundancy"],
        "key_facts": "Employee made redundant but similar role advertised within weeks under different title.",
        "key_holding": "A redundancy is not genuine if employer could have reasonably redeployed employee. Re-advertising substantially similar role shortly after supports finding redundancy was not genuine.",
        "outcome": "plaintiff",
        "relevance_keywords": ["redundancy", "genuine", "redeployment", "similar role", "sham"],
    },
    {
        "case_name": "Morrison v Retail Giant Pty Ltd",
        "citation": "[2020] FWC 3421",
        "year": 2020,
        "jurisdiction": "FEDERAL",
        "legal_area": "employment",
        "sub_categories": ["underpayment", "award_rates"],
        "key_facts": "Retail worker paid flat rate below award minimums for 2 years including unpaid overtime.",
        "key_holding": "Employers cannot contract out of award entitlements. Employees entitled to recover underpayments plus interest. Systematic underpayment may attract penalties.",
        "outcome": "plaintiff",
        "relevance_keywords": ["underpayment", "award", "overtime", "minimum wage", "recovery"],
    },
    {
        "case_name": "Williams v ABC Construction",
        "citation": "[2023] FWC 892",
        "year": 2023,
        "jurisdiction": "FEDERAL",
        "legal_area": "employment",
        "sub_categories": ["unfair_dismissal", "valid_reason"],
        "key_facts": "Employee dismissed for single instance of lateness after 10 years of satisfactory service.",
        "key_holding": "Single minor breach after long service without prior warnings generally insufficient for valid dismissal. Response must be proportionate to conduct.",
        "outcome": "plaintiff",
        "relevance_keywords": ["unfair dismissal", "single incident", "long service", "proportionate", "warnings"],
    },
    {
        "case_name": "Patel v Medical Centre Group",
        "citation": "[2021] FWC 5567",
        "year": 2021,
        "jurisdiction": "FEDERAL",
        "legal_area": "employment",
        "sub_categories": ["unfair_dismissal", "discrimination"],
        "key_facts": "Pregnant employee dismissed during probation period shortly after announcing pregnancy.",
        "key_holding": "While probation dismissals have lower threshold, dismissal for prohibited reason (pregnancy) remains unlawful. Timing of dismissal relevant to inferring discriminatory reason.",
        "outcome": "plaintiff",
        "relevance_keywords": ["pregnancy", "discrimination", "probation", "unlawful", "adverse action"],
    },
]


# ============================================
# Family Law Cases
# ============================================

FAMILY_CASES: list[MockCase] = [
    {
        "case_name": "Rice v Asplund",
        "citation": "[1979] FamCA 18",
        "year": 1979,
        "jurisdiction": "FEDERAL",
        "legal_area": "family",
        "sub_categories": ["child_custody", "parenting_orders", "change_circumstances"],
        "key_facts": "Parent sought to vary parenting orders based on changed circumstances.",
        "key_holding": "Court will only reconsider parenting orders where material change in circumstances shown. Stability for children is important consideration.",
        "outcome": "mixed",
        "relevance_keywords": ["parenting orders", "variation", "changed circumstances", "stability", "custody"],
    },
    {
        "case_name": "Mallet v Mallet",
        "citation": "[1984] HCA 21",
        "year": 1984,
        "jurisdiction": "FEDERAL",
        "legal_area": "family",
        "sub_categories": ["property_settlement", "contributions"],
        "key_facts": "Dispute over property division after long marriage with unequal financial contributions.",
        "key_holding": "Both financial and non-financial contributions (homemaking, parenting) are to be assessed. Equal division not automatic but common in long marriages.",
        "outcome": "mixed",
        "relevance_keywords": ["property settlement", "contributions", "homemaker", "division", "marriage"],
    },
    {
        "case_name": "Kennon v Kennon",
        "citation": "[1997] FamCA 27",
        "year": 1997,
        "jurisdiction": "FEDERAL",
        "legal_area": "family",
        "sub_categories": ["property_settlement", "domestic_violence"],
        "key_facts": "Wife sought adjustment to property settlement based on family violence during marriage.",
        "key_holding": "Family violence may be relevant to property adjustment where it significantly affected party's contributions or earning capacity.",
        "outcome": "plaintiff",
        "relevance_keywords": ["property settlement", "family violence", "contribution", "adjustment", "domestic violence"],
    },
    {
        "case_name": "CDJ v VAJ",
        "citation": "[1998] HCA 67",
        "year": 1998,
        "jurisdiction": "FEDERAL",
        "legal_area": "family",
        "sub_categories": ["child_custody", "relocation"],
        "key_facts": "Parent sought to relocate interstate with children against other parent's wishes.",
        "key_holding": "Child's best interests paramount. Relocation not automatic right but may be permitted where in child's best interests considering meaningful relationship with both parents.",
        "outcome": "mixed",
        "relevance_keywords": ["relocation", "custody", "best interests", "interstate", "meaningful relationship"],
    },
]


# ============================================
# Consumer Law Cases
# ============================================

CONSUMER_CASES: list[MockCase] = [
    {
        "case_name": "ACCC v Valve Corporation",
        "citation": "[2016] FCA 196",
        "year": 2016,
        "jurisdiction": "FEDERAL",
        "legal_area": "consumer",
        "sub_categories": ["refund", "consumer_guarantees", "digital_goods"],
        "key_facts": "Gaming platform denied refunds to Australian consumers claiming their terms excluded refunds.",
        "key_holding": "Consumer guarantees under ACL cannot be excluded by contract. Digital goods are covered by consumer guarantees including right to refund for major failures.",
        "outcome": "plaintiff",
        "relevance_keywords": ["refund", "digital", "consumer guarantees", "major failure", "ACL"],
    },
    {
        "case_name": "ACCC v Kogan Australia",
        "citation": "[2021] FCA 1493",
        "year": 2021,
        "jurisdiction": "FEDERAL",
        "legal_area": "consumer",
        "sub_categories": ["refund", "misleading_conduct"],
        "key_facts": "Retailer advertised tax-time sale prices that were not genuine discounts from usual prices.",
        "key_holding": "Price comparisons must be genuine. Inflating 'was' price to make 'now' price appear discounted is misleading conduct.",
        "outcome": "plaintiff",
        "relevance_keywords": ["misleading", "price", "discount", "sale", "genuine"],
    },
    {
        "case_name": "Carpet Call v Chan",
        "citation": "[2018] QCATA 89",
        "year": 2018,
        "jurisdiction": "QLD",
        "legal_area": "consumer",
        "sub_categories": ["refund", "acceptable_quality"],
        "key_facts": "Consumer sought refund for carpet that showed premature wear within first year.",
        "key_holding": "Goods must be of acceptable quality including being durable. Premature failure indicates goods not of acceptable quality entitling consumer to remedy.",
        "outcome": "plaintiff",
        "relevance_keywords": ["acceptable quality", "durability", "premature failure", "refund", "remedy"],
    },
]


# ============================================
# Lookup Functions
# ============================================

ALL_CASES: list[MockCase] = (
    TENANCY_CASES + EMPLOYMENT_CASES + FAMILY_CASES + CONSUMER_CASES
)


def get_cases_by_area(legal_area: str) -> list[MockCase]:
    """Get all cases for a specific legal area."""
    return [c for c in ALL_CASES if c["legal_area"] == legal_area]


def get_cases_by_subcategory(legal_area: str, sub_category: str) -> list[MockCase]:
    """Get cases matching both legal area and sub-category."""
    return [
        c for c in ALL_CASES
        if c["legal_area"] == legal_area and sub_category in c["sub_categories"]
    ]


def search_cases_by_keywords(keywords: list[str], legal_area: str | None = None) -> list[MockCase]:
    """
    Search cases by keywords with optional legal area filter.
    Returns cases sorted by relevance (keyword match count).
    """
    results = []
    keywords_lower = [k.lower() for k in keywords]

    for case in ALL_CASES:
        if legal_area and case["legal_area"] != legal_area:
            continue

        # Count keyword matches
        case_keywords = [k.lower() for k in case["relevance_keywords"]]
        case_text = f"{case['key_facts']} {case['key_holding']}".lower()

        match_count = sum(
            1 for kw in keywords_lower
            if kw in case_keywords or kw in case_text
        )

        if match_count > 0:
            results.append((match_count, case))

    # Sort by match count descending
    results.sort(key=lambda x: x[0], reverse=True)
    return [case for _, case in results]


def get_case_by_name(case_name: str) -> MockCase | None:
    """Get a specific case by name."""
    for case in ALL_CASES:
        if case["case_name"].lower() == case_name.lower():
            return case
    return None
