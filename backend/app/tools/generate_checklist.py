"""Generate checklist tool - creates step-by-step guides for legal procedures."""

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json

from app.db import supabase
from app.config import logger


llm = ChatOpenAI(model="gpt-4o", temperature=0)


@tool
def generate_checklist(procedure: str, state: str = "VIC") -> str:
    """
    Generate a step-by-step checklist for a legal procedure.

    Args:
        procedure: Description of what the user wants to do (e.g., "get my bond back", "break my lease")
        state: Australian state (VIC, NSW, QLD, etc.). Defaults to VIC.

    Returns:
        A formatted checklist with numbered steps.
    """
    logger.info(f"generate_checklist called: '{procedure}' for state '{state}'")

    # First, try to find a matching template
    try:
        response = supabase.table("action_templates").select("*").eq("state", state).execute()
        templates = response.data if response.data else []

        if templates:
            # Simple keyword matching
            procedure_lower = procedure.lower()
            for template in templates:
                keywords = template.get("keywords", [])
                if any(kw.lower() in procedure_lower for kw in keywords):
                    logger.info(f"Found matching template: {template['id']}")
                    steps = template.get("steps", [])
                    return _format_steps(steps, template.get("title", "Checklist"))
    except Exception as e:
        logger.warning(f"Template lookup failed (table may not exist): {e}")

    # No template found, generate with LLM
    logger.info("No template found, generating with LLM")

    GENERATOR_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an Australian legal procedure expert.
Generate a practical step-by-step checklist for the user's request.

State: {state}

Return a JSON array of steps:
[
  {{"order": 1, "title": "Step title", "description": "What to do", "details": "Additional info"}}
]

Be practical and specific to Australian law in {state}. Include:
- Government websites where relevant
- Timeframes and deadlines
- Required documents

Keep it to 5-8 steps. Return ONLY the JSON array."""),
        ("human", "{procedure}")
    ])

    try:
        result = llm.invoke(GENERATOR_PROMPT.format_messages(state=state, procedure=procedure))
        content = result.content.strip()

        # Handle markdown code blocks
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:].strip()

        steps = json.loads(content)
        return _format_steps(steps, f"How to: {procedure}")

    except Exception as e:
        logger.error(f"Checklist generation failed: {e}")
        return f"I couldn't generate a checklist for '{procedure}'. Please try rephrasing your request."


def _format_steps(steps: list, title: str) -> str:
    """Format steps as readable markdown."""
    lines = [f"## {title}\n"]

    for step in steps:
        order = step.get("order", "")
        step_title = step.get("title", "")
        description = step.get("description", "")
        details = step.get("details", "")

        lines.append(f"**Step {order}: {step_title}**")
        lines.append(f"{description}")
        if details:
            lines.append(f"_💡 {details}_")
        lines.append("")

    return "\n".join(lines)
