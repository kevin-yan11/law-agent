import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from copilotkit import CopilotKitState, LangGraphAGUIAgent
from ag_ui_langgraph import add_langgraph_fastapi_endpoint

from app.tools import lookup_law, find_lawyer, analyze_document
from app.tools.generate_checklist import generate_checklist
from app.utils.document_parser import parse_document
from app.config import logger, CORS_ORIGINS
from app.db import supabase

# Security: File upload size limit (10MB)
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Validate configuration on startup."""
    # Validate Supabase connection
    try:
        supabase.table("legislation_documents").select("id").limit(1).execute()
        logger.info("✓ Supabase connection validated")
    except Exception as e:
        logger.error(f"✗ Supabase connection failed: {e}")
        raise SystemExit(1)

    # Validate OpenAI API key by making a minimal request
    try:
        test_model = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=5)
        test_model.invoke("test")
        logger.info("✓ OpenAI API key validated")
    except Exception as e:
        logger.error(f"✗ OpenAI API key validation failed: {e}")
        raise SystemExit(1)

    logger.info("🚀 AusLaw AI backend started successfully")
    yield
    logger.info("👋 AusLaw AI backend shutting down")


app = FastAPI(
    title="AusLaw AI API",
    description="Australian Legal Assistant Backend",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# Rate limiting middleware for /copilotkit endpoint
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply rate limiting to specific paths."""

    # Simple in-memory rate limiting (for production, use Redis)
    _requests: dict[str, list[float]] = {}
    RATE_LIMIT = 30  # requests per minute
    WINDOW = 60  # seconds

    async def dispatch(self, request: Request, call_next):
        import time

        # Only rate limit /copilotkit POST requests
        if request.url.path == "/copilotkit" and request.method == "POST":
            client_ip = get_remote_address(request)
            current_time = time.time()

            # Clean old entries and get recent requests
            if client_ip not in self._requests:
                self._requests[client_ip] = []

            self._requests[client_ip] = [
                t for t in self._requests[client_ip]
                if current_time - t < self.WINDOW
            ]

            if len(self._requests[client_ip]) >= self.RATE_LIMIT:
                logger.warning(f"Rate limit exceeded for {client_ip} on /copilotkit")
                return Response(
                    content='{"detail": "Rate limit exceeded. Please try again later."}',
                    status_code=429,
                    media_type="application/json",
                )

            self._requests[client_ip].append(current_time)

        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

# Setup Agent Logic
model = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [lookup_law, find_lawyer, generate_checklist, analyze_document]
model_with_tools = model.bind_tools(tools)

BASE_SYSTEM_PROMPT = """
You are 'AusLaw AI', a transparent Australian legal assistant.

CAPABILITIES:
1. **Research**: Answer legal questions with citations using `lookup_law`
2. **Action**: Generate step-by-step checklists using `generate_checklist`
3. **Match**: Find lawyers using `find_lawyer`
4. **Document Analysis**: Analyze uploaded legal documents using `analyze_document`

RULES:
1. For legal questions: ALWAYS use `lookup_law(query, state)` first. You MUST base your answer ONLY on the results returned.
2. CRITICAL - CITATIONS: You may ONLY cite legislation that appears in the lookup_law results.
   - If lookup_law returns results: Cite using the exact citation and source_url from the results
   - If lookup_law returns no results or "No legislation found": Tell the user honestly that you couldn't find relevant legislation in the database for their query. Do NOT make up citations from your training data.
   - NEVER invent section numbers or Act names that weren't in the RAG results
3. CITATIONS FORMAT (only for results from lookup_law):
   "According to the **[Act Name]** ([State]): [quote from content]"
   Include the source URL when available: "Source: [source_url]"
4. For "how to" questions: Use `generate_checklist(procedure, state)` tool.
5. For lawyer requests: Use `find_lawyer(specialty, state)`.
6. For uploaded documents (leases, contracts, visa docs): Use `analyze_document(document_url, analysis_type, state)`.
   - analysis_type options: "lease", "contract", "visa", "general"
   - When user uploads a file, the document URL will be provided. Pass the URL to analyze_document.
   - The tool returns the document text. YOU must then analyze it thoroughly.
7. End responses with: "_This is general information, not legal advice. Please consult a qualified lawyer for your specific situation._"

DOCUMENT ANALYSIS GUIDELINES:
When analyze_document returns document content, provide a thorough analysis with this structure:

## Document Summary
Brief overview of what this document is and its purpose.

## Key Terms & Conditions
- List important terms as bullet points
- Include amounts, durations, obligations

## Important Dates & Deadlines
- Any dates that need attention
- Notice periods, expiry dates

## Potential Concerns
- Unusual or one-sided terms
- Clauses that may be problematic under the relevant state law
- Missing protections

## Recommendations
- What the user should do or be aware of
- Questions to ask before signing

Be thorough but use clear language accessible to non-lawyers.
"""


# Define state that inherits from CopilotKitState
class AgentState(CopilotKitState):
    pass


def extract_context_item(state: AgentState, keyword: str) -> str | None:
    """Extract a context item from CopilotKit context by keyword in description."""
    copilotkit_data = state.get("copilotkit", {})
    context_items = copilotkit_data.get("context", [])

    for item in context_items:
        try:
            # CopilotContextItem can be a TypedDict or an object with attributes
            description = item.get("description", "") if isinstance(item, dict) else getattr(item, "description", "")
            value = item.get("value", "") if isinstance(item, dict) else getattr(item, "value", "")

            if keyword.lower() in description.lower():
                return value
        except Exception:
            continue

    return None


def clean_context_value(value: str | None) -> str | None:
    """Remove extra quotes from context values if present."""
    if value and isinstance(value, str):
        # Strip leading/trailing quotes that may be added by serialization
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        # Unescape inner quotes
        value = value.replace('\\"', '"')
    return value


def extract_user_state(state: AgentState) -> str | None:
    """Extract user's Australian state from CopilotKit context."""
    return clean_context_value(extract_context_item(state, "state/territory"))


def extract_uploaded_document(state: AgentState) -> str | None:
    """Extract uploaded document content from CopilotKit context."""
    return clean_context_value(extract_context_item(state, "document"))


def chat_node(state: AgentState, config: RunnableConfig):
    """Main chat node that reads CopilotKit context."""
    # Extract user state from CopilotKit context
    user_state_context = extract_user_state(state)
    # Extract uploaded document from CopilotKit context
    uploaded_document = extract_uploaded_document(state)

    # Build dynamic system message
    if user_state_context:
        state_instruction = f"""
USER LOCATION CONTEXT:
{user_state_context}

CRITICAL: The user's state is provided above. You MUST use this state for ALL tool calls.
- DO NOT ask for the user's state or location - you already have it!
- Use the state code (VIC, NSW, QLD, SA, WA, TAS, NT, ACT) from the context above for all tools.
"""
    else:
        state_instruction = """
USER LOCATION: Not yet selected.
Ask the user to select their Australian state/territory so you can provide accurate legal information.
"""

    # Add document context if available (URL-based)
    document_instruction = ""
    if uploaded_document and "document url" in uploaded_document.lower():
        document_instruction = f"""
UPLOADED DOCUMENT:
{uploaded_document}

IMPORTANT: The user has uploaded a document. When they ask to analyze it, use the analyze_document tool with the document_url parameter from the context above.
"""

    system_message = SystemMessage(content=BASE_SYSTEM_PROMPT + state_instruction + document_instruction)

    # Invoke model with context-aware system message
    response = model_with_tools.invoke(
        [system_message, *state["messages"]],
        config
    )

    return {"messages": [response]}


def should_continue(state: AgentState):
    """Check if we should continue to tools or end."""
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


# Build the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("chat", chat_node)
workflow.add_node("tools", ToolNode(tools))

# Add edges
workflow.set_entry_point("chat")
workflow.add_conditional_edges("chat", should_continue, {"tools": "tools", END: END})
workflow.add_edge("tools", "chat")

# Compile with checkpointer
checkpointer = MemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

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


@app.post("/upload")
@limiter.limit("10/minute")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    Upload and parse a document (PDF, DOCX, or image).
    Returns the parsed text content.
    """
    allowed_extensions = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_extensions)}"
        )

    try:
        # Security: Check file size before reading entirely into memory
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB"
            )

        parsed_content, content_type = parse_document(content, filename)

        logger.info(f"Parsed file: {filename}, type: {content_type}, length: {len(parsed_content)}")

        return {
            "filename": filename,
            "content_type": content_type,
            "parsed_content": parsed_content,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse file")


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host=host, port=port)
