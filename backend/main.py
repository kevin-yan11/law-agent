import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from copilotkit import LangGraphAGUIAgent
from ag_ui_langgraph import add_langgraph_fastapi_endpoint

from app.tools import lookup_law, find_lawyer
from app.config import logger

app = FastAPI(
    title="AusLaw AI API",
    description="Australian Legal Assistant Backend",
    version="1.0.0",
)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Setup Agent Logic
model = ChatOpenAI(model="gpt-4o", temperature=0)

SYSTEM_PROMPT = """
You are 'AusLaw AI', a transparent Australian legal assistant.

You have two main capabilities:
1. **Research**: Answer legal questions with citations
2. **Action**: Generate step-by-step checklists for legal procedures

RULES:
1. For legal questions: Use the `lookup_law` tool to find legislation. DO NOT answer from memory.
2. CITATIONS: When you find a law, cite it like this: "According to [Act Name] [Section]..."
3. For "how to" questions (e.g., "How do I get my bond back?"): Use the `generate_checklist` tool.
4. If the user needs professional help: Use `find_lawyer` to suggest a contact.
5. Always remind users this is not legal advice - they should consult a qualified lawyer for their specific situation.
"""

# Import the new checklist tool
from app.tools.generate_checklist import generate_checklist

# Create the Graph with checkpointer for state management
checkpointer = MemorySaver()
graph = create_react_agent(
    model,
    tools=[lookup_law, find_lawyer, generate_checklist],
    prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)

# Integrate with CopilotKit (using LangGraphAGUIAgent)
add_langgraph_fastapi_endpoint(
    app=app,
    agent=LangGraphAGUIAgent(
        name="auslaw_agent",
        description="Australian Legal Assistant that searches laws, generates checklists, and finds lawyers",
        graph=graph,
    ),
    path="/copilotkit",
)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host=host, port=port)
