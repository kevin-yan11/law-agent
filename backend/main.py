import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from langchain_openai import ChatOpenAI
from copilotkit import LangGraphAGUIAgent
from ag_ui_langgraph import add_langgraph_fastapi_endpoint

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

# Load conversational graph
from app.agents.conversational_graph import get_conversational_graph

graph = get_conversational_graph()
agent_description = (
    "Australian Legal Assistant - natural conversational help with "
    "legal questions, rights information, lawyer referrals, and optional deep analysis"
)
logger.info("Using CONVERSATIONAL graph with optional deep analysis")

# Integrate with CopilotKit (using LangGraphAGUIAgent)
add_langgraph_fastapi_endpoint(
    app=app,
    agent=LangGraphAGUIAgent(
        name="auslaw_agent",
        description=agent_description,
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
