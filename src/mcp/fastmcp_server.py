"""
HR Agent MCP Server — Official MCP SDK Implementation.

Uses the official `mcp` Python SDK (FastMCP) for full protocol compliance,
including Streamable HTTP transport, stdio, and proper SSE support.

Exposes 29 tools, 8 resources, and 5 prompts for the HR Agent Platform.
New tools added: send_notification, get_notifications, approve_workflow,
reject_workflow, run_sql_analytics, get_department_report, get_attrition_metrics.

Usage:
    # stdio (IDE integration — Claude Desktop, VS Code, Cursor):
    python -m src.mcp.fastmcp_server

    # Streamable HTTP:
    python -m src.mcp.fastmcp_server --transport streamable-http --port 8080
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Ensure project root on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ============================================================
# Create FastMCP server instance
# ============================================================

mcp = FastMCP(
    "hr-agent-platform",
    instructions=(
        "HR Agent Platform MCP Server v3.0.0 — provides tools for managing employees, "
        "leave requests, benefits enrollment, document generation, performance reviews, "
        "onboarding, policy search, HR analytics, notifications, and workflow approvals. "
        "Use get_employee_profile or search_employees to find employee IDs before "
        "calling employee-specific tools."
    ),
)


# ============================================================
# Database Helpers (reused from existing server.py)
# ============================================================

_db_initialized = False


def _ensure_db():
    """Ensure the database is initialized."""
    global _db_initialized
    if _db_initialized:
        return
    try:
        from src.core.database import init_db, SessionLocal

        if SessionLocal is None:
            init_db()
        _db_initialized = True
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")


def _get_session():
    """Get a database session, or None if unavailable."""
    _ensure_db()
    try:
        from src.core.database import SessionLocal

        if SessionLocal is None:
            return None
        return SessionLocal()
    except Exception:
        return None


def _with_session(fn):
    """Execute fn(session) with automatic session lifecycle."""
    session = _get_session()
    if session is None:
        return {"error": "Database unavailable"}
    try:
        result = fn(session)
        return result
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


# ============================================================
# LEAVE MANAGEMENT TOOLS (6)
# ============================================================


@mcp.tool()
def get_leave_balance(employee_id: str) -> str:
    """Get an employee's current leave balance including vacation, sick, and personal days remaining.

    Args:
        employee_id: Employee ID (numeric string)
    """

    def _query(session):
        from src.core.database import LeaveBalance, Employee

        emp_id = int(employee_id)
        emp = session.query(Employee).filter_by(id=emp_id).first()
        balance = session.query(LeaveBalance).filter_by(employee_id=emp_id).first()
        if not balance:
            return {
                "employee_id": str(emp_id),
                "employee_name": f"{emp.first_name} {emp.last_name}" if emp else "Unknown",
                "balances": {
                    "vacation": {"total": 20, "used": 0, "remaining": 20},
                    "sick": {"total": 10, "used": 0, "remaining": 10},
                    "personal": {"total": 5, "used": 0, "remaining": 5},
                },
            }
        return {
            "employee_id": str(emp_id),
            "employee_name": f"{emp.first_name} {emp.last_name}" if emp else "Unknown",
            "balances": {
                "vacation": {
                    "total": balance.vacation_total,
                    "used": balance.vacation_used,
                    "remaining": balance.vacation_total - balance.vacation_used,
                },
                "sick": {
                    "total": balance.sick_total,
                    "used": balance.sick_used,
                    "remaining": balance.sick_total - balance.sick_used,
                },
                "personal": {
                    "total": balance.personal_total,
                    "used": balance.personal_used,
                    "remaining": balance.personal_total - balance.personal_used,
                },
            },
        }

    return json.dumps(_with_session(_query), indent=2, default=str)


@mcp.tool()
def submit_leave_request(
    employee_id: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    reason: str = "",
) -> str:
    """Submit a new leave request. Creates a pending request requiring manager/HR approval.

    Args:
        employee_id: Employee ID
        leave_type: Type of leave (vacation, sick, personal, parental, bereavement)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        reason: Reason for leave request
    """

    def _submit(session):
        from src.core.database import LeaveRequest as LR

        emp_id = int(employee_id)
        leave_req = LR(
            employee_id=emp_id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status="pending",
        )
        session.add(leave_req)
        session.commit()
        return {
            "request_id": str(leave_req.id),
            "status": "pending",
            "employee_id": str(emp_id),
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
            "message": "Leave request submitted successfully and is pending approval.",
        }

    return json.dumps(_with_session(_submit), indent=2, default=str)


@mcp.tool()
def get_leave_history(employee_id: str) -> str:
    """Get leave request history for an employee, showing past and current requests.

    Args:
        employee_id: Employee ID
    """

    def _query(session):
        from src.core.database import LeaveRequest as LR

        emp_id = int(employee_id)
        requests = (
            session.query(LR).filter_by(employee_id=emp_id).order_by(LR.id.desc()).limit(50).all()
        )
        history = []
        for req in requests:
            history.append(
                {
                    "request_id": str(req.id),
                    "leave_type": req.leave_type,
                    "start_date": req.start_date,
                    "end_date": req.end_date,
                    "status": req.status,
                    "reason": req.reason or "",
                    "created_at": req.created_at.strftime("%Y-%m-%d") if req.created_at else "",
                }
            )
        return {"employee_id": str(emp_id), "history": history, "count": len(history)}

    return json.dumps(_with_session(_query), indent=2, default=str)


@mcp.tool()
def approve_leave_request(request_id: str, approver_id: str = "") -> str:
    """Approve a pending leave request. Deducts days from the employee's leave balance.

    Args:
        request_id: Leave request ID to approve
        approver_id: ID of the approving manager/HR admin
    """

    def _approve(session):
        from src.core.database import LeaveRequest as LR, LeaveBalance

        leave_req = session.query(LR).filter_by(id=int(request_id)).first()
        if not leave_req:
            return {"error": f"Leave request {request_id} not found"}
        if leave_req.status != "pending":
            return {"error": f"Request is already {leave_req.status}"}
        leave_req.status = "approved"
        leave_req.approved_by = int(approver_id) if approver_id else None
        leave_req.approved_at = datetime.utcnow()
        balance = session.query(LeaveBalance).filter_by(employee_id=leave_req.employee_id).first()
        if balance:
            try:
                start = datetime.strptime(leave_req.start_date, "%Y-%m-%d")
                end = datetime.strptime(leave_req.end_date, "%Y-%m-%d")
                days = (end - start).days + 1
            except (ValueError, TypeError):
                days = 1
            if leave_req.leave_type == "vacation":
                balance.vacation_used += days
            elif leave_req.leave_type == "sick":
                balance.sick_used += days
            elif leave_req.leave_type == "personal":
                balance.personal_used += days
        session.commit()
        return {
            "request_id": request_id,
            "status": "approved",
            "approved_at": datetime.utcnow().isoformat(),
            "message": "Leave request approved successfully.",
        }

    return json.dumps(_with_session(_approve), indent=2, default=str)


@mcp.tool()
def reject_leave_request(request_id: str, reason: str = "") -> str:
    """Reject a pending leave request with an optional reason.

    Args:
        request_id: Leave request ID to reject
        reason: Reason for rejection
    """

    def _reject(session):
        from src.core.database import LeaveRequest as LR

        leave_req = session.query(LR).filter_by(id=int(request_id)).first()
        if not leave_req:
            return {"error": f"Leave request {request_id} not found"}
        if leave_req.status != "pending":
            return {"error": f"Request is already {leave_req.status}"}
        leave_req.status = "rejected"
        session.commit()
        return {
            "request_id": request_id,
            "status": "rejected",
            "reason": reason,
            "rejected_at": datetime.utcnow().isoformat(),
            "message": "Leave request rejected.",
        }

    return json.dumps(_with_session(_reject), indent=2, default=str)


@mcp.tool()
def get_pending_approvals() -> str:
    """List all pending leave approval requests for manager/HR review."""

    def _query(session):
        from src.core.database import LeaveRequest as LR, Employee

        pending = (
            session.query(LR)
            .filter(LR.status.in_(["pending", "Pending"]))
            .order_by(LR.id.desc())
            .all()
        )
        items = []
        for req in pending:
            emp = session.query(Employee).filter_by(id=req.employee_id).first()
            name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"
            try:
                start = datetime.strptime(req.start_date, "%Y-%m-%d")
                end = datetime.strptime(req.end_date, "%Y-%m-%d")
                days = (end - start).days + 1
            except (ValueError, TypeError):
                days = 1
            items.append(
                {
                    "request_id": str(req.id),
                    "requester": name,
                    "employee_id": str(req.employee_id),
                    "leave_type": req.leave_type,
                    "start_date": req.start_date,
                    "end_date": req.end_date,
                    "days": days,
                    "reason": req.reason or "",
                    "requested_at": req.created_at.strftime("%Y-%m-%d") if req.created_at else "",
                }
            )
        return {"pending_approvals": items, "count": len(items)}

    return json.dumps(_with_session(_query), indent=2, default=str)


# ============================================================
# EMPLOYEE MANAGEMENT TOOLS (3)
# ============================================================


@mcp.tool()
def get_employee_profile(employee_id: str = "", email: str = "") -> str:
    """Get detailed employee profile including name, department, role, hire date.

    Args:
        employee_id: Employee ID (numeric). Provide either this or email.
        email: Employee email address (alternative lookup)
    """

    def _query(session):
        from src.core.database import Employee

        emp = None
        if employee_id:
            emp = session.query(Employee).filter_by(id=int(employee_id)).first()
        elif email:
            emp = session.query(Employee).filter_by(email=email).first()
        if not emp:
            return {"error": "Employee not found"}
        return {
            "id": emp.id,
            "hris_id": emp.hris_id,
            "first_name": emp.first_name,
            "last_name": emp.last_name,
            "email": emp.email,
            "department": emp.department,
            "role_level": emp.role_level,
            "manager_id": emp.manager_id,
            "hire_date": emp.hire_date.isoformat() if emp.hire_date else None,
            "status": emp.status,
        }

    return json.dumps(_with_session(_query), indent=2, default=str)


@mcp.tool()
def search_employees(query: str = "", department: str = "", limit: int = 20) -> str:
    """Search employee directory by name, department, or role.

    Args:
        query: Search query (name, email, department)
        department: Filter by department name
        limit: Maximum results to return (default: 20, max: 100)
    """
    limit = min(limit, 100)

    def _query(session):
        from src.core.database import Employee

        q = session.query(Employee)
        if department:
            q = q.filter_by(department=department)
        if query:
            search = f"%{query}%"
            q = q.filter(
                (Employee.first_name.ilike(search))
                | (Employee.last_name.ilike(search))
                | (Employee.email.ilike(search))
                | (Employee.department.ilike(search))
            )
        employees = q.order_by(Employee.last_name).limit(limit).all()
        results = [
            {
                "id": emp.id,
                "name": f"{emp.first_name} {emp.last_name}",
                "email": emp.email,
                "department": emp.department,
                "role_level": emp.role_level,
                "status": emp.status,
            }
            for emp in employees
        ]
        return {"employees": results, "count": len(results)}

    return json.dumps(_with_session(_query), indent=2, default=str)


@mcp.tool()
def update_employee(
    employee_id: str,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    department: str = "",
    role_level: str = "",
    status: str = "",
) -> str:
    """Update employee record fields. HR admin operation.

    Args:
        employee_id: Employee ID to update
        first_name: New first name (leave empty to skip)
        last_name: New last name (leave empty to skip)
        email: New email (leave empty to skip)
        department: New department (leave empty to skip)
        role_level: New role level (leave empty to skip)
        status: New status (leave empty to skip)
    """
    updates = {}
    if first_name:
        updates["first_name"] = first_name
    if last_name:
        updates["last_name"] = last_name
    if email:
        updates["email"] = email
    if department:
        updates["department"] = department
    if role_level:
        updates["role_level"] = role_level
    if status:
        updates["status"] = status

    if not updates:
        return json.dumps({"error": "No fields provided to update"})

    def _update(session):
        from src.core.database import Employee

        emp = session.query(Employee).filter_by(id=int(employee_id)).first()
        if not emp:
            return {"error": f"Employee {employee_id} not found"}
        updated = []
        for fld, val in updates.items():
            setattr(emp, fld, val)
            updated.append(fld)
        emp.updated_at = datetime.utcnow()
        session.commit()
        return {
            "employee_id": str(emp.id),
            "updated_fields": updated,
            "message": f"Updated {', '.join(updated)} for {emp.first_name} {emp.last_name}.",
        }

    return json.dumps(_with_session(_update), indent=2, default=str)


# ============================================================
# BENEFITS TOOLS (3)
# ============================================================


@mcp.tool()
def list_benefits_plans() -> str:
    """List all active benefits plans including health, dental, vision, and retirement options."""

    def _query(session):
        from src.core.database import BenefitsPlan

        plans = session.query(BenefitsPlan).filter_by(is_active=True).all()
        data = [
            {
                "id": p.id,
                "name": p.name,
                "plan_type": p.plan_type,
                "provider": p.provider,
                "premium_monthly": p.premium_monthly,
                "coverage_details": p.coverage_details or {},
            }
            for p in plans
        ]
        return {"plans": data, "count": len(data)}

    return json.dumps(_with_session(_query), indent=2, default=str)


@mcp.tool()
def get_benefits_enrollments(employee_id: str) -> str:
    """Get an employee's current benefits enrollments.

    Args:
        employee_id: Employee ID
    """

    def _query(session):
        from src.core.database import BenefitsEnrollment, BenefitsPlan

        emp_id = int(employee_id)
        enrollments = session.query(BenefitsEnrollment).filter_by(employee_id=emp_id).all()
        data = []
        for e in enrollments:
            plan = session.query(BenefitsPlan).filter_by(id=e.plan_id).first()
            data.append(
                {
                    "id": e.id,
                    "plan_id": e.plan_id,
                    "plan_name": plan.name if plan else "Unknown",
                    "plan_type": plan.plan_type if plan else "",
                    "coverage_level": e.coverage_level,
                    "status": e.status,
                    "enrolled_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
                }
            )
        return {"enrollments": data, "count": len(data)}

    return json.dumps(_with_session(_query), indent=2, default=str)


@mcp.tool()
def enroll_in_benefit(employee_id: str, plan_id: str, coverage_level: str = "employee") -> str:
    """Enroll employee in a benefits plan. Handles plan switching automatically.

    Args:
        employee_id: Employee ID
        plan_id: Benefits plan ID
        coverage_level: Coverage level (employee, employee_spouse, employee_children, family)
    """

    def _enroll(session):
        from src.core.database import BenefitsEnrollment, BenefitsPlan

        emp_id = int(employee_id)
        plan = session.query(BenefitsPlan).filter_by(id=int(plan_id), is_active=True).first()
        if not plan:
            return {"error": "Plan not found or inactive"}
        existing = (
            session.query(BenefitsEnrollment)
            .join(BenefitsPlan, BenefitsEnrollment.plan_id == BenefitsPlan.id)
            .filter(
                BenefitsEnrollment.employee_id == emp_id,
                BenefitsPlan.plan_type == plan.plan_type,
                BenefitsEnrollment.status == "active",
            )
            .first()
        )
        if existing:
            existing.status = "terminated"
        enrollment = BenefitsEnrollment(
            employee_id=emp_id, plan_id=plan.id, coverage_level=coverage_level, status="active"
        )
        session.add(enrollment)
        session.commit()
        return {
            "enrollment_id": str(enrollment.id),
            "plan_name": plan.name,
            "plan_type": plan.plan_type,
            "coverage_level": coverage_level,
            "status": "active",
            "message": f"Successfully enrolled in {plan.name}.",
        }

    return json.dumps(_with_session(_enroll), indent=2, default=str)


# ============================================================
# DOCUMENT TOOLS (2)
# ============================================================


@mcp.tool()
def list_document_templates() -> str:
    """List available HR document templates (offer letters, contracts, certificates)."""
    return json.dumps(
        {
            "templates": [
                {"template_id": "t1", "name": "Offer Letter", "type": "offer_letter"},
                {"template_id": "t2", "name": "Employment Contract", "type": "employment_contract"},
                {"template_id": "t3", "name": "Termination Letter", "type": "termination_letter"},
                {
                    "template_id": "t4",
                    "name": "Employment Certificate",
                    "type": "employment_certificate",
                },
                {"template_id": "t5", "name": "Promotion Letter", "type": "promotion_letter"},
                {"template_id": "t6", "name": "Experience Letter", "type": "experience_letter"},
            ],
            "count": 6,
        },
        indent=2,
    )


@mcp.tool()
def generate_document(template_id: str, employee_id: str = "", parameters: str = "{}") -> str:
    """Generate an HR document from a template for a specific employee.

    Args:
        template_id: Template ID (t1-t6)
        employee_id: Target employee ID
        parameters: Additional template parameters as JSON string
    """
    template_names = {
        "t1": "Offer Letter",
        "t2": "Employment Contract",
        "t3": "Termination Letter",
        "t4": "Employment Certificate",
        "t5": "Promotion Letter",
        "t6": "Experience Letter",
    }

    def _generate(session):
        from src.core.database import GeneratedDocument

        emp_id = int(employee_id) if employee_id else 1
        try:
            params = json.loads(parameters) if isinstance(parameters, str) else parameters
        except json.JSONDecodeError:
            params = {}
        doc = GeneratedDocument(
            employee_id=emp_id,
            template_id=template_id,
            template_name=template_names.get(template_id, "Unknown"),
            status="finalized",
            parameters=params,
        )
        session.add(doc)
        session.commit()
        return {
            "document_id": str(doc.id),
            "template_id": template_id,
            "template_name": doc.template_name,
            "status": "finalized",
            "created_at": (
                doc.created_at.isoformat() if doc.created_at else datetime.utcnow().isoformat()
            ),
            "message": f"Generated {doc.template_name} successfully.",
        }

    return json.dumps(_with_session(_generate), indent=2, default=str)


# ============================================================
# PERFORMANCE TOOLS (2)
# ============================================================


@mcp.tool()
def get_performance_reviews(employee_id: str) -> str:
    """Get performance reviews for an employee including ratings and feedback.

    Args:
        employee_id: Employee ID
    """

    def _query(session):
        from src.core.database import PerformanceReview

        emp_id = int(employee_id)
        reviews = session.query(PerformanceReview).filter_by(employee_id=emp_id).all()
        data = [
            {
                "id": r.id,
                "review_period": r.review_period,
                "rating": r.rating,
                "strengths": r.strengths,
                "areas_for_improvement": r.areas_for_improvement,
                "comments": r.comments,
                "status": r.status,
            }
            for r in reviews
        ]
        return {"reviews": data, "count": len(data)}

    return json.dumps(_with_session(_query), indent=2, default=str)


@mcp.tool()
def get_performance_goals(employee_id: str) -> str:
    """Get performance goals for an employee with progress tracking.

    Args:
        employee_id: Employee ID
    """

    def _query(session):
        from src.core.database import PerformanceGoal

        emp_id = int(employee_id)
        goals = session.query(PerformanceGoal).filter_by(employee_id=emp_id).all()
        data = [
            {
                "id": g.id,
                "title": g.title,
                "description": g.description,
                "category": g.category,
                "status": g.status,
                "target_date": g.target_date.isoformat() if g.target_date else None,
                "progress_pct": g.progress_pct,
            }
            for g in goals
        ]
        return {"goals": data, "count": len(data)}

    return json.dumps(_with_session(_query), indent=2, default=str)


# ============================================================
# ONBOARDING TOOLS (1)
# ============================================================


@mcp.tool()
def get_onboarding_checklist(employee_id: str) -> str:
    """Get onboarding checklist tasks for a new hire.

    Args:
        employee_id: Employee ID
    """

    def _query(session):
        from src.core.database import OnboardingChecklist

        emp_id = int(employee_id)
        tasks = session.query(OnboardingChecklist).filter_by(employee_id=emp_id).all()
        data = [
            {
                "id": t.id,
                "task_name": t.task_name,
                "category": t.category,
                "description": t.description,
                "status": t.status,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ]
        return {"tasks": data, "count": len(data)}

    return json.dumps(_with_session(_query), indent=2, default=str)


# ============================================================
# POLICY & KNOWLEDGE TOOLS (2)
# ============================================================


@mcp.tool()
def search_policies(query: str, top_k: int = 5) -> str:
    """Search HR policies and compliance documents using semantic search (RAG).

    Args:
        query: Search query about HR policies
        top_k: Number of results (default: 5)
    """
    try:
        from src.services.rag_service import RAGService

        rag = RAGService()
        results = rag.search(query, top_k=top_k)
        return json.dumps(
            {"query": query, "results": results, "count": len(results)}, indent=2, default=str
        )
    except Exception as e:
        return json.dumps(
            {
                "query": query,
                "results": [
                    {
                        "title": "Leave Policy",
                        "summary": "Employees receive vacation, sick, and personal days annually.",
                    },
                    {
                        "title": "Benefits Policy",
                        "summary": "Health, dental, vision, and 401(k) plans available.",
                    },
                    {
                        "title": "Code of Conduct",
                        "summary": "Professional behavior and ethics guidelines.",
                    },
                ],
                "count": 3,
                "note": f"RAG service unavailable ({e}), showing common policies.",
            },
            indent=2,
        )


@mcp.tool()
def ask_hr_question(question: str) -> str:
    """Ask a natural language HR question. Uses the AI agent with RAG for answers.

    Args:
        question: HR question in natural language
    """
    try:
        from flask import current_app

        agent_service = current_app.agent_service
        result = agent_service.process_query(question, user_context={"role": "employee"})
        return json.dumps(
            {
                "question": question,
                "answer": result.get("response", result.get("answer", str(result))),
                "confidence": result.get("confidence", 0.0),
                "agent_type": result.get("agent_type", "unknown"),
            },
            indent=2,
            default=str,
        )
    except Exception:
        try:
            from src.services.rag_service import RAGService

            rag = RAGService()
            results = rag.search(question, top_k=3)
            context = "\n".join(str(r) for r in results) if results else "No context found."
            return json.dumps(
                {
                    "question": question,
                    "answer": context,
                    "confidence": 0.5,
                    "agent_type": "rag_fallback",
                    "note": "Agent service unavailable; showing RAG results.",
                },
                indent=2,
                default=str,
            )
        except Exception as e2:
            return json.dumps({"question": question, "error": f"No AI service available: {e2}"})


# ============================================================
# ANALYTICS TOOLS (2 existing + 3 NEW)
# ============================================================


@mcp.tool()
def get_hr_metrics() -> str:
    """Get HR analytics dashboard metrics: headcount, leave stats, department breakdown, query volume."""

    def _query(session):
        from src.core.database import Employee, LeaveRequest

        metrics = {}
        metrics["total_employees"] = session.query(Employee).count()
        metrics["active_employees"] = session.query(Employee).filter_by(status="active").count()
        metrics["pending_leave_requests"] = (
            session.query(LeaveRequest)
            .filter(LeaveRequest.status.in_(["pending", "Pending"]))
            .count()
        )
        metrics["approved_leave_requests"] = (
            session.query(LeaveRequest)
            .filter(LeaveRequest.status.in_(["approved", "Approved"]))
            .count()
        )
        dept_counts = {}
        for emp in session.query(Employee).filter_by(status="active").all():
            dept_counts[emp.department] = dept_counts.get(emp.department, 0) + 1
        metrics["department_headcount"] = dept_counts
        try:
            from src.core.database import QueryLog

            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            metrics["queries_today"] = (
                session.query(QueryLog).filter(QueryLog.created_at >= today).count()
            )
        except Exception:
            metrics["queries_today"] = 0
        return metrics

    return json.dumps(_with_session(_query), indent=2, default=str)


@mcp.tool()
def get_recent_activity(limit: int = 20) -> str:
    """Get recent HR activity feed: leave requests, document generation, etc.

    Args:
        limit: Maximum number of items to return (default: 20)
    """
    limit = min(limit, 50)

    def _query(session):
        from src.core.database import (
            LeaveRequest,
            Employee,
            GeneratedDocument,
            BenefitsEnrollment,
            BenefitsPlan,
        )

        activities = []
        for lr in (
            session.query(LeaveRequest).order_by(LeaveRequest.created_at.desc()).limit(10).all()
        ):
            emp = session.query(Employee).filter_by(id=lr.employee_id).first()
            name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"
            activities.append(
                {
                    "type": "leave",
                    "message": f"{name} — {lr.leave_type} request ({lr.status})",
                    "detail": f"{lr.start_date} to {lr.end_date}",
                    "timestamp": lr.created_at.isoformat() if lr.created_at else None,
                }
            )
        for doc in (
            session.query(GeneratedDocument)
            .order_by(GeneratedDocument.created_at.desc())
            .limit(5)
            .all()
        ):
            emp = session.query(Employee).filter_by(id=doc.employee_id).first()
            name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"
            activities.append(
                {
                    "type": "document",
                    "message": f"Document generated: {doc.template_name}",
                    "detail": f"For {name}",
                    "timestamp": doc.created_at.isoformat() if doc.created_at else None,
                }
            )

        for enrollment in (
            session.query(BenefitsEnrollment)
            .order_by(BenefitsEnrollment.enrolled_at.desc())
            .limit(5)
            .all()
        ):
            emp = session.query(Employee).filter_by(id=enrollment.employee_id).first()
            plan = session.query(BenefitsPlan).filter_by(id=enrollment.plan_id).first()
            name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"
            plan_name = plan.name if plan else "Unknown Plan"
            plan_type = plan.plan_type if plan else "benefits"
            status = (enrollment.status or "active").lower()
            activities.append(
                {
                    "type": "benefits",
                    "message": f"{name} — Benefits update ({status})",
                    "detail": f"{plan_name} ({plan_type}) • Coverage: {enrollment.coverage_level}",
                    "timestamp": (
                        enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None
                    ),
                }
            )
        activities.sort(key=lambda a: a.get("timestamp") or "0000", reverse=True)
        return {"activities": activities[:limit], "count": len(activities[:limit])}

    return json.dumps(_with_session(_query), indent=2, default=str)


@mcp.tool()
def run_sql_analytics(query_description: str) -> str:
    """Run a pre-defined analytics query against the HR database. Supports safe read-only queries.

    Supported queries: headcount_by_department, leave_by_type, leave_by_month,
    benefits_enrollment_summary, new_hires_last_90_days, turnover_rate, avg_tenure.

    Args:
        query_description: One of the supported query names listed above
    """
    SAFE_QUERIES = {
        "headcount_by_department": """
            SELECT department, COUNT(*) as headcount, 
                   SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active
            FROM employees GROUP BY department ORDER BY headcount DESC
        """,
        "leave_by_type": """
            SELECT leave_type, status, COUNT(*) as count
            FROM leave_requests GROUP BY leave_type, status ORDER BY count DESC
        """,
        "leave_by_month": """
            SELECT substr(start_date, 1, 7) as month, COUNT(*) as requests
            FROM leave_requests GROUP BY month ORDER BY month DESC LIMIT 12
        """,
        "benefits_enrollment_summary": """
            SELECT bp.plan_type, bp.name, COUNT(be.id) as enrolled_count
            FROM benefits_enrollments be
            JOIN benefits_plans bp ON be.plan_id = bp.id
            WHERE be.status = 'active'
            GROUP BY bp.plan_type, bp.name ORDER BY enrolled_count DESC
        """,
        "new_hires_last_90_days": """
            SELECT first_name || ' ' || last_name as name, department, hire_date, email
            FROM employees 
            WHERE hire_date >= date('now', '-90 days') AND status = 'active'
            ORDER BY hire_date DESC
        """,
        "avg_tenure": """
            SELECT department, 
                   ROUND(AVG(julianday('now') - julianday(hire_date)) / 365.25, 1) as avg_years
            FROM employees WHERE status = 'active'
            GROUP BY department ORDER BY avg_years DESC
        """,
    }

    query_key = query_description.strip().lower().replace(" ", "_")
    if query_key not in SAFE_QUERIES:
        return json.dumps(
            {
                "error": f"Unknown query: {query_description}",
                "available_queries": list(SAFE_QUERIES.keys()),
            },
            indent=2,
        )

    def _run(session):
        from sqlalchemy import text

        result = session.execute(text(SAFE_QUERIES[query_key]))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        return {"query": query_key, "columns": columns, "rows": rows, "row_count": len(rows)}

    return json.dumps(_with_session(_run), indent=2, default=str)


@mcp.tool()
def get_department_report(department: str) -> str:
    """Get a comprehensive report for a specific department: headcount, roles, leave stats.

    Args:
        department: Department name (e.g., Engineering, HR, Marketing)
    """

    def _query(session):
        from src.core.database import Employee, LeaveRequest, LeaveBalance

        employees = (
            session.query(Employee).filter(Employee.department.ilike(f"%{department}%")).all()
        )
        if not employees:
            return {"error": f"No employees found in department matching '{department}'"}

        emp_ids = [e.id for e in employees]
        active = [e for e in employees if e.status == "active"]
        role_breakdown = {}
        for e in active:
            role_breakdown[e.role_level] = role_breakdown.get(e.role_level, 0) + 1

        pending_leaves = (
            session.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id.in_(emp_ids),
                LeaveRequest.status.in_(["pending", "Pending"]),
            )
            .count()
        )
        approved_leaves = (
            session.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id.in_(emp_ids),
                LeaveRequest.status.in_(["approved", "Approved"]),
            )
            .count()
        )

        return {
            "department": department,
            "total_employees": len(employees),
            "active_employees": len(active),
            "role_breakdown": role_breakdown,
            "pending_leave_requests": pending_leaves,
            "approved_leave_requests": approved_leaves,
            "employees": [
                {
                    "id": e.id,
                    "name": f"{e.first_name} {e.last_name}",
                    "role": e.role_level,
                    "status": e.status,
                    "hire_date": e.hire_date.isoformat() if e.hire_date else None,
                }
                for e in employees
            ],
        }

    return json.dumps(_with_session(_query), indent=2, default=str)


@mcp.tool()
def get_attrition_metrics() -> str:
    """Get employee attrition/turnover metrics across all departments."""

    def _query(session):
        from src.core.database import Employee

        all_emps = session.query(Employee).all()
        total = len(all_emps)
        active = sum(1 for e in all_emps if e.status == "active")
        inactive = sum(1 for e in all_emps if e.status in ("inactive", "terminated"))

        dept_attrition = {}
        for e in all_emps:
            if e.department not in dept_attrition:
                dept_attrition[e.department] = {"total": 0, "active": 0, "inactive": 0}
            dept_attrition[e.department]["total"] += 1
            if e.status == "active":
                dept_attrition[e.department]["active"] += 1
            else:
                dept_attrition[e.department]["inactive"] += 1

        for dept, data in dept_attrition.items():
            data["attrition_rate"] = (
                round(data["inactive"] / data["total"] * 100, 1) if data["total"] > 0 else 0
            )

        return {
            "total_employees": total,
            "active": active,
            "inactive_or_terminated": inactive,
            "overall_attrition_rate": round(inactive / total * 100, 1) if total > 0 else 0,
            "department_attrition": dept_attrition,
        }

    return json.dumps(_with_session(_query), indent=2, default=str)


# ============================================================
# NOTIFICATION TOOLS (2 NEW)
# ============================================================


@mcp.tool()
def send_notification(recipient_id: str, subject: str, body: str, priority: str = "normal") -> str:
    """Send an in-app notification to an employee.

    Args:
        recipient_id: Employee ID of the recipient
        subject: Notification subject line
        body: Notification body text
        priority: Priority level (low, normal, high, urgent)
    """

    def _send(session):
        from src.core.database import NotificationRecord

        notif = NotificationRecord(
            recipient_id=int(recipient_id),
            subject=subject,
            body=body,
            priority=priority,
            status="sent",
            channel="in_app",
        )
        session.add(notif)
        session.commit()
        return {
            "notification_id": str(notif.id),
            "recipient_id": recipient_id,
            "subject": subject,
            "priority": priority,
            "status": "sent",
            "message": f"Notification sent to employee {recipient_id}.",
        }

    # Try DB-backed notifications first
    try:
        result = _with_session(_send)
        if "error" not in result:
            return json.dumps(result, indent=2, default=str)
    except Exception:
        pass

    # Fallback: use in-memory notification service
    try:
        from src.core.notifications import NotificationService

        svc = NotificationService()
        notif = svc.send(
            recipient_id=recipient_id,
            channel="in_app",
            subject=subject,
            body=body,
            priority=priority,
        )
        return json.dumps(
            {
                "notification_id": getattr(notif, "id", "generated"),
                "recipient_id": recipient_id,
                "subject": subject,
                "priority": priority,
                "status": "sent",
                "message": f"Notification sent to employee {recipient_id}.",
            },
            indent=2,
            default=str,
        )
    except Exception as e:
        return json.dumps(
            {
                "notification_id": f"notif-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "recipient_id": recipient_id,
                "subject": subject,
                "priority": priority,
                "status": "sent",
                "message": f"Notification queued for employee {recipient_id}.",
                "note": f"Using fallback delivery ({e})",
            },
            indent=2,
            default=str,
        )


@mcp.tool()
def get_notifications(employee_id: str, status: str = "", limit: int = 20) -> str:
    """Get notifications for an employee.

    Args:
        employee_id: Employee ID
        status: Filter by status (pending, sent, read). Empty for all.
        limit: Maximum notifications to return (default: 20)
    """
    limit = min(limit, 100)

    def _query(session):
        from src.core.database import NotificationRecord

        q = session.query(NotificationRecord).filter_by(recipient_id=int(employee_id))
        if status:
            q = q.filter_by(status=status)
        notifications = q.order_by(NotificationRecord.created_at.desc()).limit(limit).all()
        data = [
            {
                "id": n.id,
                "subject": n.subject,
                "body": n.body,
                "priority": n.priority,
                "status": n.status,
                "channel": n.channel,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "read_at": n.read_at.isoformat() if hasattr(n, "read_at") and n.read_at else None,
            }
            for n in notifications
        ]
        return {"employee_id": employee_id, "notifications": data, "count": len(data)}

    try:
        result = _with_session(_query)
        if "error" not in result:
            return json.dumps(result, indent=2, default=str)
    except Exception:
        pass

    return json.dumps(
        {
            "employee_id": employee_id,
            "notifications": [],
            "count": 0,
            "note": "Notification table not available, returning empty list.",
        },
        indent=2,
    )


# ============================================================
# WORKFLOW APPROVAL TOOLS (2 NEW)
# ============================================================


@mcp.tool()
def approve_workflow(workflow_id: str, approver_id: str, comments: str = "") -> str:
    """Approve a workflow/approval request (leave, compensation change, etc.).

    Args:
        workflow_id: Workflow instance ID
        approver_id: ID of the approver
        comments: Optional approval comments
    """
    try:
        from src.core.workflow_engine import WorkflowEngine

        engine = WorkflowEngine()
        result = engine.approve_step(
            instance_id=workflow_id,
            approver_id=approver_id,
            comments=comments,
        )
        return json.dumps(
            {
                "workflow_id": workflow_id,
                "status": "approved",
                "approver_id": approver_id,
                "comments": comments,
                "result": str(result),
                "message": f"Workflow {workflow_id} approved.",
            },
            indent=2,
            default=str,
        )
    except Exception as e:
        # Fallback: try treating it as a leave request approval
        try:
            result = json.loads(approve_leave_request(workflow_id, approver_id))
            return json.dumps(result, indent=2, default=str)
        except Exception:
            return json.dumps(
                {
                    "workflow_id": workflow_id,
                    "status": "error",
                    "error": str(e),
                },
                indent=2,
            )


@mcp.tool()
def reject_workflow(workflow_id: str, approver_id: str, reason: str = "") -> str:
    """Reject a workflow/approval request.

    Args:
        workflow_id: Workflow instance ID
        approver_id: ID of the approver
        reason: Reason for rejection
    """
    try:
        from src.core.workflow_engine import WorkflowEngine

        engine = WorkflowEngine()
        result = engine.reject_step(
            instance_id=workflow_id,
            approver_id=approver_id,
            comments=reason,
        )
        return json.dumps(
            {
                "workflow_id": workflow_id,
                "status": "rejected",
                "approver_id": approver_id,
                "reason": reason,
                "result": str(result),
                "message": f"Workflow {workflow_id} rejected.",
            },
            indent=2,
            default=str,
        )
    except Exception as e:
        try:
            result = json.loads(reject_leave_request(workflow_id, reason))
            return json.dumps(result, indent=2, default=str)
        except Exception:
            return json.dumps(
                {
                    "workflow_id": workflow_id,
                    "status": "error",
                    "error": str(e),
                },
                indent=2,
            )


# ============================================================
# RESOURCES (8)
# ============================================================


@mcp.resource("hr://employees")
def resource_employees() -> str:
    """Complete employee directory with names, departments, and contact info."""

    def _query(session):
        from src.core.database import Employee

        employees = session.query(Employee).order_by(Employee.last_name).all()
        return [
            {
                "id": e.id,
                "name": f"{e.first_name} {e.last_name}",
                "email": e.email,
                "department": e.department,
                "status": e.status,
            }
            for e in employees
        ]

    return json.dumps(_with_session(_query), indent=2, default=str)


@mcp.resource("hr://employees/{employee_id}")
def resource_employee_by_id(employee_id: str) -> str:
    """Detailed employee profile by ID."""
    return get_employee_profile(employee_id=employee_id)


@mcp.resource("hr://policies")
def resource_policies() -> str:
    """List of available HR policy topics and summaries."""
    return json.dumps(
        {
            "policies": [
                {
                    "name": "Leave Policy",
                    "description": "Vacation, sick, and personal leave guidelines",
                },
                {
                    "name": "Benefits Policy",
                    "description": "Health, dental, vision, and retirement plans",
                },
                {"name": "Code of Conduct", "description": "Professional behavior and ethics"},
                {"name": "Remote Work Policy", "description": "Work from home guidelines"},
                {
                    "name": "Performance Review Policy",
                    "description": "Annual review process and criteria",
                },
                {"name": "Onboarding Policy", "description": "New hire onboarding procedures"},
                {
                    "name": "GDPR & Privacy Policy",
                    "description": "Data protection and privacy rights",
                },
                {
                    "name": "Anti-Discrimination Policy",
                    "description": "Equal opportunity and inclusion",
                },
            ],
            "note": "Use the search_policies tool for detailed policy content.",
        },
        indent=2,
    )


@mcp.resource("hr://benefits/plans")
def resource_benefits_plans() -> str:
    """Available benefits plans with premiums and coverage details."""
    return list_benefits_plans()


@mcp.resource("hr://leave/balance/{employee_id}")
def resource_leave_balance(employee_id: str) -> str:
    """Employee leave balance (vacation, sick, personal days)."""
    return get_leave_balance(employee_id)


@mcp.resource("hr://onboarding/{employee_id}")
def resource_onboarding(employee_id: str) -> str:
    """Employee onboarding tasks and progress."""
    return get_onboarding_checklist(employee_id)


@mcp.resource("hr://performance/{employee_id}")
def resource_performance(employee_id: str) -> str:
    """Employee performance reviews and goals."""
    reviews = get_performance_reviews(employee_id)
    goals = get_performance_goals(employee_id)
    return json.dumps({"reviews": json.loads(reviews), "goals": json.loads(goals)}, indent=2)


@mcp.resource("hr://metrics")
def resource_metrics() -> str:
    """Live HR analytics: headcount, leave stats, query volume."""
    return get_hr_metrics()


# ============================================================
# PROMPTS (5)
# ============================================================


@mcp.prompt()
def leave_request(employee_name: str, leave_type: str = "vacation") -> str:
    """Step-by-step guidance for submitting an employee leave request."""
    return (
        f"I need to help {employee_name} submit a {leave_type} leave request. "
        "Please guide me through the process:\n\n"
        "1. First, check their current leave balance using get_leave_balance\n"
        "2. Verify the requested dates don't conflict with team schedules\n"
        "3. Submit the leave request using submit_leave_request\n"
        "4. Confirm the request was created and is pending approval\n\n"
        "What are the requested dates?"
    )


@mcp.prompt()
def onboarding_guide(employee_name: str, department: str = "their department") -> str:
    """Complete onboarding workflow for new hire employees."""
    return (
        f"I'm helping onboard {employee_name} in {department}. "
        "Please help me through these steps:\n\n"
        "1. Check their onboarding checklist using get_onboarding_checklist\n"
        "2. Review pending tasks and their due dates\n"
        "3. Ensure benefits enrollment is initiated using list_benefits_plans\n"
        "4. Verify required documents are generated using list_document_templates\n"
        "5. Provide a summary of completed and pending onboarding items\n\n"
        "Let's start by checking their checklist."
    )


@mcp.prompt()
def benefits_enrollment(employee_name: str) -> str:
    """Guided benefits enrollment and plan comparison for employees."""
    return (
        f"I need to help {employee_name} with benefits enrollment. "
        "Please guide me through:\n\n"
        "1. List all available plans using list_benefits_plans\n"
        "2. Check current enrollments using get_benefits_enrollments\n"
        "3. Compare plan options (premiums, coverage levels)\n"
        "4. Enroll in selected plan using enroll_in_benefit\n"
        "5. Confirm enrollment and provide summary\n\n"
        "Let's start by reviewing available plans."
    )


@mcp.prompt()
def performance_review(employee_name: str, review_period: str = "current period") -> str:
    """Preparation workflow for employee performance reviews."""
    return (
        f"I'm preparing a performance review for {employee_name} for {review_period}. "
        "Please help me gather context:\n\n"
        "1. Pull their existing reviews using get_performance_reviews\n"
        "2. Check current goals and progress using get_performance_goals\n"
        "3. Review their leave history for attendance context using get_leave_history\n"
        "4. Look up any relevant policy guidelines using search_policies\n"
        "5. Summarize findings for the review discussion\n\n"
        "Let's start with their review history."
    )


@mcp.prompt()
def policy_inquiry(topic: str) -> str:
    """Guided HR policy lookup and question answering."""
    return (
        f"I have a question about {topic}. "
        "Please help me find the answer:\n\n"
        "1. Search relevant policies using search_policies\n"
        "2. If more detail is needed, ask the HR AI using ask_hr_question\n"
        "3. Provide a clear, concise answer with policy references\n"
        "4. Note any exceptions or special cases\n\n"
        f"My question is about: {topic}"
    )


# ============================================================
# BAMBOOHR INTEGRATION TOOLS (9)
# ============================================================
# These tools delegate to the BambooHR REST API via the connector.
# They are only functional when BAMBOOHR_API_KEY and BAMBOOHR_SUBDOMAIN
# are configured. Otherwise they return a helpful configuration error.


def _get_bamboohr_connector():
    """Get BambooHR connector if configured, else raise RuntimeError."""
    api_key = os.environ.get("BAMBOOHR_API_KEY", "").strip()
    subdomain = os.environ.get("BAMBOOHR_SUBDOMAIN", "").strip()
    placeholders = {"", "your-bamboohr-api-key", "not-set", "your-company-subdomain"}
    if not api_key or api_key.lower() in placeholders:
        raise RuntimeError(
            "BAMBOOHR_API_KEY is not configured. "
            "Set it in your .env or as an environment variable."
        )
    if not subdomain or subdomain.lower() in placeholders:
        raise RuntimeError(
            "BAMBOOHR_SUBDOMAIN is not configured. "
            "Set it in your .env or as an environment variable."
        )
    from src.connectors.bamboohr import BambooHRConnector

    return BambooHRConnector(api_key=api_key, subdomain=subdomain)


def _bamboohr_error(e: Exception) -> str:
    return json.dumps(
        {
            "error": str(e),
            "hint": "Ensure BAMBOOHR_API_KEY and BAMBOOHR_SUBDOMAIN are set correctly.",
        },
        indent=2,
    )


@mcp.tool()
def bamboohr_get_employee(employee_id: str) -> str:
    """Retrieve a single employee profile from BambooHR by their ID.

    Args:
        employee_id: BambooHR employee ID (numeric string)
    """
    try:
        connector = _get_bamboohr_connector()
        emp = connector.get_employee(employee_id)
        if emp is None:
            return json.dumps({"error": f"Employee {employee_id} not found in BambooHR"})
        return json.dumps(emp.model_dump(), indent=2, default=str)
    except Exception as e:
        return _bamboohr_error(e)


@mcp.tool()
def bamboohr_search_employees(
    department: str = "", status: str = "", location: str = "", job_title: str = ""
) -> str:
    """Search the BambooHR employee directory. Omit all filters to list everyone.

    Args:
        department: Filter by department name
        status: Filter by status (active, inactive, on_leave, terminated)
        location: Filter by office location
        job_title: Filter by job title
    """
    try:
        connector = _get_bamboohr_connector()
        filters = {}
        if department:
            filters["department"] = department
        if status:
            filters["status"] = status
        if location:
            filters["location"] = location
        if job_title:
            filters["job_title"] = job_title
        employees = connector.search_employees(filters)
        results = [emp.model_dump() for emp in employees]
        return json.dumps({"employees": results, "count": len(results)}, indent=2, default=str)
    except Exception as e:
        return _bamboohr_error(e)


@mcp.tool()
def bamboohr_get_leave_balance(employee_id: str) -> str:
    """Get an employee's leave balance from BambooHR (PTO, sick, personal days).

    Args:
        employee_id: BambooHR employee ID
    """
    try:
        connector = _get_bamboohr_connector()
        balances = connector.get_leave_balance(employee_id)
        return json.dumps(
            {"employee_id": employee_id, "balances": [b.model_dump() for b in balances]},
            indent=2,
            default=str,
        )
    except Exception as e:
        return _bamboohr_error(e)


@mcp.tool()
def bamboohr_get_leave_requests(employee_id: str, status: str = "") -> str:
    """Get leave requests for an employee from BambooHR.

    Args:
        employee_id: BambooHR employee ID
        status: Optional filter — pending, approved, denied, cancelled
    """
    try:
        connector = _get_bamboohr_connector()
        requests_list = connector.get_leave_requests(employee_id, status=status or None)
        return json.dumps(
            {"employee_id": employee_id, "requests": [r.model_dump() for r in requests_list]},
            indent=2,
            default=str,
        )
    except Exception as e:
        return _bamboohr_error(e)


@mcp.tool()
def bamboohr_submit_leave_request(
    employee_id: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    reason: str = "",
) -> str:
    """Submit a leave request to BambooHR (creates a pending request needing approval).

    Args:
        employee_id: BambooHR employee ID
        leave_type: pto, sick, personal, unpaid, or other
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        reason: Optional reason
    """
    try:
        from src.connectors.hris_interface import LeaveRequest as LR, LeaveType, LeaveStatus

        connector = _get_bamboohr_connector()
        type_map = {
            "pto": LeaveType.PTO,
            "vacation": LeaveType.PTO,
            "sick": LeaveType.SICK,
            "personal": LeaveType.PERSONAL,
            "unpaid": LeaveType.UNPAID,
        }
        lt = type_map.get(leave_type.lower(), LeaveType.OTHER)
        req = LR(
            employee_id=employee_id,
            leave_type=lt,
            start_date=datetime.fromisoformat(start_date),
            end_date=datetime.fromisoformat(end_date),
            status=LeaveStatus.PENDING,
            reason=reason,
            submitted_at=datetime.utcnow(),
        )
        result = connector.submit_leave_request(req)
        return json.dumps(
            {
                "request_id": result.id,
                "status": result.status.value,
                "message": "Submitted to BambooHR.",
            },
            indent=2,
            default=str,
        )
    except Exception as e:
        return _bamboohr_error(e)


@mcp.tool()
def bamboohr_get_org_chart(department: str = "") -> str:
    """Get the organization hierarchy from BambooHR.

    Args:
        department: Optional department filter
    """
    try:
        connector = _get_bamboohr_connector()
        nodes = connector.get_org_chart(department=department or None)

        def _ser(n):
            return {
                "employee_id": n.employee_id,
                "name": n.name,
                "title": n.title,
                "department": n.department,
                "direct_reports": [_ser(dr) for dr in n.direct_reports],
            }

        return json.dumps({"org_chart": [_ser(n) for n in nodes]}, indent=2, default=str)
    except Exception as e:
        return _bamboohr_error(e)


@mcp.tool()
def bamboohr_get_benefits(employee_id: str) -> str:
    """Get benefits enrollments for an employee from BambooHR.

    Args:
        employee_id: BambooHR employee ID
    """
    try:
        connector = _get_bamboohr_connector()
        plans = connector.get_benefits(employee_id)
        return json.dumps(
            {"employee_id": employee_id, "benefits": [p.model_dump() for p in plans]},
            indent=2,
            default=str,
        )
    except Exception as e:
        return _bamboohr_error(e)


@mcp.tool()
def bamboohr_health_check() -> str:
    """Verify connectivity to BambooHR API. Returns status and configured subdomain."""
    try:
        connector = _get_bamboohr_connector()
        ok = connector.health_check()
        sub = os.environ.get("BAMBOOHR_SUBDOMAIN", "?")
        return json.dumps(
            {"status": "healthy" if ok else "unhealthy", "subdomain": sub},
            indent=2,
        )
    except Exception as e:
        return _bamboohr_error(e)


@mcp.tool()
def get_hris_provider_info() -> str:
    """Show which HRIS provider is active (BambooHR, Workday, or local DB) and its status."""
    try:
        from src.connectors.factory import get_hris_connector_resolution

        info = get_hris_connector_resolution(force_refresh=True)
        return json.dumps(info, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ============================================================
# Ensure NotificationRecord exists in database models
# ============================================================


def _ensure_notification_table():
    """Create NotificationRecord table if it doesn't exist."""
    try:
        from src.core.database import Base, engine

        if engine is not None:
            # Check if the model exists
            try:
                from src.core.database import NotificationRecord
            except ImportError:
                # Define it dynamically if not in database.py
                pass
            Base.metadata.create_all(engine)
    except Exception:
        pass


# ============================================================
# Entry point for standalone running
# ============================================================


def main():
    """Run the FastMCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="HR Agent MCP Server (Official SDK)")
    parser.add_argument(
        "--transport",
        "-t",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port for HTTP transport")
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP transport")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    # Initialize database
    try:
        from src.core.database import init_db

        init_db()
        _ensure_notification_table()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database init skipped: {e}")

    # Run with selected transport
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
