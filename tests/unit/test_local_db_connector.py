"""Unit tests for LocalDB connector behavior."""

from src.connectors.local_db import LocalDBConnector


def test_local_db_health_check_returns_true(monkeypatch):
    """LocalDB health check should validate SQL execution successfully."""

    class FakeSession:
        def execute(self, stmt):
            return stmt

        def close(self):
            return None

    connector = LocalDBConnector()
    monkeypatch.setattr(connector, "_get_session", lambda: FakeSession())

    assert connector.health_check() is True
