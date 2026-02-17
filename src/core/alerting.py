"""
Alerting Service for HR Multi-Agent Platform.
Monitors system health and sends alerts via configurable channels.
Iteration 6 - MON-003
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    """Alert delivery channels."""

    LOG = "log"
    SLACK = "slack"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"


class Alert(BaseModel):
    """Alert model."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Alert ID")
    severity: AlertSeverity = Field(description="Alert severity level")
    title: str = Field(description="Alert title")
    message: str = Field(description="Alert message")
    source: str = Field(default="", description="Alert source")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Alert timestamp"
    )
    metadata: Dict = Field(default={}, description="Additional metadata")
    acknowledged: bool = Field(default=False, description="Whether alert is acknowledged")

    model_config = ConfigDict(frozen=False)


class AlertRule(BaseModel):
    """Alert rule definition."""

    name: str = Field(description="Rule name")
    condition: str = Field(description="Condition to monitor")
    threshold: float = Field(description="Threshold value")
    window_seconds: int = Field(default=300, description="Time window in seconds")
    severity: AlertSeverity = Field(description="Alert severity when triggered")
    channels: List[AlertChannel] = Field(description="Delivery channels")
    cooldown_seconds: int = Field(
        default=600, description="Cooldown between alerts in seconds"
    )
    enabled: bool = Field(default=True, description="Whether rule is enabled")

    model_config = ConfigDict(frozen=False)


class AlertingConfig(BaseModel):
    """Alerting service configuration."""

    enabled: bool = Field(default=True, description="Enable alerting")
    default_channels: List[AlertChannel] = Field(
        default=[AlertChannel.LOG], description="Default alert channels"
    )
    slack_webhook_url: str = Field(
        default="", description="Slack webhook URL for alerts"
    )
    pagerduty_routing_key: str = Field(
        default="", description="PagerDuty routing key"
    )
    email_recipients: List[str] = Field(
        default=[], description="Email recipients for alerts"
    )
    rules: List[AlertRule] = Field(default=[], description="Alert rules")

    model_config = ConfigDict(frozen=False)


class AlertingService:
    """
    Alerting service.
    Monitors system health and sends alerts via configurable channels.
    """

    def __init__(self, config: Optional[AlertingConfig] = None) -> None:
        """
        Initialize alerting service.

        Args:
            config: Alerting configuration (uses defaults if None)
        """
        self.config = config or AlertingConfig()
        self.alert_history: List[Alert] = []
        self.cooldown_tracker: Dict[str, datetime] = {}
        self.event_counters: Dict[str, int] = {}
        self.total_alerts: int = 0
        self.alerts_by_severity: Dict[AlertSeverity, int] = {
            severity: 0 for severity in AlertSeverity
        }
        self.alerts_by_source: Dict[str, int] = {}

        logger.info(
            "Alerting service initialized",
            extra={
                "enabled": self.config.enabled,
                "default_channels": [c.value for c in self.config.default_channels],
                "rules_count": len(self.config.rules),
            },
        )

    def check_and_alert(
        self,
        event_type: str,
        value: float,
        metadata: Optional[Dict] = None,
    ) -> Optional[Alert]:
        """
        Check event against rules and fire alert if needed.

        Args:
            event_type: Type of event
            value: Event value
            metadata: Additional metadata

        Returns:
            Alert if fired, None otherwise
        """
        if not self.config.enabled:
            return None

        # Increment event counter
        self.event_counters[event_type] = self.event_counters.get(event_type, 0) + 1

        # Check against all rules
        for rule in self.config.rules:
            if not rule.enabled:
                continue

            if rule.condition == event_type and value >= rule.threshold:
                # Check cooldown
                if self._check_cooldown(rule.name):
                    logger.debug(
                        f"Alert rule {rule.name} on cooldown",
                        extra={"event": event_type},
                    )
                    return None

                # Fire alert
                alert = self.fire_alert(
                    severity=rule.severity,
                    title=f"Alert: {rule.name}",
                    message=f"Threshold exceeded: {event_type}={value} (threshold={rule.threshold})",
                    source=event_type,
                    metadata=metadata or {},
                )

                # Set cooldown
                self._set_cooldown(rule.name, rule.cooldown_seconds)

                return alert

        return None

    def fire_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        source: str = "",
        metadata: Optional[Dict] = None,
    ) -> Alert:
        """
        Fire an alert.

        Args:
            severity: Alert severity
            title: Alert title
            message: Alert message
            source: Alert source
            metadata: Additional metadata

        Returns:
            Created Alert
        """
        alert = Alert(
            severity=severity,
            title=title,
            message=message,
            source=source,
            metadata=metadata or {},
        )

        self.alert_history.append(alert)
        self.total_alerts += 1
        self.alerts_by_severity[severity] += 1
        self.alerts_by_source[source] = self.alerts_by_source.get(source, 0) + 1

        # Dispatch to configured channels
        channels = self.config.default_channels
        self._dispatch_log(alert)

        if AlertChannel.SLACK in channels:
            self._dispatch_slack(alert)

        if AlertChannel.EMAIL in channels:
            self._dispatch_email(alert)

        if AlertChannel.PAGERDUTY in channels:
            self._dispatch_pagerduty(alert)

        logger.info(
            "Alert fired",
            extra={
                "alert_id": alert.id,
                "severity": severity.value,
                "title": title,
                "source": source,
            },
        )

        return alert

    def _dispatch_log(self, alert: Alert) -> None:
        """
        Dispatch alert to logging system.

        Args:
            alert: Alert to dispatch
        """
        level_map = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }

        level = level_map.get(alert.severity, logging.INFO)

        logger.log(
            level,
            f"Alert: {alert.title}",
            extra={
                "alert_id": alert.id,
                "severity": alert.severity.value,
                "message": alert.message,
                "source": alert.source,
                "metadata": alert.metadata,
            },
        )

    def _dispatch_slack(self, alert: Alert) -> None:
        """
        Dispatch alert to Slack.

        Args:
            alert: Alert to dispatch
        """
        if not self.config.slack_webhook_url:
            logger.debug("Slack webhook URL not configured")
            return

        # Format alert for Slack
        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9900",
            AlertSeverity.ERROR: "#ff3333",
            AlertSeverity.CRITICAL: "#990000",
        }

        color = color_map.get(alert.severity, "#808080")

        slack_payload = {
            "attachments": [
                {
                    "color": color,
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value, "short": True},
                        {"title": "Source", "value": alert.source, "short": True},
                        {
                            "title": "Timestamp",
                            "value": alert.timestamp.isoformat(),
                            "short": False,
                        },
                    ],
                    "footer": f"Alert ID: {alert.id}",
                }
            ]
        }

        logger.debug(
            "Slack alert formatted",
            extra={"alert_id": alert.id, "payload": slack_payload},
        )

    def _dispatch_email(self, alert: Alert) -> None:
        """
        Dispatch alert via email.

        Args:
            alert: Alert to dispatch
        """
        if not self.config.email_recipients:
            logger.debug("No email recipients configured")
            return

        email_body = f"""
Alert: {alert.title}

Severity: {alert.severity.value}
Source: {alert.source}
Timestamp: {alert.timestamp.isoformat()}

Message:
{alert.message}

Metadata:
{alert.metadata}

Alert ID: {alert.id}
"""

        logger.debug(
            "Email alert formatted",
            extra={
                "alert_id": alert.id,
                "recipients": self.config.email_recipients,
            },
        )

    def _dispatch_pagerduty(self, alert: Alert) -> None:
        """
        Dispatch alert to PagerDuty.

        Args:
            alert: Alert to dispatch
        """
        if not self.config.pagerduty_routing_key:
            logger.debug("PagerDuty routing key not configured")
            return

        # Format alert for PagerDuty
        severity_map = {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.ERROR: "error",
            AlertSeverity.CRITICAL: "critical",
        }

        pagerduty_event = {
            "routing_key": self.config.pagerduty_routing_key,
            "event_action": "trigger",
            "dedup_key": alert.id,
            "payload": {
                "summary": alert.title,
                "timestamp": alert.timestamp.isoformat(),
                "severity": severity_map.get(alert.severity, "error"),
                "source": alert.source,
                "custom_details": {
                    "message": alert.message,
                    "metadata": alert.metadata,
                },
            },
        }

        logger.debug(
            "PagerDuty alert formatted",
            extra={"alert_id": alert.id, "event": pagerduty_event},
        )

    def _check_cooldown(self, rule_name: str) -> bool:
        """
        Check if rule is on cooldown.

        Args:
            rule_name: Rule name

        Returns:
            True if on cooldown, False otherwise
        """
        if rule_name not in self.cooldown_tracker:
            return False

        if datetime.now() < self.cooldown_tracker[rule_name]:
            return True

        del self.cooldown_tracker[rule_name]
        return False

    def _set_cooldown(self, rule_name: str, seconds: int) -> None:
        """
        Set cooldown for rule.

        Args:
            rule_name: Rule name
            seconds: Cooldown duration in seconds
        """
        self.cooldown_tracker[rule_name] = datetime.now() + timedelta(seconds=seconds)

    def get_alert_history(self, limit: int = 50) -> List[Alert]:
        """
        Get recent alert history.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of recent alerts
        """
        return self.alert_history[-limit:]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Mark alert as acknowledged.

        Args:
            alert_id: Alert ID

        Returns:
            True if acknowledged, False if not found
        """
        for alert in self.alert_history:
            if alert.id == alert_id:
                alert.acknowledged = True
                logger.info("Alert acknowledged", extra={"alert_id": alert_id})
                return True

        return False

    def get_stats(self) -> Dict[str, any]:
        """
        Get alerting service statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "total_alerts": self.total_alerts,
            "alerts_by_severity": {k.value: v for k, v in self.alerts_by_severity.items()},
            "alerts_by_source": self.alerts_by_source,
            "event_counters": self.event_counters,
            "active_cooldowns": len(self.cooldown_tracker),
        }

    def create_default_rules(self) -> List[AlertRule]:
        """
        Create default alert rules.

        Returns:
            List of default AlertRule instances
        """
        return [
            AlertRule(
                name="circuit_breaker_open",
                condition="circuit_breaker_open",
                threshold=1,
                window_seconds=60,
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.LOG, AlertChannel.SLACK],
                cooldown_seconds=300,
            ),
            AlertRule(
                name="high_error_rate",
                condition="error_rate",
                threshold=0.1,
                window_seconds=300,
                severity=AlertSeverity.ERROR,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL],
                cooldown_seconds=600,
            ),
            AlertRule(
                name="slow_response",
                condition="response_time_seconds",
                threshold=5.0,
                window_seconds=300,
                severity=AlertSeverity.WARNING,
                channels=[AlertChannel.LOG],
                cooldown_seconds=600,
            ),
            AlertRule(
                name="pii_leak_detected",
                condition="pii_leak_detected",
                threshold=1,
                window_seconds=60,
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.LOG, AlertChannel.PAGERDUTY],
                cooldown_seconds=300,
            ),
            AlertRule(
                name="llm_failure_rate",
                condition="llm_failure_rate",
                threshold=0.2,
                window_seconds=600,
                severity=AlertSeverity.WARNING,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL],
                cooldown_seconds=900,
            ),
        ]
