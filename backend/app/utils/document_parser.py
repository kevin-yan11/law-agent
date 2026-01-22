"""Document parsing utilities for PDF, DOCX, and image files."""

import base64
import io
from typing import Tuple

from pypdf import PdfReader
from docx import Document
from PIL import Image

from app.config import logger

# Security: Resource limits to prevent DoS
MAX_PDF_PAGES = 100
MAX_IMAGE_DIMENSION = 4096  # pixels
MAX_IMAGE_PIXELS = 20_000_000  # ~20MP, prevents decompression bombs


def parse_pdf(content: bytes) -> str:
    """
    Extract text from a PDF file with page limit.

    Args:
        content: Raw PDF file bytes

    Returns:
        Extracted text content
    """
    try:
        reader = PdfReader(io.BytesIO(content))
        num_pages = len(reader.pages)

        # Limit pages to prevent DoS
        if num_pages > MAX_PDF_PAGES:
            logger.warning(f"PDF has {num_pages} pages, limiting to {MAX_PDF_PAGES}")

        text_parts = []
        for page_num, page in enumerate(reader.pages[:MAX_PDF_PAGES], 1):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"--- Page {page_num} ---\n{page_text}")

        if num_pages > MAX_PDF_PAGES:
            text_parts.append(f"\n[Note: Document truncated. Showing first {MAX_PDF_PAGES} of {num_pages} pages]")

        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"PDF parsing failed: {e}")
        raise ValueError(f"Failed to parse PDF: {e}")


def parse_docx(content: bytes) -> str:
    """
    Extract text from a Word document.

    Args:
        content: Raw DOCX file bytes

    Returns:
        Extracted text content
    """
    try:
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.error(f"DOCX parsing failed: {e}")
        raise ValueError(f"Failed to parse Word document: {e}")


def parse_image_to_base64(content: bytes, mime_type: str = "image/png") -> str:
    """
    Convert image to base64 for GPT-4o Vision with size limits.

    Args:
        content: Raw image file bytes
        mime_type: MIME type of the image (e.g., "image/png", "image/jpeg")

    Returns:
        Base64-encoded data URL string
    """
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()  # Verify it's a valid image

        # Re-open after verify (verify closes the file)
        img = Image.open(io.BytesIO(content))

        # Security: Check dimensions to prevent decompression bombs
        width, height = img.size
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise ValueError(f"Image dimensions too large. Maximum: {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}")

        if width * height > MAX_IMAGE_PIXELS:
            raise ValueError(f"Image has too many pixels. Maximum: {MAX_IMAGE_PIXELS}")

        # Convert to RGB if needed (for JPEG compatibility)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize large images to save bandwidth
        if width > 2048 or height > 2048:
            img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            logger.info(f"Resized image from {width}x{height} to {img.size}")

        # Encode to base64
        buffer = io.BytesIO()
        img_format = "PNG" if "png" in mime_type.lower() else "JPEG"
        img.save(buffer, format=img_format, quality=85)
        base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return f"data:{mime_type};base64,{base64_str}"
    except Exception as e:
        logger.error(f"Image parsing failed: {e}")
        raise ValueError(f"Failed to parse image: {e}")


def parse_document(content: bytes, filename: str) -> Tuple[str, str]:
    """
    Detect file type and parse document content.

    Args:
        content: Raw file bytes
        filename: Original filename (used to detect type)

    Returns:
        Tuple of (parsed_content, content_type)
        - content_type is "text" for PDF/DOCX, "image" for images
    """
    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        return parse_pdf(content), "text"
    elif filename_lower.endswith((".docx", ".doc")):
        return parse_docx(content), "text"
    elif filename_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        mime_type = "image/png" if filename_lower.endswith(".png") else "image/jpeg"
        if filename_lower.endswith(".gif"):
            mime_type = "image/gif"
        elif filename_lower.endswith(".webp"):
            mime_type = "image/webp"
        return parse_image_to_base64(content, mime_type), "image"
    else:
        # Try to read as plain text
        try:
            return content.decode("utf-8"), "text"
        except UnicodeDecodeError:
            raise ValueError(f"Unsupported file type: {filename}")
