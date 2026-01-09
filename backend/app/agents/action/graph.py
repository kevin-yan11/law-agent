"""Action sub-graph - handles checklist generation for legal procedures."""

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json

from app.agents.state import AusLawState, ChecklistStep
from app.db import supabase
from app.config import logger


llm = ChatOpenAI(model="gpt-4o", temperature=0)


async def match_template(state: AusLawState) -> dict:
    """Try to match user's request to a pre-built template."""
    query = state["current_query"]
    user_state = state.get("user_state", "VIC")

    logger.info(f"Action: matching template for '{query[:50]}...'")

    try:
        # Search templates by keywords (if table exists)
        response = supabase.table("action_templates").select("*").eq("state", user_state).execute()
        templates = response.data if response.data else []

        if templates:
            # Use LLM to pick the best match
            MATCHER_PROMPT = ChatPromptTemplate.from_messages([
                ("system", """Select the most relevant template for the user's request.
Return ONLY the template ID, or "none" if no template fits.

Templates:
{templates}"""),
                ("human", "User request: {query}")
            ])

            templates_text = "\n".join([
                f"- {t['id']}: {t['title']} - {t.get('description', '')}"
                for t in templates
            ])

            result = await (MATCHER_PROMPT | llm).ainvoke({
                "templates": templates_text,
                "query": query
            })

            selected_id = result.content.strip()
            if selected_id != "none" and any(t["id"] == selected_id for t in templates):
                logger.info(f"Action: matched template '{selected_id}'")
                return {"matched_template_id": selected_id, "available_templates": templates}

        logger.info("Action: no template matched, will generate checklist")
        return {"matched_template_id": None, "available_templates": templates}

    except Exception as e:
        # Table might not exist yet, that's OK
        logger.warning(f"Action: template matching skipped ({e})")
        return {"matched_template_id": None, "available_templates": []}


async def load_template(state: AusLawState) -> dict:
    """Load the matched template and convert to checklist."""
    template_id = state.get("matched_template_id")
    templates = state.get("available_templates", [])

    template = next((t for t in templates if t["id"] == template_id), None)

    if not template:
        return {"checklist": None}

    # Convert template steps to ChecklistStep format
    checklist: list[ChecklistStep] = []
    for step in template.get("steps", []):
        checklist.append({
            "order": step.get("order", len(checklist) + 1),
            "title": step.get("title", ""),
            "description": step.get("description", ""),
            "action_type": step.get("action_type", "info"),
            "status": "pending",
            "details": step.get("details")
        })

    logger.info(f"Action: loaded template with {len(checklist)} steps")
    return {
        "active_template_id": template_id,
        "checklist": checklist,
        "current_step_index": 0
    }


async def generate_checklist(state: AusLawState) -> dict:
    """Generate a checklist using LLM when no template matches."""
    query = state["current_query"]
    user_state = state.get("user_state", "VIC")

    GENERATOR_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an Australian legal procedure expert.
Generate a step-by-step checklist for the user's request.

State: {user_state}

Return a JSON array of steps with this structure:
[
  {{
    "order": 1,
    "title": "Step title",
    "description": "What to do",
    "action_type": "info",
    "details": "Additional helpful information"
  }}
]

action_type options: "info" (just information), "upload" (needs document), "external_link" (visit a website), "wait" (waiting period)

Be practical and specific to Australian law. Keep it to 5-8 steps maximum.
Return ONLY the JSON array, no other text."""),
        ("human", "User request: {query}")
    ])

    result = await (GENERATOR_PROMPT | llm).ainvoke({
        "user_state": user_state,
        "query": query
    })

    try:
        # Parse JSON response
        content = result.content.strip()
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        steps_data = json.loads(content)

        checklist: list[ChecklistStep] = []
        for step in steps_data:
            checklist.append({
                "order": step.get("order", len(checklist) + 1),
                "title": step.get("title", ""),
                "description": step.get("description", ""),
                "action_type": step.get("action_type", "info"),
                "status": "pending",
                "details": step.get("details")
            })

        logger.info(f"Action: generated checklist with {len(checklist)} steps")
        return {
            "checklist": checklist,
            "current_step_index": 0
        }
    except json.JSONDecodeError as e:
        logger.error(f"Action: failed to parse checklist JSON: {e}")
        return {"error": "Failed to generate checklist"}


def route_after_match(state: AusLawState) -> str:
    """Decide whether to load template or generate checklist."""
    if state.get("matched_template_id"):
        return "load_template"
    return "generate_checklist"


def build_action_graph() -> StateGraph:
    """Construct the action sub-graph."""
    workflow = StateGraph(AusLawState)

    # Add nodes
    workflow.add_node("match_template", match_template)
    workflow.add_node("load_template", load_template)
    workflow.add_node("generate_checklist", generate_checklist)

    # Add edges
    workflow.set_entry_point("match_template")
    workflow.add_conditional_edges(
        "match_template",
        route_after_match,
        {
            "load_template": "load_template",
            "generate_checklist": "generate_checklist"
        }
    )
    workflow.add_edge("load_template", END)
    workflow.add_edge("generate_checklist", END)

    return workflow.compile()


action_graph = build_action_graph()
