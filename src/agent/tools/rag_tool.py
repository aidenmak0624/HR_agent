# src/agent/tools/rag_tool.py

from typing import Dict, Any, List
import sys
from pathlib import Path
import logging

# Add parent directory to path to import HRKnowledgeBase
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from src.core.rag_system import HRKnowledgeBase

logger = logging.getLogger(__name__)


class RAGSearchTool:
    """
    RAG search tool with quality metrics for intelligent search prioritization.

    Priority Strategy:
    1. Always try RAG first (fast, accurate for known topics)
    2. Assess quality using multiple metrics
    3. Recommend web search if quality insufficient
    """

    name = "rag_search"
    description = """Search the local HR knowledge base using semantic search.
    This should ALWAYS be tried first before web search. Returns quality metrics to
    determine if results are sufficient or if web search is needed."""

    # ===== QUALITY THRESHOLDS =====
    # Adjust these based on your data quality and requirements

    MIN_RELEVANCE_SCORE = 0.7  # Max distance threshold (cosine distance, lower = more similar)
    # Documents with distance > 0.7 are considered poor matches

    MIN_CHUNKS = 3  # Minimum number of relevant chunks needed
    # Need at least 3 good chunks to form comprehensive answer

    MIN_AVG_QUALITY = 0.6  # Minimum average quality score (0.0 to 1.0)
    # Combined metric considering distance and coverage

    # Advanced thresholds
    MAX_WORST_DISTANCE = 0.9  # Worst acceptable distance in results
    MIN_BEST_DISTANCE = 0.5  # Best result should be at least this good

    def __init__(self):
        """Initialize RAG system with preloaded topics."""
        logger.info("Initializing RAG Search Tool...")
        self.rag = HRKnowledgeBase(preload_topics=True)
        logger.info(f"✅ RAG Tool ready with topics: {self.rag.topics}")

    def run(self, query: str, topic: str = "benefits", n_results: int = 6) -> Dict[str, Any]:
        """
        Execute RAG search with comprehensive quality assessment.

        Args:
            query: Search query string
            topic: Topic category to search in (default: benefits)
            n_results: Number of results to retrieve (default: 6)

        Returns:
            Dict containing:
                - success: bool
                - query: str
                - topic: str
                - documents: list of retrieved text chunks
                - distances: list of distance scores (lower = more similar)
                - sources: list of source filenames
                - num_results: int

                Quality Metrics:
                - quality_metrics: dict with detailed metrics
                - is_sufficient: bool (are results good enough?)
                - confidence: float (0.0 to 1.0)
                - recommendation: str (what to do next)
        """
        logger.info(f"RAG search: '{query[:100]}' in topic '{topic}'")

        try:
            # ===== 1. RETRIEVE FROM CHROMADB =====
            results = self.rag.retrieve(query, topic, n_results)

            if not results or not results.get("documents"):
                return self._no_results_response(query, topic)

            # ===== 2. EXTRACT DATA =====
            # ChromaDB returns nested lists: [[doc1, doc2, ...]]
            documents = results["documents"][0]
            distances = results["distances"][0]
            metadatas = results.get("metadatas", [[]])[0]

            logger.info(f"Retrieved {len(documents)} documents")

            # ===== 3. CALCULATE QUALITY METRICS =====
            quality_metrics = self._assess_quality(distances, documents)

            # ===== 4. DETERMINE SUFFICIENCY =====
            is_sufficient = self._is_sufficient_quality(quality_metrics)

            # ===== 5. GENERATE RECOMMENDATION =====
            recommendation = self._get_recommendation(quality_metrics, is_sufficient)

            # Log decision
            logger.info(
                f"Quality: avg_dist={quality_metrics['avg_distance']:.3f}, "
                f"relevant={quality_metrics['num_relevant']}/{len(documents)}, "
                f"confidence={quality_metrics['overall_confidence']:.3f}, "
                f"sufficient={is_sufficient}"
            )

            return {
                "success": True,
                "query": query,
                "topic": topic,
                "documents": documents,
                "distances": distances,
                "sources": [m.get("source", "unknown") for m in metadatas],
                "num_results": len(documents),
                # Quality assessment
                "quality_metrics": quality_metrics,
                "is_sufficient": is_sufficient,
                "confidence": quality_metrics["overall_confidence"],
                "recommendation": recommendation,
            }

        except Exception as e:
            logger.error(f"❌ RAG search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "topic": topic,
                "documents": [],
                "is_sufficient": False,
                "confidence": 0.0,
                "recommendation": "Try web search due to RAG error",
            }

    def _assess_quality(self, distances: List[float], documents: List[str]) -> Dict[str, Any]:
        """
        Assess the quality of RAG results using multiple metrics.

        Quality Factors:
        1. Average distance (lower = more relevant)
        2. Minimum distance (best match quality)
        3. Maximum distance (worst match quality)
        4. Number of highly relevant chunks (distance < threshold)
        5. Document completeness (length, content)

        Args:
            distances: List of cosine distances (0.0 = identical, 2.0 = opposite)
            documents: List of retrieved document chunks

        Returns:
            Dict with comprehensive quality metrics
        """
        if not distances or not documents:
            return {
                "avg_distance": 1.0,
                "min_distance": 1.0,
                "max_distance": 1.0,
                "num_relevant": 0,
                "num_total": 0,
                "overall_confidence": 0.0,
                "quality_tier": "none",
            }

        # ===== DISTANCE METRICS =====
        avg_distance = sum(distances) / len(distances)
        min_distance = min(distances)
        max_distance = max(distances)

        # Count highly relevant chunks (distance < threshold)
        num_relevant = sum(1 for d in distances if d < self.MIN_RELEVANCE_SCORE)

        # ===== CONFIDENCE CALCULATION =====
        # Component 1: Distance quality (0.0 to 1.0, higher = better)
        # Convert distance to similarity score: 1 - (distance / 2)
        # Assuming distance is in range [0, 2] for cosine distance
        distance_score = max(0, 1 - (avg_distance / 2))

        # Component 2: Coverage quality (0.0 to 1.0, higher = better)
        # How many results are actually relevant?
        relevance_ratio = num_relevant / len(distances)
        coverage_score = min(1.0, relevance_ratio)

        # Component 3: Best match quality (0.0 to 1.0, higher = better)
        # How good is the top result?
        best_match_score = max(0, 1 - min_distance)

        # Component 4: Consistency (0.0 to 1.0, higher = better)
        # Are results consistently good or highly variable?
        distance_std = (sum((d - avg_distance) ** 2 for d in distances) / len(distances)) ** 0.5
        consistency_score = max(0, 1 - (distance_std / 1.0))  # Normalize by expected std

        # Overall confidence (weighted average)
        overall_confidence = (
            distance_score * 0.35
            + coverage_score * 0.25  # 35% weight: average quality
            + best_match_score * 0.25  # 25% weight: how many are good
            + consistency_score * 0.15  # 25% weight: best result quality  # 15% weight: consistency
        )

        # ===== QUALITY TIER =====
        if overall_confidence >= 0.8:
            quality_tier = "excellent"
        elif overall_confidence >= 0.6:
            quality_tier = "good"
        elif overall_confidence >= 0.4:
            quality_tier = "fair"
        else:
            quality_tier = "poor"

        return {
            "avg_distance": round(avg_distance, 3),
            "min_distance": round(min_distance, 3),
            "max_distance": round(max_distance, 3),
            "num_relevant": num_relevant,
            "num_total": len(distances),
            "overall_confidence": round(overall_confidence, 3),
            "quality_tier": quality_tier,
            # Component scores for debugging
            "_distance_score": round(distance_score, 3),
            "_coverage_score": round(coverage_score, 3),
            "_best_match_score": round(best_match_score, 3),
            "_consistency_score": round(consistency_score, 3),
        }

    def _is_sufficient_quality(self, metrics: Dict[str, Any]) -> bool:
        """
        Determine if RAG results are sufficient or if web search is needed.

        Decision Logic (ALL must be true):
        1. Average distance < threshold (good average quality)
        2. At least MIN_CHUNKS relevant chunks (sufficient coverage)
        3. Overall confidence ≥ threshold (high confidence)
        4. Best result is good enough (at least one excellent match)

        Args:
            metrics: Quality metrics dict from _assess_quality

        Returns:
            bool: True if results are sufficient, False if web search recommended
        """
        checks = {
            "avg_distance": metrics["avg_distance"] < self.MIN_RELEVANCE_SCORE,
            "min_chunks": metrics["num_relevant"] >= self.MIN_CHUNKS,
            "confidence": metrics["overall_confidence"] >= self.MIN_AVG_QUALITY,
            "best_match": metrics["min_distance"] < self.MIN_BEST_DISTANCE,
        }

        # Log detailed check results
        logger.debug(f"Quality checks: {checks}")

        # ALL checks must pass
        return all(checks.values())

    def _get_recommendation(self, metrics: Dict[str, Any], is_sufficient: bool) -> str:
        """
        Generate human-readable recommendation based on quality assessment.

        Args:
            metrics: Quality metrics dict
            is_sufficient: Whether results pass threshold

        Returns:
            str: Recommendation message
        """
        confidence = metrics["overall_confidence"]
        quality_tier = metrics["quality_tier"]

        if is_sufficient:
            if quality_tier == "excellent":
                return "✅ Excellent quality - use RAG results confidently"
            elif quality_tier == "good":
                return "✅ Good quality - RAG results are reliable"
            else:
                return "âœ Acceptable quality - RAG results usable"
        else:
            # Not sufficient - explain why
            issues = []

            if metrics["avg_distance"] >= self.MIN_RELEVANCE_SCORE:
                issues.append("low relevance")

            if metrics["num_relevant"] < self.MIN_CHUNKS:
                issues.append(
                    f"insufficient coverage ({metrics['num_relevant']}/{self.MIN_CHUNKS})"
                )

            if confidence < self.MIN_AVG_QUALITY:
                issues.append(f"low confidence ({confidence:.2f})")

            issues_str = ", ".join(issues)

            return f"⚠️ Web search recommended - RAG issues: {issues_str}"

    def _no_results_response(self, query: str, topic: str) -> Dict[str, Any]:
        """Return structured response when no results found."""
        logger.warning(f"No documents found for query: {query} in topic: {topic}")

        return {
            "success": False,
            "error": "No documents found in database",
            "query": query,
            "topic": topic,
            "documents": [],
            "distances": [],
            "sources": [],
            "num_results": 0,
            "quality_metrics": {
                "avg_distance": 1.0,
                "overall_confidence": 0.0,
                "quality_tier": "none",
            },
            "is_sufficient": False,
            "confidence": 0.0,
            "recommendation": "❌ Web search required - no local documents found",
        }


# Quick test
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    print("🔍 Testing RAG Search Tool with Quality Metrics\n")

    tool = RAGSearchTool()

    # Test 1: Good query (should have high quality)
    print("=" * 60)
    print("TEST 1: Known good query")
    print("=" * 60)
    result1 = tool.run("What is the PTO policy?", "benefits")
    print(f"Success: {result1['success']}")
    print(f"Sufficient: {result1['is_sufficient']}")
    print(f"Confidence: {result1['confidence']}")
    print(f"Quality Tier: {result1['quality_metrics']['quality_tier']}")
    print(f"Recommendation: {result1['recommendation']}")
    print()

    # Test 2: Edge case query (might have lower quality)
    print("=" * 60)
    print("TEST 2: Edge case query")
    print("=" * 60)
    result2 = tool.run("quantum mechanics of employment", "employment_law")
    print(f"Success: {result2['success']}")
    print(f"Sufficient: {result2['is_sufficient']}")
    print(f"Confidence: {result2['confidence']}")
    print(f"Quality Tier: {result2['quality_metrics']['quality_tier']}")
    print(f"Recommendation: {result2['recommendation']}")
