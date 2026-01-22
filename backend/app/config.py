import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_required_env(name: str) -> str:
    """Get required environment variable or exit with clear error."""
    value = os.environ.get(name)
    if not value:
        logger.error(f"Required environment variable '{name}' is not set.")
        sys.exit(1)
    return value


# Validate environment variables
SUPABASE_URL = get_required_env("SUPABASE_URL")
SUPABASE_KEY = get_required_env("SUPABASE_KEY")
get_required_env("OPENAI_API_KEY")  # langchain_openai reads this automatically

# Optional: Cohere API key for reranking (gracefully degrades if not set)
COHERE_API_KEY = os.environ.get("COHERE_API_KEY")

# CORS configuration (comma-separated list of allowed origins)
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
CORS_ORIGINS = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]
