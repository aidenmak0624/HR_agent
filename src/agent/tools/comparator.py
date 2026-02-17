# src/agent/tools/comparator.py

"""
Comparator Tool - Compares different HR policies, benefits plans, or employment regulations

PURPOSE:
Enables the agent to analyze differences and similarities between:
- Different benefits plans (PPO vs HMO vs HDHP)
- Different policy versions or departments
- Federal vs state employment regulations
- Different leave types or compensation structures

USE CASES:
1. "Compare PPO and HMO health plans"
   - Finds both plan details
   - Analyzes cost/coverage differences
   - Explains trade-offs

2. "What's the difference between FMLA and company parental leave?"
   - Retrieves details of each
   - Compares eligibility and duration
   - Explains how they interact

3. "How does our remote work policy differ from hybrid policy?"
   - Compares arrangements
   - Identifies requirements
   - Shows flexibility options
"""

from typing import Dict, Any, List, Tuple
import sys
from pathlib import Path
import logging

# Add parent directory to import RAG system
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from src.core.rag_system import HRKnowledgeBase

from langchain_openai import ChatOpenAI
import os

logger = logging.getLogger(__name__)


class ComparatorTool:
    """
    Compares and contrasts different HR policies, benefits, or employment regulations.

    This tool helps the agent:
    1. Compare similar concepts (e.g., two articles)
    2. Contrast different frameworks
    3. Analyze evolution of rights over time
    4. Identify relationships between provisions
    5. Explain nuanced differences

    How it works:
    - Takes two items to compare as input
    - Searches RAG for information on both
    - Uses LLM to analyze similarities and differences
    - Returns structured comparison
    """

    name = "comparator"
    description = """Compare and contrast two HR policies, benefits plans,
    employment regulations, or workplace concepts. Use this when the user asks
    about differences, similarities, or relationships between two things.
    Input should specify the two items to compare."""

    def __init__(self):
        """Initialize with RAG system and LLM for comparison."""
        logger.info("Initializing Comparator Tool...")
        self.rag = HRKnowledgeBase(preload_topics=True)
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY", ""),
            temperature=0.2,  # Low temperature for analytical work
        )
        logger.info("✅ Comparator ready")

    def run(
        self, item_a: str, item_b: str, topic: str = "benefits", comparison_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Compare two HR policies, benefits plans, or employment provisions.

        Args:
            item_a: First item to compare (e.g., "PPO health plan")
            item_b: Second item to compare (e.g., "HMO health plan")
            topic: Topic area to search in
            comparison_type: Type of comparison:
                - "general": Overall similarities and differences
                - "scope": Compare scope and coverage
                - "cost": Compare cost and value
                - "eligibility": Compare eligibility requirements

        Returns:
            Dict with:
                - similarities: list of similar aspects
                - differences: list of different aspects
                - relationship: str describing how they relate
                - context: str providing background
                - key_insight: str main takeaway
                - sources: list of source documents

        Example:
            >>> comparator.run(
                    item_a="PPO health plan",
                    item_b="HMO health plan"
                )
            {
                "similarities": ["Both are employer-sponsored", "Both cover preventive care"],
                "differences": ["PPO allows out-of-network", ...],
                "relationship": "Alternative health plan options for employees",
                "key_insight": "PPO offers more flexibility while HMO has lower costs"
            }
        """
        logger.info(f"Comparing: '{item_a}' vs '{item_b}'")

        try:
            # Step 1: Retrieve information about both items
            info_a = self._retrieve_info(item_a, topic)
            info_b = self._retrieve_info(item_b, topic)

            # Step 2: Check if we have sufficient information
            if not self._has_sufficient_info(info_a, info_b):
                return self._insufficient_info_response(item_a, item_b)

            # Step 3: Perform comparison using LLM
            comparison_result = self._compare_with_llm(
                item_a, info_a, item_b, info_b, comparison_type
            )

            # Step 4: Add metadata
            comparison_result["item_a"] = item_a
            comparison_result["item_b"] = item_b
            comparison_result["comparison_type"] = comparison_type
            comparison_result["sources_a"] = self._extract_sources(info_a)
            comparison_result["sources_b"] = self._extract_sources(info_b)

            logger.info(
                f"Comparison complete: {len(comparison_result['similarities'])} "
                f"similarities, {len(comparison_result['differences'])} differences"
            )

            return comparison_result

        except Exception as e:
            logger.error(f"Comparison failed: {e}")
            return {
                "similarities": [],
                "differences": [],
                "relationship": "Comparison failed due to error",
                "context": f"Error: {e}",
                "key_insight": "Unable to complete comparison",
                "error": str(e),
            }

    def _retrieve_info(self, item: str, topic: str) -> Dict[str, Any]:
        """
        Retrieve information about a specific item from RAG.

        Returns dict with documents, distances, and metadatas.
        """
        results = self.rag.retrieve(
            query=item, topic=topic, n_results=8  # Get multiple perspectives
        )

        if not results or not results.get("documents"):
            return {"documents": [], "distances": [], "metadatas": []}

        return {
            "documents": results["documents"][0],
            "distances": results["distances"][0],
            "metadatas": results.get("metadatas", [[]])[0],
        }

    def _has_sufficient_info(self, info_a: dict, info_b: dict) -> bool:
        """Check if we have enough information to make a meaningful comparison."""
        return len(info_a.get("documents", [])) >= 2 and len(info_b.get("documents", [])) >= 2

    def _compare_with_llm(
        self, item_a: str, info_a: dict, item_b: str, info_b: dict, comparison_type: str
    ) -> Dict[str, Any]:
        """
        Use LLM to perform detailed comparison.

        The LLM analyzes both sets of information and provides
        structured comparison output.
        """
        # Format information about both items
        content_a = self._format_content(item_a, info_a)
        content_b = self._format_content(item_b, info_b)

        comparison_prompt = f"""You are an HR policy expert comparing two concepts or provisions.

**ITEM A:**
{content_a}

**ITEM B:**
{content_b}

**COMPARISON TYPE:** {comparison_type}

**TASK:**
Provide a thorough comparison. Return ONLY valid JSON:

{{
  "similarities": [
    "Specific similarity with explanation",
    "Another similarity"
  ],
  "differences": [
    "Key difference with details",
    "Another difference"
  ],
  "relationship": "How these items relate to each other (1-2 sentences)",
  "context": "Historical or conceptual context explaining the comparison (2-3 sentences)",
  "key_insight": "Most important takeaway from this comparison (1 sentence)",
  "nuances": ["Important subtleties or caveats"],
  "examples": [
    "Concrete example illustrating a key point"
  ]
}}

**ANALYSIS GUIDELINES:**

For "general" comparison:
- Identify 3-5 key similarities
- Identify 3-5 key differences
- Explain how they relate (complementary, contradictory, evolutionary)

For "scope" comparison:
- Compare what each covers
- Identify gaps and overlaps
- Explain why scope differs

For "enforcement" comparison:
- Compare mechanisms for implementation
- Note differences in obligations
- Explain practical implications

For "evolution" comparison:
- Establish chronological relationship
- Show how concepts developed
- Explain motivations for changes

**IMPORTANT:**
- Be specific with examples
- Quote relevant text when possible
- Note historical context
- Acknowledge complexity
- Only return JSON, no other text

**YOUR COMPARISON:**"""

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content="You are a comparative HR policy and employment law expert."),
                HumanMessage(content=comparison_prompt),
            ]

            response = self.llm.invoke(messages)

            # Parse JSON response
            import json

            result = json.loads(response.content)

            return {
                "similarities": result.get("similarities", []),
                "differences": result.get("differences", []),
                "relationship": result.get("relationship", ""),
                "context": result.get("context", ""),
                "key_insight": result.get("key_insight", ""),
                "nuances": result.get("nuances", []),
                "examples": result.get("examples", []),
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return self._fallback_comparison(item_a, info_a, item_b, info_b)
        except Exception as e:
            logger.error(f"LLM comparison failed: {e}")
            return self._fallback_comparison(item_a, info_a, item_b, info_b)

    def _format_content(self, item: str, info: dict) -> str:
        """Format retrieved information for the comparison prompt."""
        documents = info.get("documents", [])
        distances = info.get("distances", [])

        if not documents:
            return f"[No information found for: {item}]"

        formatted = [f"**About: {item}**\n"]

        # Include top 5 most relevant documents
        for i, (doc, dist) in enumerate(zip(documents[:5], distances[:5])):
            relevance = "HIGH" if dist < 0.5 else "MEDIUM" if dist < 0.7 else "LOW"
            formatted.append(f"\n[Source {i+1}] (Relevance: {relevance})\n{doc}")

        return "\n".join(formatted)

    def _fallback_comparison(
        self, item_a: str, info_a: dict, item_b: str, info_b: dict
    ) -> Dict[str, Any]:
        """
        Simple heuristic-based comparison when LLM fails.

        Uses basic text similarity and keyword analysis.
        """
        docs_a = info_a.get("documents", [])
        docs_b = info_b.get("documents", [])

        # Simple keyword overlap analysis
        text_a = " ".join(docs_a[:3]).lower()
        text_b = " ".join(docs_b[:3]).lower()

        # Find common keywords (very basic)
        words_a = set(text_a.split())
        words_b = set(text_b.split())
        common = words_a.intersection(words_b)

        # Remove common stop words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }
        common = common - stop_words

        return {
            "similarities": [
                (
                    f"Both mention: {', '.join(list(common)[:5])}"
                    if common
                    else "Both are HR policy topics"
                )
            ],
            "differences": [
                "Detailed comparison unavailable (fallback mode)",
                f"Item A has {len(docs_a)} sources, Item B has {len(docs_b)} sources",
            ],
            "relationship": "Both items are related to HR policies (fallback analysis)",
            "context": "Detailed context unavailable in fallback mode",
            "key_insight": "Further analysis needed for comprehensive comparison",
            "nuances": ["This is a basic heuristic comparison"],
            "examples": [],
        }

    def _extract_sources(self, info: dict) -> List[str]:
        """Extract source document names."""
        metadatas = info.get("metadatas", [])
        return [m.get("source", "unknown") for m in metadatas if m]

    def _insufficient_info_response(self, item_a: str, item_b: str) -> Dict[str, Any]:
        """Return when insufficient information for comparison."""
        return {
            "similarities": [],
            "differences": [],
            "relationship": "Insufficient information for comparison",
            "context": f"Could not find enough information about '{item_a}' or '{item_b}'",
            "key_insight": "More specific search terms may help",
            "error": "Insufficient information",
            "item_a": item_a,
            "item_b": item_b,
        }

    def compare_multiple(self, items: List[str], topic: str = "benefits") -> Dict[str, Any]:
        """
        Compare multiple items (3 or more) simultaneously.

        Args:
            items: List of 3+ items to compare
            topic: Topic to search in

        Returns:
            Comparative analysis across all items
        """
        if len(items) < 3:
            raise ValueError("compare_multiple requires at least 3 items")

        # Retrieve info for all items
        all_info = {}
        for item in items:
            all_info[item] = self._retrieve_info(item, topic)

        # Build comparison matrix
        comparison_matrix = {}
        for i, item_a in enumerate(items):
            for item_b in items[i + 1 :]:
                pair_key = f"{item_a} vs {item_b}"
                comparison_matrix[pair_key] = self.run(item_a, item_b, topic, "general")

        return {
            "items": items,
            "pairwise_comparisons": comparison_matrix,
            "summary": f"Compared {len(items)} items across {len(comparison_matrix)} pairs",
        }


# ===== USAGE EXAMPLES =====


def example_usage():
    """Demonstrate how the comparator works."""

    comparator = ComparatorTool()

    print("=" * 60)
    print("COMPARATOR TOOL - EXAMPLES")
    print("=" * 60)

    # Example 1: Compare two types of rights
    print("\n1. Comparing types of rights:")
    result1 = comparator.run(
        item_a="civil and political rights",
        item_b="economic, social and cultural rights",
        topic="benefits",
        comparison_type="general",
    )
    print(f"Similarities: {len(result1['similarities'])}")
    print(f"Differences: {len(result1['differences'])}")
    print(f"Key Insight: {result1['key_insight'][:150]}...")

    # Example 2: Compare specific articles
    print("\n2. Comparing articles:")
    result2 = comparator.run(
        item_a="Article 3 UDHR right to life",
        item_b="Article 6 ICCPR right to life",
        topic="benefits",
        comparison_type="scope",
    )
    print(f"Relationship: {result2['relationship'][:150]}...")

    # Example 3: Compare frameworks
    print("\n3. Comparing frameworks:")
    result3 = comparator.run(
        item_a="Universal Declaration of Human Rights",
        item_b="International Covenant on Civil and Political Rights",
        topic="benefits",
        comparison_type="evolution",
    )
    print(f"Context: {result3['context'][:200]}...")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    example_usage()
