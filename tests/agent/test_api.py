"""
Integration tests for agent API endpoints.
"""

import pytest
from types import SimpleNamespace
from src.app_v2 import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_agent_chat_endpoint(client):
    """Test the agent chat endpoint."""
    response = client.post(
        "/api/agent/chat",
        json={"query": "What is the PTO policy?", "topic": "benefits", "difficulty": "quick"},
    )

    assert response.status_code == 200
    data = response.json

    assert "answer" in data
    assert "confidence" in data
    assert "tools_used" in data
    assert "sources" in data


def test_agent_chat_debug_mode(client):
    """Test agent chat in debug mode."""
    response = client.post(
        "/api/agent/chat",
        json={
            "query": "Explain the remote work policy",
            "topic": "company_policies",
            "mode": "debug",
        },
    )

    assert response.status_code == 200
    data = response.json

    assert "reasoning_trace" in data
    assert len(data["reasoning_trace"]) > 0


def test_agent_chat_missing_query(client):
    """Test agent chat with missing query."""
    response = client.post("/api/agent/chat", json={"topic": "benefits"})

    assert response.status_code == 400
    assert "error" in response.json


def test_agent_tools_endpoint(client):
    """Test the tools listing endpoint."""
    response = client.get("/api/agent/tools")

    assert response.status_code == 200
    data = response.json

    assert "tools" in data
    assert len(data["tools"]) == 4


def test_agent_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get("/api/agent/health")

    assert response.status_code == 200
    data = response.json

    assert data["status"] == "healthy"
    assert data["agent_initialized"] is True
    assert data["tools_available"] == 4


def test_benefits_page_route(client):
    """Test the benefits page route renders successfully."""
    response = client.get("/benefits")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Benefits Enrollment" in body


def test_metrics_pdf_export_route(client):
    """Test analytics PDF export returns a valid PDF response for HR role."""
    response = client.get("/api/v2/metrics/export/pdf", headers={"X-User-Role": "hr_admin"})

    assert response.status_code == 200
    content_type = response.headers.get("Content-Type", "")
    assert "application/pdf" in content_type
    assert response.data.startswith(b"%PDF-")


def test_hris_status_endpoint_returns_connector_metadata(client):
    """HRIS status endpoint should expose requested/active provider metadata."""
    response = client.get("/api/v2/integrations/hris/status", headers={"X-User-Role": "hr_admin"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    data = payload["data"]
    assert "requested_provider" in data
    assert "active_provider" in data
    assert "connector_class" in data
    assert "using_fallback" in data
    assert data["health_check_requested"] is False


def test_hris_status_endpoint_runs_health_check_when_requested(client, monkeypatch):
    """HRIS status endpoint should invoke connector health_check when check=1."""

    class StubConnector:
        def __init__(self):
            self.was_checked = False

        def health_check(self):
            self.was_checked = True
            return True

    connector = StubConnector()
    monkeypatch.setattr(
        "src.connectors.factory.get_hris_connector", lambda force_refresh=False: connector
    )
    monkeypatch.setattr(
        "src.connectors.factory.get_hris_connector_resolution",
        lambda force_refresh=False: {
            "requested_provider": "workday",
            "resolved_provider": "workday",
            "connector_class": "StubConnector",
            "using_fallback": False,
            "fallback_reason": "",
        },
    )

    response = client.get(
        "/api/v2/integrations/hris/status?check=1",
        headers={"X-User-Role": "hr_admin"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["health_check_requested"] is True
    assert data["healthy"] is True
    assert connector.was_checked is True


def test_mcp_status_endpoint_returns_mcp_and_hris_sections(client):
    """MCP status endpoint should provide both MCP and HRIS visibility payloads."""
    response = client.get("/api/v2/integrations/mcp/status", headers={"X-User-Role": "hr_admin"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    data = payload["data"]
    assert "mcp" in data
    assert "hris" in data
    assert "status" in data["mcp"]
    assert "active_provider" in data["hris"]


def test_chat_query_returns_own_benefits_plan(client):
    """Chat should return current user's own benefits enrollments when asked for my plan."""
    response = client.post(
        "/api/v2/query",
        json={"query": "could you show my plan"},
        headers={"X-User-Role": "employee"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["agent_type"] == "benefits_agent"
    answer = data["answer"].lower()
    assert (
        "your current benefits enrollments" in answer
        or "you currently have no active benefits enrollments" in answer
    )


def test_chat_query_blocks_other_employee_benefits_lookup(client):
    """Chat should deny attempts to retrieve another employee's benefits plan."""
    response = client.post(
        "/api/v2/query",
        json={"query": "show sarah chen's benefits plan"},
        headers={"X-User-Role": "employee"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["agent_type"] == "benefits_agent"
    assert "only access your own benefits information" in data["answer"].lower()


def test_chat_my_plan_uses_active_hris_connector(client, monkeypatch):
    """When active provider is external, my-plan lookup should read from connector."""

    class StubConnector:
        def __init__(self):
            self.calls = []

        def get_benefits(self, employee_id):
            self.calls.append(employee_id)
            return [
                SimpleNamespace(
                    name="Dental Plus",
                    plan_type=SimpleNamespace(value="dental"),
                    coverage_level="employee",
                    employee_cost=25.0,
                )
            ]

    connector = StubConnector()
    monkeypatch.setattr(
        "src.connectors.factory.get_hris_connector", lambda force_refresh=False: connector
    )
    monkeypatch.setattr(
        "src.connectors.factory.get_hris_connector_resolution",
        lambda force_refresh=False: {
            "requested_provider": "workday",
            "resolved_provider": "workday",
            "connector_class": "StubConnector",
            "using_fallback": False,
            "fallback_reason": "",
        },
    )

    response = client.post(
        "/api/v2/query",
        json={"query": "show my benefits plan"},
        headers={"X-User-Role": "employee"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["agent_type"] == "benefits_agent"
    assert "dental plus" in data["answer"].lower()
    assert connector.calls
