"""
Local Database Connector — Implements HRISConnector using SQLAlchemy models.

Bridges the HRIS connector interface to the local PostgreSQL/SQLite database,
enabling AI agents to query real employee, leave, benefits, and org data.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from .hris_interface import (
    BenefitsPlan,
    Employee,
    EmployeeStatus,
    HRISConnector,
    LeaveBalance,
    LeaveRequest,
    LeaveStatus,
    LeaveType,
    OrgNode,
    PlanType,
)

logger = logging.getLogger(__name__)


def _map_leave_type(raw: str) -> LeaveType:
    """Map database leave_type strings to LeaveType enum."""
    mapping = {
        "vacation": LeaveType.PTO,
        "pto": LeaveType.PTO,
        "sick": LeaveType.SICK,
        "personal": LeaveType.PERSONAL,
        "unpaid": LeaveType.UNPAID,
    }
    return mapping.get(raw.lower(), LeaveType.OTHER)


def _map_plan_type(raw: str) -> PlanType:
    """Map database plan_type strings to PlanType enum."""
    mapping = {
        "health": PlanType.HEALTH,
        "medical": PlanType.HEALTH,
        "dental": PlanType.DENTAL,
        "vision": PlanType.VISION,
        "401k": PlanType.FOUR_01K,
        "retirement": PlanType.FOUR_01K,
        "life": PlanType.LIFE_INSURANCE,
        "life_insurance": PlanType.LIFE_INSURANCE,
    }
    return mapping.get(raw.lower(), PlanType.OTHER)


class LocalDBConnector(HRISConnector):
    """
    HRIS connector that queries the local SQLAlchemy database.

    Uses the same SessionLocal/models from src.core.database so it works
    with both PostgreSQL (production) and SQLite (development).
    """

    def __init__(self):
        """Initialize — session factory is imported lazily to avoid circular deps."""
        self._session_factory = None

    def _get_session(self):
        """Lazy import of SessionLocal to avoid circular imports at module load."""
        if self._session_factory is None:
            from src.core.database import SessionLocal

            self._session_factory = SessionLocal
        if self._session_factory is None:
            raise ConnectionError("Database session not available")
        return self._session_factory()

    # ------------------------------------------------------------------
    # Employee Operations
    # ------------------------------------------------------------------

    def get_employee(self, employee_id: str) -> Optional[Employee]:
        from src.core.database import Employee as DBEmployee

        session = self._get_session()
        try:
            emp = session.query(DBEmployee).filter_by(id=int(employee_id)).first()
            if not emp:
                return None
            return self._to_employee_model(emp)
        finally:
            session.close()

    def search_employees(self, filters: Dict[str, Any]) -> List[Employee]:
        from src.core.database import Employee as DBEmployee

        session = self._get_session()
        try:
            query = session.query(DBEmployee).filter_by(status="active")

            if "department" in filters:
                query = query.filter(DBEmployee.department.ilike(f"%{filters['department']}%"))
            if "name" in filters:
                name_term = f"%{filters['name']}%"
                query = query.filter(
                    (DBEmployee.first_name.ilike(name_term))
                    | (DBEmployee.last_name.ilike(name_term))
                )
            if "email" in filters:
                query = query.filter(DBEmployee.email.ilike(f"%{filters['email']}%"))
            if "role" in filters:
                query = query.filter(DBEmployee.role_level == filters["role"])

            employees = query.limit(50).all()
            return [self._to_employee_model(e) for e in employees]
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Leave Operations
    # ------------------------------------------------------------------

    def get_leave_balance(self, employee_id: str) -> List[LeaveBalance]:
        from src.core.database import LeaveBalance as DBBalance

        session = self._get_session()
        try:
            bal = session.query(DBBalance).filter_by(employee_id=int(employee_id)).first()
            if not bal:
                return []

            balances = []
            for leave_type, total_attr, used_attr in [
                ("vacation", "vacation_total", "vacation_used"),
                ("sick", "sick_total", "sick_used"),
                ("personal", "personal_total", "personal_used"),
            ]:
                total = getattr(bal, total_attr, 0) or 0
                used = getattr(bal, used_attr, 0) or 0
                balances.append(
                    LeaveBalance(
                        employee_id=str(employee_id),
                        leave_type=_map_leave_type(leave_type),
                        total_days=total,
                        used_days=used,
                        pending_days=0,
                        available_days=total - used,
                    )
                )

            return balances
        finally:
            session.close()

    def get_leave_requests(
        self, employee_id: str, status: Optional[str] = None
    ) -> List[LeaveRequest]:
        from src.core.database import LeaveRequest as DBLeaveReq

        session = self._get_session()
        try:
            query = session.query(DBLeaveReq).filter_by(employee_id=int(employee_id))
            if status:
                query = query.filter_by(status=status)
            query = query.order_by(DBLeaveReq.created_at.desc()).limit(20)

            requests = []
            for lr in query.all():
                status_map = {
                    "pending": LeaveStatus.PENDING,
                    "approved": LeaveStatus.APPROVED,
                    "denied": LeaveStatus.DENIED,
                    "rejected": LeaveStatus.DENIED,
                    "cancelled": LeaveStatus.CANCELLED,
                }
                requests.append(
                    LeaveRequest(
                        id=str(lr.id),
                        employee_id=str(lr.employee_id),
                        leave_type=_map_leave_type(lr.leave_type or "pto"),
                        start_date=lr.start_date,
                        end_date=lr.end_date,
                        status=status_map.get(lr.status, LeaveStatus.PENDING),
                        reason=lr.reason,
                        approver_id=str(lr.approved_by) if lr.approved_by else None,
                        submitted_at=lr.created_at or datetime.utcnow(),
                    )
                )
            return requests
        finally:
            session.close()

    def submit_leave_request(self, request: LeaveRequest) -> LeaveRequest:
        from src.core.database import LeaveRequest as DBLeaveReq

        session = self._get_session()
        try:
            new_req = DBLeaveReq(
                employee_id=int(request.employee_id),
                leave_type=(
                    request.leave_type.value
                    if hasattr(request.leave_type, "value")
                    else str(request.leave_type)
                ),
                start_date=request.start_date,
                end_date=request.end_date,
                reason=request.reason,
                status="pending",
            )
            session.add(new_req)
            session.commit()
            request.id = str(new_req.id)
            request.status = LeaveStatus.PENDING
            return request
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Org Chart
    # ------------------------------------------------------------------

    def get_org_chart(self, department: Optional[str] = None) -> List[OrgNode]:
        from src.core.database import Employee as DBEmployee

        session = self._get_session()
        try:
            query = session.query(DBEmployee).filter_by(status="active")
            if department:
                query = query.filter(DBEmployee.department.ilike(f"%{department}%"))

            employees = query.all()

            # Build parent -> children mapping
            children_map: Dict[int, List] = {}
            emp_map: Dict[int, Any] = {}
            for e in employees:
                emp_map[e.id] = e
                parent_id = e.manager_id or 0
                children_map.setdefault(parent_id, []).append(e)

            def build_node(emp) -> OrgNode:
                direct = children_map.get(emp.id, [])
                return OrgNode(
                    employee_id=str(emp.id),
                    name=f"{emp.first_name} {emp.last_name}",
                    title=emp.role_level.replace("_", " ").title(),
                    department=emp.department,
                    direct_reports=[build_node(c) for c in direct],
                )

            # Return top-level nodes (no manager or manager not in result set)
            roots = []
            for e in employees:
                if e.manager_id is None or e.manager_id not in emp_map:
                    roots.append(build_node(e))
            return roots
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Benefits
    # ------------------------------------------------------------------

    def get_benefits(self, employee_id: str) -> List[BenefitsPlan]:
        from src.core.database import BenefitsEnrollment, BenefitsPlan as DBPlan

        session = self._get_session()
        try:
            enrollments = (
                session.query(BenefitsEnrollment)
                .filter_by(employee_id=int(employee_id), status="active")
                .all()
            )

            plans = []
            for enr in enrollments:
                plan = session.query(DBPlan).filter_by(id=enr.plan_id).first()
                if plan:
                    plans.append(
                        BenefitsPlan(
                            id=str(plan.id),
                            name=plan.plan_name,
                            plan_type=_map_plan_type(plan.plan_type),
                            coverage_level=enr.coverage_level,
                            employee_cost=plan.monthly_cost or 0,
                            employer_cost=(plan.monthly_cost or 0) * 0.8,
                        )
                    )
            return plans
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        try:
            session = self._get_session()
            session.execute(text("SELECT 1"))
            session.close()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _to_employee_model(emp) -> Employee:
        """Convert a SQLAlchemy Employee row to the HRIS Employee pydantic model."""
        status_map = {
            "active": EmployeeStatus.ACTIVE,
            "inactive": EmployeeStatus.INACTIVE,
            "on_leave": EmployeeStatus.ON_LEAVE,
            "terminated": EmployeeStatus.TERMINATED,
        }
        return Employee(
            id=str(emp.id),
            hris_id=emp.hris_id or f"EMP-{emp.id}",
            first_name=emp.first_name,
            last_name=emp.last_name,
            email=emp.email,
            department=emp.department,
            job_title=emp.role_level.replace("_", " ").title(),
            manager_id=str(emp.manager_id) if emp.manager_id else None,
            hire_date=emp.hire_date or datetime(2024, 1, 1),
            status=status_map.get(emp.status, EmployeeStatus.ACTIVE),
            location="Remote",
            phone=None,
        )
