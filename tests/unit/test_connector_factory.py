"""Unit tests for runtime HRIS connector factory."""

from types import SimpleNamespace

from src.connectors.factory import (
    get_hris_connector,
    get_hris_connector_resolution,
    reset_hris_connector_cache,
)


def test_factory_uses_local_db_for_custom_db_provider(monkeypatch):
    """custom_db provider should resolve to local DB connector without fallback."""
    settings = SimpleNamespace(
        HRIS_PROVIDER="custom_db",
        BAMBOOHR_API_KEY="",
        BAMBOOHR_SUBDOMAIN="",
        WORKDAY_CLIENT_ID="",
        WORKDAY_CLIENT_SECRET="",
        WORKDAY_TENANT_URL="",
    )
    monkeypatch.setattr("src.connectors.factory.get_settings", lambda: settings)

    reset_hris_connector_cache()
    connector = get_hris_connector(force_refresh=True)
    resolution = get_hris_connector_resolution()

    assert connector.__class__.__name__ == "LocalDBConnector"
    assert resolution["requested_provider"] == "custom_db"
    assert resolution["resolved_provider"] == "local_db"
    assert resolution["using_fallback"] is False


def test_factory_falls_back_to_local_db_when_workday_missing_credentials(monkeypatch):
    """workday provider with missing credentials should fail safe to local DB."""
    settings = SimpleNamespace(
        HRIS_PROVIDER="workday",
        BAMBOOHR_API_KEY="",
        BAMBOOHR_SUBDOMAIN="",
        WORKDAY_CLIENT_ID="",
        WORKDAY_CLIENT_SECRET="",
        WORKDAY_TENANT_URL="",
    )
    monkeypatch.setattr("src.connectors.factory.get_settings", lambda: settings)

    reset_hris_connector_cache()
    connector = get_hris_connector(force_refresh=True)
    resolution = get_hris_connector_resolution()

    assert connector.__class__.__name__ == "LocalDBConnector"
    assert resolution["requested_provider"] == "workday"
    assert resolution["resolved_provider"] == "local_db"
    assert resolution["using_fallback"] is True
    assert "WORKDAY_CLIENT_ID" in resolution["fallback_reason"]


def test_factory_falls_back_when_bamboohr_health_check_fails(monkeypatch):
    """bamboohr provider should fail safe to local DB when health check fails."""
    settings = SimpleNamespace(
        HRIS_PROVIDER="bamboohr",
        BAMBOOHR_API_KEY="live-key",
        BAMBOOHR_SUBDOMAIN="company",
        WORKDAY_CLIENT_ID="",
        WORKDAY_CLIENT_SECRET="",
        WORKDAY_TENANT_URL="",
    )
    monkeypatch.setattr("src.connectors.factory.get_settings", lambda: settings)

    class StubBambooConnector:
        def __init__(self, api_key, subdomain):
            self.api_key = api_key
            self.subdomain = subdomain

        def health_check(self):
            return False

    monkeypatch.setattr("src.connectors.bamboohr.BambooHRConnector", StubBambooConnector)

    reset_hris_connector_cache()
    connector = get_hris_connector(force_refresh=True)
    resolution = get_hris_connector_resolution()

    assert connector.__class__.__name__ == "LocalDBConnector"
    assert resolution["requested_provider"] == "bamboohr"
    assert resolution["resolved_provider"] == "local_db"
    assert resolution["using_fallback"] is True
    assert "failed health check" in resolution["fallback_reason"]


def test_factory_keeps_bamboohr_when_health_check_passes(monkeypatch):
    """bamboohr provider should remain active when health check succeeds."""
    settings = SimpleNamespace(
        HRIS_PROVIDER="bamboohr",
        BAMBOOHR_API_KEY="live-key",
        BAMBOOHR_SUBDOMAIN="company",
        WORKDAY_CLIENT_ID="",
        WORKDAY_CLIENT_SECRET="",
        WORKDAY_TENANT_URL="",
    )
    monkeypatch.setattr("src.connectors.factory.get_settings", lambda: settings)

    class StubBambooConnector:
        def __init__(self, api_key, subdomain):
            self.api_key = api_key
            self.subdomain = subdomain

        def health_check(self):
            return True

    monkeypatch.setattr("src.connectors.bamboohr.BambooHRConnector", StubBambooConnector)

    reset_hris_connector_cache()
    connector = get_hris_connector(force_refresh=True)
    resolution = get_hris_connector_resolution()

    assert connector.__class__.__name__ == "StubBambooConnector"
    assert resolution["requested_provider"] == "bamboohr"
    assert resolution["resolved_provider"] == "bamboohr"
    assert resolution["using_fallback"] is False
