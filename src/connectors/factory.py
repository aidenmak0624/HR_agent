"""
HRIS connector factory for runtime provider selection.

Resolves the configured provider from settings and returns a connector
instance with safe local-db fallback when external credentials are absent
or initialization fails.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from config.settings import get_settings
from src.connectors.hris_interface import HRISConnector
from src.connectors.local_db import LocalDBConnector

logger = logging.getLogger(__name__)

_PLACEHOLDER_VALUES = {
    "",
    "not-set",
    "your-bamboohr-api-key",
    "your-company-subdomain",
    "your-workday-client-id",
    "your-workday-client-secret",
    "your-workday-tenant-url",
}

_cached_connector: Optional[HRISConnector] = None
_cached_resolution: Optional[Dict[str, Any]] = None


def _is_configured(value: Any) -> bool:
    """Return True when a config value is non-empty and not a placeholder."""
    text = str(value or "").strip()
    return bool(text) and text.lower() not in _PLACEHOLDER_VALUES


def _fallback_to_local_db(
    requested_provider: str, reason: str
) -> Tuple[HRISConnector, Dict[str, Any]]:
    """Build fallback connector metadata."""
    connector = LocalDBConnector()
    logger.warning(
        "HRIS provider '%s' is unavailable; falling back to LocalDBConnector. Reason: %s",
        requested_provider,
        reason,
    )
    return connector, {
        "requested_provider": requested_provider,
        "resolved_provider": "local_db",
        "connector_class": connector.__class__.__name__,
        "using_fallback": requested_provider not in {"custom_db", "local_db"},
        "fallback_reason": reason,
    }


def _validate_external_connector(
    connector: HRISConnector, requested_provider: str
) -> Optional[Tuple[HRISConnector, Dict[str, Any]]]:
    """Return fallback connector metadata when external provider is unhealthy."""
    try:
        if connector.health_check():
            return None
        reason = str(getattr(connector, "last_health_error", "") or "").strip()
        if not reason:
            reason = f"{requested_provider} connector failed health check."
        return _fallback_to_local_db(
            requested_provider,
            reason,
        )
    except Exception as exc:  # pragma: no cover - defensive path
        return _fallback_to_local_db(
            requested_provider,
            f"{requested_provider} health check raised: {exc}",
        )


def _create_connector() -> Tuple[HRISConnector, Dict[str, Any]]:
    """Create a connector from current settings with deterministic fallback."""
    settings = get_settings()
    requested_provider = str(getattr(settings, "HRIS_PROVIDER", "custom_db") or "custom_db").lower()

    if requested_provider in {"custom_db", "local_db"}:
        connector = LocalDBConnector()
        return connector, {
            "requested_provider": requested_provider,
            "resolved_provider": "local_db",
            "connector_class": connector.__class__.__name__,
            "using_fallback": False,
            "fallback_reason": "",
        }

    if requested_provider == "bamboohr":
        api_key = str(getattr(settings, "BAMBOOHR_API_KEY", "") or "").strip()
        subdomain = str(getattr(settings, "BAMBOOHR_SUBDOMAIN", "") or "").strip()
        if not (_is_configured(api_key) and _is_configured(subdomain)):
            return _fallback_to_local_db(
                requested_provider,
                "Missing BAMBOOHR_API_KEY or BAMBOOHR_SUBDOMAIN.",
            )
        try:
            from src.connectors.bamboohr import BambooHRConnector

            connector = BambooHRConnector(api_key=api_key, subdomain=subdomain)
            unhealthy_fallback = _validate_external_connector(connector, requested_provider)
            if unhealthy_fallback:
                return unhealthy_fallback
            return connector, {
                "requested_provider": requested_provider,
                "resolved_provider": "bamboohr",
                "connector_class": connector.__class__.__name__,
                "using_fallback": False,
                "fallback_reason": "",
            }
        except Exception as exc:  # pragma: no cover - defensive path
            return _fallback_to_local_db(requested_provider, str(exc))

    if requested_provider == "workday":
        client_id = str(getattr(settings, "WORKDAY_CLIENT_ID", "") or "").strip()
        client_secret = str(getattr(settings, "WORKDAY_CLIENT_SECRET", "") or "").strip()
        tenant_url = str(getattr(settings, "WORKDAY_TENANT_URL", "") or "").strip()
        if not (
            _is_configured(client_id)
            and _is_configured(client_secret)
            and _is_configured(tenant_url)
        ):
            return _fallback_to_local_db(
                requested_provider,
                "Missing WORKDAY_CLIENT_ID, WORKDAY_CLIENT_SECRET, or WORKDAY_TENANT_URL.",
            )
        try:
            from src.connectors.workday import WorkdayConnector

            connector = WorkdayConnector(
                client_id=client_id,
                client_secret=client_secret,
                tenant_url=tenant_url,
            )
            unhealthy_fallback = _validate_external_connector(connector, requested_provider)
            if unhealthy_fallback:
                return unhealthy_fallback
            return connector, {
                "requested_provider": requested_provider,
                "resolved_provider": "workday",
                "connector_class": connector.__class__.__name__,
                "using_fallback": False,
                "fallback_reason": "",
            }
        except Exception as exc:  # pragma: no cover - defensive path
            return _fallback_to_local_db(requested_provider, str(exc))

    return _fallback_to_local_db(
        requested_provider, f"Unsupported HRIS_PROVIDER '{requested_provider}'."
    )


def get_hris_connector(force_refresh: bool = False) -> HRISConnector:
    """Get active HRIS connector instance."""
    global _cached_connector, _cached_resolution

    if force_refresh or _cached_connector is None or _cached_resolution is None:
        _cached_connector, _cached_resolution = _create_connector()
    return _cached_connector


def get_hris_connector_resolution(force_refresh: bool = False) -> Dict[str, Any]:
    """Return metadata describing connector resolution and fallback behavior."""
    if force_refresh or _cached_resolution is None:
        get_hris_connector(force_refresh=force_refresh)
    return dict(_cached_resolution or {})


def reset_hris_connector_cache() -> None:
    """Clear connector cache (useful in tests after env changes)."""
    global _cached_connector, _cached_resolution
    _cached_connector = None
    _cached_resolution = None
