"""
HR Agent MCP Server v2.0 — Full Model Context Protocol Implementation.

Complete MCP server for the HR Agent Platform, exposing 22 tools, 8 resources,
and 5 prompts via the standardized Model Context Protocol (2024-11-05).

Works with Python 3.9+ without requiring the official MCP SDK.

Supports:
    - 22 HR tools: leave, benefits, employees, documents, performance, policies
    - 8 data resources: employee profiles, policies, metrics, benefits plans
    - 5 workflow prompts: leave request, onboarding, benefits, performance, policy
    - stdio transport: read/write JSON-RPC over stdin/stdout
    - SSE transport: Flask blueprint for HTTP-based MCP clients
    - JSON-RPC 2.0 with proper error codes and validation

Usage:
    # Standalone (stdio):
    python run_mcp.py

    # Integrated with Flask:
    from src.mcp.server import HRMCPServer
    server = HRMCPServer()
    app.register_blueprint(server.get_flask_blueprint(), url_prefix="/mcp")

    # Programmatic:
    server = HRMCPServer()
    response = server.handle_request({"jsonrpc": "2.0", "method": "tools/list", "id": 1})
"""

import inspect
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from flask import Blueprint

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project root on sys.path (for standalone mode)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ============================================================
# MCP Protocol Types
# ============================================================


@dataclass
class ToolDefinition:
    """MCP tool descriptor."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable


@dataclass
class ResourceDefinition:
    """MCP resource descriptor."""

    uri: str
    name: str
    description: str
    mime_type: str = "application/json"
    handler: Optional[Callable] = None


@dataclass
class ResourceTemplate:
    """MCP resource template (URI with parameters)."""

    uri_template: str
    name: str
    description: str
    mime_type: str = "application/json"
    handler: Optional[Callable] = None


@dataclass
class PromptArgument:
    """MCP prompt argument."""

    name: str
    description: str
    required: bool = True


@dataclass
class PromptDefinition:
    """MCP prompt descriptor."""

    name: str
    description: str
    arguments: List[PromptArgument] = field(default_factory=list)
    handler: Optional[Callable] = None


# ============================================================
# JSON-RPC 2.0 Error Codes
# ============================================================
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


# ============================================================
# Database Helpers
# ============================================================

_db_initialized = False


def _ensure_db():
    """Ensure the database is initialized. Safe to call multiple times."""
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
# Tool Implementations
# ============================================================


def _tool_get_leave_balance(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get an employee's leave balance."""
    employee_id = arguments.get("employee_id")

    def _query(session):
        from src.core.database import LeaveBalance, Employee

        emp_id = int(employee_id) if employee_id else 1
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

    return _with_session(_query)


def _tool_submit_leave_request(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Submit a new leave request."""
    employee_id = arguments.get("employee_id")
    leave_type = arguments.get("leave_type", "vacation")
    start_date = arguments.get("start_date")
    end_date = arguments.get("end_date")
    reason = arguments.get("reason", "")

    if not all([employee_id, start_date, end_date]):
        return {"error": "employee_id, start_date, and end_date are required"}

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

    return _with_session(_submit)


def _tool_get_leave_history(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get leave request history for an employee."""
    employee_id = arguments.get("employee_id")

    def _query(session):
        from src.core.database import LeaveRequest as LR

        emp_id = int(employee_id) if employee_id else 1
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

    return _with_session(_query)


def _tool_approve_leave_request(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Approve a pending leave request (manager/HR action)."""
    request_id = arguments.get("request_id")
    approver_id = arguments.get("approver_id")
    if not request_id:
        return {"error": "request_id is required"}

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

        # Deduct from balance
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

    return _with_session(_approve)


def _tool_reject_leave_request(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Reject a pending leave request (manager/HR action)."""
    request_id = arguments.get("request_id")
    reason = arguments.get("reason", "")
    if not request_id:
        return {"error": "request_id is required"}

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

    return _with_session(_reject)


def _tool_get_pending_approvals(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """List all pending leave approvals."""

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

    return _with_session(_query)


# -- Employee Management Tools --


def _tool_get_employee_profile(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get employee profile by ID or email."""
    employee_id = arguments.get("employee_id")
    email = arguments.get("email")

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

    return _with_session(_query)


def _tool_search_employees(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Search employee directory by name, department, or role."""
    query_str = arguments.get("query", "")
    department = arguments.get("department")
    limit = min(int(arguments.get("limit", 20)), 100)

    def _query(session):
        from src.core.database import Employee

        q = session.query(Employee)
        if department:
            q = q.filter_by(department=department)
        if query_str:
            search = f"%{query_str}%"
            q = q.filter(
                (Employee.first_name.ilike(search))
                | (Employee.last_name.ilike(search))
                | (Employee.email.ilike(search))
                | (Employee.department.ilike(search))
            )
        employees = q.order_by(Employee.last_name).limit(limit).all()
        results = []
        for emp in employees:
            results.append(
                {
                    "id": emp.id,
                    "name": f"{emp.first_name} {emp.last_name}",
                    "email": emp.email,
                    "department": emp.department,
                    "role_level": emp.role_level,
                    "status": emp.status,
                }
            )
        return {"employees": results, "count": len(results)}

    return _with_session(_query)


def _tool_update_employee(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Update employee record (HR admin only)."""
    employee_id = arguments.get("employee_id")
    updates = arguments.get("updates", {})
    if not employee_id:
        return {"error": "employee_id is required"}

    allowed_fields = ["first_name", "last_name", "email", "department", "role_level", "status"]

    def _update(session):
        from src.core.database import Employee

        emp = session.query(Employee).filter_by(id=int(employee_id)).first()
        if not emp:
            return {"error": f"Employee {employee_id} not found"}
        updated = []
        for fld in allowed_fields:
            if fld in updates and updates[fld] is not None:
                setattr(emp, fld, updates[fld])
                updated.append(fld)
        if not updated:
            return {"error": "No valid fields to update"}
        emp.updated_at = datetime.utcnow()
        session.commit()
        return {
            "employee_id": str(emp.id),
            "updated_fields": updated,
            "message": f"Updated {', '.join(updated)} for employee {emp.first_name} {emp.last_name}.",
        }

    return _with_session(_update)


# -- Benefits Tools --


def _tool_list_benefits_plans(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """List available benefits plans."""

    def _query(session):
        from src.core.database import BenefitsPlan

        plans = session.query(BenefitsPlan).filter_by(is_active=True).all()
        data = []
        for p in plans:
            data.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "plan_type": p.plan_type,
                    "provider": p.provider,
                    "premium_monthly": p.premium_monthly,
                    "coverage_details": p.coverage_details or {},
                }
            )
        return {"plans": data, "count": len(data)}

    return _with_session(_query)


def _tool_get_benefits_enrollments(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get employee's benefits enrollments."""
    employee_id = arguments.get("employee_id")

    def _query(session):
        from src.core.database import BenefitsEnrollment, BenefitsPlan

        emp_id = int(employee_id) if employee_id else 1
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

    return _with_session(_query)


def _tool_enroll_in_benefit(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Enroll employee in a benefits plan."""
    employee_id = arguments.get("employee_id")
    plan_id = arguments.get("plan_id")
    coverage_level = arguments.get("coverage_level", "employee")
    if not all([employee_id, plan_id]):
        return {"error": "employee_id and plan_id are required"}

    def _enroll(session):
        from src.core.database import BenefitsEnrollment, BenefitsPlan

        emp_id = int(employee_id)
        plan = session.query(BenefitsPlan).filter_by(id=int(plan_id), is_active=True).first()
        if not plan:
            return {"error": "Plan not found or inactive"}

        # Deactivate existing enrollment for same plan type
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
            employee_id=emp_id,
            plan_id=plan.id,
            coverage_level=coverage_level,
            status="active",
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

    return _with_session(_enroll)


# -- Document Tools --


def _tool_list_document_templates(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """List available document templates."""
    return {
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
    }


def _tool_generate_document(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a document from a template."""
    template_id = arguments.get("template_id")
    employee_id = arguments.get("employee_id")
    parameters = arguments.get("parameters", {})
    if not template_id:
        return {"error": "template_id is required"}

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
        doc = GeneratedDocument(
            employee_id=emp_id,
            template_id=template_id,
            template_name=template_names.get(template_id, "Unknown"),
            status="finalized",
            parameters=parameters,
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

    return _with_session(_generate)


# -- Performance Tools --


def _tool_get_performance_reviews(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get performance reviews for an employee."""
    employee_id = arguments.get("employee_id")

    def _query(session):
        from src.core.database import PerformanceReview

        emp_id = int(employee_id) if employee_id else 1
        reviews = session.query(PerformanceReview).filter_by(employee_id=emp_id).all()
        data = []
        for r in reviews:
            data.append(
                {
                    "id": r.id,
                    "review_period": r.review_period,
                    "rating": r.rating,
                    "strengths": r.strengths,
                    "areas_for_improvement": r.areas_for_improvement,
                    "comments": r.comments,
                    "status": r.status,
                }
            )
        return {"reviews": data, "count": len(data)}

    return _with_session(_query)


def _tool_get_performance_goals(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get performance goals for an employee."""
    employee_id = arguments.get("employee_id")

    def _query(session):
        from src.core.database import PerformanceGoal

        emp_id = int(employee_id) if employee_id else 1
        goals = session.query(PerformanceGoal).filter_by(employee_id=emp_id).all()
        data = []
        for g in goals:
            data.append(
                {
                    "id": g.id,
                    "title": g.title,
                    "description": g.description,
                    "category": g.category,
                    "status": g.status,
                    "target_date": g.target_date.isoformat() if g.target_date else None,
                    "progress_pct": g.progress_pct,
                }
            )
        return {"goals": data, "count": len(data)}

    return _with_session(_query)


# -- Onboarding Tools --


def _tool_get_onboarding_checklist(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get onboarding checklist for an employee."""
    employee_id = arguments.get("employee_id")

    def _query(session):
        from src.core.database import OnboardingChecklist

        emp_id = int(employee_id) if employee_id else 1
        tasks = session.query(OnboardingChecklist).filter_by(employee_id=emp_id).all()
        data = []
        for t in tasks:
            data.append(
                {
                    "id": t.id,
                    "task_name": t.task_name,
                    "category": t.category,
                    "description": t.description,
                    "status": t.status,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                }
            )
        return {"tasks": data, "count": len(data)}

    return _with_session(_query)


# -- Policy & Knowledge Tools --


def _tool_search_policies(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Search HR policies using the RAG knowledge base."""
    query = arguments.get("query", "")
    if not query:
        return {"error": "query is required"}

    try:
        from src.services.rag_service import RAGService

        rag = RAGService()
        results = rag.search(query, top_k=int(arguments.get("top_k", 5)))
        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        # Fallback: return common policy topics
        return {
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
        }


def _tool_ask_hr_question(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Ask a general HR question using the AI agent."""
    question = arguments.get("question", "")
    if not question:
        return {"error": "question is required"}

    try:
        from flask import current_app

        agent_service = current_app.agent_service
        result = agent_service.process_query(question, user_context={"role": "employee"})
        return {
            "question": question,
            "answer": result.get("response", result.get("answer", str(result))),
            "confidence": result.get("confidence", 0.0),
            "agent_type": result.get("agent_type", "unknown"),
        }
    except Exception:
        # Standalone mode — try RAG only
        try:
            from src.services.rag_service import RAGService

            rag = RAGService()
            results = rag.search(question, top_k=3)
            context = "\n".join(str(r) for r in results) if results else "No context found."
            return {
                "question": question,
                "answer": context,
                "confidence": 0.5,
                "agent_type": "rag_fallback",
                "note": "Agent service unavailable; showing RAG results.",
            }
        except Exception as e2:
            return {"question": question, "error": f"No AI service available: {e2}"}


# -- Analytics Tools --


def _tool_get_hr_metrics(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get HR analytics metrics."""

    def _query(session):
        from src.core.database import Employee, LeaveRequest, QueryLog

        metrics = {}
        metrics["total_employees"] = session.query(Employee).count()
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

        # Department breakdown
        dept_counts = {}
        for emp in session.query(Employee).all():
            dept_counts[emp.department] = dept_counts.get(emp.department, 0) + 1
        metrics["department_headcount"] = dept_counts

        # Queries today
        try:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            metrics["queries_today"] = (
                session.query(QueryLog).filter(QueryLog.created_at >= today).count()
            )
        except Exception:
            metrics["queries_today"] = 0

        return metrics

    return _with_session(_query)


def _tool_get_recent_activity(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get recent activity feed."""
    limit = min(int(arguments.get("limit", 20)), 50)

    def _query(session):
        from src.core.database import (
            LeaveRequest,
            Employee,
            GeneratedDocument,
            BenefitsEnrollment,
            BenefitsPlan,
        )

        activities = []

        # Recent leave requests
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

        # Recent documents
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

        # Recent benefits enrollments
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
                    "timestamp": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
                }
            )

        activities.sort(key=lambda a: a.get("timestamp") or "0000", reverse=True)
        return {"activities": activities[:limit], "count": len(activities[:limit])}

    return _with_session(_query)


# ============================================================
# Tool Registry (all 22 tools)
# ============================================================

TOOLS: List[ToolDefinition] = [
    # -- Leave Management (6) --
    ToolDefinition(
        name="get_leave_balance",
        description="Get an employee's current leave balance including vacation, sick, and personal days remaining.",
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID (numeric string)"},
            },
            "required": ["employee_id"],
        },
        handler=_tool_get_leave_balance,
    ),
    ToolDefinition(
        name="submit_leave_request",
        description="Submit a new leave request for an employee. Creates a pending request that requires manager/HR approval.",
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
                "leave_type": {
                    "type": "string",
                    "enum": ["vacation", "sick", "personal", "parental", "bereavement"],
                    "description": "Type of leave",
                },
                "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                "reason": {"type": "string", "description": "Reason for leave request"},
            },
            "required": ["employee_id", "leave_type", "start_date", "end_date"],
        },
        handler=_tool_submit_leave_request,
    ),
    ToolDefinition(
        name="get_leave_history",
        description="Get leave request history for an employee, showing past and current requests with their statuses.",
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
            },
            "required": ["employee_id"],
        },
        handler=_tool_get_leave_history,
    ),
    ToolDefinition(
        name="approve_leave_request",
        description="Approve a pending leave request. Manager or HR admin action that deducts days from leave balance.",
        input_schema={
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "Leave request ID to approve"},
                "approver_id": {
                    "type": "string",
                    "description": "ID of the approving manager/HR admin",
                },
            },
            "required": ["request_id"],
        },
        handler=_tool_approve_leave_request,
    ),
    ToolDefinition(
        name="reject_leave_request",
        description="Reject a pending leave request with an optional reason.",
        input_schema={
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "Leave request ID to reject"},
                "reason": {"type": "string", "description": "Reason for rejection"},
            },
            "required": ["request_id"],
        },
        handler=_tool_reject_leave_request,
    ),
    ToolDefinition(
        name="get_pending_approvals",
        description="List all pending leave approval requests for manager/HR review.",
        input_schema={
            "type": "object",
            "properties": {},
        },
        handler=_tool_get_pending_approvals,
    ),
    # -- Employee Management (3) --
    ToolDefinition(
        name="get_employee_profile",
        description="Get detailed employee profile including name, department, role, hire date, and contact information.",
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID (numeric)"},
                "email": {
                    "type": "string",
                    "description": "Employee email address (alternative lookup)",
                },
            },
        },
        handler=_tool_get_employee_profile,
    ),
    ToolDefinition(
        name="search_employees",
        description="Search the employee directory by name, department, or role. Returns matching employee summaries.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (name, email, department)",
                },
                "department": {"type": "string", "description": "Filter by department"},
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default: 20, max: 100)",
                },
            },
        },
        handler=_tool_search_employees,
    ),
    ToolDefinition(
        name="update_employee",
        description="Update employee record fields. HR admin operation for modifying employee information.",
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID to update"},
                "updates": {
                    "type": "object",
                    "description": "Fields to update",
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "email": {"type": "string"},
                        "department": {"type": "string"},
                        "role_level": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
            },
            "required": ["employee_id", "updates"],
        },
        handler=_tool_update_employee,
    ),
    # -- Benefits (3) --
    ToolDefinition(
        name="list_benefits_plans",
        description="List all active benefits plans including health, dental, vision, and retirement options with premiums.",
        input_schema={"type": "object", "properties": {}},
        handler=_tool_list_benefits_plans,
    ),
    ToolDefinition(
        name="get_benefits_enrollments",
        description="Get an employee's current benefits enrollments showing active plans and coverage levels.",
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
            },
            "required": ["employee_id"],
        },
        handler=_tool_get_benefits_enrollments,
    ),
    ToolDefinition(
        name="enroll_in_benefit",
        description="Enroll an employee in a benefits plan. Automatically handles plan switching within same type.",
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
                "plan_id": {"type": "string", "description": "Benefits plan ID"},
                "coverage_level": {
                    "type": "string",
                    "enum": ["employee", "employee_spouse", "employee_children", "family"],
                    "description": "Coverage level",
                },
            },
            "required": ["employee_id", "plan_id"],
        },
        handler=_tool_enroll_in_benefit,
    ),
    # -- Documents (2) --
    ToolDefinition(
        name="list_document_templates",
        description="List available HR document templates (offer letters, contracts, certificates, etc.).",
        input_schema={"type": "object", "properties": {}},
        handler=_tool_list_document_templates,
    ),
    ToolDefinition(
        name="generate_document",
        description="Generate an HR document from a template for a specific employee.",
        input_schema={
            "type": "object",
            "properties": {
                "template_id": {"type": "string", "description": "Template ID (t1-t6)"},
                "employee_id": {"type": "string", "description": "Target employee ID"},
                "parameters": {"type": "object", "description": "Additional template parameters"},
            },
            "required": ["template_id"],
        },
        handler=_tool_generate_document,
    ),
    # -- Performance (2) --
    ToolDefinition(
        name="get_performance_reviews",
        description="Get performance reviews for an employee including ratings, strengths, and improvement areas.",
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
            },
            "required": ["employee_id"],
        },
        handler=_tool_get_performance_reviews,
    ),
    ToolDefinition(
        name="get_performance_goals",
        description="Get performance goals for an employee with progress tracking.",
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
            },
            "required": ["employee_id"],
        },
        handler=_tool_get_performance_goals,
    ),
    # -- Onboarding (1) --
    ToolDefinition(
        name="get_onboarding_checklist",
        description="Get onboarding checklist tasks for a new hire employee.",
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
            },
            "required": ["employee_id"],
        },
        handler=_tool_get_onboarding_checklist,
    ),
    # -- Policy & Knowledge (2) --
    ToolDefinition(
        name="search_policies",
        description="Search HR policies and compliance documents using semantic search. Returns relevant policy excerpts.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query about HR policies"},
                "top_k": {"type": "integer", "description": "Number of results (default: 5)"},
            },
            "required": ["query"],
        },
        handler=_tool_search_policies,
    ),
    ToolDefinition(
        name="ask_hr_question",
        description="Ask a natural language HR question. Uses AI agent with RAG to provide contextual answers.",
        input_schema={
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "HR question in natural language"},
            },
            "required": ["question"],
        },
        handler=_tool_ask_hr_question,
    ),
    # -- Analytics (2) --
    ToolDefinition(
        name="get_hr_metrics",
        description="Get HR analytics dashboard metrics including headcount, leave stats, and query volume.",
        input_schema={"type": "object", "properties": {}},
        handler=_tool_get_hr_metrics,
    ),
    ToolDefinition(
        name="get_recent_activity",
        description="Get recent HR activity feed including leave requests, document generation, and chat queries.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max items to return (default: 20)"},
            },
        },
        handler=_tool_get_recent_activity,
    ),
]


# ============================================================
# Resource Registry (8 resources)
# ============================================================


def _resource_employees(uri: str) -> Dict[str, Any]:
    """Fetch employee directory."""

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

    return _with_session(_query)


def _resource_employee_by_id(uri: str) -> Dict[str, Any]:
    """Fetch single employee by ID extracted from URI."""
    # URI format: hr://employees/{id}
    parts = uri.replace("hr://", "").split("/")
    emp_id = parts[1] if len(parts) > 1 else "1"

    def _query(session):
        from src.core.database import Employee

        emp = session.query(Employee).filter_by(id=int(emp_id)).first()
        if not emp:
            return {"error": f"Employee {emp_id} not found"}
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

    return _with_session(_query)


def _resource_policies(uri: str) -> Dict[str, Any]:
    """Fetch available policy topics."""
    return {
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
            {
                "name": "Remote Work Policy",
                "description": "Work from home guidelines and expectations",
            },
            {
                "name": "Performance Review Policy",
                "description": "Annual review process and criteria",
            },
            {"name": "Onboarding Policy", "description": "New hire onboarding procedures"},
            {"name": "GDPR & Privacy Policy", "description": "Data protection and privacy rights"},
            {
                "name": "Anti-Discrimination Policy",
                "description": "Equal opportunity and inclusion",
            },
        ],
        "note": "Use the search_policies tool for detailed policy content.",
    }


def _resource_benefits_plans(uri: str) -> Dict[str, Any]:
    """Fetch benefits plans."""
    return _tool_list_benefits_plans({})


def _resource_leave_balance(uri: str) -> Dict[str, Any]:
    """Fetch leave balance from URI."""
    parts = uri.replace("hr://", "").split("/")
    emp_id = parts[2] if len(parts) > 2 else "1"
    return _tool_get_leave_balance({"employee_id": emp_id})


def _resource_onboarding(uri: str) -> Dict[str, Any]:
    """Fetch onboarding checklist from URI."""
    parts = uri.replace("hr://", "").split("/")
    emp_id = parts[1] if len(parts) > 1 else "1"
    return _tool_get_onboarding_checklist({"employee_id": emp_id})


def _resource_performance(uri: str) -> Dict[str, Any]:
    """Fetch performance data from URI."""
    parts = uri.replace("hr://", "").split("/")
    emp_id = parts[1] if len(parts) > 1 else "1"
    reviews = _tool_get_performance_reviews({"employee_id": emp_id})
    goals = _tool_get_performance_goals({"employee_id": emp_id})
    return {"reviews": reviews, "goals": goals}


def _resource_metrics(uri: str) -> Dict[str, Any]:
    """Fetch HR metrics."""
    return _tool_get_hr_metrics({})


# Static resources (exact URI match)
RESOURCES: List[ResourceDefinition] = [
    ResourceDefinition(
        uri="hr://employees",
        name="Employee Directory",
        description="Complete employee directory with names, departments, and contact info.",
        handler=_resource_employees,
    ),
    ResourceDefinition(
        uri="hr://policies",
        name="HR Policies",
        description="List of available HR policy topics and summaries.",
        handler=_resource_policies,
    ),
    ResourceDefinition(
        uri="hr://benefits/plans",
        name="Benefits Plans",
        description="Available benefits plans with premiums and coverage details.",
        handler=_resource_benefits_plans,
    ),
    ResourceDefinition(
        uri="hr://metrics",
        name="HR Metrics Dashboard",
        description="Live HR analytics including headcount, leave stats, and query volume.",
        handler=_resource_metrics,
    ),
]

# Templated resources (URI pattern match)
RESOURCE_TEMPLATES: List[ResourceTemplate] = [
    ResourceTemplate(
        uri_template="hr://employees/{employee_id}",
        name="Employee Profile",
        description="Detailed employee profile by ID.",
        handler=_resource_employee_by_id,
    ),
    ResourceTemplate(
        uri_template="hr://leave/balance/{employee_id}",
        name="Leave Balance",
        description="Employee leave balance (vacation, sick, personal days).",
        handler=_resource_leave_balance,
    ),
    ResourceTemplate(
        uri_template="hr://onboarding/{employee_id}",
        name="Onboarding Checklist",
        description="Employee onboarding tasks and progress.",
        handler=_resource_onboarding,
    ),
    ResourceTemplate(
        uri_template="hr://performance/{employee_id}",
        name="Performance Data",
        description="Employee performance reviews and goals.",
        handler=_resource_performance,
    ),
]


# ============================================================
# Prompt Registry (5 prompts)
# ============================================================


def _prompt_leave_request(arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate leave request guidance prompt."""
    employee_name = arguments.get("employee_name", "the employee")
    leave_type = arguments.get("leave_type", "vacation")
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"I need to help {employee_name} submit a {leave_type} leave request. "
                    "Please guide me through the process:\n\n"
                    "1. First, check their current leave balance using get_leave_balance\n"
                    "2. Verify the requested dates don't conflict with team schedules\n"
                    "3. Submit the leave request using submit_leave_request\n"
                    "4. Confirm the request was created and is pending approval\n\n"
                    "What are the requested dates?"
                ),
            },
        }
    ]


def _prompt_onboarding_guide(arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate onboarding guidance prompt."""
    employee_name = arguments.get("employee_name", "the new hire")
    department = arguments.get("department", "their department")
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"I'm helping onboard {employee_name} in {department}. "
                    "Please help me through these steps:\n\n"
                    "1. Check their onboarding checklist using get_onboarding_checklist\n"
                    "2. Review pending tasks and their due dates\n"
                    "3. Ensure benefits enrollment is initiated using list_benefits_plans\n"
                    "4. Verify required documents are generated using list_document_templates\n"
                    "5. Provide a summary of completed and pending onboarding items\n\n"
                    "Let's start by checking their checklist."
                ),
            },
        }
    ]


def _prompt_benefits_enrollment(arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate benefits enrollment guidance prompt."""
    employee_name = arguments.get("employee_name", "the employee")
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"I need to help {employee_name} with benefits enrollment. "
                    "Please guide me through:\n\n"
                    "1. List all available plans using list_benefits_plans\n"
                    "2. Check current enrollments using get_benefits_enrollments\n"
                    "3. Compare plan options (premiums, coverage levels)\n"
                    "4. Enroll in selected plan using enroll_in_benefit\n"
                    "5. Confirm enrollment and provide summary\n\n"
                    "Let's start by reviewing available plans."
                ),
            },
        }
    ]


def _prompt_performance_review(arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate performance review preparation prompt."""
    employee_name = arguments.get("employee_name", "the employee")
    review_period = arguments.get("review_period", "current period")
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"I'm preparing a performance review for {employee_name} for {review_period}. "
                    "Please help me gather context:\n\n"
                    "1. Pull their existing reviews using get_performance_reviews\n"
                    "2. Check current goals and progress using get_performance_goals\n"
                    "3. Review their leave history for attendance context using get_leave_history\n"
                    "4. Look up any relevant policy guidelines using search_policies\n"
                    "5. Summarize findings for the review discussion\n\n"
                    "Let's start with their review history."
                ),
            },
        }
    ]


def _prompt_policy_inquiry(arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate policy inquiry prompt."""
    topic = arguments.get("topic", "HR policies")
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"I have a question about {topic}. "
                    "Please help me find the answer:\n\n"
                    "1. Search relevant policies using search_policies\n"
                    "2. If more detail is needed, ask the HR AI using ask_hr_question\n"
                    "3. Provide a clear, concise answer with policy references\n"
                    "4. Note any exceptions or special cases\n\n"
                    f"My question is about: {topic}"
                ),
            },
        }
    ]


PROMPTS: List[PromptDefinition] = [
    PromptDefinition(
        name="leave_request",
        description="Step-by-step guidance for submitting an employee leave request.",
        arguments=[
            PromptArgument(
                name="employee_name", description="Name of the employee requesting leave"
            ),
            PromptArgument(
                name="leave_type",
                description="Type of leave (vacation, sick, personal)",
                required=False,
            ),
        ],
        handler=_prompt_leave_request,
    ),
    PromptDefinition(
        name="onboarding_guide",
        description="Complete onboarding workflow for new hire employees.",
        arguments=[
            PromptArgument(name="employee_name", description="Name of the new hire"),
            PromptArgument(
                name="department", description="Department the employee is joining", required=False
            ),
        ],
        handler=_prompt_onboarding_guide,
    ),
    PromptDefinition(
        name="benefits_enrollment",
        description="Guided benefits enrollment and plan comparison for employees.",
        arguments=[
            PromptArgument(name="employee_name", description="Name of the employee"),
        ],
        handler=_prompt_benefits_enrollment,
    ),
    PromptDefinition(
        name="performance_review",
        description="Preparation workflow for employee performance reviews.",
        arguments=[
            PromptArgument(name="employee_name", description="Name of the employee being reviewed"),
            PromptArgument(
                name="review_period",
                description="Review period (e.g., 'Q1 2024', 'Annual 2024')",
                required=False,
            ),
        ],
        handler=_prompt_performance_review,
    ),
    PromptDefinition(
        name="policy_inquiry",
        description="Guided HR policy lookup and question answering.",
        arguments=[
            PromptArgument(name="topic", description="Policy topic or question"),
        ],
        handler=_prompt_policy_inquiry,
    ),
]


# ============================================================
# MCP Server Core
# ============================================================


class HRMCPServer:
    """
    Full Model Context Protocol server for the HR Agent Platform.

    Implements MCP specification 2024-11-05 with support for:
    - tools/list, tools/call: 22 HR operation tools
    - resources/list, resources/read, resources/templates/list: 8 data resources
    - prompts/list, prompts/get: 5 workflow prompts
    - initialize, ping, notifications/initialized, logging/setLevel

    Transports:
    - stdio: Read/write JSON-RPC messages over stdin/stdout
    - SSE: Flask blueprint at /mcp for HTTP-based clients
    - Direct: Call handle_request() programmatically
    """

    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, name: str = "hr-agent-platform", version: str = "2.0.0"):
        self.name = name
        self.version = version
        self._initialized = False
        self._log_level = "info"

        # Build lookup tables
        self._tools = {t.name: t for t in TOOLS}
        self._resources = {r.uri: r for r in RESOURCES}
        self._resource_templates = RESOURCE_TEMPLATES
        self._prompts = {p.name: p for p in PROMPTS}

        # Method dispatch
        self._methods = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized_notification,
            "notifications/initialized": self._handle_initialized_notification,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "resources/templates/list": self._handle_resource_templates_list,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "logging/setLevel": self._handle_set_log_level,
        }

        logger.info(
            f"HRMCPServer: Created '{name}' v{version} with {len(TOOLS)} tools, "
            f"{len(RESOURCES)} resources, {len(RESOURCE_TEMPLATES)} templates, "
            f"{len(PROMPTS)} prompts"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Handle a JSON-RPC 2.0 request and return a response.

        Args:
            request: JSON-RPC 2.0 request dict.

        Returns:
            JSON-RPC 2.0 response dict, or None for notifications.
        """
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        # Notifications (no id) don't get responses
        is_notification = "id" not in request

        logger.debug(f"MCP: {method} (id={req_id}, notification={is_notification})")

        # Validate JSON-RPC version
        if request.get("jsonrpc") != "2.0":
            if is_notification:
                return None
            return self._error_response(req_id, INVALID_REQUEST, "Invalid JSON-RPC version")

        # Dispatch
        handler = self._methods.get(method)
        if not handler:
            if is_notification:
                return None
            return self._error_response(req_id, METHOD_NOT_FOUND, f"Method not found: {method}")

        try:
            result = handler(params)
            if is_notification:
                return None
            return self._success_response(req_id, result)
        except Exception as e:
            logger.error(f"MCP: Error handling {method}: {e}", exc_info=True)
            if is_notification:
                return None
            return self._error_response(req_id, INTERNAL_ERROR, str(e))

    def handle_request_json(self, json_str: str) -> Optional[str]:
        """Handle a JSON-RPC request from raw JSON string."""
        try:
            request = json.loads(json_str)
        except json.JSONDecodeError as e:
            return json.dumps(self._error_response(None, PARSE_ERROR, f"Parse error: {e}"))

        # Handle batch requests
        if isinstance(request, list):
            responses = []
            for req in request:
                resp = self.handle_request(req)
                if resp is not None:
                    responses.append(resp)
            return json.dumps(responses) if responses else None

        response = self.handle_request(request)
        return json.dumps(response) if response is not None else None

    # ------------------------------------------------------------------
    # Method Handlers
    # ------------------------------------------------------------------

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize — return server capabilities."""
        self._initialized = True
        client_info = params.get("clientInfo", {})
        logger.info(
            f"MCP: Initialized by {client_info.get('name', 'unknown')} "
            f"v{client_info.get('version', '?')}"
        )
        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
                "logging": {},
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
        }

    def _handle_initialized_notification(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialized notification from client."""
        return {}

    def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping."""
        return {}

    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list — return all tool descriptors."""
        cursor = params.get("cursor")
        tools_list = [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in TOOLS
        ]
        return {"tools": tools_list}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call — execute a tool."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not tool_name:
            raise ValueError("Tool name is required")

        tool = self._tools.get(tool_name)
        if not tool:
            raise KeyError(f"Unknown tool: {tool_name}")

        try:
            result = tool.handler(arguments)
            text = json.dumps(result, indent=2, default=str)
            is_error = isinstance(result, dict) and "error" in result
            return {
                "content": [{"type": "text", "text": text}],
                "isError": is_error,
            }
        except Exception as e:
            logger.error(f"MCP: Tool {tool_name} failed: {e}", exc_info=True)
            return {
                "content": [{"type": "text", "text": f"Error executing {tool_name}: {e}"}],
                "isError": True,
            }

    def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list — return static resources."""
        resources_list = [
            {
                "uri": r.uri,
                "name": r.name,
                "description": r.description,
                "mimeType": r.mime_type,
            }
            for r in RESOURCES
        ]
        return {"resources": resources_list}

    def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read — fetch resource content."""
        uri = params.get("uri", "")
        if not uri:
            raise ValueError("Resource URI is required")

        # Try exact match first
        resource = self._resources.get(uri)
        if resource and resource.handler:
            data = resource.handler(uri)
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": resource.mime_type,
                        "text": json.dumps(data, indent=2, default=str),
                    }
                ]
            }

        # Try template match
        for tmpl in self._resource_templates:
            if self._match_uri_template(tmpl.uri_template, uri):
                if tmpl.handler:
                    data = tmpl.handler(uri)
                    return {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": tmpl.mime_type,
                                "text": json.dumps(data, indent=2, default=str),
                            }
                        ]
                    }

        raise KeyError(f"Resource not found: {uri}")

    def _handle_resource_templates_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/templates/list — return resource templates."""
        templates = [
            {
                "uriTemplate": t.uri_template,
                "name": t.name,
                "description": t.description,
                "mimeType": t.mime_type,
            }
            for t in self._resource_templates
        ]
        return {"resourceTemplates": templates}

    def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/list — return all prompts."""
        prompts_list = [
            {
                "name": p.name,
                "description": p.description,
                "arguments": [
                    {
                        "name": a.name,
                        "description": a.description,
                        "required": a.required,
                    }
                    for a in p.arguments
                ],
            }
            for p in PROMPTS
        ]
        return {"prompts": prompts_list}

    def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get — render a prompt with arguments."""
        prompt_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not prompt_name:
            raise ValueError("Prompt name is required")

        prompt = self._prompts.get(prompt_name)
        if not prompt:
            raise KeyError(f"Unknown prompt: {prompt_name}")

        messages = prompt.handler(arguments) if prompt.handler else []
        return {
            "description": prompt.description,
            "messages": messages,
        }

    def _handle_set_log_level(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle logging/setLevel."""
        level = params.get("level", "info")
        self._log_level = level
        log_level = getattr(logging, level.upper(), logging.INFO)
        logging.getLogger("src.mcp").setLevel(log_level)
        return {}

    # ------------------------------------------------------------------
    # URI Template Matching
    # ------------------------------------------------------------------

    @staticmethod
    def _match_uri_template(template: str, uri: str) -> bool:
        """Check if a URI matches a template pattern (e.g., hr://employees/{id})."""
        import re

        # Convert template to regex: {param} -> [^/]+
        pattern = re.sub(r"\{[^}]+\}", r"[^/]+", re.escape(template))
        pattern = pattern.replace(r"\{", "{").replace(r"\}", "}")
        # Re-do properly
        pattern = re.sub(r"\{[^}]+\}", "[^/]+", template)
        pattern = "^" + re.escape(pattern).replace(r"\[^/\]\+", "[^/]+") + "$"
        # Simpler approach
        parts_tmpl = template.split("/")
        parts_uri = uri.split("/")
        if len(parts_tmpl) != len(parts_uri):
            return False
        for t, u in zip(parts_tmpl, parts_uri):
            if t.startswith("{") and t.endswith("}"):
                continue  # Wildcard match
            if t != u:
                return False
        return True

    # ------------------------------------------------------------------
    # Response Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _success_response(req_id: Any, result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _error_response(req_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    # ------------------------------------------------------------------
    # Transport: stdio
    # ------------------------------------------------------------------

    def run_stdio(self):
        """
        Run the MCP server using stdio transport.

        Reads JSON-RPC messages from stdin (one per line) and writes
        responses to stdout. Suitable for IDE/CLI integration.
        """
        logger.info("MCP: Starting stdio transport...")
        print(f"HR Agent MCP Server v{self.version} — stdio transport ready", file=sys.stderr)

        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                response_json = self.handle_request_json(line)
                if response_json:
                    sys.stdout.write(response_json + "\n")
                    sys.stdout.flush()
        except KeyboardInterrupt:
            logger.info("MCP: stdio transport stopped (Ctrl+C)")
        except EOFError:
            logger.info("MCP: stdio transport stopped (EOF)")

    # ------------------------------------------------------------------
    # Transport: Flask SSE Blueprint
    # ------------------------------------------------------------------

    def get_flask_blueprint(self) -> "Blueprint":
        """
        Create a Flask Blueprint that exposes the MCP server via HTTP.

        Endpoints:
        - POST /           JSON-RPC 2.0 endpoint (request/response)
        - GET  /sse         SSE stream for server-initiated messages
        - GET  /health      Health check

        Returns:
            Flask Blueprint instance.
        """
        from flask import Blueprint, request as flask_request, jsonify, Response

        bp = Blueprint("mcp", __name__)

        @bp.route("/", methods=["POST"])
        def mcp_endpoint():
            """Handle MCP JSON-RPC requests over HTTP."""
            try:
                body = flask_request.get_json(force=True)
            except Exception:
                return jsonify(self._error_response(None, PARSE_ERROR, "Invalid JSON")), 400

            if isinstance(body, list):
                # Batch request
                responses = []
                for req in body:
                    resp = self.handle_request(req)
                    if resp is not None:
                        responses.append(resp)
                return jsonify(responses)

            response = self.handle_request(body)
            if response is None:
                return "", 204  # Notification — no response
            return jsonify(response)

        @bp.route("/sse", methods=["GET"])
        def mcp_sse():
            """SSE endpoint for MCP server-to-client messages."""
            import queue

            msg_queue = queue.Queue()

            def generate():
                # Send endpoint event (per MCP SSE transport spec)
                yield f"event: endpoint\ndata: /mcp\n\n"
                # Heartbeat loop
                timeout = 120
                start = time.time()
                while (time.time() - start) < timeout:
                    try:
                        msg = msg_queue.get(timeout=15)
                        yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                    except queue.Empty:
                        yield ": heartbeat\n\n"

            return Response(
                generate(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        @bp.route("/health", methods=["GET"])
        def mcp_health():
            """Health check."""
            return jsonify(
                {
                    "status": "ok",
                    "server": self.name,
                    "version": self.version,
                    "protocol_version": self.PROTOCOL_VERSION,
                    "tools": len(TOOLS),
                    "resources": len(RESOURCES) + len(RESOURCE_TEMPLATES),
                    "prompts": len(PROMPTS),
                }
            )

        return bp

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            "server_name": self.name,
            "version": self.version,
            "protocol_version": self.PROTOCOL_VERSION,
            "initialized": self._initialized,
            "tools": len(TOOLS),
            "resources": len(RESOURCES),
            "resource_templates": len(RESOURCE_TEMPLATES),
            "prompts": len(PROMPTS),
            "tool_names": [t.name for t in TOOLS],
            "resource_uris": [r.uri for r in RESOURCES],
            "prompt_names": [p.name for p in PROMPTS],
        }


# ============================================================
# Factory
# ============================================================


def create_mcp_server(name: str = "hr-agent-platform", version: str = "2.0.0") -> HRMCPServer:
    """
    Create and return a configured HRMCPServer instance.

    Args:
        name: Server name for MCP identification.
        version: Server version string.

    Returns:
        Configured HRMCPServer ready for use.
    """
    return HRMCPServer(name=name, version=version)
