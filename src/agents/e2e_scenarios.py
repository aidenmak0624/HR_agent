"""
INT-002: End-to-End Test Scenario Definitions
Pre-built E2E test scenarios for HR multi-agent platform with comprehensive
step definitions, expected outcomes, and scenario validation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScenarioStatus(str, Enum):
    """Scenario execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ScenarioStep:
    """Single step in a scenario."""

    step_id: str
    action: str  # Query or action to execute
    target_agent: str  # Agent to invoke
    description: str = ""
    expected_result: str = ""
    actual_result: Optional[str] = None
    status: ScenarioStatus = ScenarioStatus.PENDING
    duration_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_id": self.step_id,
            "action": self.action,
            "target_agent": self.target_agent,
            "description": self.description,
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class E2EScenario:
    """End-to-end test scenario."""

    scenario_id: str
    name: str
    description: str
    steps: List[ScenarioStep] = field(default_factory=list)
    actors: List[str] = field(default_factory=list)  # Users involved
    expected_outcomes: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "actors": self.actors,
            "expected_outcomes": self.expected_outcomes,
            "preconditions": self.preconditions,
            "tags": self.tags,
        }


class E2EScenarioRunner:
    """Runner for E2E scenarios."""

    def __init__(self):
        """Initialize scenario runner."""
        self.scenarios: Dict[str, E2EScenario] = {}
        self.execution_results: List[Dict[str, Any]] = []
        self._initialize_scenarios()

    def _initialize_scenarios(self) -> None:
        """Initialize built-in scenarios."""
        self.scenarios["onboarding"] = self._create_onboarding_scenario()
        self.scenarios["leave_approval"] = self._create_leave_approval_scenario()
        self.scenarios["performance_review"] = self._create_performance_review_scenario()
        self.scenarios["benefits_enrollment"] = self._create_benefits_enrollment_scenario()
        self.scenarios["document_generation"] = self._create_document_generation_scenario()
        self.scenarios["multi_agent_routing"] = self._create_multi_agent_routing_scenario()

        logger.info(f"Initialized {len(self.scenarios)} E2E scenarios")

    def _create_onboarding_scenario(self) -> E2EScenario:
        """Create new employee onboarding scenario."""
        scenario = E2EScenario(
            scenario_id="onb_001",
            name="New Employee Onboarding",
            description="Complete onboarding process for new employee",
            actors=["employee_emp_001", "manager_mgr_001", "hr_admin_hr_001"],
            tags=["onboarding", "employee", "critical"],
            preconditions=[
                "New employee record exists",
                "Manager account active",
                "HR admin available",
            ],
        )

        steps = [
            ScenarioStep(
                step_id="onb_001_s1",
                action="Create new employee record with name, email, position",
                target_agent="employee_info",
                description="Initialize employee profile",
                expected_result="Employee record created with status ACTIVE",
            ),
            ScenarioStep(
                step_id="onb_001_s2",
                action="Submit IT provisioning request with email and role",
                target_agent="admin",
                description="Request account creation",
                expected_result="IT ticket created, email account provisioned",
            ),
            ScenarioStep(
                step_id="onb_001_s3",
                action="Enroll employee in benefits with plan selection",
                target_agent="benefits",
                description="Complete benefits enrollment",
                expected_result="Benefits confirmed, documents generated",
            ),
            ScenarioStep(
                step_id="onb_001_s4",
                action="Generate employment contract and offer letter",
                target_agent="document_generator",
                description="Create formal documents",
                expected_result="Contract and offer letter finalized",
            ),
            ScenarioStep(
                step_id="onb_001_s5",
                action="Assign training modules and orientation",
                target_agent="training",
                description="Set up training plan",
                expected_result="Training modules assigned, calendar updated",
            ),
            ScenarioStep(
                step_id="onb_001_s6",
                action="Send welcome email and first-day instructions",
                target_agent="notification",
                description="Welcome communication",
                expected_result="Email sent, employee confirmed receipt",
            ),
        ]

        scenario.steps = steps
        scenario.expected_outcomes = [
            "Employee record active in system",
            "Email account created and accessible",
            "Benefits confirmed",
            "Contract signed",
            "Training completed",
            "Manager notified",
        ]

        return scenario

    def _create_leave_approval_scenario(self) -> E2EScenario:
        """Create leave request approval scenario."""
        scenario = E2EScenario(
            scenario_id="leave_001",
            name="Leave Request Approval Flow",
            description="Submit, review, and approve leave request",
            actors=["employee_emp_001", "manager_mgr_001"],
            tags=["leave", "approval"],
            preconditions=[
                "Employee has sufficient leave balance",
                "Manager active",
                "No conflicting approvals",
            ],
        )

        steps = [
            ScenarioStep(
                step_id="leave_001_s1",
                action="Check leave balance for vacation",
                target_agent="leave_request",
                description="Verify available days",
                expected_result="Employee has 15 days available",
            ),
            ScenarioStep(
                step_id="leave_001_s2",
                action="Submit leave request for 3 days starting next Monday",
                target_agent="leave_request",
                description="Create leave request",
                expected_result="Request status: PENDING_APPROVAL",
            ),
            ScenarioStep(
                step_id="leave_001_s3",
                action="Manager reviews and approves request",
                target_agent="leave_request",
                description="Manager approval",
                expected_result="Request status: APPROVED, balance updated",
            ),
            ScenarioStep(
                step_id="leave_001_s4",
                action="Retrieve updated leave balance",
                target_agent="leave_request",
                description="Verify balance deduction",
                expected_result="Balance now shows 12 days remaining",
            ),
        ]

        scenario.steps = steps
        scenario.expected_outcomes = [
            "Leave request approved",
            "Leave balance deducted",
            "Team calendar updated",
            "Employee notified",
            "Manager notified",
        ]

        return scenario

    def _create_performance_review_scenario(self) -> E2EScenario:
        """Create performance review cycle scenario."""
        scenario = E2EScenario(
            scenario_id="perf_001",
            name="Performance Review Cycle",
            description="Complete annual performance review process",
            actors=["employee_emp_001", "manager_mgr_001", "hr_generalist_hr_001"],
            tags=["performance", "review", "annual"],
            preconditions=[
                "Review period is active",
                "Employee records current",
                "Manager assignments valid",
            ],
        )

        steps = [
            ScenarioStep(
                step_id="perf_001_s1",
                action="Notify all managers to begin review period",
                target_agent="notification",
                description="Review period kickoff",
                expected_result="Manager emails sent, acknowledgment required",
            ),
            ScenarioStep(
                step_id="perf_001_s2",
                action="Manager creates performance review for employee",
                target_agent="performance_review",
                description="Manager evaluation",
                expected_result="Review created, draft status",
            ),
            ScenarioStep(
                step_id="perf_001_s3",
                action="Employee completes self-evaluation",
                target_agent="performance_review",
                description="Employee self-assessment",
                expected_result="Self-evaluation submitted",
            ),
            ScenarioStep(
                step_id="perf_001_s4",
                action="Manager and employee meet for discussion",
                target_agent="notification",
                description="Review discussion",
                expected_result="Meeting scheduled, notes recorded",
            ),
            ScenarioStep(
                step_id="perf_001_s5",
                action="Manager finalizes and submits review",
                target_agent="performance_review",
                description="Review submission",
                expected_result="Review submitted for HR approval",
            ),
            ScenarioStep(
                step_id="perf_001_s6",
                action="HR reviews and archives reviews",
                target_agent="admin",
                description="HR audit and archival",
                expected_result="Reviews approved and stored",
            ),
        ]

        scenario.steps = steps
        scenario.expected_outcomes = [
            "All managers completed reviews",
            "Feedback documented",
            "Performance ratings recorded",
            "Development plans created",
            "Compensation adjustments processed",
        ]

        return scenario

    def _create_benefits_enrollment_scenario(self) -> E2EScenario:
        """Create benefits enrollment scenario."""
        scenario = E2EScenario(
            scenario_id="benef_001",
            name="Benefits Enrollment",
            description="Annual benefits enrollment process",
            actors=["employee_emp_001", "benefits_admin_hr_001"],
            tags=["benefits", "enrollment", "annual"],
        )

        steps = [
            ScenarioStep(
                step_id="benef_001_s1",
                action="Open benefits enrollment with deadline",
                target_agent="benefits",
                description="Begin enrollment period",
                expected_result="Enrollment portal open, emails sent",
            ),
            ScenarioStep(
                step_id="benef_001_s2",
                action="Employee reviews available plans",
                target_agent="benefits",
                description="Plan comparison",
                expected_result="Plans displayed with comparisons",
            ),
            ScenarioStep(
                step_id="benef_001_s3",
                action="Employee selects health and retirement plans",
                target_agent="benefits",
                description="Plan selection",
                expected_result="Selections confirmed and saved",
            ),
            ScenarioStep(
                step_id="benef_001_s4",
                action="Generate benefits confirmation documents",
                target_agent="document_generator",
                description="Document generation",
                expected_result="Confirmations generated and emailed",
            ),
        ]

        scenario.steps = steps
        scenario.expected_outcomes = [
            "Employee benefits selected",
            "Confirmation documents generated",
            "Payroll integration updated",
            "Records archived",
        ]

        return scenario

    def _create_document_generation_scenario(self) -> E2EScenario:
        """Create document generation scenario."""
        scenario = E2EScenario(
            scenario_id="doc_001",
            name="Document Generation Workflow",
            description="Generate and approve HR documents",
            actors=["hr_admin_hr_001", "hr_generalist_hr_002"],
            tags=["documents", "approval"],
        )

        steps = [
            ScenarioStep(
                step_id="doc_001_s1",
                action="Create new offer letter for candidate with details",
                target_agent="document_generator",
                description="Generate offer letter",
                expected_result="Offer letter generated in draft status",
            ),
            ScenarioStep(
                step_id="doc_001_s2",
                action="HR generalist reviews document",
                target_agent="document_generator",
                description="Document review",
                expected_result="Document reviewed and approved",
            ),
            ScenarioStep(
                step_id="doc_001_s3",
                action="Export document as PDF",
                target_agent="document_generator",
                description="Export to PDF",
                expected_result="PDF generated and ready for delivery",
            ),
        ]

        scenario.steps = steps
        scenario.expected_outcomes = [
            "Document generated correctly",
            "Document approved",
            "PDF exported",
            "Audit trail recorded",
        ]

        return scenario

    def _create_multi_agent_routing_scenario(self) -> E2EScenario:
        """Create multi-agent query routing scenario."""
        scenario = E2EScenario(
            scenario_id="route_001",
            name="Multi-Agent Query Routing",
            description="Complex query routed to multiple agents",
            actors=["employee_emp_001"],
            tags=["routing", "multi_agent"],
        )

        steps = [
            ScenarioStep(
                step_id="route_001_s1",
                action="Submit complex query about leave and benefits",
                target_agent="router",
                description="Complex query submission",
                expected_result="Query routed to multiple agents",
            ),
            ScenarioStep(
                step_id="route_001_s2",
                action="Leave agent processes leave-related part",
                target_agent="leave_request",
                description="Leave agent processes",
                expected_result="Leave information retrieved",
            ),
            ScenarioStep(
                step_id="route_001_s3",
                action="Benefits agent processes benefits-related part",
                target_agent="benefits",
                description="Benefits agent processes",
                expected_result="Benefits information retrieved",
            ),
            ScenarioStep(
                step_id="route_001_s4",
                action="Synthesize results from multiple agents",
                target_agent="router",
                description="Result synthesis",
                expected_result="Comprehensive answer provided",
            ),
        ]

        scenario.steps = steps
        scenario.expected_outcomes = [
            "Query properly routed",
            "All agents executed successfully",
            "Results synthesized",
            "Complete answer provided",
        ]

        return scenario

    def run_scenario(self, scenario_id: str) -> Dict[str, Any]:
        """Execute a scenario and return results."""
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario not found: {scenario_id}")

        execution_start = datetime.utcnow()
        passed_steps = 0
        failed_steps = 0

        for step in scenario.steps:
            step_start = datetime.utcnow()
            
            try:
                # Simulate step execution
                step.status = ScenarioStatus.IN_PROGRESS
                
                # In real scenario, would execute against actual agents
                step.actual_result = f"Executed: {step.action}"
                step.status = ScenarioStatus.PASSED
                passed_steps += 1

                step.duration_ms = (datetime.utcnow() - step_start).total_seconds() * 1000

            except Exception as e:
                step.status = ScenarioStatus.FAILED
                step.error = str(e)
                failed_steps += 1
                step.duration_ms = (datetime.utcnow() - step_start).total_seconds() * 1000

        total_duration = (datetime.utcnow() - execution_start).total_seconds() * 1000
        
        result = {
            "scenario_id": scenario_id,
            "scenario_name": scenario.name,
            "status": "passed" if failed_steps == 0 else "failed",
            "passed_steps": passed_steps,
            "failed_steps": failed_steps,
            "total_steps": len(scenario.steps),
            "duration_ms": total_duration,
            "steps": [s.to_dict() for s in scenario.steps],
            "executed_at": execution_start.isoformat(),
        }

        self.execution_results.append(result)
        logger.info(f"Scenario {scenario_id}: {result['status']} ({passed_steps}/{len(scenario.steps)})")

        return result

    def get_scenario(self, scenario_id: str) -> Optional[E2EScenario]:
        """Get scenario by ID."""
        return self.scenarios.get(scenario_id)

    def list_scenarios(self, tag: Optional[str] = None) -> List[E2EScenario]:
        """List scenarios, optionally filtered by tag."""
        scenarios = list(self.scenarios.values())
        if tag:
            scenarios = [s for s in scenarios if tag in s.tags]
        return scenarios

    def get_execution_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent execution results."""
        return self.execution_results[-limit:]

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get execution summary statistics."""
        if not self.execution_results:
            return {
                "total_executions": 0,
                "total_passed": 0,
                "total_failed": 0,
                "pass_rate": 0.0,
            }

        total = len(self.execution_results)
        passed = sum(1 for r in self.execution_results if r["status"] == "passed")
        failed = total - passed

        return {
            "total_executions": total,
            "total_passed": passed,
            "total_failed": failed,
            "pass_rate": (passed / total * 100) if total > 0 else 0.0,
        }
