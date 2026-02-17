"""
CORE-005: Quality Assessor Module
Evaluates response quality, completeness, and confidence for HR multi-agent system.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class QualityLevel(str, Enum):
    """Quality assessment levels."""
    SUFFICIENT = "sufficient"      # score >= 0.7
    MARGINAL = "marginal"          # 0.4 <= score < 0.7
    INSUFFICIENT = "insufficient"  # score < 0.4


@dataclass
class QualityScore:
    """Quality assessment result."""
    relevance: float  # 0-1: keyword overlap + semantic similarity
    completeness: float  # 0-1: addresses all query parts
    confidence: float  # 0-1: agent confidence or computed
    source_quality: float  # 0-1: quality of information sources
    overall: float  # 0-1: weighted average


class HallucinationDetector:
    """Detects potential hallucinations in responses."""
    
    # Hedging phrases that indicate low confidence
    HEDGING_PHRASES = [
        'i believe', 'i think', 'i assume', 'it seems', 'it appears',
        'possibly', 'probably', 'maybe', 'might', 'could be', 'supposedly',
        'allegedly', 'reportedly', 'perhaps', 'arguably', 'conceivably',
        'it may be', 'it is possible', 'it is likely'
    ]
    
    # Phrases indicating unsupported claims
    UNSUPPORTED_INDICATORS = [
        'without evidence', 'unverified', 'uncorroborated', 'unconfirmed',
        'allegedly said', 'claimed to have', 'reportedly'
    ]
    
    # Contradiction indicators
    CONTRADICTION_PATTERNS = [
        (r'but actually', r'however'),
        (r'on the other hand', r'conversely'),
        (r'despite', r'although'),
    ]
    
    def __init__(self):
        """Initialize hallucination detector."""
        self.hedging_pattern = re.compile(
            '|'.join(self.HEDGING_PHRASES),
            re.IGNORECASE
        )
        self.unsupported_pattern = re.compile(
            '|'.join(self.UNSUPPORTED_INDICATORS),
            re.IGNORECASE
        )
    
    def find_issues(self, text: str) -> List[str]:
        """
        Find potential hallucination indicators.
        
        Args:
            text: Response text to analyze
        
        Returns:
            List of detected issues
        """
        issues = []
        
        text_lower = text.lower()
        
        # Count hedging phrases
        hedging_matches = self.hedging_pattern.findall(text_lower)
        if len(hedging_matches) > 3:
            issues.append(
                f'excessive_hedging ({len(hedging_matches)} phrases)'
            )
        
        # Check for unsupported claims
        if self.unsupported_pattern.search(text_lower):
            issues.append('unsupported_claims_detected')
        
        # Check for contradictions
        sentences = re.split(r'[.!?]+', text)
        for i in range(len(sentences) - 1):
            current = sentences[i].lower()
            next_sent = sentences[i + 1].lower()
            
            if any(
                pattern[0] in current or pattern[1] in next_sent
                for pattern in self.CONTRADICTION_PATTERNS
            ):
                issues.append('potential_contradiction_detected')
                break
        
        return issues


class QualityAssessor:
    """
    Evaluates the quality of LLM responses.
    
    Assesses response quality across multiple dimensions and provides
    recommendations for fallback actions.
    """
    
    def __init__(self):
        """Initialize quality assessor."""
        self.hallucination_detector = HallucinationDetector()
    
    def assess(
        self,
        query: str,
        response: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[Dict[str, Any]] = None
    ) -> QualityScore:
        """
        Assess the quality of a response.
        
        Args:
            query: Original user query
            response: LLM response text
            sources: List of sources used (RAG documents, web results, etc.)
            tool_results: Results from tool calls
        
        Returns:
            QualityScore with detailed breakdown
        """
        relevance = self._assess_relevance(query, response)
        completeness = self._assess_completeness(query, response)
        confidence = self._assess_confidence(
            response,
            tool_results=tool_results
        )
        source_quality = self._assess_source_quality(sources, tool_results)
        
        # Weighted average
        overall = (
            (relevance * 0.3) +
            (completeness * 0.3) +
            (confidence * 0.2) +
            (source_quality * 0.2)
        )
        
        return QualityScore(
            relevance=round(relevance, 3),
            completeness=round(completeness, 3),
            confidence=round(confidence, 3),
            source_quality=round(source_quality, 3),
            overall=round(overall, 3)
        )
    
    def _assess_relevance(self, query: str, response: str) -> float:
        """
        Assess relevance via keyword overlap and basic semantic similarity.
        
        Args:
            query: Original query
            response: Response text
        
        Returns:
            Relevance score 0-1
        """
        if not query or not response:
            return 0.0
        
        # Extract keywords from query
        query_tokens = set(self._tokenize(query))
        response_tokens = set(self._tokenize(response))
        
        if not query_tokens:
            return 0.5
        
        # Keyword overlap
        overlap = query_tokens.intersection(response_tokens)
        keyword_relevance = len(overlap) / len(query_tokens)
        
        # Length consideration (very short responses may indicate low relevance)
        response_length_score = min(len(response) / 100, 1.0)
        
        # Check for negations
        negation_penalty = 0.0
        if any(
            neg in response.lower()
            for neg in ['i cannot', 'i dont', 'unable to', 'not available']
        ):
            negation_penalty = 0.2
        
        relevance = (
            (keyword_relevance * 0.6) +
            (response_length_score * 0.4)
        ) - negation_penalty
        
        return max(0.0, min(1.0, relevance))
    
    def _assess_completeness(self, query: str, response: str) -> float:
        """
        Assess if response addresses all parts of the query.
        
        Args:
            query: Original query
            response: Response text
        
        Returns:
            Completeness score 0-1
        """
        if not query or not response:
            return 0.0
        
        # Split query by question marks and commas
        query_parts = re.split(r'[?,]', query)
        query_parts = [p.strip() for p in query_parts if p.strip()]
        
        if not query_parts:
            return 0.5
        
        # Check how many query parts are addressed
        response_lower = response.lower()
        addressed = 0
        
        for part in query_parts:
            part_tokens = set(self._tokenize(part))
            response_tokens = set(self._tokenize(response_lower))
            
            if part_tokens.intersection(response_tokens):
                addressed += 1
        
        completeness = addressed / len(query_parts) if query_parts else 0.5
        
        # Penalize very short responses
        if len(response.split()) < 10:
            completeness *= 0.7
        
        return min(1.0, completeness)
    
    def _assess_confidence(
        self,
        response: str,
        tool_results: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Assess confidence in the response.
        
        Args:
            response: Response text
            tool_results: Results from tool calls with confidence_score
        
        Returns:
            Confidence score 0-1
        """
        confidence = 0.5
        
        # Check for explicit confidence score in tool results
        if tool_results and isinstance(tool_results, dict):
            if 'confidence_score' in tool_results:
                confidence = float(tool_results['confidence_score'])
            elif 'confidence' in tool_results:
                confidence = float(tool_results['confidence'])
        
        # Detect hallucination indicators
        issues = self.hallucination_detector.find_issues(response)
        if issues:
            confidence *= 0.7
            logger.warning(f"Hallucination indicators found: {issues}")
        
        # Check response length (very short often indicates low confidence)
        word_count = len(response.split())
        if word_count < 5:
            confidence *= 0.6
        elif word_count < 20:
            confidence *= 0.85
        
        # Check for uncertain language
        uncertain_phrases = ['might be', 'could be', 'may be', 'seems like']
        uncertain_count = sum(
            1 for phrase in uncertain_phrases
            if phrase in response.lower()
        )
        
        if uncertain_count >= 2:
            confidence *= 0.8
        
        return min(1.0, max(0.0, confidence))
    
    def _assess_source_quality(
        self,
        sources: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Assess quality based on information sources.
        
        Args:
            sources: List of source documents
            tool_results: Results from tools/APIs
        
        Returns:
            Source quality score 0-1
        """
        if not sources and not tool_results:
            return 0.5
        
        score = 0.5
        
        # Evaluate sources
        if sources:
            rag_sources = [
                s for s in sources
                if s.get('source_type') == 'rag'
            ]
            
            if rag_sources:
                score = 0.9  # RAG sources are highly reliable
                
                # Reduce score if sources have low relevance
                avg_relevance = sum(
                    s.get('relevance_score', 0.5) for s in rag_sources
                ) / len(rag_sources)
                score = score * (0.5 + 0.5 * avg_relevance)
            else:
                web_sources = [
                    s for s in sources
                    if s.get('source_type') == 'web'
                ]
                if web_sources:
                    score = 0.7  # Web sources are moderately reliable
        
        # Evaluate tool results
        if tool_results and isinstance(tool_results, dict):
            success_count = tool_results.get('successful_calls', 0)
            total_count = tool_results.get('total_calls', 0)
            
            if total_count > 0:
                tool_success_rate = success_count / total_count
                score = max(score, tool_success_rate * 0.9)
        
        return min(1.0, score)
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization (lowercase, split on whitespace, remove punctuation).
        
        Args:
            text: Text to tokenize
        
        Returns:
            List of tokens
        """
        text = text.lower()
        # Remove punctuation but keep words with numbers
        text = re.sub(r'[^\w\s]', '', text)
        tokens = text.split()
        # Filter out very short tokens
        return [t for t in tokens if len(t) > 2]
    
    def get_level(self, quality_score: QualityScore) -> QualityLevel:
        """
        Classify quality score into a level.
        
        Args:
            quality_score: QualityScore to classify
        
        Returns:
            QualityLevel enum value
        """
        overall = quality_score.overall
        
        if overall >= 0.7:
            return QualityLevel.SUFFICIENT
        elif overall >= 0.4:
            return QualityLevel.MARGINAL
        else:
            return QualityLevel.INSUFFICIENT
    
    def suggest_fallback(
        self,
        quality_score: QualityScore
    ) -> Optional[str]:
        """
        Suggest a fallback action based on quality assessment.
        
        Args:
            quality_score: QualityScore to evaluate
        
        Returns:
            Suggestion string or None if quality sufficient
        """
        level = self.get_level(quality_score)
        
        if level == QualityLevel.SUFFICIENT:
            return None
        
        # Insufficient quality
        if level == QualityLevel.INSUFFICIENT:
            if quality_score.source_quality < 0.4:
                return "web_search"
            else:
                return "human_escalation"
        
        # Marginal quality - check specific dimensions
        if quality_score.relevance < 0.4:
            return "web_search"
        
        if quality_score.completeness < 0.4:
            return "human_escalation"
        
        if quality_score.source_quality < 0.5:
            return "web_search"
        
        return None
    
    def validate_response(self, response: str) -> List[str]:
        """
        Validate response for potential issues.
        
        Args:
            response: Response text to validate
        
        Returns:
            List of validation issue descriptions
        """
        issues = []
        
        if not response:
            issues.append('empty_response')
            return issues
        
        # Check for hallucination indicators
        hallucination_issues = self.hallucination_detector.find_issues(response)
        issues.extend(hallucination_issues)
        
        # Check for common error patterns
        error_patterns = [
            'error', 'exception', 'failed', 'unable', 'cannot',
            'unavailable', 'not found', 'does not exist'
        ]
        
        response_lower = response.lower()
        if any(pattern in response_lower for pattern in error_patterns):
            issues.append('error_in_response')
        
        # Check for placeholder text
        if '[' in response and ']' in response:
            placeholder_pattern = re.findall(r'\[([^\]]+)\]', response)
            if placeholder_pattern:
                issues.append(f'unresolved_placeholders: {placeholder_pattern}')
        
        # Check response length
        word_count = len(response.split())
        if word_count < 3:
            issues.append('response_too_short')
        
        # Check for gibberish or encoding issues
        non_ascii_ratio = sum(
            1 for c in response if ord(c) > 127
        ) / len(response)
        if non_ascii_ratio > 0.1:
            issues.append('high_non_ascii_content')
        
        return issues
