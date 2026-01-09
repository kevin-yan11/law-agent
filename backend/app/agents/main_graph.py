"""Main graph orchestration - routes queries to appropriate sub-graphs."""

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage

from app.agents.state import AusLawState
from app.agents.router import router
from app.agents.research.graph import research_graph
from app.agents.action.graph import action_graph
from app.tools import lookup_law, find_lawyer
from app.config import logger


llm = ChatOpenAI(model="gpt-4o", temperature=0)


async def classify_intent(state: AusLawState) -> dict:
    """Classify user intent and update state."""
    classification = await router.classify(
        query=state["current_query"],
        user_state=state.get("user_state")
    )
    return {"intent": classification.intent}


async def run_research(state: AusLawState) -> dict:
    """Execute research sub-graph."""
    logger.info("Main: running research sub-graph")
    result = await research_graph.ainvoke(state)
    return {
        "research_result": result.get("research_result"),
        "messages": [AIMessage(content=result.get("research_result", {}).get("answer", ""))]
    }


async def run_action(state: AusLawState) -> dict:
    """Execute action sub-graph."""
    logger.info("Main: running action sub-graph")
    result = await action_graph.ainvoke(state)

    # Format checklist as readable message
    checklist = result.get("checklist", [])
    if checklist:
        steps_text = "\n".join([
            f"{step['order']}. **{step['title']}**\n   {step['description']}"
            + (f"\n   _{step['details']}_" if step.get('details') else "")
            for step in checklist
        ])
        message = f"Here's your step-by-step guide:\n\n{steps_text}"
    else:
        message = "I couldn't generate a checklist for that request. Please try rephrasing."

    return {
        "checklist": checklist,
        "active_template_id": result.get("active_template_id"),
        "current_step_index": result.get("current_step_index", 0),
        "messages": [AIMessage(content=message)]
    }


async def run_match(state: AusLawState) -> dict:
    """Find a lawyer using the find_lawyer tool."""
    logger.info("Main: running lawyer match")
    query = state["current_query"]
    user_state = state.get("user_state", "VIC")

    # Default to Melbourne for VIC, Sydney for NSW
    location_map = {"VIC": "Melbourne", "NSW": "Sydney", "QLD": "Brisbane"}
    location = location_map.get(user_state, "Melbourne")

    # Try to extract specialty from query
    result = find_lawyer.invoke({"location": location, "specialty": "Tenancy"})

    if isinstance(result, list) and result:
        lawyers_text = "\n".join([
            f"- **{l['name']}** ({l['specialty']}) - {l['location']} - {l['rate']}"
            for l in result
        ])
        message = f"Here are some lawyers who might be able to help:\n\n{lawyers_text}"
    else:
        message = "I couldn't find matching lawyers at this time. Please try a different search."

    return {"messages": [AIMessage(content=message)]}


async def ask_clarification(state: AusLawState) -> dict:
    """Ask user to clarify their question."""
    message = "I'd like to help, but I need a bit more information. Could you tell me more about:\n- What specific issue you're facing?\n- What outcome you're hoping for?"
    return {"messages": [AIMessage(content=message)]}


async def general_response(state: AusLawState) -> dict:
    """Handle general conversation."""
    query = state["current_query"]

    response = await llm.ainvoke([
        ("system", """You are a friendly Australian legal assistant called AusLaw AI.
For general questions, be helpful and guide users toward the legal help features you offer:
- Legal research (understanding laws and rights)
- Step-by-step guides for legal procedures
- Lawyer matching

Keep responses concise and friendly."""),
        ("human", query)
    ])

    return {"messages": [AIMessage(content=response.content)]}


def route_by_intent(state: AusLawState) -> str:
    """Route to appropriate handler based on intent."""
    intent = state.get("intent", "general")

    route_map = {
        "research": "research",
        "action": "action",
        "match": "match",
        "clarify": "clarify",
        "general": "general"
    }
    return route_map.get(intent, "general")


def build_main_graph() -> StateGraph:
    """Construct the main orchestration graph."""
    workflow = StateGraph(AusLawState)

    # Add nodes
    workflow.add_node("classify", classify_intent)
    workflow.add_node("research", run_research)
    workflow.add_node("action", run_action)
    workflow.add_node("match", run_match)
    workflow.add_node("clarify", ask_clarification)
    workflow.add_node("general", general_response)

    # Set entry point
    workflow.set_entry_point("classify")

    # Add routing from classifier
    workflow.add_conditional_edges(
        "classify",
        route_by_intent,
        {
            "research": "research",
            "action": "action",
            "match": "match",
            "clarify": "clarify",
            "general": "general"
        }
    )

    # All terminal nodes go to END
    workflow.add_edge("research", END)
    workflow.add_edge("action", END)
    workflow.add_edge("match", END)
    workflow.add_edge("clarify", END)
    workflow.add_edge("general", END)

    return workflow.compile()


main_graph = build_main_graph()
