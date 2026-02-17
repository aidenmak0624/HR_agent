"""
Microsoft Teams Bot Integration for HR Multi-Agent Platform.

Receives HR queries from Teams conversations, routes them through
AgentService for processing. Supports message activities, conversation
updates, and adaptive card actions. Formats responses as Adaptive Cards.

Iteration 5 - MSG-002
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TeamsBotConfig(BaseModel):
    """Configuration for Microsoft Teams Bot Integration."""

    app_id: str = Field(..., description="Microsoft App ID")
    app_password: str = Field(..., description="Microsoft App Password")
    tenant_id: str = Field(..., description="Azure Tenant ID")
    bot_name: str = Field(default="HR Assistant", description="Bot display name")
    max_message_length: int = Field(default=4000, description="Max message length")


class TeamsActivityHandler:
    """
    Handles Microsoft Teams activities (messages, conversation updates, invokes).

    Processes Teams activities and routes queries through AgentService.
    Formats responses as Adaptive Cards or Hero Cards.
    """

    def __init__(self, config: TeamsBotConfig, agent_service: Optional[Any] = None) -> None:
        """
        Initialize Teams Activity Handler.

        Args:
            config: TeamsBotConfig with bot credentials
            agent_service: Optional reference to AgentService
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
        logger.info(
            "TeamsActivityHandler initialized with bot_name=%s, app_id=%s",
            config.bot_name, config.app_id[:20]
        )

    def handle_message(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an incoming message activity from Teams.

        Extracts user ID, conversation ID, and message text.
        Validates message and routes to query processor.

        Args:
            activity: Teams activity object with type, from, conversation, text

        Returns:
            Dict with status and response
        """
        try:
            if activity.get("type") != "message":
                logger.debug("Ignoring non-message activity: %s", activity.get("type"))
                return {"status": "ignored", "reason": "not_message"}

            user_id = activity.get("from", {}).get("id", "unknown")
            conversation_id = activity.get("conversation", {}).get("id", "unknown")
            text = activity.get("text", "").strip()
            activity_id = activity.get("id")

            if not text or len(text) > self.config.max_message_length:
                logger.warning(
                    "Invalid message from %s: length=%d",
                    user_id, len(text) if text else 0
                )
                return {"status": "rejected", "reason": "invalid_length"}

            logger.info(
                "Message activity from user=%s conversation=%s activity_id=%s",
                user_id, conversation_id, activity_id
            )

            return self._process_query(
                user_id=user_id,
                text=text,
                conversation_id=conversation_id
            )

        except Exception as e:
            logger.exception("Error handling message activity: %s", e)
            self.metrics["errors"] += 1
            return {"status": "error", "error": str(e)}

    def handle_conversation_update(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle conversation update activity (member added/removed).

        Args:
            activity: Teams activity with type and membersAdded/membersRemoved

        Returns:
            Dict with status
        """
        try:
            activity_type = activity.get("type")

            if activity_type != "conversationUpdate":
                return {"status": "ignored", "reason": "not_conversation_update"}

            members_added = activity.get("membersAdded", [])
            members_removed = activity.get("membersRemoved", [])
            conversation_id = activity.get("conversation", {}).get("id", "unknown")

            if members_added:
                for member in members_added:
                    member_id = member.get("id")
                    member_name = member.get("name", "Unknown")
                    logger.info(
                        "Member added to conversation %s: %s (%s)",
                        conversation_id, member_name, member_id
                    )

            if members_removed:
                for member in members_removed:
                    member_id = member.get("id")
                    member_name = member.get("name", "Unknown")
                    logger.info(
                        "Member removed from conversation %s: %s (%s)",
                        conversation_id, member_name, member_id
                    )

            return {"status": "acknowledged"}

        except Exception as e:
            logger.exception("Error handling conversation update: %s", e)
            self.metrics["errors"] += 1
            return {"status": "error", "error": str(e)}

    def handle_invoke(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle adaptive card action invoke.

        Processes card button clicks and other interactive actions.

        Args:
            activity: Teams activity with type=invoke, value containing card data

        Returns:
            Dict with invoke response
        """
        try:
            if activity.get("type") != "invoke":
                return {"status": "ignored", "reason": "not_invoke"}

            name = activity.get("name")
            value = activity.get("value", {})
            user_id = activity.get("from", {}).get("id", "unknown")

            logger.info(
                "Invoke activity from user=%s name=%s",
                user_id, name
            )

            # Handle specific invoke actions
            if name == "adaptiveCard/action":
                action_type = value.get("actionType")
                logger.debug("Adaptive card action: %s", action_type)

            return {"status": "acknowledged"}

        except Exception as e:
            logger.exception("Error handling invoke: %s", e)
            self.metrics["errors"] += 1
            return {"status": "error", "error": str(e)}

    def _process_query(
        self,
        user_id: str,
        text: str,
        conversation_id: str
    ) -> Dict[str, Any]:
        """
        Process HR query through AgentService.

        Routes query to agent_service with Teams user context.
        Formats response as Adaptive Card.

        Args:
            user_id: Teams user ID
            text: Query text
            conversation_id: Teams conversation ID

        Returns:
            Dict with formatted Teams response
        """
        start_time = time.time()
        message_id = str(uuid.uuid4())

        try:
            user_context = self._get_user_context(user_id)

            logger.info(
                "Processing Teams query message_id=%s user=%s",
                message_id, user_id
            )

            if not self.agent_service:
                logger.warning("AgentService not configured")
                return {
                    "status": "error",
                    "error": "Agent service not available"
                }

            result = self.agent_service.process_query(
                query=text,
                user_context=user_context,
                session_id=message_id
            )

            response_time = time.time() - start_time
            self._update_metrics(response_time)

            logger.info(
                "Query processed in %.2f seconds, confidence=%.2f",
                response_time, result.get("confidence", 0.0)
            )

            # Format as Adaptive Card
            formatted_response = self._format_teams_response(result)
            formatted_response["message_id"] = message_id
            formatted_response["status"] = "success"

            return formatted_response

        except Exception as e:
            response_time = time.time() - start_time
            self._update_metrics(response_time, is_error=True)
            logger.exception("Error processing Teams query %s: %s", message_id, e)
            return {
                "status": "error",
                "error": f"Failed to process query: {str(e)[:100]}",
                "message_id": message_id
            }

    def _format_teams_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format agent response as Adaptive Card JSON.

        Creates structured Adaptive Card with answer, confidence,
        sources, and action buttons.

        Args:
            result: Agent service result dict

        Returns:
            Dict with Adaptive Card payload
        """
        try:
            answer = result.get("answer", "No answer available")
            confidence = result.get("confidence", 0.0)
            sources = result.get("sources", [])
            agent_type = result.get("agent_type", "router")

            # Confidence level indicator
            if confidence >= 0.9:
                confidence_label = "Very High"
                confidence_color = "good"
            elif confidence >= 0.7:
                confidence_label = "High"
                confidence_color = "warning"
            elif confidence >= 0.5:
                confidence_label = "Medium"
                confidence_color = "attention"
            else:
                confidence_label = "Low"
                confidence_color = "attention"

            # Build body elements
            body = [
                {
                    "type": "TextBlock",
                    "text": "HR Assistant Response",
                    "weight": "bolder",
                    "size": "large"
                },
                {
                    "type": "TextBlock",
                    "text": answer,
                    "wrap": True,
                    "spacing": "medium"
                },
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"Confidence: {confidence_label}",
                                    "color": confidence_color,
                                    "size": "small"
                                },
                                {
                                    "type": "TextBlock",
                                    "text": f"Score: {confidence:.0%}",
                                    "size": "small",
                                    "spacing": "none"
                                }
                            ]
                        },
                        {
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"Agent: {agent_type}",
                                    "size": "small"
                                }
                            ]
                        }
                    ],
                    "spacing": "medium"
                }
            ]

            # Add sources if available
            if sources:
                sources_text = "**Sources:**\n"
                for i, source in enumerate(sources[:5], 1):
                    if isinstance(source, dict):
                        src_title = source.get("title", "Source")
                        src_url = source.get("url", "#")
                        sources_text += f"{i}. [{src_title}]({src_url})\n"
                    else:
                        sources_text += f"{i}. {source}\n"

                body.append({
                    "type": "TextBlock",
                    "text": sources_text,
                    "wrap": True,
                    "spacing": "medium",
                    "size": "small",
                    "weight": "lighter"
                })

            # Create Adaptive Card
            card = {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": body,
                "actions": [
                    {
                        "type": "Action.OpenUrl",
                        "title": "Learn More",
                        "url": "https://www.example.com"
                    },
                    {
                        "type": "Action.Submit",
                        "title": "Ask Follow-up",
                        "data": {
                            "action": "followup"
                        }
                    }
                ]
            }

            logger.debug("Formatted Teams Adaptive Card response")

            return {
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "contentUrl": None,
                        "content": card
                    }
                ]
            }

        except Exception as e:
            logger.exception("Error formatting Teams response: %s", e)
            return {
                "text": f"Error formatting response: {str(e)[:100]}"
            }

    def _format_hero_card(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format agent response as Hero Card (alternative format).

        Creates a Hero Card with title, text, image, and buttons.

        Args:
            result: Agent service result dict

        Returns:
            Dict with Hero Card attachment
        """
        try:
            answer = result.get("answer", "No answer available")
            confidence = result.get("confidence", 0.0)

            card = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "summary": "HR Assistant",
                "themeColor": "0078D4",
                "title": "HR Assistant Response",
                "sections": [
                    {
                        "activityTitle": f"Confidence: {confidence:.0%}",
                        "activitySubtitle": f"Agent Response",
                        "text": answer
                    }
                ],
                "potentialAction": [
                    {
                        "@type": "OpenUri",
                        "name": "Learn More",
                        "targets": [
                            {
                                "os": "default",
                                "uri": "https://www.example.com"
                            }
                        ]
                    }
                ]
            }

            logger.debug("Formatted Teams Hero Card response")

            return {
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.hero",
                        "content": card
                    }
                ]
            }

        except Exception as e:
            logger.exception("Error formatting hero card: %s", e)
            return {"text": f"Error: {str(e)[:100]}"}

    def _get_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        Map Teams user to HR platform user context.

        Returns context dict with user identifier and source.
        In production, would lookup user from Azure AD or Teams API.

        Args:
            user_id: Teams user ID (UPN or object ID)

        Returns:
            Dict with user context
        """
        return {
            "user_id": user_id,
            "source": "teams",
            "platform": "microsoft_teams",
            "tenant_id": self.config.tenant_id,
            "timezone": "UTC"
        }

    def _update_metrics(self, response_time: float, is_error: bool = False) -> None:
        """
        Update metrics with response time.

        Args:
            response_time: Processing time in seconds
            is_error: Whether this was an error
        """
        self.metrics["messages_processed"] += 1
        if is_error:
            self.metrics["errors"] += 1

        old_avg = self.metrics["avg_response_time"]
        count = self.metrics["messages_processed"]
        self.metrics["avg_response_time"] = (
            (old_avg * (count - 1) + response_time) / count
        )

    def get_health(self) -> Dict[str, Any]:
        """
        Get handler health status.

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
            "messages_processed": self.metrics["messages_processed"],
            "errors": self.metrics["errors"],
            "error_rate": f"{error_rate:.1%}",
            "avg_response_time_ms": f"{self.metrics['avg_response_time'] * 1000:.1f}",
            "uptime_minutes": f"{uptime / 60:.1f}"
        }


class TeamsBotService:
    """
    Teams Bot service lifecycle manager.

    Manages startup, shutdown, and status of Teams bot.
    """

    def __init__(self, config: TeamsBotConfig) -> None:
        """
        Initialize Teams Bot Service.

        Args:
            config: TeamsBotConfig with credentials
        """
        self.config = config
        self.activity_handler = TeamsActivityHandler(config)
        self.running = False
        logger.info("TeamsBotService initialized with bot_name=%s", config.bot_name)

    def start(self) -> None:
        """
        Start the Teams bot service.

        In production, would initialize the Bot Framework adapter
        and register message handlers.
        """
        try:
            self.running = True
            logger.info(
                "TeamsBotService starting - app_id=%s, bot_name=%s",
                self.config.app_id[:20], self.config.bot_name
            )
            # In production: adapter = BotFrameworkAdapter(...)
            # adapter.onTurnError = error_handler
            # bot = TeamsBot(adapter, ...)
        except Exception as e:
            logger.exception("Error starting TeamsBotService: %s", e)
            self.running = False
            raise

    def stop(self) -> None:
        """
        Stop the Teams bot service.

        Gracefully shuts down and logs final metrics.
        """
        try:
            self.running = False
            health = self.activity_handler.get_health()
            logger.info("TeamsBotService stopping - final health: %s", health)
        except Exception as e:
            logger.exception("Error stopping TeamsBotService: %s", e)

    def get_status(self) -> Dict[str, Any]:
        """
        Get overall service status.

        Returns:
            Dict with running state and handler health
        """
        return {
            "service_running": self.running,
            "handler_health": self.activity_handler.get_health(),
            "config": {
                "bot_name": self.config.bot_name,
                "max_message_length": self.config.max_message_length,
                "tenant_id": self.config.tenant_id
            }
        }
