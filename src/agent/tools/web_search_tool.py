# src/agent/tools/web_search_tool.py

from typing import Dict, Any
import os
import requests
from langchain_openai import ChatOpenAI
import logging

logger = logging.getLogger(__name__)


class WebSearchTool:
    """
    Web search tool that searches the internet when RAG quality is insufficient.
    Uses Google Custom Search API with intelligent fallback.
    """

    name = "web_search"
    description = """Search the web for HR policy and employment law information when
    local documents are insufficient. Use this when RAG search quality is low or
    query is outside document scope."""

    def __init__(self):
        self.search_api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        self.search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        self.llm = ChatOpenAI(
            model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY", ""), temperature=0.3
        )

        # Log initialization status
        if self.search_api_key and self.search_engine_id:
            logger.info("✅ Web Search Tool initialized with Google Custom Search API")
        else:
            logger.warning("⚠️ Web Search Tool initialized in FALLBACK mode (no API keys)")

    def run(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        """
        Execute web search and return structured results.

        Args:
            query: Search query
            num_results: Number of results to return (default 5)

        Returns:
            Dict with:
                - success: bool
                - query: str
                - results: list of search results
                - summary: str (LLM-generated synthesis)
                - source: str ("web_search")
                - num_results: int
                - mode: str ("api" or "fallback")
        """
        logger.info(f"Web search for: {query[:100]}")

        try:
            # Try real API if configured
            if self.search_api_key and self.search_engine_id:
                results, mode = self._google_search(query, num_results), "api"
            else:
                # Use fallback for development/testing
                results, mode = self._fallback_search(query), "fallback"

            # Synthesize results with LLM
            summary = self._synthesize_results(query, results)

            logger.info(f"✅ Web search completed ({mode}): {len(results)} results")

            return {
                "success": True,
                "query": query,
                "results": results,
                "summary": summary,
                "source": "web_search",
                "num_results": len(results),
                "mode": mode,
            }

        except Exception as e:
            logger.error(f"❌ Web search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "results": [],
                "summary": f"Web search failed: {e}",
                "mode": "error",
            }

    def _google_search(self, query: str, num_results: int) -> list:
        """
        Execute Google Custom Search API request.

        Requires:
        - GOOGLE_SEARCH_API_KEY in environment
        - GOOGLE_SEARCH_ENGINE_ID in environment
        """
        url = "https://www.googleapis.com/customsearch/v1"

        # Enhance query with HR context
        enhanced_query = f"{query} employment HR policy"

        params = {
            "key": self.search_api_key,
            "cx": self.search_engine_id,
            "q": enhanced_query,
            "num": min(num_results, 10),  # API max is 10
        }

        logger.debug(f"Google Search API request: {enhanced_query}")

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("items", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", ""),
                    "source": item.get("displayLink", ""),
                    "published": item.get("snippet", "")[:50],  # Approximate date from snippet
                }
            )

        return results

    def _fallback_search(self, query: str) -> list:
        """
        Fallback search for development/testing without API keys.
        Returns realistic-looking results with HR policy focus.
        """
        logger.info("Using fallback search (no API keys configured)")

        # Provide helpful fallback results pointing to authoritative sources
        fallback_results = [
            {
                "title": f"Employment Law Information: {query}",
                "snippet": (
                    "The U.S. Department of Labor provides comprehensive information on federal "
                    "employment laws including FMLA, FLSA, ADA, and more. For real-time search "
                    "results, configure GOOGLE_SEARCH_API_KEY in your environment."
                ),
                "url": "https://www.dol.gov/agencies/whd",
                "source": "dol.gov",
                "published": "U.S. Department of Labor",
            },
            {
                "title": "EEOC - Employment Discrimination Laws",
                "snippet": (
                    "The Equal Employment Opportunity Commission enforces federal laws prohibiting "
                    "employment discrimination based on race, color, religion, sex, and more."
                ),
                "url": "https://www.eeoc.gov/statutes/laws-enforced-eeoc",
                "source": "eeoc.gov",
                "published": "EEOC",
            },
            {
                "title": "SHRM - HR Resources and Policies",
                "snippet": (
                    "Access comprehensive HR policy templates, compliance guides, and best practices "
                    "from the Society for Human Resource Management."
                ),
                "url": "https://www.shrm.org/topics-tools",
                "source": "shrm.org",
                "published": "SHRM",
            },
        ]

        return fallback_results

    def _synthesize_results(self, query: str, results: list) -> str:
        """
        Use LLM to synthesize search results into coherent summary.

        Args:
            query: Original search query
            results: List of search result dicts

        Returns:
            Synthesized summary string
        """
        if not results:
            return "No web results found."

        # Combine snippets from top results
        combined_snippets = "\n\n".join(
            [
                f"**Source {i+1}: {r['source']}**\n"
                f"Title: {r['title']}\n"
                f"Content: {r['snippet']}\n"
                f"URL: {r['url']}"
                for i, r in enumerate(results[:5])
            ]
        )

        prompt = f"""You are an HR policy expert synthesizing web search results.

**Original Query:** "{query}"

**Web Search Results:**
{combined_snippets}

**Task:** Provide a clear, factual summary (2-3 paragraphs) that:
1. Directly answers the query based on the search results
2. Integrates information from multiple sources
3. Maintains HR policy and employment focus
4. Uses natural language (not bullet points)
5. Mentions sources naturally when relevant

**Important:** If results are in fallback/development mode, acknowledge this and explain what real results would provide.

**Summary:**"""

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content="You are an HR policy and employment expert."),
                HumanMessage(content=prompt),
            ]

            response = self.llm.invoke(messages)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            # Fallback to simple concatenation
            return "\n\n".join([r["snippet"] for r in results[:3]])

    def get_source_urls(self, results: list) -> list:
        """Extract just the URLs from search results."""
        return [r.get("url", "") for r in results if r.get("url")]


# Quick test
# Around line 248-260, replace with:
if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).parent.parent.parent.parent))

    from dotenv import load_dotenv

    load_dotenv()

    print("🔍 Testing Web Search Tool\n")

    tool = WebSearchTool()

    try:
        result = tool.run("What is FMLA leave eligibility?", num_results=3)

        print(f"Success: {result.get('success', False)}")
        print(f"Mode: {result.get('mode', 'unknown')}")
        print(f"Num Results: {result.get('num_results', 0)}")

        if result.get("success"):
            print(f"\nSummary:\n{result.get('summary', 'No summary')}")
            print(f"\n📚 Sources:")
            for i, r in enumerate(result.get("results", []), 1):
                print(f"  {i}. {r.get('title', 'No title')} ({r.get('source', 'No source')})")
        else:
            print(f"\n⚠️ Error: {result.get('error', 'Unknown error')}")
            print("\nThis is expected if you don't have Google Custom Search API keys.")
            print("The web search will use fallback mode in production.")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("\nNote: Web search errors are OK - fallback mode will be used.")
