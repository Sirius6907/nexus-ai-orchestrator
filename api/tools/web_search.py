"""
Web Search Tool — Searches the web using DuckDuckGo's lite HTML endpoint.
No API key required.
"""
import httpx
import logging
from api.tools.base import BaseTool

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "Search the web for current information. Input: search query string."

    async def execute(self, query: str, **kwargs) -> str:
        """Search DuckDuckGo and return top results as text."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; NexusAI/1.0)"
                    },
                )
                response.raise_for_status()

            # Parse results from HTML
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            for result in soup.select(".result")[:5]:
                title_el = result.select_one(".result__a")
                snippet_el = result.select_one(".result__snippet")

                title = title_el.get_text(strip=True) if title_el else ""
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                if title:
                    results.append(f"• {title}: {snippet}")

            if not results:
                return f"No results found for: {query}"

            return f"Web search results for '{query}':\n" + "\n".join(results)

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return f"Search failed: {str(e)}"
