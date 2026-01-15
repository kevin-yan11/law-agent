"""Utility to fetch and parse documents from URLs."""

import httpx
from app.utils.document_parser import parse_document
from app.config import logger


def fetch_and_parse_document(url: str) -> tuple[str, str]:
    """
    Fetch a document from a URL and parse it.

    Args:
        url: URL to fetch the document from (e.g., Supabase Storage public URL)

    Returns:
        Tuple of (parsed_content, content_type)
        - content_type is "text" for PDF/DOCX, "image" for images
    """
    try:
        # Extract filename from URL (remove query params)
        filename = url.split("/")[-1].split("?")[0]

        logger.info(f"Fetching document from URL: {url}")

        # Fetch the file
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()

        content = response.content
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
