"""Emergency and crisis resources for Australian legal matters."""

from typing import Literal

# National resources available across all states
NATIONAL_RESOURCES = {
    "family_violence": [
        {
            "name": "1800RESPECT",
            "phone": "1800 737 732",
            "url": "https://www.1800respect.org.au",
            "description": "National domestic violence and sexual assault helpline (24/7)",
        },
        {
            "name": "MensLine Australia",
            "phone": "1300 78 99 78",
            "url": "https://mensline.org.au",
            "description": "Support for men dealing with family violence",
        },
    ],
    "criminal": [
        {
            "name": "National Legal Aid",
            "phone": None,
            "url": "https://www.nationallegalaid.org",
            "description": "Find your state's Legal Aid for criminal matters",
        },
    ],
    "suicide_self_harm": [
        {
            "name": "Lifeline",
            "phone": "13 11 14",
            "url": "https://www.lifeline.org.au",
            "description": "24/7 crisis support and suicide prevention",
        },
        {
            "name": "Beyond Blue",
            "phone": "1300 22 4636",
            "url": "https://www.beyondblue.org.au",
            "description": "Mental health support (24/7)",
        },
        {
            "name": "Kids Helpline",
            "phone": "1800 55 1800",
            "url": "https://kidshelpline.com.au",
            "description": "24/7 counselling for young people aged 5-25",
        },
    ],
    "child_welfare": [
        {
            "name": "Kids Helpline",
            "phone": "1800 55 1800",
            "url": "https://kidshelpline.com.au",
            "description": "24/7 counselling for young people aged 5-25",
        },
    ],
    "urgent_deadline": [
        {
            "name": "LawAccess NSW",
            "phone": "1300 888 529",
            "url": "https://www.lawaccess.nsw.gov.au",
            "description": "Free legal help for NSW residents",
        },
    ],
}

# State-specific resources
STATE_RESOURCES = {
    "NSW": {
        "family_violence": [
            {
                "name": "NSW Domestic Violence Line",
                "phone": "1800 65 64 63",
                "url": "https://www.facs.nsw.gov.au/domestic-violence",
                "description": "NSW crisis support for domestic violence (24/7)",
            },
        ],
        "criminal": [
            {
                "name": "Legal Aid NSW",
                "phone": "1300 888 529",
                "url": "https://www.legalaid.nsw.gov.au",
                "description": "Free legal advice for criminal matters in NSW",
            },
        ],
        "child_welfare": [
            {
                "name": "NSW Child Protection Helpline",
                "phone": "132 111",
                "url": "https://www.facs.nsw.gov.au/families/Protecting-kids",
                "description": "Report child abuse or neglect in NSW",
            },
        ],
        "urgent_deadline": [
            {
                "name": "LawAccess NSW",
                "phone": "1300 888 529",
                "url": "https://www.lawaccess.nsw.gov.au",
                "description": "Free legal help for NSW residents",
            },
        ],
    },
    "VIC": {
        "family_violence": [
            {
                "name": "Safe Steps Family Violence Response Centre",
                "phone": "1800 015 188",
                "url": "https://www.safesteps.org.au",
                "description": "Victoria's family violence response centre (24/7)",
            },
        ],
        "criminal": [
            {
                "name": "Victoria Legal Aid",
                "phone": "1300 792 387",
                "url": "https://www.legalaid.vic.gov.au",
                "description": "Free legal advice for criminal matters in Victoria",
            },
        ],
        "child_welfare": [
            {
                "name": "Child Protection Victoria",
                "phone": "1300 664 977",
                "url": "https://services.dffh.vic.gov.au/child-protection",
                "description": "Report child abuse or neglect in Victoria",
            },
        ],
        "urgent_deadline": [
            {
                "name": "Victoria Legal Aid",
                "phone": "1300 792 387",
                "url": "https://www.legalaid.vic.gov.au",
                "description": "Free legal advice for Victorian residents",
            },
        ],
    },
    "QLD": {
        "family_violence": [
            {
                "name": "DVConnect Womensline",
                "phone": "1800 811 811",
                "url": "https://www.dvconnect.org",
                "description": "Queensland domestic violence helpline (24/7)",
            },
            {
                "name": "DVConnect Mensline",
                "phone": "1800 600 636",
                "url": "https://www.dvconnect.org",
                "description": "Support for men in Queensland",
            },
        ],
        "criminal": [
            {
                "name": "Legal Aid Queensland",
                "phone": "1300 651 188",
                "url": "https://www.legalaid.qld.gov.au",
                "description": "Free legal advice for criminal matters in Queensland",
            },
        ],
        "child_welfare": [
            {
                "name": "Child Safety Services Queensland",
                "phone": "1800 177 135",
                "url": "https://www.cyjma.qld.gov.au/protecting-children",
                "description": "Report child abuse or neglect in Queensland",
            },
        ],
        "urgent_deadline": [
            {
                "name": "Legal Aid Queensland",
                "phone": "1300 651 188",
                "url": "https://www.legalaid.qld.gov.au",
                "description": "Free legal advice for Queensland residents",
            },
        ],
    },
    "SA": {
        "family_violence": [
            {
                "name": "Domestic Violence Crisis Line SA",
                "phone": "1800 800 098",
                "url": "https://www.womenssafetyservices.com.au",
                "description": "South Australia domestic violence support (24/7)",
            },
        ],
        "criminal": [
            {
                "name": "Legal Services Commission SA",
                "phone": "1300 366 424",
                "url": "https://lsc.sa.gov.au",
                "description": "Free legal advice for criminal matters in SA",
            },
        ],
        "urgent_deadline": [
            {
                "name": "Legal Services Commission SA",
                "phone": "1300 366 424",
                "url": "https://lsc.sa.gov.au",
                "description": "Free legal advice for SA residents",
            },
        ],
    },
    "WA": {
        "family_violence": [
            {
                "name": "Women's Domestic Violence Helpline WA",
                "phone": "1800 007 339",
                "url": "https://www.wa.gov.au/service/community-services/family-and-domestic-violence",
                "description": "Western Australia domestic violence helpline (24/7)",
            },
        ],
        "criminal": [
            {
                "name": "Legal Aid WA",
                "phone": "1300 650 579",
                "url": "https://www.legalaid.wa.gov.au",
                "description": "Free legal advice for criminal matters in WA",
            },
        ],
        "urgent_deadline": [
            {
                "name": "Legal Aid WA",
                "phone": "1300 650 579",
                "url": "https://www.legalaid.wa.gov.au",
                "description": "Free legal advice for WA residents",
            },
        ],
    },
    "TAS": {
        "family_violence": [
            {
                "name": "Family Violence Counselling and Support Service TAS",
                "phone": "1800 608 122",
                "url": "https://www.communities.tas.gov.au/children/family_violence",
                "description": "Tasmania family violence support",
            },
        ],
        "criminal": [
            {
                "name": "Legal Aid Commission Tasmania",
                "phone": "1300 366 611",
                "url": "https://www.legalaid.tas.gov.au",
                "description": "Free legal advice for criminal matters in Tasmania",
            },
        ],
        "urgent_deadline": [
            {
                "name": "Legal Aid Commission Tasmania",
                "phone": "1300 366 611",
                "url": "https://www.legalaid.tas.gov.au",
                "description": "Free legal advice for Tasmanian residents",
            },
        ],
    },
    "NT": {
        "family_violence": [
            {
                "name": "Dawn House",
                "phone": "1800 193 111",
                "url": "https://www.dawnhouse.org.au",
                "description": "Northern Territory domestic violence crisis support",
            },
        ],
        "criminal": [
            {
                "name": "Northern Territory Legal Aid Commission",
                "phone": "1800 019 343",
                "url": "https://www.ntlac.nt.gov.au",
                "description": "Free legal advice for criminal matters in NT",
            },
        ],
        "urgent_deadline": [
            {
                "name": "Northern Territory Legal Aid Commission",
                "phone": "1800 019 343",
                "url": "https://www.ntlac.nt.gov.au",
                "description": "Free legal advice for NT residents",
            },
        ],
    },
    "ACT": {
        "family_violence": [
            {
                "name": "Domestic Violence Crisis Service ACT",
                "phone": "02 6280 0900",
                "url": "https://dvcs.org.au",
                "description": "ACT domestic violence crisis support (24/7)",
            },
        ],
        "criminal": [
            {
                "name": "Legal Aid ACT",
                "phone": "1300 654 314",
                "url": "https://www.legalaidact.org.au",
                "description": "Free legal advice for criminal matters in ACT",
            },
        ],
        "urgent_deadline": [
            {
                "name": "Legal Aid ACT",
                "phone": "1300 654 314",
                "url": "https://www.legalaidact.org.au",
                "description": "Free legal advice for ACT residents",
            },
        ],
    },
}

# Combined lookup structure
EMERGENCY_RESOURCES: dict[str, list[dict]] = {
    **NATIONAL_RESOURCES,
}


def get_resources_for_risk(
    risk_category: Literal[
        "criminal",
        "family_violence",
        "urgent_deadline",
        "child_welfare",
        "suicide_self_harm"
    ],
    user_state: str | None = None,
) -> list[dict]:
    """
    Get relevant emergency resources for a risk category and optional state.

    Args:
        risk_category: The type of high-risk situation detected
        user_state: Australian state/territory code (e.g., "NSW", "VIC")

    Returns:
        List of resource dictionaries with name, phone, url, description
    """
    resources = []

    # Add national resources for this category
    national = NATIONAL_RESOURCES.get(risk_category, [])
    resources.extend(national)

    # Add state-specific resources if state is known
    if user_state and user_state in STATE_RESOURCES:
        state_specific = STATE_RESOURCES[user_state].get(risk_category, [])
        resources.extend(state_specific)

    # Deduplicate by name while preserving order
    seen_names = set()
    unique_resources = []
    for resource in resources:
        if resource["name"] not in seen_names:
            seen_names.add(resource["name"])
            unique_resources.append(resource)

    return unique_resources
