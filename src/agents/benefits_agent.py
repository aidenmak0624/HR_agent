"""
Benefits & Compensation Agent (AGENT-005) for HR multi-agent platform.

Handles benefits program management, enrollment tracking, plan comparison,
compensation band lookups, life event processing, and cost calculations.
Extends BaseAgent with benefits-specific tools and data models.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent, BaseAgentState
from ..connectors.hris_interface import HRISConnector, PlanType, BenefitsPlan
from ..core.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ==================== Enums & Dataclasses ====================

class LifeEventType(str, Enum):
    """Types of qualifying life events."""
    MARRIAGE = "marriage"
    DIVORCE = "divorce"
    BIRTH = "birth"
    ADOPTION = "adoption"
    DEATH = "death"
    LOSS_OF_COVERAGE = "loss_of_coverage"
    SIGNIFICANT_INCOME_CHANGE = "income_change"
    RELOCATION = "relocation"


class EnrollmentStatus(str, Enum):
    """Enrollment status."""
    NOT_ENROLLED = "not_enrolled"
    ENROLLED = "enrolled"
    WAIVED = "waived"
    PENDING = "pending"
    TERMINATED = "terminated"


class CoverageLevel(str, Enum):
    """Coverage levels."""
    EMPLOYEE = "employee"
    EMPLOYEE_SPOUSE = "employee_spouse"
    EMPLOYEE_CHILDREN = "employee_children"
    FAMILY = "family"


@dataclass
class BenefitsEnrollment:
    """Employee benefits enrollment record."""
    enrollment_id: str
    employee_id: str
    plan_id: str
    plan_type: PlanType
    coverage_level: CoverageLevel
    status: EnrollmentStatus = EnrollmentStatus.PENDING
    effective_date: Optional[datetime] = None
    enrolled_date: datetime = field(default_factory=datetime.utcnow)
    dependents: List[Dict[str, Any]] = field(default_factory=list)
    contribution_amount: float = 0.0
    election_period_id: Optional[str] = None
    notes: str = ""


@dataclass
class EnrollmentWindow:
    """Benefits enrollment period."""
    window_id: str
    name: str  # "Open Enrollment 2024", "New Hire Enrollment"
    window_type: str  # "open_enrollment", "new_hire", "life_event"
    start_date: datetime
    end_date: datetime
    plans_available: List[str] = field(default_factory=list)
    is_active: bool = True

    def is_open(self) -> bool:
        """Check if enrollment window is currently open."""
        now = datetime.utcnow()
        return self.is_active and self.start_date <= now <= self.end_date


@dataclass
class CompensationBand:
    """Salary compensation band by role/level/location."""
    band_id: str
    role_title: str
    job_level: str  # "entry", "mid", "senior", "lead", "manager"
    location: str
    currency: str = "USD"
    min_salary: float = 0.0
    mid_salary: float = 0.0
    max_salary: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    effective_date: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LifeEvent:
    """Qualifying life event record."""
    event_id: str
    employee_id: str
    event_type: LifeEventType
    event_date: datetime
    enrollment_window_start: datetime
    enrollment_window_end: datetime
    supporting_documents: List[str] = field(default_factory=list)
    verified: bool = False
    verification_date: Optional[datetime] = None
    verification_notes: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HSAFSAAccount:
    """Health Savings Account or Flexible Spending Account."""
    account_id: str
    employee_id: str
    account_type: str  # "hsa", "fsa"
    plan_year: int
    annual_contribution_limit: float
    current_contribution: float = 0.0
    current_balance: float = 0.0
    employer_contribution: float = 0.0
    last_transaction_date: Optional[datetime] = None


@dataclass
class PlanComparison:
    """Plan comparison for decision making."""
    comparison_id: str
    employee_id: str
    plans: List[Dict[str, Any]] = field(default_factory=list)
    monthly_premium_costs: Dict[str, float] = field(default_factory=dict)
    annual_cost_estimates: Dict[str, float] = field(default_factory=dict)
    coverage_comparison: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    recommendation: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


# ==================== Benefits Agent ====================

class BenefitsAgent(BaseAgent):
    """
    Specialist agent for benefits and compensation management.

    Provides tools for:
    - Looking up benefits plans and enrollment information
    - Checking enrollment status and windows
    - Comparing plan options with cost analysis
    - Calculating compensation bands by role/level/location
    - Processing life events with eligibility changes
    - Tracking HSA/FSA contributions
    - Open enrollment guidance and recommendations
    """

    def __init__(
        self,
        llm=None,
        hris_connector: Optional[HRISConnector] = None,
        rag_pipeline: Optional[RAGPipeline] = None,
    ):
        """
        Initialize Benefits Agent.

        Args:
            llm: Language model instance (passed from RouterAgent)
            hris_connector: HRIS connector instance
            rag_pipeline: RAG pipeline for benefits policy documents
        """
        self.hris_connector = hris_connector
        self.rag_pipeline = rag_pipeline

        # In-memory storage
        self.enrollments: Dict[str, BenefitsEnrollment] = {}
        self.enrollment_windows: Dict[str, EnrollmentWindow] = {}
        self.compensation_bands: Dict[str, CompensationBand] = {}
        self.life_events: Dict[str, LifeEvent] = {}
        self.hsa_fsa_accounts: Dict[str, HSAFSAAccount] = {}
        self.plan_comparisons: Dict[str, PlanComparison] = {}

        # Initialize standard enrollment windows and comp bands
        self._init_enrollment_windows()
        self._init_compensation_bands()

        super().__init__(llm=llm)

    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "benefits_compensation"

    def get_system_prompt(self) -> str:
        """Return system prompt for benefits specialist."""
        return (
            "You are a Benefits & Compensation specialist agent. Your role is to help employees "
            "understand and manage their benefits programs, including health insurance, dental, vision, "
            "401k, and other compensation elements. You can look up plan details, compare options, "
            "process life events, calculate costs, and provide open enrollment guidance. Use available "
            "tools to retrieve plan information, check eligibility, compare coverage options, and ensure "
            "employees make informed benefits decisions. Always explain costs, coverage, and deadlines clearly."
        )

    def get_tools(self) -> Dict[str, Any]:
        """
        Return available tools for benefits management.

        Tools:
        - benefits_lookup: Find plan details and enrollment info
        - enrollment_checker: Check enrollment status and windows
        - plan_comparison: Compare plans with cost analysis
        - compensation_calculator: Look up salary bands
        - life_event_processor: Process qualifying events
        - open_enrollment_guide: Provide enrollment guidance

        Returns:
            Dict of tool_name -> tool_function with description attribute
        """
        tools = {}

        # Tool 1: Benefits Lookup
        def benefits_lookup(
            employee_id: str,
            plan_type: Optional[str] = None,
        ) -> Dict[str, Any]:
            """
            Look up benefits plans and enrollment info.

            Args:
                employee_id: Employee ID
                plan_type: Optional filter (medical, dental, vision, 401k)

            Returns:
                Benefits information and current enrollments
            """
            try:
                logger.info(f"BENEFITS_LOOKUP: Searching benefits for {employee_id}")

                # Get employee benefits from HRIS
                if self.hris_connector:
                    plans = self.hris_connector.get_benefits(employee_id)
                else:
                    plans = []

                # Get current enrollments
                employee_enrollments = [
                    e for e in self.enrollments.values()
                    if e.employee_id == employee_id
                ]

                # Filter by plan type if specified
                if plan_type:
                    employee_enrollments = [
                        e for e in employee_enrollments
                        if e.plan_type.value.lower() == plan_type.lower()
                    ]

                result = {
                    "employee_id": employee_id,
                    "current_enrollments": [
                        {
                            "plan_id": e.plan_id,
                            "plan_type": e.plan_type.value,
                            "status": e.status.value,
                            "coverage_level": e.coverage_level.value,
                            "effective_date": e.effective_date.isoformat() if e.effective_date else None,
                        }
                        for e in employee_enrollments
                    ],
                    "enrollment_count": len(employee_enrollments),
                    "available_plans": len(plans),
                    "source": "benefits_system",
                }

                logger.info(f"BENEFITS_LOOKUP: Found {len(employee_enrollments)} enrollments")
                return result

            except Exception as e:
                logger.error(f"BENEFITS_LOOKUP failed: {e}")
                return {"error": f"Benefits lookup failed: {str(e)}"}

        benefits_lookup.description = (
            "Look up current benefits plans and enrollment status for an employee. "
            "Returns plan details, coverage levels, and effective dates."
        )
        tools["benefits_lookup"] = benefits_lookup

        # Tool 2: Enrollment Checker
        def enrollment_checker(
            employee_id: str,
            window_type: Optional[str] = None,
        ) -> Dict[str, Any]:
            """
            Check enrollment status and available windows.

            Args:
                employee_id: Employee ID
                window_type: Optional filter (open_enrollment, new_hire, life_event)

            Returns:
                Enrollment status and available windows
            """
            try:
                logger.info(f"ENROLLMENT_CHECKER: Checking enrollment for {employee_id}")

                # Get available windows
                windows = [w for w in self.enrollment_windows.values() if w.is_active]
                if window_type:
                    windows = [w for w in windows if w.window_type == window_type]

                # Get enrollment status
                employee_enrollments = [
                    e for e in self.enrollments.values()
                    if e.employee_id == employee_id
                ]

                status_breakdown = {
                    "enrolled": len([e for e in employee_enrollments if e.status == EnrollmentStatus.ENROLLED]),
                    "waived": len([e for e in employee_enrollments if e.status == EnrollmentStatus.WAIVED]),
                    "pending": len([e for e in employee_enrollments if e.status == EnrollmentStatus.PENDING]),
                }

                return {
                    "employee_id": employee_id,
                    "enrollment_status": status_breakdown,
                    "open_windows": [
                        {
                            "window_id": w.window_id,
                            "name": w.name,
                            "type": w.window_type,
                            "start_date": w.start_date.isoformat(),
                            "end_date": w.end_date.isoformat(),
                            "is_open": w.is_open(),
                        }
                        for w in windows
                    ],
                    "active_window_count": len([w for w in windows if w.is_open()]),
                    "source": "enrollment_system",
                }

            except Exception as e:
                logger.error(f"ENROLLMENT_CHECKER failed: {e}")
                return {"error": f"Enrollment check failed: {str(e)}"}

        enrollment_checker.description = (
            "Check employee enrollment status and available enrollment windows. "
            "Returns active/waived status and upcoming enrollment periods."
        )
        tools["enrollment_checker"] = enrollment_checker

        # Tool 3: Plan Comparison
        def plan_comparison(
            employee_id: str,
            plan_ids: List[str],
            employee_health_profile: Optional[str] = None,
        ) -> Dict[str, Any]:
            """
            Compare multiple benefit plans with cost analysis.

            Args:
                employee_id: Employee ID
                plan_ids: List of plan IDs to compare
                employee_health_profile: Optional (healthy, chronic, family_dependent)

            Returns:
                Comparison with costs and coverage breakdown
            """
            try:
                logger.info(f"PLAN_COMPARISON: Comparing {len(plan_ids)} plans for {employee_id}")

                plans_data = []
                costs = {}

                # Get plan details from HRIS
                if self.hris_connector:
                    all_plans = self.hris_connector.get_benefits(employee_id)
                    for plan_id in plan_ids:
                        plan = next((p for p in all_plans if p.id == plan_id), None)
                        if plan:
                            plans_data.append(plan)
                            # Estimate annual cost
                            annual_cost = plan.employee_cost * 12
                            costs[plan_id] = {
                                "monthly": plan.employee_cost,
                                "annual": annual_cost,
                                "employer_contribution": plan.employer_cost * 12,
                            }

                from uuid import uuid4
                comparison_id = f"comparison_{uuid4().hex[:8]}"

                comparison = PlanComparison(
                    comparison_id=comparison_id,
                    employee_id=employee_id,
                    monthly_premium_costs={pid: costs[pid]["monthly"] for pid in costs},
                    annual_cost_estimates={pid: costs[pid]["annual"] for pid in costs},
                )
                self.plan_comparisons[comparison_id] = comparison

                return {
                    "comparison_id": comparison_id,
                    "employee_id": employee_id,
                    "plan_count": len(plans_data),
                    "cost_estimates": costs,
                    "lowest_cost_plan": min(costs.items(), key=lambda x: x[1]["monthly"])[0] if costs else None,
                    "health_profile": employee_health_profile,
                    "source": "comparison_system",
                }

            except Exception as e:
                logger.error(f"PLAN_COMPARISON failed: {e}")
                return {"error": f"Plan comparison failed: {str(e)}"}

        plan_comparison.description = (
            "Compare multiple benefit plans side-by-side with cost analysis. "
            "Shows monthly/annual costs, coverage details, and recommendations."
        )
        tools["plan_comparison"] = plan_comparison

        # Tool 4: Compensation Calculator
        def compensation_calculator(
            role_title: str,
            job_level: str,
            location: str,
        ) -> Dict[str, Any]:
            """
            Look up compensation band for role/level/location.

            Args:
                role_title: Job title
                job_level: Level (entry, mid, senior, lead, manager)
                location: Work location

            Returns:
                Salary band information
            """
            try:
                logger.info(f"COMPENSATION_CALCULATOR: Looking up band for {role_title}/{job_level}/{location}")

                # Search compensation bands
                matching_bands = [
                    b for b in self.compensation_bands.values()
                    if (b.role_title.lower() == role_title.lower() and
                        b.job_level.lower() == job_level.lower() and
                        b.location.lower() == location.lower())
                ]

                if not matching_bands:
                    return {"error": f"No compensation band found for {role_title}/{job_level} in {location}"}

                band = matching_bands[0]

                return {
                    "band_id": band.band_id,
                    "role_title": band.role_title,
                    "job_level": band.job_level,
                    "location": band.location,
                    "currency": band.currency,
                    "salary_range": {
                        "minimum": band.min_salary,
                        "midpoint": band.mid_salary,
                        "maximum": band.max_salary,
                    },
                    "effective_date": band.effective_date.isoformat(),
                    "source": "compensation_system",
                }

            except Exception as e:
                logger.error(f"COMPENSATION_CALCULATOR failed: {e}")
                return {"error": f"Compensation lookup failed: {str(e)}"}

        compensation_calculator.description = (
            "Look up compensation bands by role, job level, and location. "
            "Returns salary ranges (min, midpoint, max) for benchmarking and offers."
        )
        tools["compensation_calculator"] = compensation_calculator

        # Tool 5: Life Event Processor
        def life_event_processor(
            employee_id: str,
            event_type: str,
            event_date: str,
            supporting_docs: Optional[List[str]] = None,
        ) -> Dict[str, Any]:
            """
            Process qualifying life event for benefits eligibility changes.

            Args:
                employee_id: Employee ID
                event_type: Event type (marriage, birth, divorce, etc.)
                event_date: Event date (YYYY-MM-DD)
                supporting_docs: List of document names for verification

            Returns:
                Life event record and enrollment window info
            """
            try:
                logger.info(f"LIFE_EVENT_PROCESSOR: Processing {event_type} for {employee_id}")

                # Parse event date
                event_dt = datetime.strptime(event_date, "%Y-%m-%d")

                # Create life event
                from uuid import uuid4
                event_id = f"event_{uuid4().hex[:8]}"

                # Enrollment window: typically 30 days from event
                window_start = event_dt
                window_end = event_dt + timedelta(days=30)

                event = LifeEvent(
                    event_id=event_id,
                    employee_id=employee_id,
                    event_type=LifeEventType(event_type),
                    event_date=event_dt,
                    enrollment_window_start=window_start,
                    enrollment_window_end=window_end,
                    supporting_documents=supporting_docs or [],
                )
                self.life_events[event_id] = event

                logger.info(f"LIFE_EVENT_PROCESSOR: Created event {event_id}")

                return {
                    "event_id": event_id,
                    "employee_id": employee_id,
                    "event_type": event_type,
                    "event_date": event_date,
                    "enrollment_window": {
                        "start": window_start.isoformat(),
                        "end": window_end.isoformat(),
                        "days_available": 30,
                    },
                    "eligible_plan_changes": True,
                    "requires_verification": True,
                    "source": "life_event_system",
                }

            except Exception as e:
                logger.error(f"LIFE_EVENT_PROCESSOR failed: {e}")
                return {"error": f"Life event processing failed: {str(e)}"}

        life_event_processor.description = (
            "Process qualifying life events (marriage, birth, adoption, death, etc.) "
            "to initiate special enrollment periods and update eligibility."
        )
        tools["life_event_processor"] = life_event_processor

        # Tool 6: Open Enrollment Guide
        def open_enrollment_guide(
            employee_id: str,
            window_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            """
            Get open enrollment guidance and recommendations.

            Args:
                employee_id: Employee ID
                window_id: Specific enrollment window ID

            Returns:
                Guidance and recommended action items
            """
            try:
                logger.info(f"OPEN_ENROLLMENT_GUIDE: Providing guidance for {employee_id}")

                # Get relevant windows
                windows = [w for w in self.enrollment_windows.values() if w.is_open()]
                if window_id:
                    windows = [w for w in windows if w.window_id == window_id]

                # Get current enrollments
                current = [e for e in self.enrollments.values() if e.employee_id == employee_id]

                action_items = [
                    "Review current plan coverage and costs",
                    "Compare medical plan options",
                    "Check dental and vision coverage",
                    "Review 401k contribution levels",
                    "Confirm beneficiary designations",
                    "Consider HSA/FSA elections if eligible",
                ]

                guidance = {
                    "employee_id": employee_id,
                    "active_windows": [
                        {
                            "window_id": w.window_id,
                            "name": w.name,
                            "deadline": w.end_date.isoformat(),
                            "days_remaining": (w.end_date - datetime.utcnow()).days,
                        }
                        for w in windows
                    ],
                    "current_enrollments": len(current),
                    "action_items": action_items,
                    "key_deadlines": [
                        {
                            "date": w.end_date.isoformat(),
                            "action": f"{w.name} deadline",
                        }
                        for w in windows
                    ],
                    "resources": [
                        "Benefits Guide (PDF)",
                        "Plan Comparison Tool",
                        "Cost Calculator",
                        "FAQ",
                    ],
                    "source": "enrollment_guide_system",
                }

                return guidance

            except Exception as e:
                logger.error(f"OPEN_ENROLLMENT_GUIDE failed: {e}")
                return {"error": f"Enrollment guidance failed: {str(e)}"}

        open_enrollment_guide.description = (
            "Provide open enrollment guidance with action items, deadlines, "
            "and recommended steps for making benefits decisions."
        )
        tools["open_enrollment_guide"] = open_enrollment_guide

        return tools

    # ==================== Helper Methods ====================

    def _init_enrollment_windows(self) -> None:
        """Initialize standard enrollment windows."""
        from uuid import uuid4

        # Open enrollment window
        now = datetime.utcnow()
        open_enrollment = EnrollmentWindow(
            window_id=f"window_{uuid4().hex[:8]}",
            name="Open Enrollment 2024",
            window_type="open_enrollment",
            start_date=datetime(2024, 11, 1),
            end_date=datetime(2024, 11, 30),
            plans_available=["medical_hmo", "medical_ppo", "dental", "vision", "401k"],
        )
        self.enrollment_windows[open_enrollment.window_id] = open_enrollment

        logger.info("Initialized standard enrollment windows")

    def _init_compensation_bands(self) -> None:
        """Initialize standard compensation bands."""
        from uuid import uuid4

        # Sample bands
        bands = [
            {
                "role_title": "Software Engineer",
                "job_level": "mid",
                "location": "San Francisco",
                "min": 120000,
                "mid": 150000,
                "max": 180000,
            },
            {
                "role_title": "Software Engineer",
                "job_level": "senior",
                "location": "San Francisco",
                "min": 180000,
                "mid": 220000,
                "max": 260000,
            },
            {
                "role_title": "Product Manager",
                "job_level": "mid",
                "location": "New York",
                "min": 130000,
                "mid": 160000,
                "max": 190000,
            },
            {
                "role_title": "HR Specialist",
                "job_level": "entry",
                "location": "Remote",
                "min": 50000,
                "mid": 62000,
                "max": 75000,
            },
        ]

        for band_data in bands:
            band = CompensationBand(
                band_id=f"band_{uuid4().hex[:8]}",
                role_title=band_data["role_title"],
                job_level=band_data["job_level"],
                location=band_data["location"],
                min_salary=band_data["min"],
                mid_salary=band_data["mid"],
                max_salary=band_data["max"],
            )
            self.compensation_bands[band.band_id] = band

        logger.info(f"Initialized {len(bands)} compensation bands")


# Register agent class for discovery
__all__ = [
    "BenefitsAgent",
    "BenefitsPlan",
    "EnrollmentWindow",
    "LifeEvent",
    "CompensationBand",
    "BenefitsEnrollment",
]
