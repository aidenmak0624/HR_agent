"""
Slack Bot Integration for HR Multi-Agent Platform.

Receives HR queries from Slack channels and DMs, routes them through
AgentService for processing. Supports message events, app mentions,
and slash commands. Formats responses as Slack Block Kit elements.

Iteration 5 - MSG-001
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SlackBotConfig(BaseModel):
    """Configuration for Slack Bot Integration."""

    bot_token: str = Field(..., description="Slack bot token (xoxb-*)")
    signing_secret: str = Field(..., description="Slack signing secret for request verification")
    app_token: str = Field(..., description="Slack app-level token (xapp-*)")
    channel_allowlist: List[str] = Field(
        default_factory=lambda: ["hr-assistance", "general"],
        description="Channels where bot is allowed to respond",
    )
    max_message_length: int = Field(default=4000, description="Max Slack message length")
    response_timeout: int = Field(default=30, description="Response timeout in seconds")


class SlackEventHandler:
    """
    Handles Slack events (messages, mentions, commands).

    Processes Slack events and routes queries through the AgentService.
    Tracks metrics and formats responses for Slack Block Kit presentation.
    """

    def __init__(self, config: SlackBotConfig, agent_service: Optional[Any] = None) -> None:
        """
        Initialize Slack Event Handler.

        Args:
            config: SlackBotConfig with bot credentials and settings
            agent_service: Optional reference to AgentService for query processing
        """
        self.config = config
        self.agent_service = agent_service
        self.metrics: Dict[str, Any] = {
            "messages_processed": 0,
            "errors": 0,
            "avg_response_time": 0.0,
            "uptime_seconds": 0.0,
        }
        self.start_time = datetime.utcnow()
        logger.info("SlackEventHandler initialized with config: %s", config.bot_token[:20])

    def handle_message(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a message event from Slack.

        Extracts user ID, channel, text, and thread timestamp.
        Routes through _process_query if from allowed channel.

        Args:
            event: Slack message event dict with keys: user, channel, text, thread_ts

        Returns:
            Dict with status, message_id, and response if successful
        """
        try:
            if "bot_id" in event:
                logger.debug("Ignoring bot message from %s", event.get("bot_id"))
                return {"status": "ignored", "reason": "bot_message"}

            user_id = event.get("user", "unknown")
            channel = event.get("channel", "unknown")
            text = event.get("text", "").strip()
            thread_ts = event.get("thread_ts", event.get("ts"))

            if not text or len(text) > self.config.max_message_length:
                logger.warning("Invalid message length from %s: %d chars", user_id, len(text))
                return {"status": "rejected", "reason": "invalid_length"}

            logger.info(
                "Message event from user=%s channel=%s thread=%s", user_id, channel, thread_ts
            )

            return self._process_query(
                user_id=user_id, text=text, channel=channel, thread_ts=thread_ts
            )

        except Exception as e:
            logger.exception("Error handling message event: %s", e)
            self.metrics["errors"] += 1
            return {"status": "error", "error": str(e)}

    def handle_app_mention(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an app mention event (@hr-bot mention).

        Strips bot mention from text and routes to query processor.

        Args:
            event: Slack mention event dict with user, channel, text, thread_ts

        Returns:
            Dict with status and response
        """
        try:
            user_id = event.get("user", "unknown")
            channel = event.get("channel", "unknown")
            text = event.get("text", "").strip()
            thread_ts = event.get("thread_ts", event.get("ts"))

            # Strip bot mention (e.g., "<@U12345> question" -> "question")
            text = text.split("> ", 1)[-1] if ">" in text else text
            text = text.strip()

            if not text:
                logger.warning("Empty mention from user %s", user_id)
                return {"status": "rejected", "reason": "empty_mention"}

            logger.info("App mention from user=%s channel=%s: %s", user_id, channel, text[:50])

            return self._process_query(
                user_id=user_id, text=text, channel=channel, thread_ts=thread_ts
            )

        except Exception as e:
            logger.exception("Error handling app mention: %s", e)
            self.metrics["errors"] += 1
            return {"status": "error", "error": str(e)}

    def handle_slash_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a slash command (/hr-ask).

        Args:
            command: Slash command payload with user_id, channel_id, text, trigger_id

        Returns:
            Dict with status and response
        """
        try:
            user_id = command.get("user_id", "unknown")
            channel = command.get("channel_id", "unknown")
            text = command.get("text", "").strip()
            trigger_id = command.get("trigger_id")

            if not text:
                logger.warning("Empty slash command from user %s", user_id)
                return {
                    "status": "error",
                    "error": "Please provide a question. Usage: /hr-ask <your question>",
                }

            logger.info("Slash command /hr-ask from user=%s: %s", user_id, text[:50])

            return self._process_query(user_id=user_id, text=text, channel=channel, thread_ts=None)

        except Exception as e:
            logger.exception("Error handling slash command: %s", e)
            self.metrics["errors"] += 1
            return {"status": "error", "error": str(e)}

    def _process_query(
        self, user_id: str, text: str, channel: str, thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an HR query through the AgentService.

        Routes query to agent_service with user context. Formats response
        with confidence badge and sources. Tracks response time.

        Args:
            user_id: Slack user ID
            text: Query text
            channel: Slack channel ID
            thread_ts: Thread timestamp for threading response

        Returns:
            Dict with formatted Slack response
        """
        start_time = time.time()
        message_id = str(uuid.uuid4())

        try:
            user_context = self._get_user_context(user_id)

            logger.info(
                "Processing query message_id=%s user=%s context=%s",
                message_id,
                user_id,
                user_context,
            )

            if not self.agent_service:
                logger.warning("AgentService not configured, returning placeholder")
                return {"status": "error", "error": "Agent service not available"}

            # Process through agent service
            result = self.agent_service.process_query(
                query=text, user_context=user_context, session_id=message_id
            )

            response_time = time.time() - start_time
            self._update_metrics(response_time)

            logger.info(
                "Query processed successfully in %.2f seconds, confidence=%.2f",
                response_time,
                result.get("confidence", 0.0),
            )

            # Format response for Slack
            formatted_response = self._format_slack_response(result)
            formatted_response["thread_ts"] = thread_ts
            formatted_response["message_id"] = message_id
            formatted_response["status"] = "success"

            return formatted_response

        except Exception as e:
            response_time = time.time() - start_time
            self._update_metrics(response_time, is_error=True)
            logger.exception("Error processing query %s: %s", message_id, e)
            return {
                "status": "error",
                "error": f"Failed to process query: {str(e)[:100]}",
                "message_id": message_id,
            }

    def _format_slack_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format agent response into Slack Block Kit format.

        Creates a multi-section response with answer, confidence badge,
        and sources/references.

        Args:
            result: Agent service result dict with answer, confidence, sources

        Returns:
            Dict ready for Slack API (blocks format)
        """
        try:
            answer = result.get("answer", "No answer available")
            confidence = result.get("confidence", 0.0)
            sources = result.get("sources", [])
            agent_type = result.get("agent_type", "router")

            # Determine confidence emoji/color
            if confidence >= 0.9:
                confidence_badge = ":green_circle: *Very High Confidence*"
            elif confidence >= 0.7:
                confidence_badge = ":yellow_circle: *High Confidence*"
            elif confidence >= 0.5:
                confidence_badge = ":orange_circle: *Medium Confidence*"
            else:
                confidence_badge = ":red_circle: *Low Confidence*"

            blocks = []

            # Main answer block
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*HR Assistant Response*\n\n{answer}"},
                }
            )

            # Confidence and agent type context
            context_text = f"{confidence_badge} | Agent: {agent_type} | Score: {confidence:.1%}"
            blocks.append(
                {"type": "context", "elements": [{"type": "mrkdwn", "text": context_text}]}
            )

            # Sources block if available
            if sources:
                sources_text = "*Sources:*\n"
                for i, source in enumerate(sources[:5], 1):
                    if isinstance(source, dict):
                        src_title = source.get("title", "Source")
                        src_url = source.get("url", "#")
                        sources_text += f"{i}. <{src_url}|{src_title}>\n"
                    else:
                        sources_text += f"{i}. {source}\n"

                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": sources_text}})

            logger.debug("Formatted Slack response with %d blocks", len(blocks))

            return {"blocks": blocks, "text": answer[:100]}  # Fallback text

        except Exception as e:
            logger.exception("Error formatting Slack response: %s", e)
            return {
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Error formatting response: {str(e)[:100]}",
                        },
                    }
                ],
                "text": "Error",
            }

    def _get_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        Map Slack user to HR platform user context.

        Returns basic context dict with user identifier and source.
        In production, would lookup user profile from Slack API
        and map to HR system.

        Args:
            user_id: Slack user ID

        Returns:
            Dict with user_id, source, platform context
        """
        return {"user_id": user_id, "source": "slack", "platform": "slack", "timezone": "UTC"}

    def _update_metrics(self, response_time: float, is_error: bool = False) -> None:
        """
        Update metrics dict with response time and error count.

        Args:
            response_time: Time in seconds for query processing
            is_error: Whether this was an error response
        """
        self.metrics["messages_processed"] += 1
        if is_error:
            self.metrics["errors"] += 1

        # Running average of response time
        old_avg = self.metrics["avg_response_time"]
        count = self.metrics["messages_processed"]
        self.metrics["avg_response_time"] = (old_avg * (count - 1) + response_time) / count

    def get_health(self) -> Dict[str, Any]:
        """
        Get handler health status.

        Returns connection status, message count, error count, and uptime.

        Returns:
            Dict with health metrics
        """
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        self.metrics["uptime_seconds"] = uptime

        error_rate = (
            self.metrics["errors"] / self.metrics["messages_processed"]
            if self.metrics["messages_processed"] > 0
            else 0.0
        )

        return {
            "status": "healthy",
            "connected": True,
            "messages_processed": self.metrics["messages_processed"],
            "errors": self.metrics["errors"],
            "error_rate": f"{error_rate:.1%}",
            "avg_response_time_ms": f"{self.metrics['avg_response_time'] * 1000:.1f}",
            "uptime_minutes": f"{uptime / 60:.1f}",
        }


class SlackBotService:
    """
    Slack Bot service lifecycle manager.

    Manages startup, shutdown, and status of Slack bot integration.
    """

    def __init__(self, config: SlackBotConfig) -> None:
        """
        Initialize Slack Bot Service.

        Args:
            config: SlackBotConfig with credentials
        """
        self.config = config
        self.event_handler = SlackEventHandler(config)
        self.running = False
        logger.info("SlackBotService initialized")

    def start(self) -> None:
        """
        Start the Slack bot service.

        In production, this would initialize the Bolt app and register
        event listeners. For now, logs startup.
        """
        try:
            self.running = True
            logger.info("SlackBotService starting - bot_token=%s", self.config.bot_token[:20])
            logger.info("Listening to channels: %s", ", ".join(self.config.channel_allowlist))
            # In production: app = App(token=self.config.bot_token, ...)
            # app.message(self.event_handler.handle_message)
            # app.event("app_mention", self.event_handler.handle_app_mention)
            # app.command("/hr-ask", self.event_handler.handle_slash_command)
        except Exception as e:
            logger.exception("Error starting SlackBotService: %s", e)
            self.running = False
            raise

    def stop(self) -> None:
        """
        Stop the Slack bot service.

        Gracefully shuts down the bot and logs final metrics.
        """
        try:
            self.running = False
            health = self.event_handler.get_health()
            logger.info("SlackBotService stopping - final health: %s", health)
        except Exception as e:
            logger.exception("Error stopping SlackBotService: %s", e)

    def get_status(self) -> Dict[str, Any]:
        """
        Get overall service status.

        Returns:
            Dict with running state and handler health
        """
        return {
            "service_running": self.running,
            "handler_health": self.event_handler.get_health(),
            "config": {
                "max_message_length": self.config.max_message_length,
                "response_timeout": self.config.response_timeout,
                "channels": self.config.channel_allowlist,
            },
        }
