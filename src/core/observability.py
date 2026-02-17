"""
Observability Middleware for HR Agent Platform.

Provides structured logging, request tracing, and metrics collection.
Implements:

1. STRUCTURED LOGGING — JSON-formatted log entries with correlation IDs
2. REQUEST TRACING — End-to-end trace of agent workflows with timing
3. METRICS COLLECTION — Counters and histograms for monitoring
4. METRICS ENDPOINT — Prometheus-compatible /metrics output

Usage:
    obs = ObservabilityManager()
    trace = obs.start_trace("query-123", agent_type="leave_request")
    trace.add_span("classify_intent", duration_ms=15)
    trace.add_span("execute_tool", tool="submit_leave_request", duration_ms=230)
    trace.finish(success=True)
    metrics = obs.get_prometheus_metrics()
"""

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ─── Structured Log Entry ────────────────────────────────────────


@dataclass
class StructuredLogEntry:
    """
    A single structured log entry in JSON format.

    Attributes:
        timestamp: ISO 8601 timestamp
        level: Log level (INFO, WARNING, ERROR)
        correlation_id: Request correlation ID for tracing
        agent_type: Which agent produced this log
        event: Event name (e.g., "tool_executed", "query_classified")
        duration_ms: Duration in milliseconds (if applicable)
        metadata: Additional key-value pairs
    """

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    level: str = "INFO"
    correlation_id: str = ""
    agent_type: str = ""
    event: str = ""
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialise to JSON string."""
        data = {
            "timestamp": self.timestamp,
            "level": self.level,
            "correlation_id": self.correlation_id,
            "agent_type": self.agent_type,
            "event": self.event,
        }
        if self.duration_ms is not None:
            data["duration_ms"] = round(self.duration_ms, 2)
        if self.metadata:
            data["metadata"] = self.metadata
        return json.dumps(data)


# ─── Trace Span ──────────────────────────────────────────────────


@dataclass
class TraceSpan:
    """
    A single span within a request trace.

    Represents one step in the agent workflow (e.g., classify, execute, reflect).

    Attributes:
        name: Span name (e.g., "classify_intent", "execute_tool")
        start_time: When the span started
        end_time: When the span ended
        duration_ms: Calculated duration
        success: Whether the step succeeded
        metadata: Additional span data (tool name, result type, etc.)
    """

    name: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(self, success: bool = True) -> None:
        """Mark span as finished and calculate duration."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "success": self.success,
            "metadata": self.metadata,
        }


# ─── Request Trace ───────────────────────────────────────────────


class RequestTrace:
    """
    End-to-end trace for a single request through the agent system.

    Collects all spans (steps) for a request, tracks total timing,
    and produces structured trace data for debugging and monitoring.

    Usage:
        trace = RequestTrace("corr-123", agent_type="leave_request")
        span = trace.start_span("classify_intent")
        # ... do work ...
        span.finish(success=True)
        trace.finish(success=True)
    """

    def __init__(self, correlation_id: str, agent_type: str = "", query: str = ""):
        self.correlation_id = correlation_id
        self.agent_type = agent_type
        self.query = query[:100]  # Truncate for safety
        self.spans: List[TraceSpan] = []
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.total_duration_ms: Optional[float] = None
        self.success: bool = True
        self.error: Optional[str] = None

    def start_span(self, name: str, **metadata) -> TraceSpan:
        """
        Start a new span within this trace.

        Args:
            name: Span name (e.g., "execute_tool")
            **metadata: Additional span metadata

        Returns:
            TraceSpan that should be finished when the step completes.
        """
        span = TraceSpan(name=name, metadata=metadata)
        self.spans.append(span)
        return span

    def add_span(self, name: str, duration_ms: float = 0, success: bool = True, **metadata) -> None:
        """
        Add a pre-completed span (for retroactive tracing).

        Args:
            name: Span name
            duration_ms: Duration in milliseconds
            success: Whether the step succeeded
            **metadata: Additional span data
        """
        span = TraceSpan(
            name=name,
            duration_ms=duration_ms,
            success=success,
            metadata=metadata,
        )
        span.end_time = time.time()
        self.spans.append(span)

    def finish(self, success: bool = True, error: Optional[str] = None) -> None:
        """
        Mark the trace as finished.

        Args:
            success: Whether the overall request succeeded
            error: Error message if failed
        """
        self.end_time = time.time()
        self.total_duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a structured dictionary."""
        return {
            "correlation_id": self.correlation_id,
            "agent_type": self.agent_type,
            "query": self.query,
            "total_duration_ms": (
                round(self.total_duration_ms, 2) if self.total_duration_ms else None
            ),
            "success": self.success,
            "error": self.error,
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
        }


# ─── Metrics Collector ───────────────────────────────────────────


class MetricsCollector:
    """
    Collects and aggregates metrics for monitoring.

    Tracks:
    - Request counts by agent type
    - Error counts by agent type
    - Latency histograms (p50, p90, p99)
    - Tool call counts
    - Active request gauge
    """

    def __init__(self):
        self.request_count: Dict[str, int] = defaultdict(int)
        self.error_count: Dict[str, int] = defaultdict(int)
        self.tool_call_count: Dict[str, int] = defaultdict(int)
        self.latencies: Dict[str, List[float]] = defaultdict(list)
        self.active_requests: int = 0
        self._start_time = time.time()

    def record_request(self, agent_type: str, duration_ms: float, success: bool = True) -> None:
        """Record a completed request."""
        self.request_count[agent_type] += 1
        self.latencies[agent_type].append(duration_ms)

        if not success:
            self.error_count[agent_type] += 1

        # Keep only last 1000 latency samples per agent
        if len(self.latencies[agent_type]) > 1000:
            self.latencies[agent_type] = self.latencies[agent_type][-1000:]

    def record_tool_call(self, tool_name: str) -> None:
        """Record a tool invocation."""
        self.tool_call_count[tool_name] += 1

    def increment_active(self) -> None:
        """Increment active request gauge."""
        self.active_requests += 1

    def decrement_active(self) -> None:
        """Decrement active request gauge."""
        self.active_requests = max(0, self.active_requests - 1)

    def get_percentile(self, agent_type: str, percentile: float) -> float:
        """
        Calculate latency percentile for an agent type.

        Args:
            agent_type: Agent type to query
            percentile: Percentile (0.0 - 1.0, e.g., 0.95 for p95)

        Returns:
            Latency value at the given percentile in milliseconds.
        """
        values = sorted(self.latencies.get(agent_type, []))
        if not values:
            return 0.0
        index = int(len(values) * percentile)
        index = min(index, len(values) - 1)
        return values[index]

    def to_prometheus(self) -> str:
        """
        Generate Prometheus-compatible metrics text.

        Returns:
            Multi-line string in Prometheus exposition format.
        """
        lines = []
        uptime = time.time() - self._start_time

        # Uptime
        lines.append("# HELP hr_agent_uptime_seconds Server uptime in seconds")
        lines.append("# TYPE hr_agent_uptime_seconds gauge")
        lines.append(f"hr_agent_uptime_seconds {uptime:.1f}")

        # Active requests
        lines.append("# HELP hr_agent_active_requests Current active requests")
        lines.append("# TYPE hr_agent_active_requests gauge")
        lines.append(f"hr_agent_active_requests {self.active_requests}")

        # Request counts
        lines.append("# HELP hr_agent_requests_total Total requests by agent type")
        lines.append("# TYPE hr_agent_requests_total counter")
        for agent, count in self.request_count.items():
            lines.append(f'hr_agent_requests_total{{agent_type="{agent}"}} {count}')

        # Error counts
        lines.append("# HELP hr_agent_errors_total Total errors by agent type")
        lines.append("# TYPE hr_agent_errors_total counter")
        for agent, count in self.error_count.items():
            lines.append(f'hr_agent_errors_total{{agent_type="{agent}"}} {count}')

        # Latency percentiles
        lines.append("# HELP hr_agent_latency_ms Request latency in milliseconds")
        lines.append("# TYPE hr_agent_latency_ms summary")
        for agent in self.request_count:
            p50 = self.get_percentile(agent, 0.5)
            p90 = self.get_percentile(agent, 0.9)
            p99 = self.get_percentile(agent, 0.99)
            lines.append(f'hr_agent_latency_ms{{agent_type="{agent}",quantile="0.5"}} {p50:.1f}')
            lines.append(f'hr_agent_latency_ms{{agent_type="{agent}",quantile="0.9"}} {p90:.1f}')
            lines.append(f'hr_agent_latency_ms{{agent_type="{agent}",quantile="0.99"}} {p99:.1f}')

        # Tool call counts
        lines.append("# HELP hr_agent_tool_calls_total Total tool invocations")
        lines.append("# TYPE hr_agent_tool_calls_total counter")
        for tool, count in self.tool_call_count.items():
            lines.append(f'hr_agent_tool_calls_total{{tool="{tool}"}} {count}')

        return "\n".join(lines) + "\n"

    def get_summary(self) -> Dict[str, Any]:
        """Get a JSON-friendly metrics summary."""
        total_requests = sum(self.request_count.values())
        total_errors = sum(self.error_count.values())

        return {
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": total_errors / max(total_requests, 1),
            "active_requests": self.active_requests,
            "by_agent": {
                agent: {
                    "requests": self.request_count[agent],
                    "errors": self.error_count.get(agent, 0),
                    "p50_ms": round(self.get_percentile(agent, 0.5), 1),
                    "p90_ms": round(self.get_percentile(agent, 0.9), 1),
                    "p99_ms": round(self.get_percentile(agent, 0.99), 1),
                }
                for agent in self.request_count
            },
            "tool_calls": dict(self.tool_call_count),
            "uptime_seconds": round(time.time() - self._start_time, 1),
        }


# ─── Observability Manager ───────────────────────────────────────


class ObservabilityManager:
    """
    Central observability manager combining logging, tracing, and metrics.

    Singleton pattern — use ObservabilityManager.instance() for shared access.

    Provides:
    - start_trace(): Begin tracing a request
    - log(): Write structured log entries
    - metrics: Access to MetricsCollector
    - get_prometheus_metrics(): Prometheus-compatible output
    """

    _instance: Optional["ObservabilityManager"] = None

    def __init__(self):
        self.metrics = MetricsCollector()
        self._traces: List[RequestTrace] = []
        self._log_entries: List[StructuredLogEntry] = []
        self._max_traces = 500
        self._max_logs = 2000

    @classmethod
    def instance(cls) -> "ObservabilityManager":
        """Get or create the singleton ObservabilityManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def start_trace(
        self,
        correlation_id: Optional[str] = None,
        agent_type: str = "",
        query: str = "",
    ) -> RequestTrace:
        """
        Start a new request trace.

        Args:
            correlation_id: Unique ID for this request (auto-generated if None)
            agent_type: Agent handling this request
            query: Original user query

        Returns:
            RequestTrace instance to collect spans.
        """
        if correlation_id is None:
            correlation_id = str(uuid4())[:12]

        trace = RequestTrace(
            correlation_id=correlation_id,
            agent_type=agent_type,
            query=query,
        )

        self._traces.append(trace)
        if len(self._traces) > self._max_traces:
            self._traces = self._traces[-self._max_traces :]

        self.metrics.increment_active()
        return trace

    def finish_trace(
        self, trace: RequestTrace, success: bool = True, error: Optional[str] = None
    ) -> None:
        """
        Finish a trace and record metrics.

        Args:
            trace: The RequestTrace to finish
            success: Whether the request succeeded
            error: Error message if failed
        """
        trace.finish(success=success, error=error)
        self.metrics.decrement_active()

        if trace.total_duration_ms:
            self.metrics.record_request(
                trace.agent_type,
                trace.total_duration_ms,
                success=success,
            )

        # Log trace completion
        self.log(
            event="request_completed",
            correlation_id=trace.correlation_id,
            agent_type=trace.agent_type,
            duration_ms=trace.total_duration_ms,
            level="INFO" if success else "ERROR",
            metadata={"span_count": len(trace.spans), "error": error},
        )

    def log(
        self,
        event: str,
        correlation_id: str = "",
        agent_type: str = "",
        duration_ms: Optional[float] = None,
        level: str = "INFO",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StructuredLogEntry:
        """
        Write a structured log entry.

        Args:
            event: Event name
            correlation_id: Request correlation ID
            agent_type: Agent type
            duration_ms: Duration in ms
            level: Log level
            metadata: Additional data

        Returns:
            The created StructuredLogEntry.
        """
        entry = StructuredLogEntry(
            level=level,
            correlation_id=correlation_id,
            agent_type=agent_type,
            event=event,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        self._log_entries.append(entry)
        if len(self._log_entries) > self._max_logs:
            self._log_entries = self._log_entries[-self._max_logs :]

        # Also emit to Python logger
        log_fn = getattr(logger, level.lower(), logger.info)
        log_fn(entry.to_json())

        return entry

    def get_recent_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent traces as dicts."""
        return [t.to_dict() for t in self._traces[-limit:]]

    def get_recent_logs(self, limit: int = 50) -> List[str]:
        """Get recent structured log entries as JSON strings."""
        return [e.to_json() for e in self._log_entries[-limit:]]

    def get_prometheus_metrics(self) -> str:
        """Get Prometheus-compatible metrics text."""
        return self.metrics.to_prometheus()

    def get_summary(self) -> Dict[str, Any]:
        """Get observability summary."""
        return {
            "metrics": self.metrics.get_summary(),
            "recent_traces": len(self._traces),
            "recent_logs": len(self._log_entries),
        }
