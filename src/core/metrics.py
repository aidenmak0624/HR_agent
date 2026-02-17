"""
Prometheus-Style Metrics for HR Multi-Agent Platform.
Collects and exposes application metrics in Prometheus format.
Iteration 6 - MON-001
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Metric type enumeration."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class Metric(BaseModel):
    """Metric data model."""

    name: str = Field(description="Metric name")
    type: MetricType = Field(description="Metric type")
    description: str = Field(description="Metric description")
    value: float = Field(default=0.0, description="Metric value")
    labels: Dict[str, str] = Field(default={}, description="Metric labels")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp")

    model_config = ConfigDict(frozen=False)


class MetricsConfig(BaseModel):
    """Metrics configuration model."""

    prefix: str = Field(default="hr_platform", description="Metrics prefix")
    enable_default_metrics: bool = Field(default=True, description="Enable default metrics")
    histogram_buckets: List[float] = Field(
        default=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        description="Histogram bucket boundaries",
    )
    enable_process_metrics: bool = Field(default=True, description="Enable process-level metrics")

    model_config = ConfigDict(frozen=False)


class Counter:
    """Counter metric type."""

    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize counter.

        Args:
            name: Counter name
            description: Counter description
            labels: Label names
        """
        self.name = name
        self.description = description
        self.labels = labels or []
        self.values: Dict[str, float] = {}

        logger.debug(f"Counter created: {name}")

    def inc(self, value: float = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Increment counter.

        Args:
            value: Amount to increment by
            labels: Label values
        """
        key = self._make_key(labels)
        self.values[key] = self.values.get(key, 0) + value

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """
        Get counter value.

        Args:
            labels: Label values

        Returns:
            Counter value
        """
        key = self._make_key(labels)
        return self.values.get(key, 0)

    def _make_key(self, labels: Optional[Dict[str, str]]) -> str:
        """
        Create cache key from labels.

        Args:
            labels: Label values

        Returns:
            Cache key string
        """
        if not labels:
            return "default"
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))


class Gauge:
    """Gauge metric type."""

    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize gauge.

        Args:
            name: Gauge name
            description: Gauge description
            labels: Label names
        """
        self.name = name
        self.description = description
        self.labels = labels or []
        self.values: Dict[str, float] = {}

        logger.debug(f"Gauge created: {name}")

    def set(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Set gauge value.

        Args:
            value: Value to set
            labels: Label values
        """
        key = self._make_key(labels)
        self.values[key] = value

    def inc(self, value: float = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Increment gauge.

        Args:
            value: Amount to increment by
            labels: Label values
        """
        key = self._make_key(labels)
        self.values[key] = self.values.get(key, 0) + value

    def dec(self, value: float = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Decrement gauge.

        Args:
            value: Amount to decrement by
            labels: Label values
        """
        key = self._make_key(labels)
        self.values[key] = self.values.get(key, 0) - value

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """
        Get gauge value.

        Args:
            labels: Label values

        Returns:
            Gauge value
        """
        key = self._make_key(labels)
        return self.values.get(key, 0)

    def _make_key(self, labels: Optional[Dict[str, str]]) -> str:
        """
        Create cache key from labels.

        Args:
            labels: Label values

        Returns:
            Cache key string
        """
        if not labels:
            return "default"
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))


class Histogram:
    """Histogram metric type."""

    def __init__(
        self,
        name: str,
        description: str,
        buckets: List[float],
        labels: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize histogram.

        Args:
            name: Histogram name
            description: Histogram description
            buckets: Bucket boundaries
            labels: Label names
        """
        self.name = name
        self.description = description
        self.buckets = sorted(buckets)
        self.labels = labels or []
        self.bucket_counts: Dict[str, Dict[float, int]] = {}
        self.sums: Dict[str, float] = {}
        self.counts: Dict[str, int] = {}

        logger.debug(f"Histogram created: {name} with {len(buckets)} buckets")

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Record observation in histogram.

        Args:
            value: Observation value
            labels: Label values
        """
        key = self._make_key(labels)

        # Initialize if needed
        if key not in self.bucket_counts:
            self.bucket_counts[key] = {bucket: 0 for bucket in self.buckets}
            self.bucket_counts[key][float("inf")] = 0
            self.sums[key] = 0
            self.counts[key] = 0

        # Increment appropriate buckets
        for bucket in self.buckets:
            if value <= bucket:
                self.bucket_counts[key][bucket] += 1
        self.bucket_counts[key][float("inf")] += 1

        # Update sum and count
        self.sums[key] += value
        self.counts[key] += 1

    def get_buckets(self, labels: Optional[Dict[str, str]]) -> Dict:
        """
        Get histogram bucket data.

        Args:
            labels: Label values

        Returns:
            Dictionary with bucket counts, sum, and count
        """
        key = self._make_key(labels)

        return {
            "buckets": self.bucket_counts.get(key, {}),
            "sum": self.sums.get(key, 0),
            "count": self.counts.get(key, 0),
        }

    def _make_key(self, labels: Optional[Dict[str, str]]) -> str:
        """
        Create cache key from labels.

        Args:
            labels: Label values

        Returns:
            Cache key string
        """
        if not labels:
            return "default"
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))


class MetricsRegistry:
    """Metrics registry for managing all metrics."""

    def __init__(self, config: Optional[MetricsConfig] = None) -> None:
        """
        Initialize metrics registry.

        Args:
            config: Metrics configuration (uses defaults if None)
        """
        self.config = config or MetricsConfig()
        self.metrics: Dict[str, any] = {}

        logger.info(
            "Metrics registry initialized",
            extra={
                "prefix": self.config.prefix,
                "default_metrics_enabled": self.config.enable_default_metrics,
            },
        )

        if self.config.enable_default_metrics:
            self._register_default_metrics()

    def counter(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> Counter:
        """
        Create or get counter metric.

        Args:
            name: Counter name
            description: Counter description
            labels: Label names

        Returns:
            Counter instance
        """
        full_name = f"{self.config.prefix}_{name}"

        if full_name not in self.metrics:
            self.metrics[full_name] = Counter(full_name, description, labels)

        return self.metrics[full_name]

    def gauge(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> Gauge:
        """
        Create or get gauge metric.

        Args:
            name: Gauge name
            description: Gauge description
            labels: Label names

        Returns:
            Gauge instance
        """
        full_name = f"{self.config.prefix}_{name}"

        if full_name not in self.metrics:
            self.metrics[full_name] = Gauge(full_name, description, labels)

        return self.metrics[full_name]

    def histogram(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> Histogram:
        """
        Create or get histogram metric.

        Args:
            name: Histogram name
            description: Histogram description
            labels: Label names

        Returns:
            Histogram instance
        """
        full_name = f"{self.config.prefix}_{name}"

        if full_name not in self.metrics:
            self.metrics[full_name] = Histogram(
                full_name, description, self.config.histogram_buckets, labels
            )

        return self.metrics[full_name]

    def get_all(self) -> Dict:
        """
        Get all metrics.

        Returns:
            Dictionary of all metrics
        """
        return self.metrics.copy()

    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus text format.

        Returns:
            Prometheus formatted metric text
        """
        lines = []

        for name, metric in self.metrics.items():
            # Add help and type lines
            lines.append(f"# HELP {name} {metric.description}")
            lines.append(f"# TYPE {name} {metric.__class__.__name__.lower()}")

            # Add metric values
            if isinstance(metric, Counter) or isinstance(metric, Gauge):
                for label_key, value in metric.values.items():
                    if label_key == "default":
                        lines.append(f"{name} {value}")
                    else:
                        label_str = "{" + label_key.replace(",", ", ") + "}"
                        lines.append(f"{name}{label_str} {value}")

            elif isinstance(metric, Histogram):
                for label_key, buckets in metric.bucket_counts.items():
                    label_suffix = (
                        "" if label_key == "default" else "{" + label_key.replace(",", ", ") + "}"
                    )
                    for bucket, count in buckets.items():
                        if bucket == float("inf"):
                            lines.append(f'{name}_bucket{{le="+Inf"{label_suffix}}} {count}')
                        else:
                            lines.append(f'{name}_bucket{{le="{bucket}"{label_suffix}}} {count}')

                    lines.append(f"{name}_sum{label_suffix} {metric.sums[label_key]}")
                    lines.append(f"{name}_count{label_suffix} {metric.counts[label_key]}")

            lines.append("")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics to default values."""
        for metric in self.metrics.values():
            if isinstance(metric, Counter) or isinstance(metric, Gauge):
                metric.values.clear()
            elif isinstance(metric, Histogram):
                metric.bucket_counts.clear()
                metric.sums.clear()
                metric.counts.clear()

        logger.info("All metrics reset")

    def _register_default_metrics(self) -> None:
        """Register default metrics."""
        self.counter("http_requests_total", "Total HTTP requests")
        self.histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
        )
        self.counter("llm_calls_total", "Total LLM API calls")
        self.histogram(
            "llm_call_duration_seconds",
            "LLM call duration in seconds",
        )
        self.counter("agent_queries_total", "Total agent queries")
        self.gauge("active_sessions", "Number of active sessions")
        self.counter("error_count_total", "Total error count")

        logger.debug("Default metrics registered")
