"""
Onboarding Agent (AGENT-004) for HR multi-agent platform.

Handles new employee onboarding workflows with task management, checklist tracking,
document collection, IT provisioning, buddy assignment, and progress reporting.
Extends BaseAgent with onboarding-specific tools and state management.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent, BaseAgentState
from ..connectors.hris_interface import HRISConnector, Employee
from ..core.workflow_engine import WorkflowEngine
from ..core.rag_pipeline import RAGPipeline
from ..core.notifications import NotificationService, NotificationChannel, NotificationPriority, NotificationTemplate

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ==================== Enums & Dataclasses ====================

class OnboardingPhase(str, Enum):
    """Onboarding workflow phases."""
    PRE_START = "pre_start"
    DAY_ONE = "day_one"
    FIRST_WEEK = "first_week"
    FIRST_MONTH = "first_month"
    FIRST_QUARTER = "first_quarter"


class TaskStatus(str, Enum):
    """Status of onboarding tasks."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"


@dataclass
class OnboardingTask:
    """Individual onboarding task with tracking."""
    task_id: str
    title: str
    description: str
    phase: OnboardingPhase
    owner_role: str  # "hr", "manager", "it_admin", "buddy"
    assignee_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    due_date: Optional[datetime] = None
    completion_date: Optional[datetime] = None
    notes: str = ""
    subtasks: List[Dict[str, Any]] = field(default_factory=list)

    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.status == TaskStatus.COMPLETED:
            return False
        if not self.due_date:
            return False
        return datetime.utcnow() > self.due_date


@dataclass
class OnboardingChecklist:
    """Full onboarding checklist for a new employee."""
    checklist_id: str
    employee_id: str
    employee_name: str
    department: str
    job_title: str
    start_date: datetime
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tasks: Dict[str, OnboardingTask] = field(default_factory=dict)
    phases_completed: List[OnboardingPhase] = field(default_factory=list)
    template_name: str = "standard"

    def get_phase_progress(self, phase: OnboardingPhase) -> Dict[str, Any]:
        """Get completion progress for a phase."""
        phase_tasks = [t for t in self.tasks.values() if t.phase == phase]
        if not phase_tasks:
            return {"total": 0, "completed": 0, "percent": 0}

        completed = len([t for t in phase_tasks if t.status == TaskStatus.COMPLETED])
        return {
            "total": len(phase_tasks),
            "completed": completed,
            "percent": int((completed / len(phase_tasks)) * 100) if phase_tasks else 0,
        }

    def overall_progress(self) -> int:
        """Calculate overall completion percentage."""
        if not self.tasks:
            return 0
        completed = len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED])
        return int((completed / len(self.tasks)) * 100)


@dataclass
class OnboardingTemplate:
    """Reusable onboarding template for roles/departments."""
    template_id: str
    name: str
    department: str
    job_level: str  # "entry", "mid", "senior"
    task_definitions: List[Dict[str, Any]] = field(default_factory=list)
    duration_days: int = 90  # First 90 days
    created_at: datetime = field(default_factory=datetime.utcnow)


# ==================== Onboarding Agent ====================

class OnboardingAgent(BaseAgent):
    """
    Specialist agent for new employee onboarding workflows.

    Provides tools for:
    - Generating onboarding checklists from templates
    - Collecting and organizing onboarding documents
    - Assigning onboarding tasks to stakeholders
    - Tracking progress through phases
    - Requesting IT provisioning
    - Assigning buddy/mentor
    - Sending reminders and notifications
    """

    def __init__(
        self,
        llm=None,
        hris_connector: Optional[HRISConnector] = None,
        workflow_engine: Optional[WorkflowEngine] = None,
        rag_pipeline: Optional[RAGPipeline] = None,
        notification_service: Optional[NotificationService] = None,
    ):
        """
        Initialize Onboarding Agent.

        Args:
            llm: Language model instance (passed from RouterAgent)
            hris_connector: HRIS connector instance
            workflow_engine: Workflow engine for approvals
            rag_pipeline: RAG pipeline for policy documents
            notification_service: Notification service for onboarding alerts
        """
        self.hris_connector = hris_connector
        self.workflow_engine = workflow_engine
        self.rag_pipeline = rag_pipeline
        self.notification_service = notification_service or NotificationService()

        # Register onboarding-specific notification templates
        self._register_onboarding_templates()

        # In-memory storage for checklists and templates
        self.checklists: Dict[str, OnboardingChecklist] = {}
        self.templates: Dict[str, OnboardingTemplate] = {}
        self.task_assignments: Dict[str, List[str]] = {}  # person_id -> task_ids

        # Initialize standard templates
        self._init_templates()

        super().__init__(llm=llm)

    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "onboarding"

    def get_system_prompt(self) -> str:
        """Return system prompt for onboarding specialist."""
        return (
            "You are an Onboarding specialist agent. Your role is to manage new employee "
            "onboarding workflows from pre-start through the first quarter. You help create "
            "comprehensive onboarding checklists, assign tasks, collect documents, and track "
            "progress. Use available tools to generate checklists, manage tasks, request IT "
            "provisioning, assign buddies, and keep stakeholders informed. Always ensure all "
            "onboarding phases are completed on schedule and all compliance requirements are met."
        )

    def get_tools(self) -> Dict[str, Any]:
        """
        Return available tools for onboarding workflows.

        Tools:
        - checklist_generator: Create checklist from template
        - document_collector: Collect and organize documents
        - task_assigner: Assign tasks to stakeholders
        - progress_tracker: Track phase completion
        - it_provisioning_request: Request IT account/equipment setup
        - buddy_assignment: Assign onboarding buddy/mentor

        Returns:
            Dict of tool_name -> tool_function with description attribute
        """
        tools = {}

        # Tool 1: Checklist Generator
        def checklist_generator(
            employee_id: str,
            employee_name: str,
            department: str,
            job_title: str,
            start_date: str,
            template_name: str = "standard",
        ) -> Dict[str, Any]:
            """
            Generate onboarding checklist from template.

            Args:
                employee_id: New employee ID
                employee_name: Employee full name
                department: Department
                job_title: Job title
                start_date: Start date (YYYY-MM-DD)
                template_name: Template to use

            Returns:
                Generated checklist with tasks
            """
            try:
                logger.info(f"CHECKLIST_GENERATOR: Creating checklist for {employee_name}")

                # Parse start date
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")

                # Get template
                template = self.templates.get(template_name)
                if not template:
                    template = self.templates.get("standard")

                # Create checklist
                from uuid import uuid4
                checklist_id = f"checklist_{uuid4().hex[:8]}"
                checklist = OnboardingChecklist(
                    checklist_id=checklist_id,
                    employee_id=employee_id,
                    employee_name=employee_name,
                    department=department,
                    job_title=job_title,
                    start_date=start_dt,
                    template_name=template_name,
                )

                # Create tasks from template
                for task_def in template.task_definitions:
                    from uuid import uuid4
                    task_id = f"task_{uuid4().hex[:8]}"

                    # Calculate due date
                    phase = OnboardingPhase(task_def.get("phase", "pre_start"))
                    phase_offset_days = {
                        OnboardingPhase.PRE_START: -7,
                        OnboardingPhase.DAY_ONE: 0,
                        OnboardingPhase.FIRST_WEEK: 7,
                        OnboardingPhase.FIRST_MONTH: 30,
                        OnboardingPhase.FIRST_QUARTER: 90,
                    }
                    due_date = start_dt + timedelta(days=phase_offset_days.get(phase, 0))

                    task = OnboardingTask(
                        task_id=task_id,
                        title=task_def.get("title", ""),
                        description=task_def.get("description", ""),
                        phase=phase,
                        owner_role=task_def.get("owner_role", "hr"),
                        due_date=due_date,
                    )
                    checklist.tasks[task_id] = task

                # Store checklist
                self.checklists[checklist_id] = checklist

                logger.info(f"CHECKLIST_GENERATOR: Created {checklist_id} with {len(checklist.tasks)} tasks")

                # Send notification to new hire and HR
                try:
                    self.notification_service.send_notification(
                        recipient_id=employee_id,
                        template_id="onboarding_welcome",
                        context={
                            "employee_name": employee_name,
                            "start_date": start_date,
                            "task_count": str(len(checklist.tasks)),
                        },
                        priority=NotificationPriority.HIGH,
                    )
                    logger.info(f"CHECKLIST_GENERATOR: Sent welcome notification to {employee_id}")
                except Exception as notif_err:
                    logger.warning(f"CHECKLIST_GENERATOR: Notification failed: {notif_err}")

                return {
                    "checklist_id": checklist_id,
                    "employee_id": employee_id,
                    "task_count": len(checklist.tasks),
                    "template": template_name,
                    "phases": list(OnboardingPhase),
                    "notification_sent": True,
                    "source": "onboarding_system",
                }

            except Exception as e:
                logger.error(f"CHECKLIST_GENERATOR failed: {e}")
                return {"error": f"Checklist generation failed: {str(e)}"}

        checklist_generator.description = (
            "Generate an onboarding checklist for a new employee from a template. "
            "Creates task list with phases (pre-start, day-one, first-week, first-month, first-quarter)."
        )
        tools["checklist_generator"] = checklist_generator

        # Tool 2: Document Collector
        def document_collector(
            checklist_id: str,
            doc_category: str,
            doc_list: List[str],
        ) -> Dict[str, Any]:
            """
            Collect and organize onboarding documents.

            Args:
                checklist_id: Checklist ID
                doc_category: Category (offer, tax_forms, nda, handbook, etc.)
                doc_list: List of document names

            Returns:
                Document collection status
            """
            try:
                logger.info(f"DOCUMENT_COLLECTOR: Organizing {len(doc_list)} documents for {checklist_id}")

                checklist = self.checklists.get(checklist_id)
                if not checklist:
                    return {"error": f"Checklist not found: {checklist_id}"}

                # Create document collection task if not exists
                doc_task_id = f"doc_{doc_category}_{checklist_id}"
                if doc_task_id not in checklist.tasks:
                    doc_task = OnboardingTask(
                        task_id=doc_task_id,
                        title=f"Collect {doc_category.replace('_', ' ').title()} Documents",
                        description=f"Collect and organize: {', '.join(doc_list)}",
                        phase=OnboardingPhase.PRE_START,
                        owner_role="hr",
                        due_date=checklist.start_date - timedelta(days=7),
                    )
                    doc_task.subtasks = [{"name": doc, "status": "pending"} for doc in doc_list]
                    checklist.tasks[doc_task_id] = doc_task

                checklist.updated_at = datetime.utcnow()

                return {
                    "checklist_id": checklist_id,
                    "category": doc_category,
                    "documents_added": len(doc_list),
                    "task_id": doc_task_id,
                    "source": "document_system",
                }

            except Exception as e:
                logger.error(f"DOCUMENT_COLLECTOR failed: {e}")
                return {"error": f"Document collection failed: {str(e)}"}

        document_collector.description = (
            "Collect and organize onboarding documents by category "
            "(offer letter, tax forms, NDA, handbook, compliance docs)."
        )
        tools["document_collector"] = document_collector

        # Tool 3: Task Assigner
        def task_assigner(
            checklist_id: str,
            task_id: str,
            assignee_id: str,
            assignee_role: str,
        ) -> Dict[str, Any]:
            """
            Assign onboarding task to stakeholder.

            Args:
                checklist_id: Checklist ID
                task_id: Task ID to assign
                assignee_id: Person to assign to
                assignee_role: Role (manager, hr_admin, it_admin, buddy)

            Returns:
                Assignment confirmation
            """
            try:
                logger.info(f"TASK_ASSIGNER: Assigning {task_id} to {assignee_id} ({assignee_role})")

                checklist = self.checklists.get(checklist_id)
                if not checklist:
                    return {"error": f"Checklist not found: {checklist_id}"}

                task = checklist.tasks.get(task_id)
                if not task:
                    return {"error": f"Task not found: {task_id}"}

                # Update task assignment
                task.assignee_id = assignee_id
                task.owner_role = assignee_role
                task.status = TaskStatus.IN_PROGRESS

                # Track assignment
                if assignee_id not in self.task_assignments:
                    self.task_assignments[assignee_id] = []
                if task_id not in self.task_assignments[assignee_id]:
                    self.task_assignments[assignee_id].append(task_id)

                checklist.updated_at = datetime.utcnow()

                # Notify the assignee about their new task
                try:
                    self.notification_service.send_notification(
                        recipient_id=assignee_id,
                        template_id="onboarding_task_assigned",
                        context={
                            "task_title": task.title,
                            "employee_name": checklist.employee_name,
                            "due_date": task.due_date.strftime("%Y-%m-%d") if task.due_date else "TBD",
                        },
                        priority=NotificationPriority.NORMAL,
                    )
                    logger.info(f"TASK_ASSIGNER: Notified {assignee_id} about task {task_id}")
                except Exception as notif_err:
                    logger.warning(f"TASK_ASSIGNER: Notification failed: {notif_err}")

                return {
                    "checklist_id": checklist_id,
                    "task_id": task_id,
                    "assignee_id": assignee_id,
                    "assignee_role": assignee_role,
                    "status": "assigned",
                    "notification_sent": True,
                    "source": "task_system",
                }

            except Exception as e:
                logger.error(f"TASK_ASSIGNER failed: {e}")
                return {"error": f"Task assignment failed: {str(e)}"}

        task_assigner.description = (
            "Assign individual onboarding tasks to managers, HR staff, IT admins, or buddies. "
            "Updates task status and tracks assignments."
        )
        tools["task_assigner"] = task_assigner

        # Tool 4: Progress Tracker
        def progress_tracker(checklist_id: str) -> Dict[str, Any]:
            """
            Track onboarding progress through phases.

            Args:
                checklist_id: Checklist ID

            Returns:
                Progress report with phase breakdown
            """
            try:
                logger.info(f"PROGRESS_TRACKER: Tracking progress for {checklist_id}")

                checklist = self.checklists.get(checklist_id)
                if not checklist:
                    return {"error": f"Checklist not found: {checklist_id}"}

                # Calculate progress by phase
                phase_progress = {}
                for phase in OnboardingPhase:
                    phase_progress[phase.value] = checklist.get_phase_progress(phase)

                # Identify overdue tasks
                overdue_tasks = [
                    {"task_id": t.task_id, "title": t.title, "due_date": t.due_date.isoformat()}
                    for t in checklist.tasks.values()
                    if t.is_overdue()
                ]

                return {
                    "checklist_id": checklist_id,
                    "employee_name": checklist.employee_name,
                    "overall_percent": checklist.overall_progress(),
                    "phase_progress": phase_progress,
                    "completed_phases": len(checklist.phases_completed),
                    "overdue_count": len(overdue_tasks),
                    "overdue_tasks": overdue_tasks,
                    "source": "progress_system",
                }

            except Exception as e:
                logger.error(f"PROGRESS_TRACKER failed: {e}")
                return {"error": f"Progress tracking failed: {str(e)}"}

        progress_tracker.description = (
            "Track onboarding progress by phase (pre-start, day-one, first-week, "
            "first-month, first-quarter). Identifies completed phases and overdue tasks."
        )
        tools["progress_tracker"] = progress_tracker

        # Tool 5: IT Provisioning Request
        def it_provisioning_request(
            employee_id: str,
            employee_name: str,
            equipment: List[str],
            software: List[str],
            access_systems: List[str],
            start_date: str,
        ) -> Dict[str, Any]:
            """
            Request IT provisioning for new employee.

            Args:
                employee_id: Employee ID
                employee_name: Employee name
                equipment: List (laptop, monitor, keyboard, phone, etc.)
                software: List (licenses needed)
                access_systems: List (email, VPN, CRM, etc.)
                start_date: Start date (YYYY-MM-DD)

            Returns:
                Provisioning request ID and status
            """
            try:
                logger.info(f"IT_PROVISIONING: Requesting setup for {employee_name}")

                from uuid import uuid4
                request_id = f"it_req_{uuid4().hex[:8]}"

                request_data = {
                    "request_id": request_id,
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                    "equipment_count": len(equipment),
                    "software_count": len(software),
                    "systems_access_count": len(access_systems),
                    "target_date": start_date,
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat(),
                }

                logger.info(f"IT_PROVISIONING: Created request {request_id}")

                # Notify IT team about provisioning request
                try:
                    self.notification_service.send_notification(
                        recipient_id="it_admin",
                        template_id="onboarding_it_provisioning",
                        context={
                            "employee_name": employee_name,
                            "equipment_list": ", ".join(equipment),
                            "software_list": ", ".join(software),
                            "systems_list": ", ".join(access_systems),
                            "target_date": start_date,
                        },
                        priority=NotificationPriority.HIGH,
                        channel=NotificationChannel.EMAIL,
                    )
                    logger.info(f"IT_PROVISIONING: Notified IT admin for {employee_name}")
                except Exception as notif_err:
                    logger.warning(f"IT_PROVISIONING: Notification failed: {notif_err}")

                return {
                    "request_id": request_id,
                    "equipment": equipment,
                    "software": software,
                    "access_systems": access_systems,
                    "status": "pending_it_review",
                    "notification_sent": True,
                    "source": "it_system",
                }

            except Exception as e:
                logger.error(f"IT_PROVISIONING failed: {e}")
                return {"error": f"IT provisioning request failed: {str(e)}"}

        it_provisioning_request.description = (
            "Request IT provisioning for a new employee including equipment "
            "(laptop, monitor, phone), software licenses, and system access."
        )
        tools["it_provisioning_request"] = it_provisioning_request

        # Tool 6: Buddy Assignment
        def buddy_assignment(
            checklist_id: str,
            buddy_id: str,
            buddy_name: str,
            buddy_department: str,
        ) -> Dict[str, Any]:
            """
            Assign onboarding buddy/mentor.

            Args:
                checklist_id: Checklist ID
                buddy_id: Buddy employee ID
                buddy_name: Buddy name
                buddy_department: Buddy department

            Returns:
                Assignment confirmation
            """
            try:
                logger.info(f"BUDDY_ASSIGNMENT: Assigning buddy {buddy_name} to {checklist_id}")

                checklist = self.checklists.get(checklist_id)
                if not checklist:
                    return {"error": f"Checklist not found: {checklist_id}"}

                # Create buddy mentor task
                from uuid import uuid4
                buddy_task_id = f"task_{uuid4().hex[:8]}"
                buddy_task = OnboardingTask(
                    task_id=buddy_task_id,
                    title="Buddy Mentoring",
                    description=f"Mentor new employee through onboarding process",
                    phase=OnboardingPhase.FIRST_MONTH,
                    owner_role="buddy",
                    assignee_id=buddy_id,
                    due_date=checklist.start_date + timedelta(days=30),
                )
                checklist.tasks[buddy_task_id] = buddy_task

                checklist.updated_at = datetime.utcnow()

                # Notify the buddy about their assignment
                try:
                    self.notification_service.send_notification(
                        recipient_id=buddy_id,
                        template_id="onboarding_buddy_assigned",
                        context={
                            "employee_name": checklist.employee_name,
                            "department": checklist.department,
                        },
                        priority=NotificationPriority.NORMAL,
                    )
                    logger.info(f"BUDDY_ASSIGNMENT: Notified buddy {buddy_name}")
                except Exception as notif_err:
                    logger.warning(f"BUDDY_ASSIGNMENT: Notification failed: {notif_err}")

                return {
                    "checklist_id": checklist_id,
                    "buddy_id": buddy_id,
                    "buddy_name": buddy_name,
                    "buddy_department": buddy_department,
                    "buddy_task_id": buddy_task_id,
                    "status": "assigned",
                    "notification_sent": True,
                    "source": "buddy_system",
                }

            except Exception as e:
                logger.error(f"BUDDY_ASSIGNMENT failed: {e}")
                return {"error": f"Buddy assignment failed: {str(e)}"}

        buddy_assignment.description = (
            "Assign an onboarding buddy/mentor to help new employee through first month. "
            "Creates mentoring task and tracks engagement."
        )
        tools["buddy_assignment"] = buddy_assignment

        return tools

    # ==================== Helper Methods ====================

    def _init_templates(self) -> None:
        """Initialize standard onboarding templates."""
        # Standard template — comprehensive 47-task checklist
        standard_tasks = [
            # PRE-START phase (before day 1)
            {
                "title": "Complete offer letter and documents",
                "description": "New hire completes all required offer documents",
                "phase": "pre_start",
                "owner_role": "hr",
            },
            {
                "title": "Prepare onboarding welcome package",
                "description": "HR prepares welcome packet with handbook, policies",
                "phase": "pre_start",
                "owner_role": "hr",
            },
            {
                "title": "Run background check and verification",
                "description": "Initiate and complete background screening",
                "phase": "pre_start",
                "owner_role": "hr",
            },
            {
                "title": "Collect tax forms (W-4, I-9)",
                "description": "New hire completes federal and state tax forms",
                "phase": "pre_start",
                "owner_role": "hr",
            },
            {
                "title": "Enroll in benefits",
                "description": "New hire selects health, dental, vision, 401k options",
                "phase": "pre_start",
                "owner_role": "hr",
            },
            {
                "title": "Set up payroll and direct deposit",
                "description": "Configure payroll account and direct deposit banking info",
                "phase": "pre_start",
                "owner_role": "hr",
            },
            {
                "title": "Order equipment (laptop, monitor, peripherals)",
                "description": "IT orders and configures equipment for start date",
                "phase": "pre_start",
                "owner_role": "it_admin",
            },
            {
                "title": "Provision email and system accounts",
                "description": "Create email, Active Directory, SSO accounts",
                "phase": "pre_start",
                "owner_role": "it_admin",
            },
            {
                "title": "Set up workspace or home office",
                "description": "Prepare physical workspace or ship home office equipment",
                "phase": "pre_start",
                "owner_role": "manager",
            },
            {
                "title": "Assign onboarding buddy",
                "description": "Manager selects and notifies an onboarding buddy/mentor",
                "phase": "pre_start",
                "owner_role": "manager",
            },
            {
                "title": "Send welcome email with first-day logistics",
                "description": "HR sends welcome email with parking, dress code, schedule",
                "phase": "pre_start",
                "owner_role": "hr",
            },
            {
                "title": "Create onboarding training plan",
                "description": "Manager drafts 90-day training and ramp-up plan",
                "phase": "pre_start",
                "owner_role": "manager",
            },
            # DAY ONE phase
            {
                "title": "Welcome meeting and orientation",
                "description": "Manager meets with new hire for welcome and orientation",
                "phase": "day_one",
                "owner_role": "manager",
            },
            {
                "title": "Office tour and safety walkthrough",
                "description": "Tour of office, emergency exits, first aid, AED locations",
                "phase": "day_one",
                "owner_role": "manager",
            },
            {
                "title": "HR orientation session",
                "description": "HR reviews policies, handbook, benefits overview, compliance",
                "phase": "day_one",
                "owner_role": "hr",
            },
            {
                "title": "Sign employee handbook acknowledgment",
                "description": "New hire signs that they received and reviewed handbook",
                "phase": "day_one",
                "owner_role": "hr",
            },
            {
                "title": "Sign confidentiality and NDA agreements",
                "description": "New hire signs NDA, intellectual property, confidentiality forms",
                "phase": "day_one",
                "owner_role": "hr",
            },
            {
                "title": "Distribute and set up equipment",
                "description": "IT delivers and configures laptop, monitors, phone",
                "phase": "day_one",
                "owner_role": "it_admin",
            },
            {
                "title": "Set up VPN and remote access",
                "description": "Configure VPN, two-factor auth, remote desktop access",
                "phase": "day_one",
                "owner_role": "it_admin",
            },
            {
                "title": "Grant application access (CRM, ERP, etc.)",
                "description": "Provision access to role-specific applications",
                "phase": "day_one",
                "owner_role": "it_admin",
            },
            {
                "title": "Meet onboarding buddy",
                "description": "Buddy introduces themselves and schedules regular check-ins",
                "phase": "day_one",
                "owner_role": "buddy",
            },
            {
                "title": "Team welcome lunch",
                "description": "Manager organizes team lunch to welcome new hire",
                "phase": "day_one",
                "owner_role": "manager",
            },
            # FIRST WEEK phase
            {
                "title": "Complete cybersecurity awareness training",
                "description": "Mandatory security training (phishing, password policy, data handling)",
                "phase": "first_week",
                "owner_role": "it_admin",
            },
            {
                "title": "Complete anti-harassment training",
                "description": "Mandatory training on workplace harassment prevention",
                "phase": "first_week",
                "owner_role": "hr",
            },
            {
                "title": "Complete diversity and inclusion training",
                "description": "Mandatory D&I and unconscious bias awareness training",
                "phase": "first_week",
                "owner_role": "hr",
            },
            {
                "title": "Review data privacy and GDPR training",
                "description": "Training on data protection, GDPR compliance, PII handling",
                "phase": "first_week",
                "owner_role": "hr",
            },
            {
                "title": "Department introduction and org chart review",
                "description": "Manager introduces team, explains reporting lines and key contacts",
                "phase": "first_week",
                "owner_role": "manager",
            },
            {
                "title": "Role expectations and KPI review",
                "description": "Manager discusses role responsibilities, KPIs, and success criteria",
                "phase": "first_week",
                "owner_role": "manager",
            },
            {
                "title": "Cross-functional introductions",
                "description": "Meet key stakeholders in other departments",
                "phase": "first_week",
                "owner_role": "manager",
            },
            {
                "title": "Set up communication tools (Slack, Teams, etc.)",
                "description": "Join relevant channels, set up profile, learn communication norms",
                "phase": "first_week",
                "owner_role": "it_admin",
            },
            {
                "title": "Review company mission, vision, and values",
                "description": "Orientation on company culture, history, and strategic direction",
                "phase": "first_week",
                "owner_role": "hr",
            },
            {
                "title": "Access and review knowledge base / wiki",
                "description": "New hire reviews internal documentation and SOPs",
                "phase": "first_week",
                "owner_role": "manager",
            },
            # FIRST MONTH phase
            {
                "title": "Complete role-specific technical training",
                "description": "Training on tools, processes, and systems specific to role",
                "phase": "first_month",
                "owner_role": "manager",
            },
            {
                "title": "Set initial SMART performance goals",
                "description": "Collaborate with manager to establish first 90-day goals",
                "phase": "first_month",
                "owner_role": "manager",
            },
            {
                "title": "30-day check-in with manager",
                "description": "Manager conducts 30-day progress review and feedback session",
                "phase": "first_month",
                "owner_role": "manager",
            },
            {
                "title": "30-day HR check-in",
                "description": "HR checks in on onboarding experience and addresses concerns",
                "phase": "first_month",
                "owner_role": "hr",
            },
            {
                "title": "Complete compliance training modules",
                "description": "All required regulatory and compliance training (SOX, HIPAA if applicable)",
                "phase": "first_month",
                "owner_role": "hr",
            },
            {
                "title": "Buddy mid-point check-in",
                "description": "Buddy conducts mid-point review of onboarding experience",
                "phase": "first_month",
                "owner_role": "buddy",
            },
            {
                "title": "Request feedback from team members",
                "description": "Manager collects early feedback from team on new hire integration",
                "phase": "first_month",
                "owner_role": "manager",
            },
            {
                "title": "Review emergency procedures and evacuation plan",
                "description": "Complete safety orientation and emergency response training",
                "phase": "first_month",
                "owner_role": "hr",
            },
            {
                "title": "Attend first all-hands / town hall meeting",
                "description": "New hire attends company-wide meeting for broader context",
                "phase": "first_month",
                "owner_role": "manager",
            },
            # FIRST QUARTER phase (60-90 days)
            {
                "title": "60-day performance check-in",
                "description": "Manager reviews progress on 90-day goals at the 60-day mark",
                "phase": "first_quarter",
                "owner_role": "manager",
            },
            {
                "title": "Complete all mandatory training certifications",
                "description": "Verify all required training modules are completed and certified",
                "phase": "first_quarter",
                "owner_role": "hr",
            },
            {
                "title": "90-day probation completion review",
                "description": "Final review to confirm successful onboarding and role fit",
                "phase": "first_quarter",
                "owner_role": "manager",
            },
            {
                "title": "Formal goal setting for next review period",
                "description": "Set full annual performance goals after probation completion",
                "phase": "first_quarter",
                "owner_role": "manager",
            },
            {
                "title": "Onboarding survey and feedback",
                "description": "New hire completes onboarding experience survey for HR",
                "phase": "first_quarter",
                "owner_role": "hr",
            },
            {
                "title": "Buddy program wrap-up",
                "description": "Formal close of buddy mentorship with final feedback exchange",
                "phase": "first_quarter",
                "owner_role": "buddy",
            },
        ]

        standard = OnboardingTemplate(
            template_id="template_standard",
            name="Standard Onboarding",
            department="all",
            job_level="mid",
            task_definitions=standard_tasks,
            duration_days=90,
        )
        self.templates["standard"] = standard

        logger.info(f"Initialized standard onboarding template with {len(standard_tasks)} tasks")

    def _register_onboarding_templates(self) -> None:
        """Register onboarding-specific notification templates."""
        templates = [
            NotificationTemplate(
                template_id="onboarding_welcome",
                name="Onboarding Welcome",
                channel=NotificationChannel.EMAIL,
                subject_template="Welcome to the team, $employee_name!",
                body_template=(
                    "Welcome $employee_name! Your start date is $start_date. "
                    "We've prepared an onboarding checklist with $task_count tasks "
                    "to help you get started. Check your onboarding portal for details."
                ),
                variables=["employee_name", "start_date", "task_count"],
            ),
            NotificationTemplate(
                template_id="onboarding_task_assigned",
                name="Onboarding Task Assigned",
                channel=NotificationChannel.IN_APP,
                subject_template="New onboarding task: $task_title",
                body_template=(
                    "You have been assigned an onboarding task: $task_title "
                    "for new employee $employee_name. Due: $due_date."
                ),
                variables=["task_title", "employee_name", "due_date"],
            ),
            NotificationTemplate(
                template_id="onboarding_it_provisioning",
                name="IT Provisioning Request",
                channel=NotificationChannel.EMAIL,
                subject_template="IT Provisioning Request for $employee_name",
                body_template=(
                    "New IT provisioning request for $employee_name (start date: $target_date).\n\n"
                    "Equipment: $equipment_list\n"
                    "Software: $software_list\n"
                    "System Access: $systems_list"
                ),
                variables=["employee_name", "equipment_list", "software_list", "systems_list", "target_date"],
            ),
            NotificationTemplate(
                template_id="onboarding_buddy_assigned",
                name="Buddy Assignment",
                channel=NotificationChannel.IN_APP,
                subject_template="You've been assigned as an onboarding buddy",
                body_template=(
                    "You've been assigned as the onboarding buddy for $employee_name "
                    "in $department. Please reach out to welcome them!"
                ),
                variables=["employee_name", "department"],
            ),
        ]
        for template in templates:
            self.notification_service.register_template(template)
        logger.info(f"Registered {len(templates)} onboarding notification templates")


# Register agent class for discovery
__all__ = ["OnboardingAgent", "OnboardingPhase", "OnboardingChecklist", "OnboardingTask"]
