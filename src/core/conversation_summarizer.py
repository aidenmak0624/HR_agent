"""
Conversation Summarizer for HR Multi-Agent Platform.

Summarizes long conversation histories to maintain context within
token limits. Uses LLM for intelligent summarization.

Iteration 5 - MEM-002
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class SummarizationConfig(BaseModel):
    """Configuration for conversation summarization."""

    max_summary_tokens: int = Field(
        default=500, description="Maximum tokens in summary"
    )
    summarize_threshold: int = Field(
        default=20, description="Summarize when message count exceeds this"
    )
    summary_model: str = Field(
        default="gpt-4o-mini", description="Model for summarization"
    )
    include_key_facts: bool = Field(
        default=True, description="Extract key facts"
    )
    include_action_items: bool = Field(
        default=True, description="Extract action items"
    )


class ConversationSummary(BaseModel):
    """Structured conversation summary."""

    summary_text: str = Field(..., description="Summary of conversation")
    key_facts: List[str] = Field(default_factory=list, description="Key facts extracted")
    action_items: List[str] = Field(default_factory=list, description="Action items extracted")
    topics_discussed: List[str] = Field(default_factory=list, description="Topics covered")
    message_count_summarized: int = Field(..., description="Number of messages in summary")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    confidence: float = Field(default=0.0, description="Confidence score 0-1")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ConversationSummarizer:
    """
    Summarizes conversation history using LLM.

    Condenses long conversations into structured summaries while
    maintaining key information and context.
    """

    def __init__(self, config: Optional[SummarizationConfig] = None) -> None:
        """
        Initialize conversation summarizer.

        Args:
            config: SummarizationConfig or None for defaults
        """
        self.config = config or SummarizationConfig()
        logger.info(
            "ConversationSummarizer initialized - model=%s threshold=%d",
            self.config.summary_model, self.config.summarize_threshold
        )

    def should_summarize(self, messages: List[Dict[str, Any]]) -> bool:
        """
        Determine if conversation should be summarized.

        Args:
            messages: List of message dicts

        Returns:
            True if message count exceeds threshold
        """
        should = len(messages) > self.config.summarize_threshold
        if should:
            logger.debug(
                "Should summarize: %d messages exceeds threshold of %d",
                len(messages), self.config.summarize_threshold
            )
        return should

    def summarize(
        self,
        messages: List[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> ConversationSummary:
        """
        Generate summary from conversation messages.

        Builds LLM prompt requesting summary, key facts, action items,
        and topics. Parses response into structured ConversationSummary.

        Args:
            messages: List of message dicts with role and content
            user_context: Optional user context for personalization

        Returns:
            ConversationSummary with extracted information

        Note:
            For testing/development, returns placeholder summary.
            In production, calls LLM API.
        """
        try:
            if not messages:
                logger.warning("No messages to summarize")
                return ConversationSummary(
                    summary_text="No messages to summarize",
                    message_count_summarized=0,
                    confidence=0.0
                )

            logger.info(
                "Summarizing %d messages for user_context=%s",
                len(messages), user_context
            )

            # Build prompt
            prompt = self._build_summarization_prompt(messages, user_context)

            # In production: call LLM API
            # response = llm_api.generate(prompt, model=self.config.summary_model)
            # For now: placeholder response
            response = self._generate_mock_response(messages)

            # Parse response
            summary = self._parse_summary_response(response, len(messages))

            logger.info(
                "Summary created: %d facts, %d action items, %d topics, confidence=%.2f",
                len(summary.key_facts),
                len(summary.action_items),
                len(summary.topics_discussed),
                summary.confidence
            )

            return summary

        except Exception as e:
            logger.exception("Error summarizing conversation: %s", e)
            return ConversationSummary(
                summary_text=f"Error summarizing conversation: {str(e)}",
                message_count_summarized=len(messages),
                confidence=0.0
            )

    def _build_summarization_prompt(
        self,
        messages: List[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Construct summarization prompt for LLM.

        Args:
            messages: List of message dicts
            user_context: Optional user context

        Returns:
            Prompt string for LLM
        """
        context_str = ""
        if user_context:
            context_str = f"User Context: {user_context}\n\n"

        # Format messages for prompt
        messages_str = "Conversation History:\n"
        for i, msg in enumerate(messages[-50:], 1):  # Last 50 messages
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")[:200]  # Truncate long messages
            messages_str += f"{i}. {role}: {content}\n"

        prompt = f"""{context_str}{messages_str}

Please analyze this conversation and provide:

1. SUMMARY: A concise 2-3 sentence summary of the conversation
2. KEY FACTS: List the important facts discussed (use bullet points)
3. ACTION ITEMS: What needs to be done next (if any)
4. TOPICS: List the main topics discussed
5. CONFIDENCE: Your confidence in the summary (0-100)

Format your response with clear sections for each part."""

        logger.debug("Built summarization prompt: %d chars", len(prompt))
        return prompt

    def _parse_summary_response(
        self,
        response: str,
        message_count: int
    ) -> ConversationSummary:
        """
        Parse LLM response into structured summary.

        Extracts sections for summary, facts, action items, topics.

        Args:
            response: LLM response text
            message_count: Number of messages summarized

        Returns:
            ConversationSummary object
        """
        try:
            # Extract summary (first paragraph before KEY FACTS)
            summary_match = re.search(
                r"(?:SUMMARY|^):\s*(.*?)(?=KEY FACTS|ACTION ITEMS|$)",
                response, re.IGNORECASE | re.DOTALL
            )
            summary_text = summary_match.group(1).strip() if summary_match else response[:200]

            # Extract key facts
            key_facts = self._extract_key_facts(response) if self.config.include_key_facts else []

            # Extract action items
            action_items = self._extract_action_items(response) if self.config.include_action_items else []

            # Extract topics
            topics = self._extract_topics(response)

            # Extract confidence score
            confidence_match = re.search(r"CONFIDENCE[:\s]*(\d+)", response, re.IGNORECASE)
            confidence = float(confidence_match.group(1)) / 100 if confidence_match else 0.8

            logger.debug(
                "Parsed response: summary=%d chars, facts=%d, actions=%d, topics=%d",
                len(summary_text), len(key_facts), len(action_items), len(topics)
            )

            return ConversationSummary(
                summary_text=summary_text,
                key_facts=key_facts,
                action_items=action_items,
                topics_discussed=topics,
                message_count_summarized=message_count,
                confidence=confidence
            )

        except Exception as e:
            logger.exception("Error parsing summary response: %s", e)
            return ConversationSummary(
                summary_text=response[:200],
                message_count_summarized=message_count,
                confidence=0.5
            )

    def _extract_key_facts(self, text: str) -> List[str]:
        """
        Extract key facts from summary text.

        Looks for "KEY FACTS:" section and extracts bullet points.

        Args:
            text: Summary text

        Returns:
            List of key facts
        """
        match = re.search(
            r"KEY FACTS[:\s]*(.*?)(?=ACTION ITEMS|TOPICS|CONFIDENCE|$)",
            text, re.IGNORECASE | re.DOTALL
        )

        if not match:
            return []

        facts_text = match.group(1)
        # Extract bullet points
        facts = re.findall(r"[-•*]\s*(.+?)(?:\n|$)", facts_text)
        facts = [f.strip() for f in facts if f.strip()]

        logger.debug("Extracted %d key facts", len(facts))
        return facts

    def _extract_action_items(self, text: str) -> List[str]:
        """
        Extract action items from summary text.

        Looks for "ACTION ITEMS:" section and extracts bullet points.

        Args:
            text: Summary text

        Returns:
            List of action items
        """
        match = re.search(
            r"ACTION ITEMS[:\s]*(.*?)(?=TOPICS|KEY FACTS|CONFIDENCE|$)",
            text, re.IGNORECASE | re.DOTALL
        )

        if not match:
            return []

        items_text = match.group(1)
        # Extract bullet points
        items = re.findall(r"[-•*]\s*(.+?)(?:\n|$)", items_text)
        items = [i.strip() for i in items if i.strip()]

        logger.debug("Extracted %d action items", len(items))
        return items

    def _extract_topics(self, text: str) -> List[str]:
        """
        Extract topics from summary text.

        Looks for "TOPICS:" section and extracts comma-separated items.

        Args:
            text: Summary text

        Returns:
            List of topics
        """
        match = re.search(
            r"TOPICS[:\s]*(.*?)(?=CONFIDENCE|ACTION ITEMS|KEY FACTS|$)",
            text, re.IGNORECASE | re.DOTALL
        )

        if not match:
            return []

        topics_text = match.group(1)
        # Try bullet points first
        topics = re.findall(r"[-•*]\s*(.+?)(?:\n|$)", topics_text)

        # If no bullets, try comma-separated
        if not topics:
            topics = [t.strip() for t in topics_text.split(",") if t.strip()]

        logger.debug("Extracted %d topics", len(topics))
        return topics

    def merge_summaries(
        self,
        summaries: List[ConversationSummary]
    ) -> ConversationSummary:
        """
        Merge multiple summaries into one.

        Combines facts, action items, and topics from multiple summaries.

        Args:
            summaries: List of ConversationSummary objects

        Returns:
            Merged ConversationSummary
        """
        if not summaries:
            return ConversationSummary(
                summary_text="No summaries to merge",
                message_count_summarized=0,
                confidence=0.0
            )

        if len(summaries) == 1:
            return summaries[0]

        try:
            # Combine summaries
            combined_text = " ".join(s.summary_text for s in summaries)

            # Merge facts (deduplicate)
            all_facts = []
            for s in summaries:
                all_facts.extend(s.key_facts)
            unique_facts = list(dict.fromkeys(all_facts))

            # Merge action items
            all_items = []
            for s in summaries:
                all_items.extend(s.action_items)
            unique_items = list(dict.fromkeys(all_items))

            # Merge topics
            all_topics = []
            for s in summaries:
                all_topics.extend(s.topics_discussed)
            unique_topics = list(dict.fromkeys(all_topics))

            # Average confidence
            avg_confidence = sum(s.confidence for s in summaries) / len(summaries)

            # Sum message counts
            total_messages = sum(s.message_count_summarized for s in summaries)

            logger.info(
                "Merged %d summaries: %d facts, %d items, %d topics",
                len(summaries), len(unique_facts), len(unique_items), len(unique_topics)
            )

            return ConversationSummary(
                summary_text=combined_text[:500],
                key_facts=unique_facts,
                action_items=unique_items,
                topics_discussed=unique_topics,
                message_count_summarized=total_messages,
                confidence=avg_confidence
            )

        except Exception as e:
            logger.exception("Error merging summaries: %s", e)
            return ConversationSummary(
                summary_text="Error merging summaries",
                message_count_summarized=0,
                confidence=0.0
            )

    def create_context_with_summary(
        self,
        summary: ConversationSummary,
        recent_messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create context list with summary as system message plus recent messages.

        Args:
            summary: ConversationSummary to include
            recent_messages: Recent messages to append

        Returns:
            List of message dicts with summary system message first
        """
        context: List[Dict[str, Any]] = []

        # Add summary as system message
        summary_content = f"""Summary of prior conversation:
{summary.summary_text}

Key Facts:
{chr(10).join(f'- {f}' for f in summary.key_facts[:5])}

Action Items:
{chr(10).join(f'- {i}' for i in summary.action_items[:5])}

Topics Discussed: {', '.join(summary.topics_discussed[:5])}
"""

        context.append({
            "role": "system",
            "content": summary_content
        })

        # Add recent messages
        context.extend(recent_messages)

        logger.debug(
            "Created context with summary: %d messages total",
            len(context)
        )

        return context

    def _generate_mock_response(self, messages: List[Dict[str, Any]]) -> str:
        """
        Generate a mock LLM response for testing.

        Args:
            messages: List of messages

        Returns:
            Mock summary response
        """
        user_messages = [m for m in messages if m.get("role") == "user"]
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]

        topics = []
        for msg in user_messages:
            if "leave" in msg.get("content", "").lower():
                topics.append("Leave Policy")
            if "benefit" in msg.get("content", "").lower():
                topics.append("Benefits")
            if "salary" in msg.get("content", "").lower():
                topics.append("Compensation")

        if not topics:
            topics = ["HR Policy", "Company Information"]

        response = f"""SUMMARY:
The conversation covered HR-related inquiries including {', '.join(topics[:2])}.
The user asked {len(user_messages)} questions and received {len(assistant_messages)} responses.

KEY FACTS:
- {len(messages)} total messages in conversation
- Topics: {', '.join(set(topics))}
- User asked about HR policies and procedures

ACTION ITEMS:
- Follow up with HR department if needed
- Review company handbook for more details

TOPICS: {', '.join(set(topics[:3]))}

CONFIDENCE: 85"""

        return response
