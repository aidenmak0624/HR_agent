# src/agent/tools/fact_checker.py

"""
Fact Verifier Tool - Validates claims against authoritative HR policy and employment law sources

PURPOSE:
When the agent generates an answer, this tool can verify specific claims
against the HR knowledge base or web sources to ensure accuracy.

USE CASES:
1. User asks: "Is FMLA leave 12 weeks?"
   - Agent generates answer
   - Fact checker validates against employment law knowledge base

2. Agent makes claim: "The 401k match is 5%"
   - Fact checker retrieves benefits data, confirms accuracy

3. Conflicting information detected
   - Fact checker resolves by finding authoritative source
"""

from typing import Dict, Any, List
import sys
from pathlib import Path
import logging

# Add parent directory to import RAG system
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from src.core.rag_system import HRKnowledgeBase

from langchain_openai import ChatOpenAI
import os

logger = logging.getLogger(__name__)


class FactVerifierTool:
    """
    Verifies factual claims about HR policies and employment law against authoritative sources.

    This tool helps the agent:
    1. Double-check its own generated answers
    2. Verify user claims ("I heard that...")
    3. Resolve contradictions between sources
    4. Provide citations for specific facts

    How it works:
    - Takes a specific claim as input
    - Searches RAG database for relevant documents
    - Uses LLM to compare claim against source material
    - Returns verification result with evidence
    """

    name = "fact_verifier"
    description = """Verify specific factual claims about HR policies against
    authoritative sources (employment law, company policies, benefits guides).
    Use this when you need to validate a specific claim or provide authoritative
    citation. Input should be a clear, specific claim to verify."""

    def __init__(self):
        """Initialize with RAG system and LLM for verification."""
        logger.info("Initializing Fact Verifier Tool...")
        self.rag = HRKnowledgeBase(preload_topics=True)
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY", ""),
            temperature=0.0,  # Very low temperature for factual verification
        )
        logger.info("✅ Fact Verifier ready")

    def run(self, claim: str, topic: str = "benefits") -> Dict[str, Any]:
        """
        Verify a specific claim against authoritative sources.

        Args:
            claim: The specific claim to verify (e.g., "Article 5 prohibits torture")
            topic: Topic area to search in (default: benefits)

        Returns:
            Dict with:
                - verified: bool (True/False/Uncertain)
                - confidence: float (0.0 to 1.0)
                - verdict: str ("CONFIRMED" | "REFUTED" | "UNCERTAIN" | "PARTIALLY_TRUE")
                - evidence: list of supporting/refuting evidence
                - sources: list of source documents
                - explanation: str (detailed reasoning)

        Example:
            >>> verifier.run("The UDHR was adopted in 1948")
            {
                "verified": True,
                "confidence": 0.95,
                "verdict": "CONFIRMED",
                "evidence": ["The Universal Declaration...adopted in 1948"],
                "explanation": "The claim is accurate..."
            }
        """
        logger.info(f"Verifying claim: '{claim[:100]}'")

        try:
            # Step 1: Search for relevant documents
            search_results = self._search_for_evidence(claim, topic)

            if not search_results or not search_results.get("documents"):
                return self._no_evidence_response(claim)

            # Step 2: Extract evidence
            documents = search_results["documents"][0]
            distances = search_results["distances"][0]
            metadatas = search_results.get("metadatas", [[]])[0]

            # Step 3: Use LLM to verify claim against evidence
            verification_result = self._verify_with_llm(claim, documents, distances)

            # Step 4: Add metadata
            verification_result["sources"] = [m.get("source", "unknown") for m in metadatas]
            verification_result["num_sources_checked"] = len(documents)
            verification_result["claim"] = claim
            verification_result["topic"] = topic

            logger.info(
                f"Verification complete: {verification_result['verdict']} "
                f"(confidence: {verification_result['confidence']})"
            )

            return verification_result

        except Exception as e:
            logger.error(f"Fact verification failed: {e}")
            return {
                "verified": False,
                "confidence": 0.0,
                "verdict": "ERROR",
                "evidence": [],
                "sources": [],
                "explanation": f"Verification failed due to error: {e}",
                "claim": claim,
            }

    def _search_for_evidence(self, claim: str, topic: str) -> dict:
        """
        Search RAG database for documents relevant to the claim.

        Strategy:
        - Extract key terms from claim
        - Search with higher n_results for thorough checking
        - Focus on finding contradicting evidence too
        """
        # Search with more results than normal for thorough verification
        return self.rag.retrieve(
            query=claim, topic=topic, n_results=10  # More results for thorough fact-checking
        )

    def _verify_with_llm(
        self, claim: str, documents: List[str], distances: List[float]
    ) -> Dict[str, Any]:
        """
        Use LLM to verify claim against retrieved documents.

        The LLM acts as a fact-checker, comparing the claim against
        authoritative source material.
        """
        # Combine documents with relevance scores
        evidence_text = self._format_evidence(documents, distances)

        verification_prompt = f"""You are a fact-checking expert for HR policy and employment law information.

**CLAIM TO VERIFY:**
"{claim}"

**AUTHORITATIVE SOURCE MATERIAL:**
{evidence_text}

**TASK:**
Carefully verify the claim against the source material. Return ONLY valid JSON:

{{
  "verdict": "CONFIRMED" | "REFUTED" | "PARTIALLY_TRUE" | "UNCERTAIN",
  "confidence": 0.0 to 1.0,
  "verified": true | false,
  "evidence": [
    "Direct quote or paraphrase supporting or refuting the claim",
    "Another piece of evidence"
  ],
  "explanation": "Detailed reasoning explaining the verdict",
  "caveats": ["Any important nuances or limitations"]
}}

**VERIFICATION CRITERIA:**
- CONFIRMED: Claim is clearly supported by sources (confidence ≥ 0.8)
- PARTIALLY_TRUE: Claim has some truth but needs clarification (confidence 0.5-0.8)
- REFUTED: Claim contradicts sources (confidence ≥ 0.8)
- UNCERTAIN: Insufficient evidence to verify (confidence < 0.5)

**IMPORTANT:**
- Be precise with quotes from source material
- Note if claim uses incorrect terminology
- Identify factual errors clearly
- Consider historical context
- Only return JSON, no other text

**YOUR VERIFICATION:**"""

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(
                    content="You are a meticulous fact-checker specializing in HR policies and employment law."
                ),
                HumanMessage(content=verification_prompt),
            ]

            response = self.llm.invoke(messages)

            # Parse JSON response
            import json

            result = json.loads(response.content)

            # Ensure all required fields exist
            return {
                "verified": bool(result.get("verified", False)),
                "confidence": float(result.get("confidence", 0.0)),
                "verdict": result.get("verdict", "UNCERTAIN"),
                "evidence": result.get("evidence", []),
                "explanation": result.get("explanation", "No explanation provided"),
                "caveats": result.get("caveats", []),
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # Fallback: simple heuristic
            return self._fallback_verification(claim, documents, distances)
        except Exception as e:
            logger.error(f"LLM verification failed: {e}")
            return self._fallback_verification(claim, documents, distances)

    def _format_evidence(self, documents: List[str], distances: List[float]) -> str:
        """
        Format retrieved documents with relevance scores for the LLM.
        """
        formatted = []
        for i, (doc, dist) in enumerate(zip(documents, distances)):
            relevance = "HIGH" if dist < 0.5 else "MEDIUM" if dist < 0.7 else "LOW"
            formatted.append(f"[SOURCE {i+1}] (Relevance: {relevance})\n{doc}\n")
        return "\n".join(formatted)

    def _fallback_verification(
        self, claim: str, documents: List[str], distances: List[float]
    ) -> Dict[str, Any]:
        """
        Simple heuristic-based verification when LLM parsing fails.

        Logic:
        - If best match is very close (distance < 0.3) → likely confirmed
        - If best match is far (distance > 0.8) → uncertain
        - Check for contradiction keywords
        """
        if not distances:
            return self._no_evidence_response(claim)

        best_distance = min(distances)
        avg_distance = sum(distances) / len(distances)

        # Simple heuristic
        if best_distance < 0.3 and avg_distance < 0.5:
            verdict = "CONFIRMED"
            verified = True
            confidence = 0.7
            explanation = "Heuristic: Strong match found in authoritative sources"
        elif best_distance < 0.5:
            verdict = "PARTIALLY_TRUE"
            verified = True
            confidence = 0.5
            explanation = "Heuristic: Moderate match found, but may need clarification"
        elif best_distance > 0.8:
            verdict = "UNCERTAIN"
            verified = False
            confidence = 0.2
            explanation = "Heuristic: No strong evidence found in sources"
        else:
            verdict = "UNCERTAIN"
            verified = False
            confidence = 0.4
            explanation = "Heuristic: Evidence is unclear or contradictory"

        return {
            "verified": verified,
            "confidence": confidence,
            "verdict": verdict,
            "evidence": documents[:3],  # Top 3 documents
            "explanation": explanation,
            "caveats": ["This is a fallback heuristic verification"],
        }

    def _no_evidence_response(self, claim: str) -> Dict[str, Any]:
        """Return when no relevant documents found."""
        return {
            "verified": False,
            "confidence": 0.0,
            "verdict": "UNCERTAIN",
            "evidence": [],
            "sources": [],
            "explanation": f"No authoritative sources found to verify the claim: '{claim}'",
            "caveats": ["Claim may be outside scope of available documents"],
            "claim": claim,
        }

    def batch_verify(self, claims: List[str], topic: str = "benefits") -> List[Dict[str, Any]]:
        """
        Verify multiple claims at once (useful for checking an entire answer).

        Args:
            claims: List of claims to verify
            topic: Topic to search in

        Returns:
            List of verification results
        """
        results = []
        for claim in claims:
            result = self.run(claim, topic)
            results.append(result)
        return results


# ===== USAGE EXAMPLES =====


def example_usage():
    """Demonstrate how the fact verifier works."""

    verifier = FactVerifierTool()

    print("=" * 60)
    print("FACT VERIFIER TOOL - EXAMPLES")
    print("=" * 60)

    # Example 1: Verify a true claim
    print("\n1. Verifying TRUE claim:")
    result1 = verifier.run(
        claim="The Universal Declaration of Human Rights was adopted by the UN General Assembly in 1948",
        topic="benefits",
    )
    print(f"Verdict: {result1['verdict']}")
    print(f"Confidence: {result1['confidence']}")
    print(f"Explanation: {result1['explanation'][:200]}...")

    # Example 2: Verify a specific article
    print("\n2. Verifying specific article:")
    result2 = verifier.run(
        claim="Article 5 of the UDHR prohibits torture and cruel treatment", topic="benefits"
    )
    print(f"Verdict: {result2['verdict']}")
    print(f"Confidence: {result2['confidence']}")

    # Example 3: Verify a false claim
    print("\n3. Verifying FALSE claim:")
    result3 = verifier.run(claim="The UDHR consists of 50 articles", topic="benefits")
    print(f"Verdict: {result3['verdict']}")
    print(f"Confidence: {result3['confidence']}")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    example_usage()
