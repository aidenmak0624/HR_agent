"""
Comprehensive test suite for HR Platform Implementation Phases 1-4.

Covers:
  - Unit tests: Event bus, database models, router agent
  - Integration tests: API endpoints with real DB, event bus persistence
  - System tests: End-to-end leave workflow, cross-component data flow
  - UI-facing tests: API contract validation for frontend consumption

Run: pytest tests/test_implementation_phases.py -v
"""

import os
import sys
import json
import time
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")
os.environ.setdefault("HR_DB_PATH", "/tmp/hr_test_phases.db")


# ═══════════════════════════════════════════════════════════════
# UNIT TESTS
# ═══════════════════════════════════════════════════════════════


class TestEventBusUnit:
    """Unit tests for the EventBus singleton pub/sub system."""

    def setup_method(self):
        from src.core.event_bus import EventBus

        EventBus.reset()

    def test_singleton_pattern(self):
        """EventBus.instance() returns the same object on repeated calls."""
        from src.core.event_bus import EventBus

        bus1 = EventBus.instance()
        bus2 = EventBus.instance()
        assert bus1 is bus2

    def test_reset_creates_new_instance(self):
        """EventBus.reset() allows a fresh instance to be created."""
        from src.core.event_bus import EventBus

        bus1 = EventBus.instance()
        EventBus.reset()
        bus2 = EventBus.instance()
        assert bus1 is not bus2

    def test_subscribe_and_publish(self):
        """Subscribed handlers are called when events are published."""
        from src.core.event_bus import EventBus, Event

        bus = EventBus.instance()
        received = []
        bus.subscribe("test.event", lambda e: received.append(e))
        event = Event(type="test.event", source="test", payload={"key": "value"})
        bus.publish(event)
        assert len(received) == 1
        assert received[0].type == "test.event"
        assert received[0].payload == {"key": "value"}

    def test_wildcard_subscriber(self):
        """A '*' subscriber receives all event types."""
        from src.core.event_bus import EventBus, Event

        bus = EventBus.instance()
        received = []
        bus.subscribe("*", lambda e: received.append(e.type))
        bus.publish(Event(type="a", source="test"))
        bus.publish(Event(type="b", source="test"))
        assert received == ["a", "b"]

    def test_unsubscribe(self):
        """Unsubscribed handlers no longer receive events."""
        from src.core.event_bus import EventBus, Event

        bus = EventBus.instance()
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)
        bus.publish(Event(type="test.event", source="test"))
        assert len(received) == 0

    def test_max_depth_prevents_cascade(self):
        """Recursive event publishing is stopped at MAX_DEPTH."""
        from src.core.event_bus import EventBus, Event

        bus = EventBus.instance()
        depths = []

        def recursive_handler(e):
            depths.append(bus._publishing_depth)
            bus.publish(Event(type="cascade", source="test"))

        bus.subscribe("cascade", recursive_handler)
        bus.publish(Event(type="cascade", source="test"))
        # Should stop at MAX_DEPTH (3)
        assert len(depths) == EventBus.MAX_DEPTH

    def test_handler_error_doesnt_break_bus(self):
        """A failing handler doesn't prevent other handlers from running."""
        from src.core.event_bus import EventBus, Event

        bus = EventBus.instance()
        results = []

        def bad_handler(e):
            raise ValueError("intentional error")

        def good_handler(e):
            results.append("ok")

        bus.subscribe("test", bad_handler)
        bus.subscribe("test", good_handler)
        bus.publish(Event(type="test", source="test"))
        assert results == ["ok"]

    def test_event_has_correlation_id(self):
        """Each event automatically gets a correlation ID."""
        from src.core.event_bus import Event

        e1 = Event(type="test", source="test")
        e2 = Event(type="test", source="test")
        assert e1.correlation_id
        assert e2.correlation_id
        assert e1.correlation_id != e2.correlation_id

    def test_get_recent_events(self):
        """get_recent_events returns published events in order."""
        from src.core.event_bus import EventBus, Event

        bus = EventBus.instance()
        for i in range(5):
            bus.publish(Event(type=f"event.{i}", source="test"))
        recent = bus.get_recent_events()
        assert len(recent) == 5
        assert recent[0].type == "event.0"
        assert recent[4].type == "event.4"

    def test_get_recent_events_filtered(self):
        """get_recent_events can filter by event type."""
        from src.core.event_bus import EventBus, Event

        bus = EventBus.instance()
        bus.publish(Event(type="leave.submitted", source="test"))
        bus.publish(Event(type="leave.approved", source="test"))
        bus.publish(Event(type="leave.submitted", source="test"))
        filtered = bus.get_recent_events(event_type="leave.submitted")
        assert len(filtered) == 2

    def test_get_stats(self):
        """get_stats returns correct event counts."""
        from src.core.event_bus import EventBus, Event

        bus = EventBus.instance()
        bus.publish(Event(type="a", source="test"))
        bus.publish(Event(type="a", source="test"))
        bus.publish(Event(type="b", source="test"))
        stats = bus.get_stats()
        assert stats["total_events"] == 3
        assert stats["event_types"]["a"] == 2
        assert stats["event_types"]["b"] == 1

    def test_all_event_type_constants_defined(self):
        """All expected event type constants are defined."""
        from src.core import event_bus

        expected = [
            "LEAVE_SUBMITTED",
            "LEAVE_APPROVED",
            "LEAVE_REJECTED",
            "EMPLOYEE_ONBOARDED",
            "REVIEW_COMPLETED",
            "BENEFITS_ENROLLED",
            "POLICY_UPDATED",
            "GOAL_COMPLETED",
        ]
        for const in expected:
            assert hasattr(event_bus, const), f"Missing constant: {const}"


class TestDatabaseModelsUnit:
    """Unit tests for new SQLAlchemy models."""

    def test_benefits_plan_model_exists(self):
        from src.core.database import BenefitsPlan

        assert BenefitsPlan.__tablename__ == "benefits_plans"

    def test_benefits_enrollment_model_exists(self):
        from src.core.database import BenefitsEnrollment

        assert BenefitsEnrollment.__tablename__ == "benefits_enrollments"

    def test_onboarding_checklist_model_exists(self):
        from src.core.database import OnboardingChecklist

        assert OnboardingChecklist.__tablename__ == "onboarding_checklists"

    def test_performance_review_model_exists(self):
        from src.core.database import PerformanceReview

        assert PerformanceReview.__tablename__ == "performance_reviews"

    def test_performance_goal_model_exists(self):
        from src.core.database import PerformanceGoal

        assert PerformanceGoal.__tablename__ == "performance_goals"

    def test_event_log_model_exists(self):
        from src.core.database import EventLog

        assert EventLog.__tablename__ == "event_log"


class TestRouterAgentUnit:
    """Unit tests for the refactored RouterAgent."""

    def test_leave_request_in_intent_categories(self):
        from src.agents.router_agent import RouterAgent

        assert "leave_request" in RouterAgent.INTENT_CATEGORIES

    def test_leave_request_in_agent_registry(self):
        from src.agents.router_agent import RouterAgent

        assert "leave_request" in RouterAgent.AGENT_REGISTRY
        assert RouterAgent.AGENT_REGISTRY["leave_request"] == "LeaveRequestAgent"

    def test_analytics_maps_to_performance(self):
        """Analytics intent now maps to PerformanceAgent (no standalone analytics agent)."""
        from src.agents.router_agent import RouterAgent

        assert RouterAgent.AGENT_REGISTRY["analytics"] == "PerformanceAgent"

    def test_classify_leave_request_intent(self):
        """Leave request keywords are classified correctly."""
        from src.agents.router_agent import RouterAgent

        router = RouterAgent(llm=None)
        intent, confidence = router.classify_intent("I want to request leave for next week")
        assert intent in ("leave_request", "leave")

    def test_classify_benefits_intent(self):
        from src.agents.router_agent import RouterAgent

        router = RouterAgent(llm=None)
        intent, confidence = router.classify_intent("What health insurance plans are available?")
        assert intent == "benefits"

    def test_rbac_all_roles_have_hr_admin(self):
        """hr_admin should have access to all intent types."""
        from src.agents.router_agent import RouterAgent

        router = RouterAgent(llm=None)
        ctx = {"role": "hr_admin", "user_id": "hr-001"}
        for intent in RouterAgent.INTENT_CATEGORIES:
            result = router.check_permissions(ctx, intent)
            assert result, f"hr_admin should have access to {intent}"


# ═══════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════


class TestDatabaseIntegration:
    """Integration tests: models + database + seed data."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Initialize a fresh test database."""
        test_db = "/tmp/hr_test_integration.db"
        if os.path.exists(test_db):
            os.remove(test_db)
        os.environ["HR_DB_PATH"] = test_db

        # Re-import to pick up new path
        import importlib
        import src.core.database as db_mod

        importlib.reload(db_mod)

        db_mod.init_db()
        db_mod.seed_demo_data()
        self.SessionLocal = db_mod.SessionLocal
        self.db = db_mod
        yield
        if os.path.exists(test_db):
            os.remove(test_db)

    def test_seed_creates_employees(self):
        session = self.SessionLocal()
        count = session.query(self.db.Employee).count()
        session.close()
        assert count >= 3

    def test_seed_creates_benefits_plans(self):
        session = self.SessionLocal()
        plans = session.query(self.db.BenefitsPlan).all()
        session.close()
        assert len(plans) == 5
        types = {p.plan_type for p in plans}
        assert "medical" in types
        assert "dental" in types
        assert "vision" in types
        assert "retirement" in types

    def test_seed_creates_enrollments(self):
        session = self.SessionLocal()
        count = session.query(self.db.BenefitsEnrollment).count()
        session.close()
        assert count >= 2

    def test_seed_creates_onboarding_checklist(self):
        session = self.SessionLocal()
        tasks = session.query(self.db.OnboardingChecklist).all()
        session.close()
        assert len(tasks) == 8
        completed = [t for t in tasks if t.status == "completed"]
        pending = [t for t in tasks if t.status == "pending"]
        assert len(completed) == 4
        assert len(pending) == 4

    def test_seed_creates_performance_reviews(self):
        session = self.SessionLocal()
        reviews = session.query(self.db.PerformanceReview).all()
        session.close()
        assert len(reviews) >= 1
        assert reviews[0].rating in range(1, 6)

    def test_seed_creates_performance_goals(self):
        session = self.SessionLocal()
        goals = session.query(self.db.PerformanceGoal).all()
        session.close()
        assert len(goals) >= 3
        for goal in goals:
            assert 0 <= goal.progress_pct <= 100

    def test_event_log_persistence(self):
        """Events published via EventBus are persisted to the EventLog table."""
        from src.core.event_bus import EventBus, Event, LEAVE_SUBMITTED

        EventBus.reset()
        bus = EventBus.instance()
        bus.publish(
            Event(
                type=LEAVE_SUBMITTED,
                source="test",
                payload={"employee_id": "1", "leave_type": "vacation"},
            )
        )
        session = self.SessionLocal()
        logs = session.query(self.db.EventLog).all()
        session.close()
        assert len(logs) >= 1
        assert logs[0].event_type == "leave.submitted"
        assert logs[0].source == "test"
        assert "employee_id" in (logs[0].payload or {})

    def test_seed_idempotent(self):
        """Calling seed_demo_data twice doesn't duplicate data."""
        self.db.seed_demo_data()  # Second call
        session = self.SessionLocal()
        plans = session.query(self.db.BenefitsPlan).count()
        session.close()
        assert plans == 5  # Not 10


# ═══════════════════════════════════════════════════════════════
# SYSTEM TESTS (API level, end-to-end)
# ═══════════════════════════════════════════════════════════════


class TestAPISystem:
    """System tests: full API request/response cycle against running server.

    These test the API contract the frontend relies on.
    Requires the server to be running on port 5050.
    """

    BASE = "http://localhost:5050/api/v2"
    EMPLOYEE_HEADERS = {
        "Authorization": "Bearer demo-token-employee",
        "X-User-Role": "employee",
        "Content-Type": "application/json",
    }
    MANAGER_HEADERS = {
        "Authorization": "Bearer demo-token-manager",
        "X-User-Role": "manager",
        "Content-Type": "application/json",
    }
    HR_HEADERS = {
        "Authorization": "Bearer demo-token-hr_admin",
        "X-User-Role": "hr_admin",
        "Content-Type": "application/json",
    }

    @pytest.fixture(autouse=True)
    def check_server(self):
        """Skip system tests if server isn't running."""
        import urllib.request

        try:
            urllib.request.urlopen("http://localhost:5050/", timeout=2)
        except Exception:
            pytest.skip("Server not running on port 5050")

    def _get(self, path, headers=None):
        import urllib.request

        req = urllib.request.Request(f"{self.BASE}{path}", headers=headers or self.EMPLOYEE_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()), resp.status

    def _post(self, path, data, headers=None):
        import urllib.request

        body = json.dumps(data).encode()
        req = urllib.request.Request(
            f"{self.BASE}{path}", data=body, headers=headers or self.EMPLOYEE_HEADERS, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read()), resp.status
        except urllib.error.HTTPError as e:
            return json.loads(e.read()), e.code

    # --- Phase 1: Profile & Employee endpoints ---

    def test_get_profile_returns_employee(self):
        data, status = self._get("/profile")
        assert status == 200
        assert data["success"] is True
        assert "first_name" in data["data"]
        assert "email" in data["data"]

    def test_get_employees_requires_hr_admin(self):
        """Non-admin users get 403 on /employees."""
        import urllib.request, urllib.error

        req = urllib.request.Request(f"{self.BASE}/employees", headers=self.EMPLOYEE_HEADERS)
        try:
            urllib.request.urlopen(req, timeout=10)
            assert False, "Should have returned 403"
        except urllib.error.HTTPError as e:
            assert e.code == 403

    def test_get_employees_as_hr_admin(self):
        data, status = self._get("/employees", headers=self.HR_HEADERS)
        assert status == 200
        assert data["success"] is True
        assert len(data["data"]) > 0

    # --- Phase 2: Benefits, Onboarding, Performance endpoints ---

    def test_benefits_plans_returns_list(self):
        data, status = self._get("/benefits/plans")
        assert status == 200
        assert data["success"] is True
        plans = data["data"]
        assert len(plans) >= 5
        assert all("name" in p and "plan_type" in p and "premium_monthly" in p for p in plans)

    def test_benefits_enrollments_returns_user_data(self):
        data, status = self._get("/benefits/enrollments")
        assert status == 200
        assert data["success"] is True
        for enrollment in data["data"]:
            assert "plan_name" in enrollment
            assert "status" in enrollment

    def test_onboarding_checklist(self):
        data, status = self._get("/onboarding/checklist")
        assert status == 200
        assert data["success"] is True
        tasks = data["data"]
        assert len(tasks) >= 1
        for task in tasks:
            assert "task_name" in task
            assert "status" in task
            assert task["status"] in ("completed", "pending", "in_progress")

    def test_performance_reviews(self):
        data, status = self._get("/performance/reviews")
        assert status == 200
        assert data["success"] is True
        for review in data["data"]:
            assert "review_period" in review
            assert "rating" in review
            assert 1 <= review["rating"] <= 5

    def test_performance_goals(self):
        data, status = self._get("/performance/goals")
        assert status == 200
        assert data["success"] is True
        for goal in data["data"]:
            assert "title" in goal
            assert "progress_pct" in goal
            assert 0 <= goal["progress_pct"] <= 100

    # --- Phase 3: Event bus endpoints ---

    def test_events_endpoint_returns_list(self):
        data, status = self._get("/events")
        assert status == 200
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_leave_submit_creates_event(self):
        """Submitting a leave request creates a leave.submitted event."""
        # Submit leave
        leave_data = {
            "leave_type": "sick",
            "start_date": "2026-04-01",
            "end_date": "2026-04-02",
            "reason": "Test event creation",
        }
        resp, status = self._post("/leave/request", leave_data)
        assert status == 201
        assert resp["success"] is True

        # Check events
        events_data, _ = self._get("/events")
        event_types = [e["event_type"] for e in events_data["data"]]
        assert "leave.submitted" in event_types

    def test_approve_creates_event(self):
        """Approving a leave request creates a leave.approved event."""
        # Submit
        leave_data = {
            "leave_type": "vacation",
            "start_date": "2026-05-01",
            "end_date": "2026-05-02",
            "reason": "test",
        }
        resp, status = self._post("/leave/request", leave_data)
        assert status == 201
        req_id = resp["data"]["request_id"]

        # Approve
        approve_resp, approve_status = self._post(
            "/workflows/approve", {"request_id": req_id}, headers=self.MANAGER_HEADERS
        )
        assert approve_status == 200

        # Check events
        events_data, _ = self._get("/events")
        event_types = [e["event_type"] for e in events_data["data"]]
        assert "leave.approved" in event_types

    # --- Cross-cutting: API contract for frontend ---

    def test_all_responses_have_standard_shape(self):
        """Every endpoint returns {success, data} at minimum."""
        endpoints = [
            "/profile",
            "/benefits/plans",
            "/benefits/enrollments",
            "/onboarding/checklist",
            "/performance/reviews",
            "/performance/goals",
            "/events",
            "/metrics",
        ]
        for ep in endpoints:
            data, status = self._get(ep)
            assert "success" in data, f"{ep} missing 'success'"
            assert "data" in data, f"{ep} missing 'data'"
            assert data["success"] is True, f"{ep} returned success=False"

    def test_leave_history_after_submit(self):
        """After submitting leave, it appears in the history."""
        # Submit
        self._post(
            "/leave/request",
            {
                "leave_type": "personal",
                "start_date": "2026-06-01",
                "end_date": "2026-06-01",
                "reason": "history test",
            },
        )
        # Check history
        data, status = self._get("/leave/history")
        assert status == 200
        requests_in_history = data["data"].get("history", [])
        assert len(requests_in_history) >= 1

    def test_metrics_returns_department_data(self):
        """Metrics endpoint returns data the dashboard needs."""
        data, status = self._get("/metrics")
        assert status == 200
        assert data["success"] is True
        # Should have total_employees or similar
        metrics = data["data"]
        assert isinstance(metrics, dict)


# ═══════════════════════════════════════════════════════════════
# UI CONTRACT TESTS
# ═══════════════════════════════════════════════════════════════


class TestUIContracts:
    """Tests that validate the API returns data in the shape the frontend JS expects.

    These ensure that frontend code (dashboard.js, leave.js, etc.) will work
    with the API responses without modification.
    """

    BASE = "http://localhost:5050/api/v2"
    HEADERS = {
        "Authorization": "Bearer demo-token-employee",
        "X-User-Role": "employee",
    }

    @pytest.fixture(autouse=True)
    def check_server(self):
        import urllib.request

        try:
            urllib.request.urlopen("http://localhost:5050/", timeout=2)
        except Exception:
            pytest.skip("Server not running on port 5050")

    def _get(self, path):
        import urllib.request

        req = urllib.request.Request(f"{self.BASE}{path}", headers=self.HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def test_benefits_plan_has_frontend_fields(self):
        """Frontend benefits.js expects: id, name, plan_type, premium_monthly, coverage_details."""
        data = self._get("/benefits/plans")
        for plan in data["data"]:
            assert "id" in plan
            assert "name" in plan
            assert "plan_type" in plan
            assert "premium_monthly" in plan
            assert isinstance(plan["premium_monthly"], (int, float))
            assert "coverage_details" in plan

    def test_onboarding_task_has_status_field(self):
        """Frontend expects status to be one of: completed, pending, in_progress."""
        data = self._get("/onboarding/checklist")
        valid_statuses = {"completed", "pending", "in_progress"}
        for task in data["data"]:
            assert task["status"] in valid_statuses, f"Invalid status: {task['status']}"

    def test_performance_goal_has_progress_field(self):
        """Frontend renders a progress bar from 0-100."""
        data = self._get("/performance/goals")
        for goal in data["data"]:
            assert isinstance(goal["progress_pct"], int)
            assert 0 <= goal["progress_pct"] <= 100

    def test_events_have_timestamp(self):
        """Frontend activity feed needs created_at for display."""
        data = self._get("/events")
        for event in data["data"]:
            assert "created_at" in event
            assert "event_type" in event
            assert "source" in event

    def test_profile_has_role_and_department(self):
        """Frontend role switcher relies on role_level and department."""
        data = self._get("/profile")
        profile = data["data"]
        assert "role_level" in profile or "role" in profile
        assert "department" in profile
        assert "first_name" in profile
        assert "last_name" in profile


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
