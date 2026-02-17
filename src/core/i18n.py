"""
Internationalization (i18n) Module for HR Multi-Agent Platform.
Language detection and LLM-based translation for multi-language support.
Iteration 6 - I18N-001, I18N-002
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class SupportedLanguage(str, Enum):
    """Supported language codes."""

    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"
    ZH = "zh"
    JA = "ja"
    PT = "pt"
    KO = "ko"
    AR = "ar"
    HI = "hi"


class LanguageDetectionResult(BaseModel):
    """Language detection result model."""

    detected_language: str = Field(description="Detected language code")
    confidence: float = Field(description="Detection confidence (0-1)")
    is_supported: bool = Field(description="Whether language is supported")

    model_config = ConfigDict(frozen=False)


class TranslationResult(BaseModel):
    """Translation result model."""

    original_text: str = Field(description="Original text")
    translated_text: str = Field(description="Translated text")
    source_language: str = Field(description="Source language code")
    target_language: str = Field(description="Target language code")
    confidence: float = Field(default=0.0, description="Translation confidence")
    method: str = Field(default="llm", description="Translation method used")

    model_config = ConfigDict(frozen=False)


class I18nConfig(BaseModel):
    """Internationalization configuration model."""

    default_language: str = Field(default="en", description="Default language code")
    supported_languages: List[str] = Field(
        default=["en", "es", "fr", "de", "zh"],
        description="List of supported language codes",
    )
    auto_detect: bool = Field(default=True, description="Auto-detect input language")
    translation_model: str = Field(
        default="gpt-4o-mini", description="Model for translation"
    )
    cache_translations: bool = Field(
        default=True, description="Cache translation results"
    )
    max_cache_size: int = Field(
        default=1000, description="Maximum cache size"
    )

    model_config = ConfigDict(frozen=False)


class LanguageDetector:
    """Language detection using heuristics and pattern matching."""

    # Common words/patterns per language
    LANGUAGE_PATTERNS = {
        "en": [
            r"\b(the|and|or|is|are|was|were|be|being|been|have|has|do|does|did|will|would|should|could|may|might)\b"
        ],
        "es": [
            r"\b(el|la|los|las|y|o|es|son|de|que|en|un|una|unos|unas|se|le|me|te|nos|os|les)\b"
        ],
        "fr": [
            r"\b(le|la|les|et|ou|est|sont|de|que|en|un|une|des|se|me|te|nous|vous|leur|ils|elles)\b"
        ],
        "de": [
            r"\b(der|die|das|den|des|dem|und|oder|ist|sind|von|in|zu|ein|eine|einen|einem|eines|einen|einer)\b"
        ],
        "pt": [
            r"\b(o|a|os|as|e|ou|é|são|de|que|em|um|uma|uns|umas|se|me|te|nos|vos|lhe|lhes)\b"
        ],
        "ja": [
            r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]"
        ],
        "zh": [
            r"[\u4E00-\u9FFF]"
        ],
        "ko": [
            r"[\uAC00-\uD7AF]"
        ],
        "ar": [
            r"[\u0600-\u06FF]"
        ],
        "hi": [
            r"[\u0900-\u097F]"
        ],
    }

    # Language names mapping
    LANGUAGE_NAMES = {
        "en": {"name": "English", "native": "English"},
        "es": {"name": "Spanish", "native": "Español"},
        "fr": {"name": "French", "native": "Français"},
        "de": {"name": "German", "native": "Deutsch"},
        "zh": {"name": "Chinese", "native": "中文"},
        "ja": {"name": "Japanese", "native": "日本語"},
        "pt": {"name": "Portuguese", "native": "Português"},
        "ko": {"name": "Korean", "native": "한국어"},
        "ar": {"name": "Arabic", "native": "العربية"},
        "hi": {"name": "Hindi", "native": "हिन्दी"},
    }

    def __init__(self) -> None:
        """Initialize language detector."""
        # Compile regex patterns
        self.compiled_patterns = {}
        for lang, patterns in self.LANGUAGE_PATTERNS.items():
            self.compiled_patterns[lang] = [re.compile(p, re.IGNORECASE) for p in patterns]

        logger.info(
            "Language detector initialized",
            extra={"supported_languages": list(self.LANGUAGE_PATTERNS.keys())},
        )

    def detect(self, text: str) -> LanguageDetectionResult:
        """
        Detect language of text.

        Args:
            text: Text to detect language for

        Returns:
            LanguageDetectionResult with detected language and confidence
        """
        if not text or len(text.strip()) == 0:
            return LanguageDetectionResult(
                detected_language="en",
                confidence=0.0,
                is_supported=True,
            )

        # Try unicode detection first
        unicode_lang = self._detect_by_unicode(text)
        if unicode_lang:
            return LanguageDetectionResult(
                detected_language=unicode_lang,
                confidence=0.95,
                is_supported=unicode_lang in [lang.value for lang in SupportedLanguage],
            )

        # Try pattern matching
        pattern_result = self._detect_by_patterns(text)
        if pattern_result:
            lang, confidence = pattern_result
            return LanguageDetectionResult(
                detected_language=lang,
                confidence=confidence,
                is_supported=lang in [lang_val.value for lang_val in SupportedLanguage],
            )

        # Default to English with low confidence
        return LanguageDetectionResult(
            detected_language="en",
            confidence=0.0,
            is_supported=True,
        )

    def _detect_by_unicode(self, text: str) -> Optional[str]:
        """
        Detect language by unicode character ranges.

        Args:
            text: Text to analyze

        Returns:
            Language code if detected, None otherwise
        """
        # Check for CJK characters
        cjk_pattern = re.compile(r"[\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF]")
        if cjk_pattern.search(text):
            # Count different character types
            han = len(re.findall(r"[\u4E00-\u9FFF]", text))
            hiragana = len(re.findall(r"[\u3040-\u309F]", text))
            katakana = len(re.findall(r"[\u30A0-\u30FF]", text))

            if han > hiragana + katakana:
                return "zh"
            else:
                return "ja"

        # Check for Korean
        korean_pattern = re.compile(r"[\uAC00-\uD7AF]")
        if korean_pattern.search(text):
            return "ko"

        # Check for Arabic
        arabic_pattern = re.compile(r"[\u0600-\u06FF]")
        if arabic_pattern.search(text):
            return "ar"

        # Check for Devanagari (Hindi)
        hindi_pattern = re.compile(r"[\u0900-\u097F]")
        if hindi_pattern.search(text):
            return "hi"

        return None

    def _detect_by_patterns(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Detect language by word/pattern matching.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (language_code, confidence) if detected, None otherwise
        """
        scores = {}

        for lang, patterns in self.compiled_patterns.items():
            matches = 0
            for pattern in patterns:
                matches += len(pattern.findall(text))

            if matches > 0:
                scores[lang] = matches

        if not scores:
            return None

        # Find language with highest score
        best_lang = max(scores, key=scores.get)
        total_matches = sum(scores.values())
        confidence = scores[best_lang] / total_matches if total_matches > 0 else 0

        return (best_lang, min(confidence, 0.9))


class TranslationService:
    """Translation service with LLM and caching."""

    def __init__(self, config: Optional[I18nConfig] = None) -> None:
        """
        Initialize translation service.

        Args:
            config: I18n configuration (uses defaults if None)
        """
        self.config = config or I18nConfig()
        self.cache: Dict[str, TranslationResult] = {}
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.translations_count: int = 0

        logger.info(
            "Translation service initialized",
            extra={
                "supported_languages": self.config.supported_languages,
                "cache_enabled": self.config.cache_translations,
                "max_cache_size": self.config.max_cache_size,
            },
        )

    def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> TranslationResult:
        """
        Translate text to target language.

        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language code (auto-detected if None)

        Returns:
            TranslationResult with translated text
        """
        if not text or len(text.strip()) == 0:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language or "en",
                target_language=target_language,
                confidence=1.0,
                method="passthrough",
            )

        # Determine source language
        if source_language is None:
            detector = LanguageDetector()
            detection = detector.detect(text)
            source_language = detection.detected_language

        # If source and target are same, return as-is
        if source_language == target_language:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                target_language=target_language,
                confidence=1.0,
                method="passthrough",
            )

        # Check cache
        cache_key = self._cache_key(text, source_language, target_language)
        cached = self._get_cached(cache_key)
        if cached:
            self.cache_hits += 1
            return cached

        # Perform translation (mock implementation for non-production)
        self.cache_misses += 1
        self.translations_count += 1

        # Mock translation - in production this would call an LLM API
        translated_text = self._mock_translate(
            text, source_language, target_language
        )

        result = TranslationResult(
            original_text=text,
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language,
            confidence=0.8,
            method="llm",
        )

        # Cache result
        self._set_cached(cache_key, result)

        logger.debug(
            "Text translated",
            extra={
                "source": source_language,
                "target": target_language,
                "length": len(text),
            },
        )

        return result

    def _mock_translate(
        self, text: str, source: str, target: str
    ) -> str:
        """
        Mock translation (for non-production use).

        Args:
            text: Text to translate
            source: Source language
            target: Target language

        Returns:
            Mock translated text
        """
        # Simple mock: append language indicator
        return f"[{target.upper()}] {text}"

    def _build_translation_prompt(
        self, text: str, source: str, target: str
    ) -> str:
        """
        Build LLM prompt for translation.

        Args:
            text: Text to translate
            source: Source language code
            target: Target language code

        Returns:
            Translation prompt
        """
        source_name = LanguageDetector.LANGUAGE_NAMES.get(source, {}).get(
            "name", source
        )
        target_name = LanguageDetector.LANGUAGE_NAMES.get(target, {}).get(
            "name", target
        )

        return f"""Translate the following text from {source_name} to {target_name}.
Only provide the translation, without any explanations.

Text: {text}

Translation:"""

    def _cache_key(self, text: str, source: str, target: str) -> str:
        """
        Generate cache key for translation.

        Args:
            text: Input text
            source: Source language
            target: Target language

        Returns:
            Cache key string
        """
        return f"{source}_{target}_{hash(text)}"

    def _get_cached(self, key: str) -> Optional[TranslationResult]:
        """
        Get cached translation.

        Args:
            key: Cache key

        Returns:
            TranslationResult if cached, None otherwise
        """
        return self.cache.get(key)

    def _set_cached(
        self, key: str, result: TranslationResult
    ) -> None:
        """
        Cache translation result with LRU eviction.

        Args:
            key: Cache key
            result: TranslationResult to cache
        """
        if not self.config.cache_translations:
            return

        # Simple LRU: remove oldest if cache is full
        if len(self.cache) >= self.config.max_cache_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]

        self.cache[key] = result

    def get_stats(self) -> Dict[str, any]:
        """
        Get translation service statistics.

        Returns:
            Dictionary with statistics
        """
        total_cache_requests = self.cache_hits + self.cache_misses
        hit_rate = (
            self.cache_hits / total_cache_requests if total_cache_requests > 0 else 0
        )

        return {
            "translations_count": self.translations_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": hit_rate,
            "cache_size": len(self.cache),
            "max_cache_size": self.config.max_cache_size,
        }


class I18nMiddleware:
    """
    Internationalization middleware.
    Handles language detection and translation for requests/responses.
    """

    def __init__(self, config: Optional[I18nConfig] = None) -> None:
        """
        Initialize i18n middleware.

        Args:
            config: I18n configuration (uses defaults if None)
        """
        self.config = config or I18nConfig()
        self.detector = LanguageDetector()
        self.translator = TranslationService(config)

        logger.info(
            "I18n middleware initialized",
            extra={
                "default_language": self.config.default_language,
                "supported_languages": self.config.supported_languages,
                "auto_detect": self.config.auto_detect,
            },
        )

    def process_input(
        self, text: str, preferred_language: Optional[str] = None
    ) -> Dict:
        """
        Process input and detect/handle language.

        Args:
            text: Input text
            preferred_language: Preferred language code

        Returns:
            Dictionary with text, detected language, and translation info
        """
        if self.config.auto_detect:
            detection = self.detector.detect(text)
            detected_language = detection.detected_language
            confidence = detection.confidence
        else:
            detected_language = preferred_language or self.config.default_language
            confidence = 1.0

        needs_translation = (
            preferred_language is not None
            and preferred_language != detected_language
        )

        return {
            "text": text,
            "detected_language": detected_language,
            "confidence": confidence,
            "needs_translation": needs_translation,
            "preferred_language": preferred_language,
        }

    def process_output(
        self, text: str, target_language: str
    ) -> TranslationResult:
        """
        Process output and translate if needed.

        Args:
            text: Output text
            target_language: Target language code

        Returns:
            TranslationResult with translated text
        """
        # Detect source language
        detection = self.detector.detect(text)
        source_language = detection.detected_language

        # Translate if needed
        if source_language != target_language:
            return self.translator.translate(
                text, target_language, source_language
            )

        return TranslationResult(
            original_text=text,
            translated_text=text,
            source_language=source_language,
            target_language=target_language,
            confidence=1.0,
            method="passthrough",
        )

    def get_supported_languages(self) -> List[Dict]:
        """
        Get list of supported languages.

        Returns:
            List of language dictionaries with code, name, native_name
        """
        languages = []

        for lang_code in self.config.supported_languages:
            if lang_code in LanguageDetector.LANGUAGE_NAMES:
                lang_info = LanguageDetector.LANGUAGE_NAMES[lang_code]
                languages.append({
                    "code": lang_code,
                    "name": lang_info["name"],
                    "native_name": lang_info["native"],
                })

        return languages

    def is_supported(self, language_code: str) -> bool:
        """
        Check if language is supported.

        Args:
            language_code: Language code to check

        Returns:
            True if supported, False otherwise
        """
        return language_code in self.config.supported_languages
