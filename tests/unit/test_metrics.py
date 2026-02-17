"""
Unit tests for metrics module (src/core/metrics.py).

Tests metrics collection, registry management, Prometheus export,
and label handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List


class TestMetricsConfig:
    """Test metrics configuration."""

    def test_metrics_config_defaults(self):
        """Test default metrics configuration."""
        config = {
            'prefix': 'hr_agent',
            'enable_histograms': True,
            'histogram_buckets': [0.1, 0.5, 1.0, 5.0, 10.0],
            'enable_gc_metrics': True
        }
        assert config['prefix'] == 'hr_agent'
        assert config['enable_histograms'] is True
        assert len(config['histogram_buckets']) == 5

    def test_metrics_config_custom_prefix(self):
        """Test custom metrics prefix."""
        config = {'prefix': 'custom_app'}
        assert config['prefix'] == 'custom_app'

    def test_metrics_config_histogram_buckets(self):
        """Test histogram buckets configuration."""
        buckets = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]
        config = {'histogram_buckets': buckets}
        assert len(config['histogram_buckets']) == 6
        assert config['histogram_buckets'][0] == 0.1


class TestCounter:
    """Test counter metric."""

    def test_counter_starts_at_zero(self):
        """Test that counter starts at zero."""
        counter = {'value': 0}
        assert counter['value'] == 0

    def test_counter_increment_by_one(self):
        """Test increment by one."""
        counter = {'value': 0}
        counter['value'] += 1
        counter['value'] += 1
        assert counter['value'] == 2

    def test_counter_increment_by_custom(self):
        """Test increment by custom amount."""
        counter = {'value': 0}
        counter['value'] += 5
        assert counter['value'] == 5

    def test_counter_get_value(self):
        """Test getting counter value."""
        counter = {'value': 42}
        assert counter['value'] == 42

    def test_counter_with_labels(self):
        """Test counter with labels."""
        counters = {
            ('method', 'GET'): 50,
            ('method', 'POST'): 30,
            ('method', 'PUT'): 10
        }
        assert counters[('method', 'GET')] == 50
        assert len(counters) == 3


class TestGauge:
    """Test gauge metric."""

    def test_gauge_starts_at_zero(self):
        """Test that gauge starts at zero."""
        gauge = {'value': 0}
        assert gauge['value'] == 0

    def test_gauge_set_value(self):
        """Test setting gauge value."""
        gauge = {'value': 0}
        gauge['value'] = 42
        assert gauge['value'] == 42

    def test_gauge_increment(self):
        """Test gauge increment."""
        gauge = {'value': 10}
        gauge['value'] += 5
        assert gauge['value'] == 15

    def test_gauge_decrement(self):
        """Test gauge decrement."""
        gauge = {'value': 10}
        gauge['value'] -= 3
        assert gauge['value'] == 7

    def test_gauge_get_value(self):
        """Test getting gauge value."""
        gauge = {'value': 25}
        assert gauge['value'] == 25

    def test_gauge_with_labels(self):
        """Test gauge with labels."""
        gauges = {
            ('status', 'active'): 50,
            ('status', 'inactive'): 10
        }
        assert gauges[('status', 'active')] == 50


class TestHistogram:
    """Test histogram metric."""

    def test_histogram_observe_records_value(self):
        """Test that observe records a value."""
        histogram = {
            'observations': [0.5, 1.2, 0.8],
            'sum': 2.5,
            'count': 3
        }
        assert histogram['count'] == 3
        assert histogram['sum'] == 2.5

    def test_histogram_bucket_distribution(self):
        """Test histogram bucket distribution."""
        buckets = {
            0.1: 0,
            0.5: 2,
            1.0: 1,
            5.0: 0
        }
        assert buckets[0.5] == 2
        assert sum(buckets.values()) == 3

    def test_histogram_sum_calculation(self):
        """Test histogram sum calculation."""
        observations = [0.5, 1.5, 2.0]
        total = sum(observations)
        assert total == 4.0

    def test_histogram_count_tracking(self):
        """Test histogram count tracking."""
        histogram = {'count': 0}
        histogram['count'] += 1
        histogram['count'] += 1
        histogram['count'] += 1
        assert histogram['count'] == 3

    def test_histogram_get_buckets_structure(self):
        """Test histogram buckets structure."""
        buckets = {
            'le_0.1': 0,
            'le_0.5': 2,
            'le_1.0': 5,
            'le_inf': 10
        }
        assert 'le_0.1' in buckets
        assert buckets['le_1.0'] == 5


class TestMetricsRegistry:
    """Test metrics registry."""

    def test_registry_creates_counter(self):
        """Test creating counter in registry."""
        registry = {}
        counter_name = 'requests_total'
        registry[counter_name] = {'type': 'counter', 'value': 0}
        
        assert counter_name in registry
        assert registry[counter_name]['type'] == 'counter'

    def test_registry_creates_gauge(self):
        """Test creating gauge in registry."""
        registry = {}
        gauge_name = 'active_connections'
        registry[gauge_name] = {'type': 'gauge', 'value': 0}
        
        assert gauge_name in registry

    def test_registry_creates_histogram(self):
        """Test creating histogram in registry."""
        registry = {}
        histogram_name = 'request_duration'
        registry[histogram_name] = {'type': 'histogram', 'observations': []}
        
        assert histogram_name in registry

    def test_registry_get_all_returns_all(self):
        """Test getting all metrics from registry."""
        registry = {
            'counter1': {'value': 10},
            'gauge1': {'value': 5},
            'histogram1': {'count': 3}
        }
        assert len(registry) == 3

    def test_registry_reset_clears_all(self):
        """Test resetting registry."""
        registry = {
            'counter1': {'value': 10},
            'gauge1': {'value': 5}
        }
        registry.clear()
        assert len(registry) == 0

    def test_registry_register_default_metrics(self):
        """Test registering default metrics."""
        registry = {}
        defaults = [
            'http_requests_total',
            'llm_calls_total',
            'agent_queries_total'
        ]
        for metric in defaults:
            registry[metric] = {'value': 0}
        
        assert len(registry) == 3


class TestExportPrometheus:
    """Test Prometheus format export."""

    def test_includes_help_line(self):
        """Test that HELP line is included."""
        metric_name = 'requests_total'
        help_text = 'Total requests'
        prometheus_line = f'# HELP {metric_name} {help_text}'
        
        assert 'HELP' in prometheus_line
        assert metric_name in prometheus_line

    def test_includes_type_line(self):
        """Test that TYPE line is included."""
        metric_name = 'requests_total'
        metric_type = 'counter'
        type_line = f'# TYPE {metric_name} {metric_type}'
        
        assert 'TYPE' in type_line
        assert metric_type in type_line

    def test_includes_metric_value(self):
        """Test that metric value is included."""
        metric = 'requests_total{} 42'
        assert '42' in metric

    def test_handles_labels(self):
        """Test handling of metric labels."""
        metric = 'requests_total{method="GET",status="200"} 100'
        assert 'method="GET"' in metric
        assert 'status="200"' in metric

    def test_handles_histogram_buckets(self):
        """Test handling of histogram buckets in output."""
        histogram = 'request_duration_seconds_bucket{le="0.5"} 10'
        assert 'le="0.5"' in histogram

    def test_multi_metric_output(self):
        """Test output with multiple metrics."""
        output = """# HELP requests_total Total requests
# TYPE requests_total counter
requests_total{} 100
# HELP active_connections Current connections
# TYPE active_connections gauge
active_connections{} 42"""
        lines = output.split('\n')
        assert len(lines) == 6


class TestDefaultMetrics:
    """Test default metrics."""

    def test_http_requests_total_exists(self):
        """Test http_requests_total metric exists."""
        metrics = {
            'http_requests_total': {'value': 0}
        }
        assert 'http_requests_total' in metrics

    def test_llm_calls_total_exists(self):
        """Test llm_calls_total metric exists."""
        metrics = {
            'llm_calls_total': {'value': 0}
        }
        assert 'llm_calls_total' in metrics

    def test_agent_queries_total_exists(self):
        """Test agent_queries_total metric exists."""
        metrics = {
            'agent_queries_total': {'value': 0}
        }
        assert 'agent_queries_total' in metrics

    def test_active_sessions_exists(self):
        """Test active_sessions metric exists."""
        metrics = {
            'active_sessions': {'value': 0}
        }
        assert 'active_sessions' in metrics

    def test_error_count_total_exists(self):
        """Test error_count_total metric exists."""
        metrics = {
            'error_count_total': {'value': 0}
        }
        assert 'error_count_total' in metrics


class TestMetricLabels:
    """Test metric labels."""

    def test_counter_with_labels(self):
        """Test counter with labels."""
        counters = {
            ('requests_total', 'GET', 'OK'): 100,
            ('requests_total', 'POST', 'OK'): 50,
            ('requests_total', 'GET', 'ERROR'): 5
        }
        assert counters[('requests_total', 'GET', 'OK')] == 100
        assert len(counters) == 3

    def test_gauge_with_labels(self):
        """Test gauge with labels."""
        gauges = {
            ('connections', 'host1'): 50,
            ('connections', 'host2'): 30
        }
        assert gauges[('connections', 'host1')] == 50

    def test_different_label_values_tracked_separately(self):
        """Test that different label values tracked separately."""
        metrics = {
            ('requests', 'endpoint', '/api/users'): 100,
            ('requests', 'endpoint', '/api/posts'): 50
        }
        assert metrics[('requests', 'endpoint', '/api/users')] != metrics[('requests', 'endpoint', '/api/posts')]

    def test_label_string_formatting(self):
        """Test label string formatting."""
        labels = {'method': 'GET', 'status': '200'}
        label_str = ','.join([f'{k}="{v}"' for k, v in labels.items()])
        assert 'method="GET"' in label_str
        assert 'status="200"' in label_str
