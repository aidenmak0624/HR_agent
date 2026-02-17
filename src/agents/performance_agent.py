"""
Performance Review Agent (AGENT-006) for HR multi-agent platform.

Handles performance review cycles, goal setting and tracking, 360-degree feedback
collection, calibration sessions, and Performance Improvement Plans (PIPs).
Extends BaseAgent with performance management tools and evaluation frameworks.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent, BaseAgentState
from ..connectors.hris_interface import HRISConnector, Employee
from ..core.workflow_engine import WorkflowEngine
from ..core.bias_audit import BiasAuditor, BiasIncident

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ==================== Enums & Dataclasses ====================

class ReviewCyclePhase(str, Enum):
    """Phases of performance review cycle."""
    GOAL_SETTING = "goal_setting"
    MID_YEAR = "mid_year"
    YEAR_END = "year_end"
    CALIBRATION = "calibration"
    CLOSED = "closed"


class FeedbackType(str, Enum):
    """Types of feedback in 360 reviews."""
    SELF = "self"
    MANAGER = "manager"
    PEER = "peer"
    DIRECT_REPORT = "direct_report"
    SKIP_LEVEL = "skip_level"


class RatingLevel(str, Enum):
    """Performance rating scale."""
    EXCEPTIONAL = 5
    EXCEEDS = 4
    MEETS = 3
    NEEDS_IMPROVEMENT = 2
    UNSATISFACTORY = 1


class PIPStatus(str, Enum):
    """Performance Improvement Plan status."""
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    COMPLETED_SUCCESS = "completed_success"
    COMPLETED_UNSUCCESSFUL = "completed_unsuccessful"


@dataclass
class PerformanceGoal:
    """SMART performance goal."""
    goal_id: str
    employee_id: str
    title: str
    description: str
    category: str  # "business", "development", "management", "culture"
    weight: float  # 0.0-1.0, sum should be 1.0
    target_value: Optional[float] = None
    achieved_value: Optional[float] = None
    progress_percent: float = 0.0
    status: str = "pending"  # pending, in_progress, achieved, not_achieved
    created_date: datetime = field(default_factory=datetime.utcnow)
    target_date: Optional[datetime] = None
    notes: str = ""
    supports_strategic_objective: Optional[str] = None

    def is_smart(self) -> bool:
        """Validate SMART criteria (Specific, Measurable, Achievable, Relevant, Time-bound)."""
        has_title = bool(self.title and len(self.title) > 5)
        has_description = bool(self.description and len(self.description) > 10)
        has_target = self.target_value is not None
        has_deadline = self.target_date is not None
        has_category = bool(self.category)

        return has_title and has_description and has_target and has_deadline and has_category


@dataclass
class PerformanceFeedback:
    """Individual feedback entry in 360 review."""
    feedback_id: str
    review_id: str
    feedback_provider_id: str
    feedback_type: FeedbackType
    rating: int  # 1-5
    comments: str
    strengths: List[str] = field(default_factory=list)
    development_areas: List[str] = field(default_factory=list)
    provided_date: datetime = field(default_factory=datetime.utcnow)
    is_anonymous: bool = False


@dataclass
class PerformanceReview:
    """Complete performance review record."""
    review_id: str
    employee_id: str
    employee_name: str
    manager_id: str
    review_period: str  # "2024 Q4", "2023-2024"
    cycle_phase: ReviewCyclePhase
    overall_rating: Optional[RatingLevel] = None
    manager_rating: Optional[int] = None
    goals: List[PerformanceGoal] = field(default_factory=list)
    feedback: List[PerformanceFeedback] = field(default_factory=list)
    narrative_summary: str = ""
    development_plan: str = ""
    calibration_score: Optional[float] = None
    created_date: datetime = field(default_factory=datetime.utcnow)
    submitted_date: Optional[datetime] = None
    finalized_date: Optional[datetime] = None
    is_draft: bool = True

    def calculate_goal_achievement(self) -> float:
        """Calculate weighted goal achievement percentage."""
        if not self.goals:
            return 0.0

        achieved_goals = [g for g in self.goals if g.progress_percent >= 100]
        total_weight = sum(g.weight for g in self.goals) if self.goals else 0.0

        if total_weight == 0:
            return 0.0

        weighted_achieved = sum(
            g.weight for g in self.goals if g.progress_percent >= 100
        )
        return (weighted_achieved / total_weight) * 100

    def average_feedback_rating(self) -> float:
        """Calculate average rating from all feedback."""
        if not self.feedback:
            return 0.0

        total_rating = sum(f.rating for f in self.feedback)
        return total_rating / len(self.feedback)


@dataclass
class PerformanceImprovementPlan:
    """Performance Improvement Plan (PIP)."""
    pip_id: str
    employee_id: str
    manager_id: str
    start_date: datetime
    end_date: datetime
    duration_days: int  # typically 30, 60, or 90
    status: PIPStatus = PIPStatus.CREATED
    improvement_areas: List[str] = field(default_factory=list)
    success_criteria: List[Dict[str, Any]] = field(default_factory=list)
    check_in_dates: List[datetime] = field(default_factory=list)
    check_in_notes: List[str] = field(default_factory=list)
    documents: List[str] = field(default_factory=list)
    created_date: datetime = field(default_factory=datetime.utcnow)
    completion_date: Optional[datetime] = None
    outcome: Optional[str] = None  # "success", "unsuccessful"
    hr_involvement: bool = True


@dataclass
class CalibrationSession:
    """Calibration session for aligning ratings across managers."""
    session_id: str
    department: str
    facilitator_id: str
    participants: List[str] = field(default_factory=list)  # Manager IDs
    review_cycle: str = ""
    scheduled_date: datetime = field(default_factory=datetime.utcnow)
    completed_date: Optional[datetime] = None
    rating_distribution_before: Dict[str, int] = field(default_factory=dict)
    rating_distribution_after: Dict[str, int] = field(default_factory=dict)
    adjustments: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    is_completed: bool = False


# ==================== Performance Agent ====================

class PerformanceAgent(BaseAgent):
    """
    Specialist agent for performance management and reviews.

    Provides tools for:
    - Managing review cycles (goal setting, mid-year, year-end)
    - Creating and tracking SMART performance goals
    - Collecting 360-degree feedback
    - Calculating performance ratings
    - Managing Performance Improvement Plans (PIPs)
    - Supporting calibration sessions
    - Handling manager and self-assessments
    - Tracking historical performance data
    """

    def __init__(
        self,
        llm=None,
        hris_connector: Optional[HRISConnector] = None,
        workflow_engine: Optional[WorkflowEngine] = None,
        bias_auditor: Optional[BiasAuditor] = None,
    ):
        """
        Initialize Performance Agent.

        Args:
            llm: Language model instance (passed from RouterAgent)
            hris_connector: HRIS connector instance
            workflow_engine: Workflow engine for review approvals
            bias_auditor: Bias auditor for scanning feedback and reviews
        """
        self.hris_connector = hris_connector
        self.workflow_engine = workflow_engine
        self.bias_auditor = bias_auditor or BiasAuditor()

        # In-memory storage
        self.reviews: Dict[str, PerformanceReview] = {}
        self.goals: Dict[str, PerformanceGoal] = {}
        self.pips: Dict[str, PerformanceImprovementPlan] = {}
        self.calibration_sessions: Dict[str, CalibrationSession] = {}
        self.review_cycles: Dict[str, Dict[str, Any]] = {}

        super().__init__(llm=llm)

    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "performance"

    def get_system_prompt(self) -> str:
        """Return system prompt for performance specialist."""
        return (
            "You are a Performance Management specialist agent. Your role is to facilitate "
            "fair, consistent, and developmental performance reviews. You help managers set "
            "SMART goals, collect 360-degree feedback, conduct calibration sessions, calculate "
            "ratings, and create improvement plans when needed. Use available tools to create "
            "reviews, track goals, collect feedback, calculate ratings, and manage PIPs. Always "
            "emphasize developmental feedback, consistency, and documentation. Ensure processes "
            "are fair, transparent, and legally compliant."
        )

    def get_tools(self) -> Dict[str, Any]:
        """
        Return available tools for performance management.

        Tools:
        - review_cycle_manager: Create and manage review cycles
        - goal_tracker: Create and track SMART goals
        - feedback_collector: Collect 360-degree feedback
        - rating_calculator: Calculate performance ratings
        - pip_manager: Create and manage Performance Improvement Plans
        - calibration_helper: Support calibration sessions

        Returns:
            Dict of tool_name -> tool_function with description attribute
        """
        tools = {}

        # Tool 1: Review Cycle Manager
        def review_cycle_manager(
            cycle_name: str,
            department: str,
            start_phase: str,
            participants: List[str],
        ) -> Dict[str, Any]:
            """
            Create and manage performance review cycles.

            Args:
                cycle_name: Cycle identifier (e.g., "2024 Q4")
                department: Department or "all"
                start_phase: Starting phase (goal_setting, mid_year, year_end)
                participants: Manager IDs participating

            Returns:
                Review cycle creation confirmation
            """
            try:
                logger.info(f"REVIEW_CYCLE_MANAGER: Creating cycle {cycle_name}")

                from uuid import uuid4
                cycle_id = f"cycle_{uuid4().hex[:8]}"

                # Phase timeline
                phase_timeline = {
                    "goal_setting": {"duration_days": 14, "order": 1},
                    "mid_year": {"duration_days": 30, "order": 2},
                    "year_end": {"duration_days": 30, "order": 3},
                    "calibration": {"duration_days": 14, "order": 4},
                }

                cycle_data = {
                    "cycle_id": cycle_id,
                    "name": cycle_name,
                    "department": department,
                    "start_phase": start_phase,
                    "current_phase": start_phase,
                    "participants": participants,
                    "created_date": datetime.utcnow().isoformat(),
                    "phase_timeline": phase_timeline,
                    "reviews_created": 0,
                    "reviews_completed": 0,
                    "status": "active",
                }

                self.review_cycles[cycle_id] = cycle_data

                logger.info(f"REVIEW_CYCLE_MANAGER: Created cycle {cycle_id}")

                return {
                    "cycle_id": cycle_id,
                    "name": cycle_name,
                    "department": department,
                    "current_phase": start_phase,
                    "participant_count": len(participants),
                    "phases": list(ReviewCyclePhase),
                    "source": "review_cycle_system",
                }

            except Exception as e:
                logger.error(f"REVIEW_CYCLE_MANAGER failed: {e}")
                return {"error": f"Review cycle creation failed: {str(e)}"}

        review_cycle_manager.description = (
            "Create and manage performance review cycles with phases: goal-setting, "
            "mid-year, year-end, and calibration. Track participants and cycle progression."
        )
        tools["review_cycle_manager"] = review_cycle_manager

        # Tool 2: Goal Tracker
        def goal_tracker(
            employee_id: str,
            goal_title: str,
            goal_description: str,
            category: str,
            target_value: float,
            target_date: str,
            weight: float = 0.25,
        ) -> Dict[str, Any]:
            """
            Create and track SMART performance goals.

            Args:
                employee_id: Employee ID
                goal_title: Goal title (5+ chars)
                goal_description: Goal description (10+ chars)
                category: Category (business, development, management, culture)
                target_value: Numeric target
                target_date: Target date (YYYY-MM-DD)
                weight: Goal weight in review (0.0-1.0)

            Returns:
                Goal creation and SMART validation result
            """
            try:
                logger.info(f"GOAL_TRACKER: Creating goal for {employee_id}")

                target_dt = datetime.strptime(target_date, "%Y-%m-%d")

                from uuid import uuid4
                goal_id = f"goal_{uuid4().hex[:8]}"

                goal = PerformanceGoal(
                    goal_id=goal_id,
                    employee_id=employee_id,
                    title=goal_title,
                    description=goal_description,
                    category=category,
                    weight=weight,
                    target_value=target_value,
                    target_date=target_dt,
                    status="pending",
                )

                # Validate SMART criteria
                is_smart = goal.is_smart()

                self.goals[goal_id] = goal

                logger.info(f"GOAL_TRACKER: Created goal {goal_id}, SMART={is_smart}")

                return {
                    "goal_id": goal_id,
                    "employee_id": employee_id,
                    "title": goal_title,
                    "category": category,
                    "target_value": target_value,
                    "target_date": target_date,
                    "weight": weight,
                    "is_smart_compliant": is_smart,
                    "validation_message": "Goal meets SMART criteria" if is_smart else "Review goal for SMART compliance",
                    "source": "goal_system",
                }

            except Exception as e:
                logger.error(f"GOAL_TRACKER failed: {e}")
                return {"error": f"Goal creation failed: {str(e)}"}

        goal_tracker.description = (
            "Create SMART (Specific, Measurable, Achievable, Relevant, Time-bound) performance goals. "
            "Validates goal quality and tracks progress toward targets."
        )
        tools["goal_tracker"] = goal_tracker

        # Tool 3: Feedback Collector
        def feedback_collector(
            review_id: str,
            feedback_provider_id: str,
            feedback_type: str,
            rating: int,
            comments: str,
            strengths: Optional[List[str]] = None,
            development_areas: Optional[List[str]] = None,
        ) -> Dict[str, Any]:
            """
            Collect 360-degree feedback.

            Args:
                review_id: Review ID
                feedback_provider_id: Person providing feedback
                feedback_type: Type (self, manager, peer, direct_report, skip_level)
                rating: Rating (1-5)
                comments: Feedback comments
                strengths: List of strengths
                development_areas: List of development areas

            Returns:
                Feedback submission confirmation
            """
            try:
                logger.info(f"FEEDBACK_COLLECTOR: Collecting {feedback_type} feedback for {review_id}")

                review = self.reviews.get(review_id)
                if not review:
                    return {"error": f"Review not found: {review_id}"}

                # Validate rating
                if not 1 <= rating <= 5:
                    return {"error": "Rating must be between 1 and 5"}

                from uuid import uuid4
                feedback_id = f"feedback_{uuid4().hex[:8]}"

                feedback = PerformanceFeedback(
                    feedback_id=feedback_id,
                    review_id=review_id,
                    feedback_provider_id=feedback_provider_id,
                    feedback_type=FeedbackType(feedback_type),
                    rating=rating,
                    comments=comments,
                    strengths=strengths or [],
                    development_areas=development_areas or [],
                )

                review.feedback.append(feedback)

                # Scan feedback for potential bias
                bias_incidents = []
                try:
                    bias_incidents = self.bias_auditor.scan_response(
                        agent_type="performance_feedback",
                        query=f"{feedback_type} feedback for review {review_id}",
                        response=comments,
                    )
                    if bias_incidents:
                        logger.warning(
                            f"FEEDBACK_COLLECTOR: Detected {len(bias_incidents)} bias "
                            f"concerns in feedback {feedback_id}"
                        )
                except Exception as bias_err:
                    logger.warning(f"FEEDBACK_COLLECTOR: Bias scan failed: {bias_err}")

                logger.info(f"FEEDBACK_COLLECTOR: Added feedback {feedback_id} to review {review_id}")

                return {
                    "feedback_id": feedback_id,
                    "review_id": review_id,
                    "feedback_type": feedback_type,
                    "rating": rating,
                    "total_feedback_count": len(review.feedback),
                    "submission_date": datetime.utcnow().isoformat(),
                    "bias_scan": {
                        "scanned": True,
                        "incidents_found": len(bias_incidents),
                        "warnings": [
                            {
                                "category": str(inc.category.value),
                                "severity": str(inc.severity.value),
                                "description": inc.description,
                                "recommendations": inc.recommendations,
                            }
                            for inc in bias_incidents
                        ] if bias_incidents else [],
                    },
                    "source": "feedback_system",
                }

            except Exception as e:
                logger.error(f"FEEDBACK_COLLECTOR failed: {e}")
                return {"error": f"Feedback collection failed: {str(e)}"}

        feedback_collector.description = (
            "Collect 360-degree feedback from managers, peers, direct reports, and self. "
            "Aggregates feedback with ratings and qualitative comments."
        )
        tools["feedback_collector"] = feedback_collector

        # Tool 4: Rating Calculator
        def rating_calculator(review_id: str) -> Dict[str, Any]:
            """
            Calculate performance rating from feedback and goals.

            Args:
                review_id: Review ID

            Returns:
                Calculated rating with component breakdown
            """
            try:
                logger.info(f"RATING_CALCULATOR: Calculating rating for {review_id}")

                review = self.reviews.get(review_id)
                if not review:
                    return {"error": f"Review not found: {review_id}"}

                # Calculate goal achievement
                goal_achievement = review.calculate_goal_achievement()

                # Calculate feedback average
                feedback_avg = review.average_feedback_rating()

                # Calculate overall rating (60% goals, 40% feedback)
                if goal_achievement > 0 or feedback_avg > 0:
                    overall = (goal_achievement * 0.6 + feedback_avg * 40) / 100
                    overall = min(5, max(1, overall))  # Clamp to 1-5
                else:
                    overall = 3.0  # Default to "meets"

                # Map to rating level
                if overall >= 4.5:
                    rating_level = RatingLevel.EXCEPTIONAL.name
                elif overall >= 3.75:
                    rating_level = RatingLevel.EXCEEDS.name
                elif overall >= 2.5:
                    rating_level = RatingLevel.MEETS.name
                elif overall >= 1.75:
                    rating_level = RatingLevel.NEEDS_IMPROVEMENT.name
                else:
                    rating_level = RatingLevel.UNSATISFACTORY.name

                review.overall_rating = RatingLevel[rating_level]
                review.manager_rating = int(overall)

                # Scan narrative summary for bias if present
                bias_scan_result = {"scanned": False}
                if review.narrative_summary:
                    try:
                        bias_incidents = self.bias_auditor.scan_response(
                            agent_type="performance_review",
                            query=f"Performance review for {review.employee_name}",
                            response=review.narrative_summary,
                        )
                        bias_scan_result = {
                            "scanned": True,
                            "incidents_found": len(bias_incidents),
                            "passed": len(bias_incidents) == 0,
                        }
                        if bias_incidents:
                            logger.warning(
                                f"RATING_CALCULATOR: {len(bias_incidents)} bias "
                                f"concerns in review {review_id} narrative"
                            )
                    except Exception as bias_err:
                        logger.warning(f"RATING_CALCULATOR: Bias scan failed: {bias_err}")

                return {
                    "review_id": review_id,
                    "employee_id": review.employee_id,
                    "goal_achievement_percent": goal_achievement,
                    "feedback_average_rating": round(feedback_avg, 2),
                    "calculated_overall_rating": round(overall, 2),
                    "rating_level": rating_level,
                    "feedback_count": len(review.feedback),
                    "goal_count": len(review.goals),
                    "bias_audit": bias_scan_result,
                    "source": "rating_system",
                }

            except Exception as e:
                logger.error(f"RATING_CALCULATOR failed: {e}")
                return {"error": f"Rating calculation failed: {str(e)}"}

        rating_calculator.description = (
            "Calculate overall performance rating from goals achievement (60%) "
            "and 360-degree feedback (40%). Maps to rating level (Exceptional to Unsatisfactory)."
        )
        tools["rating_calculator"] = rating_calculator

        # Tool 5: PIP Manager
        def pip_manager(
            employee_id: str,
            improvement_areas: List[str],
            duration_days: int = 60,
            manager_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            """
            Create and manage Performance Improvement Plans.

            Args:
                employee_id: Employee ID
                improvement_areas: Areas needing improvement
                duration_days: PIP duration (30, 60, 90 days)
                manager_id: Manager overseeing PIP

            Returns:
                PIP creation confirmation
            """
            try:
                logger.info(f"PIP_MANAGER: Creating PIP for {employee_id}")

                # Validate duration
                if duration_days not in [30, 60, 90]:
                    return {"error": "Duration must be 30, 60, or 90 days"}

                from uuid import uuid4
                pip_id = f"pip_{uuid4().hex[:8]}"

                start_date = datetime.utcnow()
                end_date = start_date + timedelta(days=duration_days)

                # Create check-in dates
                check_in_interval = duration_days // 3
                check_in_dates = [
                    start_date + timedelta(days=check_in_interval * i)
                    for i in range(1, 3)
                ]

                pip = PerformanceImprovementPlan(
                    pip_id=pip_id,
                    employee_id=employee_id,
                    manager_id=manager_id or "unknown",
                    start_date=start_date,
                    end_date=end_date,
                    duration_days=duration_days,
                    improvement_areas=improvement_areas,
                    check_in_dates=check_in_dates,
                )

                self.pips[pip_id] = pip

                logger.info(f"PIP_MANAGER: Created PIP {pip_id} for {employee_id}")

                return {
                    "pip_id": pip_id,
                    "employee_id": employee_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "duration_days": duration_days,
                    "improvement_areas": improvement_areas,
                    "check_in_count": len(check_in_dates),
                    "status": "created",
                    "requires_hr_involvement": True,
                    "source": "pip_system",
                }

            except Exception as e:
                logger.error(f"PIP_MANAGER failed: {e}")
                return {"error": f"PIP creation failed: {str(e)}"}

        pip_manager.description = (
            "Create and manage Performance Improvement Plans with defined areas, "
            "success criteria, check-in dates, and clear outcomes."
        )
        tools["pip_manager"] = pip_manager

        # Tool 6: Calibration Helper
        def calibration_helper(
            cycle_id: str,
            department: str,
            facilitator_id: str,
            participating_managers: List[str],
        ) -> Dict[str, Any]:
            """
            Support calibration sessions for rating consistency.

            Args:
                cycle_id: Review cycle ID
                department: Department
                facilitator_id: Session facilitator (HR)
                participating_managers: Manager IDs

            Returns:
                Calibration session setup
            """
            try:
                logger.info(f"CALIBRATION_HELPER: Setting up calibration for {department}")

                from uuid import uuid4
                session_id = f"calibration_{uuid4().hex[:8]}"

                session = CalibrationSession(
                    session_id=session_id,
                    department=department,
                    facilitator_id=facilitator_id,
                    participants=participating_managers,
                    review_cycle=cycle_id,
                    scheduled_date=datetime.utcnow() + timedelta(days=7),
                )

                self.calibration_sessions[session_id] = session

                return {
                    "session_id": session_id,
                    "department": department,
                    "facilitator_id": facilitator_id,
                    "participant_count": len(participating_managers),
                    "scheduled_date": session.scheduled_date.isoformat(),
                    "objectives": [
                        "Align rating standards across managers",
                        "Review exceptional and concerning ratings",
                        "Discuss impact of ratings on talent decisions",
                        "Document calibration rationale",
                    ],
                    "agenda_items": [
                        "Company performance context",
                        "Review rating distribution",
                        "Discuss outlier cases",
                        "Alignment and commitment",
                    ],
                    "source": "calibration_system",
                }

            except Exception as e:
                logger.error(f"CALIBRATION_HELPER failed: {e}")
                return {"error": f"Calibration setup failed: {str(e)}"}

        calibration_helper.description = (
            "Set up and support calibration sessions to ensure consistent ratings "
            "across managers and departments. Aligns rating standards and documents rationale."
        )
        tools["calibration_helper"] = calibration_helper

        return tools


# Register agent class for discovery
__all__ = [
    "PerformanceAgent",
    "PerformanceReview",
    "PerformanceGoal",
    "PerformanceImprovementPlan",
    "CalibrationSession",
    "ReviewCyclePhase",
]
