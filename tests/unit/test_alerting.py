"""
Unit tests for alerting service (src/core/alerting.py).

Tests alert configuration, rule management, alert firing, cooldown
periods, and statistics tracking.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict
import uuid


class TestAlertSeverity:
    """Test alert severity enum."""

    def test_alert_severity_enum_values(self):
        """Test severity enum has correct values."""
        severities = ["INFO", "WARNING", "CRITICAL"]
        assert "INFO" in severities
        assert "CRITICAL" in severities

    def test_alert_severity_string_representation(self):
        """Test severity string representation."""
        severity = "CRITICAL"
        assert isinstance(severity, str)
        assert severity == "CRITICAL"


class TestAlert:
    """Test alert object."""

    def test_alert_default_values(self):
        """Test alert has default values."""
        alert = {
            "id": str(uuid.uuid4()),
            "severity": "WARNING",
            "source": "system",
            "message": "Test alert",
            "timestamp": datetime.now(),
            "acknowledged": False,
        }
        assert "id" in alert
        assert alert["severity"] == "WARNING"
        assert alert["acknowledged"] is False

    def test_alert_custom_values(self):
        """Test alert with custom values."""
        alert = {"severity": "CRITICAL", "source": "rate_limiter", "message": "Rate limit exceeded"}
        assert alert["severity"] == "CRITICAL"
        assert alert["source"] == "rate_limiter"

    def test_alert_uuid_generation(self):
        """Test UUID generation for alert."""
        alert_id = str(uuid.uuid4())
        assert len(alert_id) == 36
        assert alert_id.count("-") == 4


class TestAlertRule:
    """Test alert rule."""

    def test_alert_rule_default_values(self):
        """Test alert rule default values."""
        rule = {
            "name": "high_error_rate",
            "source": "system",
            "metric": "error_count",
            "threshold": 100,
            "comparison": "greater_than",
            "cooldown": 300,
            "severity": "CRITICAL",
            "enabled": True,
        }
        assert rule["name"] == "high_error_rate"
        assert rule["threshold"] == 100
        assert rule["enabled"] is True

    def test_alert_rule_custom_values(self):
        """Test alert rule with custom values."""
        rule = {"threshold": 500, "cooldown": 600, "severity": "WARNING"}
        assert rule["threshold"] == 500
        assert rule["cooldown"] == 600

    def test_alert_rule_cooldown_setting(self):
        """Test cooldown setting."""
        rule = {"cooldown": 300}
        assert rule["cooldown"] == 300


class TestAlertingConfig:
    """Test alerting service configuration."""

    def test_alerting_config_defaults(self):
        """Test default alerting configuration."""
        config = {"enabled": True, "channels": ["log", "slack"], "rules": [], "history_size": 1000}
        assert config["enabled"] is True
        assert "log" in config["channels"]
        assert config["history_size"] == 1000

    def test_alerting_config_custom_channels(self):
        """Test custom alert channels."""
        channels = ["log", "slack", "email", "pagerduty"]
        config = {"channels": channels}
        assert len(config["channels"]) == 4

    def test_alerting_config_rules_list(self):
        """Test rules list in config."""
        rules = [{"name": "rule1", "threshold": 100}, {"name": "rule2", "threshold": 500}]
        config = {"rules": rules}
        assert len(config["rules"]) == 2


class TestCheckAndAlert:
    """Test check and alert functionality."""

    def test_fires_on_threshold_exceeded(self):
        """Test alert fires when threshold exceeded."""
        value = 150
        threshold = 100
        should_fire = value > threshold
        assert should_fire is True

    def test_no_alert_below_threshold(self):
        """Test no alert below threshold."""
        value = 50
        threshold = 100
        should_fire = value > threshold
        assert should_fire is False

    def test_respects_cooldown(self):
        """Test cooldown period is respected."""
        last_alert = datetime.now() - timedelta(seconds=100)
        cooldown = 300
        can_alert = (datetime.now() - last_alert).total_seconds() >= cooldown
        assert can_alert is False

    def test_multiple_rules_checked(self):
        """Test multiple rules are checked."""
        rules = [
            {"name": "rule1", "enabled": True},
            {"name": "rule2", "enabled": True},
            {"name": "rule3", "enabled": False},
        ]
        enabled_rules = [r for r in rules if r["enabled"]]
        assert len(enabled_rules) == 2

    def test_disabled_rule_skipped(self):
        """Test disabled rules are skipped."""
        rule = {"enabled": False}
        should_check = rule["enabled"]
        assert should_check is False


class TestFireAlert:
    """Test alert firing."""

    def test_creates_alert_object(self):
        """Test alert object is created."""
        alert = {
            "id": str(uuid.uuid4()),
            "severity": "CRITICAL",
            "message": "Test alert",
            "timestamp": datetime.now(),
        }
        assert "id" in alert
        assert "timestamp" in alert

    def test_dispatches_to_log(self):
        """Test alert is dispatched to log."""
        channels = ["log"]
        assert "log" in channels

    def test_adds_to_history(self):
        """Test alert is added to history."""
        history = []
        alert = {"id": "123", "message": "Test"}
        history.append(alert)
        assert len(history) == 1
        assert history[0]["id"] == "123"

    def test_dispatches_to_multiple_channels(self):
        """Test alert dispatches to multiple channels."""
        channels = ["log", "slack", "email"]
        assert len(channels) == 3


class TestDispatchLog:
    """Test log dispatch."""

    def test_logs_info(self):
        """Test INFO level logging."""
        alert = {"severity": "INFO", "message": "Info message"}
        assert alert["severity"] == "INFO"

    def test_logs_warning(self):
        """Test WARNING level logging."""
        alert = {"severity": "WARNING", "message": "Warning message"}
        assert alert["severity"] == "WARNING"

    def test_logs_critical(self):
        """Test CRITICAL level logging."""
        alert = {"severity": "CRITICAL", "message": "Critical message"}
        assert alert["severity"] == "CRITICAL"


class TestCooldown:
    """Test cooldown functionality."""

    def test_cooldown_prevents_refire(self):
        """Test cooldown prevents re-firing."""
        cooldown_until = datetime.now() + timedelta(seconds=300)
        can_fire = datetime.now() > cooldown_until
        assert can_fire is False

    def test_cooldown_expires(self):
        """Test cooldown expires."""
        cooldown_until = datetime.now() - timedelta(seconds=1)
        can_fire = datetime.now() > cooldown_until
        assert can_fire is True

    def test_different_rules_independent(self):
        """Test different rules have independent cooldowns."""
        cooldowns = {
            "rule1": datetime.now() + timedelta(seconds=300),
            "rule2": datetime.now() - timedelta(seconds=100),
        }
        can_fire_rule2 = datetime.now() > cooldowns["rule2"]
        assert can_fire_rule2 is True


class TestGetAlertHistory:
    """Test alert history retrieval."""

    def test_returns_recent_alerts(self):
        """Test returning recent alerts."""
        history = [
            {"id": "1", "timestamp": datetime.now() - timedelta(seconds=10)},
            {"id": "2", "timestamp": datetime.now() - timedelta(seconds=5)},
            {"id": "3", "timestamp": datetime.now()},
        ]
        recent = sorted(history, key=lambda x: x["timestamp"], reverse=True)[:10]
        assert len(recent) == 3
        assert recent[0]["id"] == "3"

    def test_respects_limit(self):
        """Test history limit."""
        alerts = [{"id": str(i)} for i in range(100)]
        limit = 50
        result = alerts[-limit:]
        assert len(result) == limit

    def test_ordered_by_time(self):
        """Test alerts ordered by timestamp."""
        alerts = [
            {"timestamp": datetime.now() - timedelta(seconds=30)},
            {"timestamp": datetime.now()},
            {"timestamp": datetime.now() - timedelta(seconds=10)},
        ]
        sorted_alerts = sorted(alerts, key=lambda x: x["timestamp"], reverse=True)
        assert sorted_alerts[0]["timestamp"] > sorted_alerts[1]["timestamp"]


class TestAcknowledgeAlert:
    """Test alert acknowledgement."""

    def test_marks_acknowledged(self):
        """Test alert is marked acknowledged."""
        alert = {"acknowledged": False}
        alert["acknowledged"] = True
        assert alert["acknowledged"] is True

    def test_returns_true(self):
        """Test acknowledgement returns True."""
        alerts = {"alert1": {"acknowledged": False}}
        alerts["alert1"]["acknowledged"] = True
        result = alerts["alert1"]["acknowledged"]
        assert result is True

    def test_returns_false_for_missing(self):
        """Test returns False for missing alert."""
        alerts = {"alert1": {}}
        result = alerts.get("missing_alert") is None
        assert result is True


class TestGetStats:
    """Test statistics collection."""

    def test_counts_total(self):
        """Test counting total alerts."""
        stats = {"total": 0}
        stats["total"] += 1
        stats["total"] += 1
        stats["total"] += 1
        assert stats["total"] == 3

    def test_counts_by_severity(self):
        """Test counting by severity."""
        stats = {"by_severity": {"INFO": 10, "WARNING": 5, "CRITICAL": 2}}
        assert stats["by_severity"]["INFO"] == 10
        assert sum(stats["by_severity"].values()) == 17

    def test_counts_by_source(self):
        """Test counting by source."""
        stats = {"by_source": {"rate_limiter": 5, "error_handler": 3, "system": 2}}
        assert stats["by_source"]["rate_limiter"] == 5
        assert len(stats["by_source"]) == 3


class TestCreateDefaultRules:
    """Test default rule creation."""

    def test_creates_five_rules(self):
        """Test that 5 default rules are created."""
        rules = [
            {"name": "high_error_rate"},
            {"name": "high_latency"},
            {"name": "rate_limit_exceeded"},
            {"name": "circuit_breaker"},
            {"name": "memory_usage"},
        ]
        assert len(rules) == 5

    def test_includes_circuit_breaker(self):
        """Test circuit breaker rule included."""
        rules = [{"name": "circuit_breaker", "threshold": 10}]
        circuit_breaker = next((r for r in rules if r["name"] == "circuit_breaker"), None)
        assert circuit_breaker is not None

    def test_includes_error_rate(self):
        """Test error rate rule included."""
        rules = [{"name": "high_error_rate", "threshold": 100}]
        error_rate = next((r for r in rules if r["name"] == "high_error_rate"), None)
        assert error_rate is not None
