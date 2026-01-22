"""Utility to fetch and parse documents from URLs."""

import os
import ipaddress
from urllib.parse import urlparse

import httpx
from app.utils.document_parser import parse_document
from app.config import logger

# Security: Maximum file size to fetch (10MB)
MAX_FETCH_SIZE_BYTES = 10 * 1024 * 1024

# Security: Allowed hosts for document fetching (SSRF protection)
# Add your Supabase project URL domain here
ALLOWED_HOSTS = []
_extra_hosts = os.environ.get("ALLOWED_DOCUMENT_HOSTS", "")
if _extra_hosts:
    ALLOWED_HOSTS.extend([h.strip() for h in _extra_hosts.split(",") if h.strip()])


def is_safe_url(url: str) -> bool:
    """
    Validate URL to prevent SSRF attacks.

    Returns True only if:
    - URL uses http or https scheme
    - Host is not localhost, loopback, or private IP
    - Host is in allowlist (if configured)
    """
    try:
        parsed = urlparse(url)

        # Must be http or https
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        hostname_lower = hostname.lower()

        # Block localhost variants
        if hostname_lower in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False

        # Check if it's an IP address and block private/reserved ranges
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            # Not an IP address, it's a hostname - continue with allowlist check
            pass

        # Check allowlist if configured
        if ALLOWED_HOSTS:
            if not any(hostname_lower.endswith(allowed.lower()) for allowed in ALLOWED_HOSTS):
                return False

        return True

    except Exception:
        return False


def fetch_and_parse_document(url: str) -> tuple[str, str]:
    """
    Fetch a document from a URL and parse it.

    Args:
        url: URL to fetch the document from (e.g., Supabase Storage public URL)

    Returns:
        Tuple of (parsed_content, content_type)
        - content_type is "text" for PDF/DOCX, "image" for images
    """
    # SSRF protection: validate URL before fetching
    if not is_safe_url(url):
        logger.warning(f"Blocked potentially unsafe URL: {url}")
        raise ValueError("URL not allowed. Only trusted storage URLs are permitted.")

    try:
        # Extract filename from URL (remove query params)
        filename = url.split("/")[-1].split("?")[0]

        logger.info(f"Fetching document from URL: {url}")

        # Fetch with redirect limit and streaming for size check
        with httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            max_redirects=2
        ) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()

                # Check Content-Length header if available
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_FETCH_SIZE_BYTES:
                    raise ValueError(f"Document too large. Maximum size is {MAX_FETCH_SIZE_BYTES // (1024*1024)}MB")

                # Read with size limit
                content = b""
                for chunk in response.iter_bytes():
                    content += chunk
                    if len(content) > MAX_FETCH_SIZE_BYTES:
                        raise ValueError(f"Document too large. Maximum size is {MAX_FETCH_SIZE_BYTES // (1024*1024)}MB")

                # Verify final URL after redirects is also safe
                final_url = str(response.url)
                if final_url != url and not is_safe_url(final_url):
                    raise ValueError("Redirect to unsafe URL blocked")

        logger.info(f"Fetched {len(content)} bytes from {filename}")

        # Parse the document
        parsed_content, content_type = parse_document(content, filename)

        return parsed_content, content_type

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching URL {url}: {e}")
        raise ValueError(f"Failed to fetch document: HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Request error fetching URL {url}: {e}")
        raise ValueError(f"Failed to fetch document: {str(e)}")
    except Exception as e:
        logger.error(f"Error fetching/parsing document from URL: {e}")
        raise ValueError(f"Failed to process document from URL: {str(e)}")
