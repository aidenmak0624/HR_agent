"""Unit tests for BambooHR connector health-check behavior."""

from src.connectors.bamboohr import BambooHRConnector
from src.connectors.hris_interface import AuthenticationError, NotFoundError


def test_health_check_uses_directory_endpoint_first(monkeypatch):
    """Health check should succeed when /employees/directory responds."""
    connector = BambooHRConnector(api_key="test-key", subdomain="testco")
    calls = []

    def fake_make_request(method, endpoint, **kwargs):
        calls.append((method, endpoint))
        return {}

    monkeypatch.setattr(connector, "_make_request", fake_make_request)

    assert connector.health_check() is True
    assert calls[0] == ("GET", "/employees/directory")


def test_health_check_falls_back_to_meta_fields_on_not_found(monkeypatch):
    """If directory endpoint is missing, health check should try /meta/fields."""
    connector = BambooHRConnector(api_key="test-key", subdomain="testco")
    calls = []

    def fake_make_request(method, endpoint, **kwargs):
        calls.append((method, endpoint))
        if endpoint == "/employees/directory":
            raise NotFoundError("missing")
        return {}

    monkeypatch.setattr(connector, "_make_request", fake_make_request)

    assert connector.health_check() is True
    assert calls == [("GET", "/employees/directory"), ("GET", "/meta/fields")]


def test_health_check_returns_false_on_authentication_error(monkeypatch):
    """Auth failures should make health check fail."""
    connector = BambooHRConnector(api_key="test-key", subdomain="testco")

    def fake_make_request(method, endpoint, **kwargs):
        raise AuthenticationError("invalid key")

    monkeypatch.setattr(connector, "_make_request", fake_make_request)

    assert connector.health_check() is False
