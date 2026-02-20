"""
AustLII Search Service

Searches the Australian Legal Information Institute (AustLII) for legislation
and case law. Used as a fallback when the RAG database has no results and as
the primary source for case law search.

AustLII is a free public legal database operated by UNSW and UTS Law faculties.
"""

import re
import asyncio
from urllib.parse import urlparse
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.config import logger


# Allowed hostnames for content fetching (SSRF protection)
_ALLOWED_HOSTS = {"www.austlii.edu.au", "austlii.edu.au"}

# Min delay between requests to be respectful of AustLII's resources
_REQUEST_DELAY = 0.3  # seconds


class AustLIISearcher:
    """Search AustLII for Australian legislation and case law."""

    SEARCH_URL = "https://www.austlii.edu.au/cgi-bin/sinosrch.cgi"
    BASE_URL = "https://www.austlii.edu.au"
    TIMEOUT = 30
    HEADERS = {
        "User-Agent": "AusLawAI/1.0 (legal research tool)",
        "Referer": "https://www.austlii.edu.au/forms/search1.html",
    }

    # Consolidated legislation (current versions) per state
    LEGISLATION_PATHS = {
        "NSW": "au/legis/nsw/consol_act",
        "VIC": "au/legis/vic/consol_act",
        "QLD": "au/legis/qld/consol_act",
        "SA": "au/legis/sa/consol_act",
        "WA": "au/legis/wa/consol_act",
        "TAS": "au/legis/tas/consol_act",
        "NT": "au/legis/nt/consol_act",
        "ACT": "au/legis/act/consol_act",
        "FEDERAL": "au/legis/cth/consol_act",
    }

    # Case law (all courts) per state
    CASE_LAW_PATHS = {
        "NSW": "au/cases/nsw",
        "VIC": "au/cases/vic",
        "QLD": "au/cases/qld",
        "SA": "au/cases/sa",
        "WA": "au/cases/wa",
        "TAS": "au/cases/tas",
        "NT": "au/cases/nt",
        "ACT": "au/cases/act",
        "FEDERAL": "au/cases/cth",
    }

    def __init__(self):
        logger.info("AustLII searcher initialized")

    async def search_legislation(
        self, query: str, state: str, max_results: int = 5
    ) -> list[dict]:
        """
        Search AustLII for consolidated legislation.

        Args:
            query: Legal search query
            state: Australian state code (NSW, VIC, QLD, etc.)
            max_results: Maximum results to return

        Returns:
            List of {title, url, jurisdiction, type}
        """
        mask_path = self.LEGISLATION_PATHS.get(state)
        if not mask_path:
            logger.warning(f"No legislation path for state: {state}")
            return []

        results = await self._search_austlii(query, mask_path, max_results)

        for r in results:
            r["type"] = "legislation"
            r["jurisdiction"] = state

        return results

    async def search_cases(
        self, query: str, state: str, max_results: int = 5
    ) -> list[dict]:
        """
        Search AustLII for case law.

        Args:
            query: Legal search query
            state: Australian state code (NSW, VIC, QLD, etc.)
            max_results: Maximum results to return

        Returns:
            List of {title, citation, court, date, url, jurisdiction, type}
        """
        mask_path = self.CASE_LAW_PATHS.get(state)
        if not mask_path:
            logger.warning(f"No case law path for state: {state}")
            return []

        results = await self._search_austlii(query, mask_path, max_results)

        for r in results:
            r["type"] = "case"
            r["jurisdiction"] = state

        return results

    async def fetch_content(self, url: str) -> Optional[str]:
        """
        Fetch and extract text content from an AustLII page.

        Used for legislation sections to get actual legislative text.
        Returns cleaned text truncated to ~2000 characters.
        """
        # Validate URL is on AustLII (SSRF protection)
        if not self._is_austlii_url(url):
            logger.warning(f"Blocked non-AustLII URL in fetch_content: {url}")
            return None

        try:
            async with httpx.AsyncClient(
                headers=self.HEADERS, timeout=self.TIMEOUT, follow_redirects=True
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Verify final URL after redirects is still on AustLII
                final_host = response.url.host
                if final_host not in _ALLOWED_HOSTS:
                    logger.warning(
                        f"AustLII redirect to non-AustLII host blocked: {final_host}"
                    )
                    return None

            soup = BeautifulSoup(response.text, "html.parser")

            # AustLII puts legislative content in <article> tags
            article = soup.find("article")
            if article:
                text = article.get_text(separator="\n", strip=True)
            else:
                # Fallback: try the main body content
                body = soup.find("body")
                if not body:
                    return None
                # Remove nav, header, footer, script, style
                for tag in body.find_all(
                    ["nav", "header", "footer", "script", "style"]
                ):
                    tag.decompose()
                text = body.get_text(separator="\n", strip=True)

            # Clean up and truncate
            text = re.sub(r"\n{3,}", "\n\n", text)
            if len(text) > 2000:
                text = text[:2000] + "\n\n[Truncated - view full text at source URL]"

            return text if text.strip() else None

        except Exception as e:
            logger.warning(f"Failed to fetch AustLII content from {url}: {e}")
            return None

    async def _search_austlii(
        self, query: str, mask_path: str, max_results: int
    ) -> list[dict]:
        """
        Execute a search against AustLII's search endpoint.

        Args:
            query: Search query string
            mask_path: AustLII database path (e.g., 'au/legis/vic/consol_act')
            max_results: Maximum number of results

        Returns:
            List of parsed result dicts
        """
        params = {
            "method": "auto",
            "query": query,
            "meta": "/au",
            "mask_path": mask_path,
            "results": str(max_results),
        }

        try:
            async with httpx.AsyncClient(
                headers=self.HEADERS, timeout=self.TIMEOUT, follow_redirects=True
            ) as client:
                response = await client.get(self.SEARCH_URL, params=params)
                logger.info(
                    f"AustLII search: status={response.status_code}, "
                    f"size={len(response.text)} bytes, path={mask_path}"
                )
                response.raise_for_status()

            results = self._parse_search_results(response.text)
            logger.info(f"AustLII parsed {len(results)} results for query='{query}'")
            return results

        except httpx.TimeoutException:
            logger.warning(
                f"AustLII search timed out for query='{query}', path={mask_path}"
            )
            return []
        except httpx.HTTPStatusError as e:
            logger.error(
                f"AustLII HTTP {e.response.status_code} for query='{query}': {e}"
            )
            return []
        except Exception as e:
            logger.error(f"AustLII search error: {type(e).__name__}: {e}")
            return []

    def _parse_search_results(self, html: str) -> list[dict]:
        """
        Parse AustLII search results HTML.

        Results are in <li data-count class="multi"> elements containing:
        - First <a>: title + URL
        - <p class="meta">: court name, date, LawCite link
        """
        if not html or not html.strip():
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []

        for li in soup.select("li.multi"):
            result = self._parse_result_item(li)
            if result:
                results.append(result)

        return results

    def _parse_result_item(self, li) -> Optional[dict]:
        """Parse a single search result <li> element."""
        # Extract title and URL from first <a> tag
        link = li.find("a")
        if not link:
            return None

        title = link.get_text(strip=True)
        if not title:
            return None

        href = link.get("href", "")

        # Build absolute URL
        if href.startswith("/"):
            url = self.BASE_URL + href
        elif href.startswith("http"):
            url = href
        else:
            url = self.BASE_URL + "/" + href

        result = {"title": title, "url": url}

        # Parse metadata from <p class="meta">
        meta = li.find("p", class_="meta")
        if meta:
            # Court name from first <a> in meta
            court_link = meta.find("a")
            if court_link:
                court_text = court_link.get_text(strip=True)
                if court_text and "LawCite" not in court_text:
                    result["court"] = court_text

            # Date from <span class="break">
            date_spans = meta.find_all("span", class_="break")
            for span in date_spans:
                text = span.get_text(strip=True)
                if re.match(
                    r"\d{1,2}\s+"
                    r"(?:January|February|March|April|May|June|"
                    r"July|August|September|October|November|December)"
                    r"\s+(?:19|20)\d{2}$",
                    text,
                ):
                    result["date"] = text
                    break

        # Extract citation from title (e.g., "[2020] VCAT 1391")
        citation_match = re.search(r"\[\d{4}\]\s+[A-Z]{2,10}\s+\d+", title)
        if citation_match:
            result["citation"] = citation_match.group()

        return result

    @staticmethod
    def _is_austlii_url(url: str) -> bool:
        """Check that a URL points to AustLII (SSRF protection)."""
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in ("http", "https")
                and parsed.hostname in _ALLOWED_HOSTS
            )
        except Exception:
            return False


# Singleton
_austlii_searcher = None


def get_austlii_searcher() -> AustLIISearcher:
    """Get or create the singleton AustLIISearcher instance."""
    global _austlii_searcher
    if _austlii_searcher is None:
        _austlii_searcher = AustLIISearcher()
    return _austlii_searcher
