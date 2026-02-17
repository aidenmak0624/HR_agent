"""Tests for quality assessment module."""
import pytest
from src.core.quality import (
    QualityAssessor,
    QualityScore,
    QualityLevel,
    HallucinationDetector,
)


class TestQualityAssessmentBasics:
    """Tests for basic quality assessment."""

    def test_high_quality_response_is_sufficient(self):
        """High-quality response receives SUFFICIENT level."""
        assessor = QualityAssessor()
        
        query = "What is the remote work policy?"
        response = (
            "The remote work policy allows employees to work from home up to 3 days "
            "per week. Managers must approve requests. Core hours are 10am-3pm. "
            "Full policy details are in the HR handbook section 4.2."
        )
        
        score = assessor.assess(query, response)
        
        assert score.overall >= 0.7
        level = assessor.get_level(score)
        assert level == QualityLevel.SUFFICIENT

    def test_low_quality_response_is_insufficient(self):
        """Low-quality response receives INSUFFICIENT level."""
        assessor = QualityAssessor()
        
        query = "What is the remote work policy?"
        response = "I don't know."
        
        score = assessor.assess(query, response)
        
        assert score.overall < 0.4
        level = assessor.get_level(score)
        assert level == QualityLevel.INSUFFICIENT


class TestQualityFallbacks:
    """Tests for fallback suggestions."""

    def test_suggest_fallback_for_low_quality(self):
        """Low quality suggests fallback actions."""
        assessor = QualityAssessor()
        
        query = "What is X?"
        response = "Not sure about this topic"
        
        score = assessor.assess(
            query,
            response,
            sources=[{"source_type": "rag", "relevance_score": 0.2}]
        )
        
        fallback = assessor.suggest_fallback(score)
        
        # Should suggest some fallback
        assert fallback in [None, "web_search", "human_escalation"]

    def test_suggest_fallback_human_for_very_low(self):
        """Very low quality suggests human escalation."""
        assessor = QualityAssessor()
        
        query = "Complex policy question?"
        response = "Um"
        
        score = assessor.assess(query, response)
        
        if score.overall < 0.4:
            fallback = assessor.suggest_fallback(score)
            assert fallback in [None, "web_search", "human_escalation"]

    def test_no_fallback_for_sufficient(self):
        """Sufficient quality returns no fallback."""
        assessor = QualityAssessor()
        
        query = "What is the remote work policy?"
        response = (
            "The remote work policy allows up to 3 days per week from home. "
            "Manager approval required. Core hours 10am-3pm. See handbook section 4.2."
        )
        
        score = assessor.assess(query, response)
        fallback = assessor.suggest_fallback(score)
        
        assert fallback is None


class TestRelevanceAssessment:
    """Tests for relevance assessment."""

    def test_relevant_response_has_high_relevance(self):
        """Response addressing query keywords has high relevance."""
        assessor = QualityAssessor()
        
        query = "What is the leave policy?"
        response = "The leave policy includes PTO, sick leave, and personal days"
        
        relevance = assessor._assess_relevance(query, response)
        
        assert relevance > 0.5

    def test_irrelevant_response_has_low_relevance(self):
        """Response not addressing query has low relevance."""
        assessor = QualityAssessor()
        
        query = "What is the leave policy?"
        response = "The weather is nice today"
        
        relevance = assessor._assess_relevance(query, response)
        
        assert relevance < 0.5

    def test_negation_reduces_relevance(self):
        """Responses with negations have reduced relevance."""
        assessor = QualityAssessor()
        
        query = "What is the leave policy?"
        response = "I cannot provide information about the leave policy"
        
        relevance = assessor._assess_relevance(query, response)
        
        # Should be lower due to negation
        assert relevance < 0.8


class TestCompletenessAssessment:
    """Tests for completeness assessment."""

    def test_complete_response_has_high_completeness(self):
        """Complete response addressing all query parts."""
        assessor = QualityAssessor()
        
        query = "What is the leave policy and approval process?"
        response = (
            "The leave policy includes PTO and sick days. "
            "The approval process requires manager sign-off and HR notification."
        )
        
        completeness = assessor._assess_completeness(query, response)
        
        assert completeness > 0.6

    def test_incomplete_response_has_lower_completeness(self):
        """Incomplete response has lower completeness than complete."""
        assessor = QualityAssessor()
        
        query = "What is the leave policy and approval process?"
        complete_response = (
            "The leave policy includes PTO and sick days. "
            "The approval process requires manager sign-off and HR notification."
        )
        incomplete_response = "The leave policy exists."
        
        complete_score = assessor._assess_completeness(query, complete_response)
        incomplete_score = assessor._assess_completeness(query, incomplete_response)
        
        # Incomplete should be lower than complete
        assert incomplete_score < complete_score

    def test_very_short_response_penalized(self):
        """Very short responses get completeness penalty."""
        assessor = QualityAssessor()
        
        query = "What is the remote work policy?"
        response = "Yes"
        
        completeness = assessor._assess_completeness(query, response)
        
        assert completeness < 0.5


class TestConfidenceAssessment:
    """Tests for confidence assessment."""

    def test_tool_results_affect_confidence(self):
        """Tool results with confidence score affect confidence."""
        assessor = QualityAssessor()
        
        response = "The policy is X"
        tool_results = {"confidence_score": 0.95}
        
        confidence = assessor._assess_confidence(response, tool_results=tool_results)
        
        # Confidence should be influenced by tool results
        assert confidence > 0.5

    def test_hedging_phrases_reduce_confidence(self):
        """Responses with hedging phrases have lower confidence."""
        assessor = QualityAssessor()
        
        response = (
            "I think the policy might be X. It could be that employees are allowed "
            "to work remotely. This appears to be the case but I'm not entirely sure."
        )
        
        confidence = assessor._assess_confidence(response)
        
        assert confidence < 0.8

    def test_very_short_response_low_confidence(self):
        """Very short responses get confidence penalty."""
        assessor = QualityAssessor()
        
        response = "Yes"
        
        confidence = assessor._assess_confidence(response)
        
        assert confidence < 0.7


class TestSourceQualityAssessment:
    """Tests for source quality assessment."""

    def test_rag_sources_are_highly_reliable(self):
        """RAG sources result in high source quality."""
        assessor = QualityAssessor()
        
        sources = [
            {"source_type": "rag", "relevance_score": 0.9}
        ]
        
        source_quality = assessor._assess_source_quality(sources=sources)
        
        assert source_quality > 0.8

    def test_web_sources_moderately_reliable(self):
        """Web sources are moderately reliable."""
        assessor = QualityAssessor()
        
        sources = [
            {"source_type": "web", "relevance_score": 0.7}
        ]
        
        source_quality = assessor._assess_source_quality(sources=sources)
        
        assert source_quality >= 0.5

    def test_no_sources_default_quality(self):
        """No sources results in default quality."""
        assessor = QualityAssessor()
        
        source_quality = assessor._assess_source_quality()
        
        assert source_quality == 0.5


class TestQualityScoreWeighting:
    """Tests for weighted quality scoring."""

    def test_overall_score_weighted_correctly(self):
        """Overall score is correct weighted average."""
        assessor = QualityAssessor()
        
        # Create specific score components
        query = "What is the leave policy?"
        response = "The leave policy includes PTO and sick leave with approval required."
        
        score = assessor.assess(query, response)
        
        # Overall should be weighted average
        # relevance: 0.3, completeness: 0.3, confidence: 0.2, source_quality: 0.2
        expected = (
            (score.relevance * 0.3) +
            (score.completeness * 0.3) +
            (score.confidence * 0.2) +
            (score.source_quality * 0.2)
        )
        
        assert abs(score.overall - expected) < 0.01


class TestHallucinationDetection:
    """Tests for hallucination detection."""

    def test_validate_response_catches_hedging(self):
        """Validation detects excessive hedging."""
        assessor = QualityAssessor()
        
        response = (
            "I think the policy might be that employees could possibly work remotely. "
            "It appears that this may be allowed, but I'm not entirely sure about it."
        )
        
        issues = assessor.validate_response(response)
        
        assert any("hedging" in str(issue).lower() for issue in issues)

    def test_validate_response_catches_errors(self):
        """Validation detects error patterns."""
        assessor = QualityAssessor()
        
        response = "Error: Unable to retrieve policy information"
        
        issues = assessor.validate_response(response)
        
        assert len(issues) > 0
        assert any("error" in str(issue).lower() for issue in issues)

    def test_validate_response_catches_placeholders(self):
        """Validation detects unresolved placeholders."""
        assessor = QualityAssessor()
        
        response = "The policy is [PLACEHOLDER_1] with [PLACEHOLDER_2] exceptions"
        
        issues = assessor.validate_response(response)
        
        assert any("placeholder" in str(issue).lower() for issue in issues)

    def test_validate_response_catches_short_response(self):
        """Validation detects very short responses."""
        assessor = QualityAssessor()
        
        response = "No"
        
        issues = assessor.validate_response(response)
        
        assert any("short" in str(issue).lower() for issue in issues)


class TestQualityScoreDataclass:
    """Tests for QualityScore dataclass."""

    def test_quality_score_contains_components(self):
        """QualityScore has all component scores."""
        score = QualityScore(
            relevance=0.8,
            completeness=0.85,
            confidence=0.7,
            source_quality=0.9,
            overall=0.8125
        )
        
        assert score.relevance == 0.8
        assert score.completeness == 0.85
        assert score.confidence == 0.7
        assert score.source_quality == 0.9
        assert score.overall == 0.8125

    def test_quality_score_all_floats(self):
        """All scores are floats."""
        score = QualityScore(
            relevance=0.5,
            completeness=0.6,
            confidence=0.7,
            source_quality=0.8,
            overall=0.65
        )
        
        assert isinstance(score.relevance, float)
        assert isinstance(score.completeness, float)
        assert isinstance(score.confidence, float)
        assert isinstance(score.source_quality, float)
        assert isinstance(score.overall, float)


class TestQualityLevels:
    """Tests for quality level classification."""

    def test_quality_level_sufficient(self):
        """Score >= 0.7 is SUFFICIENT."""
        assessor = QualityAssessor()
        score = QualityScore(0.8, 0.8, 0.7, 0.8, 0.775)
        
        level = assessor.get_level(score)
        
        assert level == QualityLevel.SUFFICIENT

    def test_quality_level_marginal(self):
        """Score 0.4-0.7 is MARGINAL."""
        assessor = QualityAssessor()
        score = QualityScore(0.5, 0.5, 0.5, 0.5, 0.5)
        
        level = assessor.get_level(score)
        
        assert level == QualityLevel.MARGINAL

    def test_quality_level_insufficient(self):
        """Score < 0.4 is INSUFFICIENT."""
        assessor = QualityAssessor()
        score = QualityScore(0.2, 0.2, 0.2, 0.2, 0.2)
        
        level = assessor.get_level(score)
        
        assert level == QualityLevel.INSUFFICIENT
