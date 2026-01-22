"""Shared test fixtures and configuration."""

import os
import sys
import pytest

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables for tests
from dotenv import load_dotenv
load_dotenv()


@pytest.fixture
def sample_query():
    """Sample legal query for testing."""
    return "What are the rules for bond refunds in NSW?"


@pytest.fixture
def sample_jurisdiction():
    """Sample jurisdiction."""
    return "nsw"


@pytest.fixture
def unsafe_urls():
    """URLs that should be blocked by SSRF protection."""
    return [
        "http://localhost:8000/secret",
        "http://127.0.0.1/admin",
        "http://192.168.1.1/internal",
        "http://10.0.0.1/private",
        "http://169.254.169.254/latest/meta-data/",  # AWS metadata
        "http://[::1]/ipv6-localhost",
        "file:///etc/passwd",
        "ftp://example.com/file",
    ]


@pytest.fixture
def safe_urls():
    """URLs that should be allowed (assuming proper ALLOWED_HOSTS config)."""
    return [
        "https://example.com/document.pdf",
        "https://storage.googleapis.com/bucket/file.pdf",
    ]
