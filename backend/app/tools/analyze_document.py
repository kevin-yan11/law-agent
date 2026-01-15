"""Analyze document tool - analyzes uploaded legal documents."""

from typing import Optional
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.config import logger
from app.utils.url_fetcher import fetch_and_parse_document


llm = ChatOpenAI(model="gpt-4o", temperature=0)


ANALYSIS_PROMPTS = {
    "lease": """Analyze this residential lease/tenancy agreement. Focus on:
1. Key terms: rent amount, bond, lease duration, notice periods
2. Tenant obligations and restrictions
3. Landlord responsibilities
4. Break lease clauses and penalties
5. Any unusual or potentially unfair terms
6. Important dates and deadlines

Highlight any clauses that may be concerning for the tenant under {state} tenancy law.""",

    "contract": """Analyze this contract. Focus on:
1. Parties involved and their obligations
2. Payment terms and conditions
3. Duration and termination clauses
4. Liability and indemnity clauses
5. Dispute resolution mechanisms
6. Any unusual or one-sided terms

Flag any clauses that may be problematic under Australian contract law.""",

    "visa": """Analyze this visa-related document. Focus on:
1. Visa type and conditions
2. Work rights and restrictions
3. Duration and expiry dates
4. Key obligations and requirements
5. Important deadlines
6. Any conditions that need monitoring

Provide practical guidance for compliance.""",

    "general": """Analyze this legal document. Focus on:
1. Document type and purpose
2. Key parties and their roles
3. Main obligations and rights
4. Important dates and deadlines
5. Any notable terms or conditions
6. Potential areas of concern

Provide a clear summary and highlight anything requiring attention."""
}


@tool
def analyze_document(
    document_url: Optional[str] = None,
    document_text: Optional[str] = None,
    analysis_type: str = "general",
    state: str = "VIC"
) -> str:
    """
    Analyze a legal document and provide insights.

    Args:
        document_url: URL to fetch the document from (e.g., Supabase Storage URL). Use this when user has uploaded a file.
        document_text: Direct text content of the document (fallback if URL not provided)
        analysis_type: Type of document - "lease", "contract", "visa", or "general"
        state: Australian state for jurisdiction-specific analysis (VIC, NSW, QLD, etc.)

    Returns:
        Detailed analysis of the document with key findings and recommendations.
    """
    # If URL provided, fetch and parse the document
    if document_url:
        logger.info(f"analyze_document called with URL: {document_url}")
        try:
            document_text, content_type = fetch_and_parse_document(document_url)
            logger.info(f"Fetched document: type={content_type}, length={len(document_text)}")
        except ValueError as e:
            return f"Failed to fetch document from URL: {str(e)}"

    logger.info(f"analyze_document: type='{analysis_type}', state='{state}', text_length={len(document_text) if document_text else 0}")

    if not document_text or len(document_text.strip()) < 50:
        return "The document appears to be empty or too short to analyze. Please upload a valid document."

    # Select appropriate analysis prompt
    analysis_prompt = ANALYSIS_PROMPTS.get(analysis_type.lower(), ANALYSIS_PROMPTS["general"])

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are an Australian legal document analyst specializing in {state} law.
{analysis_prompt}

Format your response as:
## Document Summary
[Brief overview of what this document is]

## Key Terms & Conditions
[Bullet points of important terms]

## Important Dates & Deadlines
[Any dates that need attention]

## Potential Concerns
[Any clauses or terms that may be problematic]

## Recommendations
[What the user should do or be aware of]

Be thorough but concise. Use clear language accessible to non-lawyers."""),
        ("human", "Please analyze this document:\n\n{document}")
    ])

    try:
        # Truncate very long documents to avoid token limits
        max_chars = 50000
        if len(document_text) > max_chars:
            document_text = document_text[:max_chars] + "\n\n[Document truncated due to length...]"
            logger.warning("Document truncated to 50000 characters")

        result = llm.invoke(prompt.format_messages(state=state, document=document_text))
        return result.content

    except Exception as e:
        logger.error(f"Document analysis failed: {e}")
        return f"I encountered an error analyzing the document: {str(e)}. Please try again or upload a different file."
