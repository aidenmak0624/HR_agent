"""
BambooHR MCP Server — Dedicated MCP server for BambooHR HRIS integration.

Exposes BambooHR operations as MCP tools so that Claude Desktop (or any
MCP client) can query employees, leave balances, org charts, benefits,
and submit leave requests directly against the BambooHR REST API.

Can run standalone or be imported and composed with the main HR Agent
MCP server.

Usage:
    # Standalone stdio (Claude Desktop / IDE integration):
    python -m src.mcp.bamboohr_mcp

    # Streamable HTTP:
    python -m src.mcp.bamboohr_mcp --transport streamable-http --port 8090

Environment:
    BAMBOOHR_API_KEY:   BambooHR API key (required)
    BAMBOOHR_SUBDOMAIN: Company subdomain, e.g. 'acme' for acme.bamboohr.com (required)
"""

import json
import logging
import os
import sys
from typing import Optional

# Ensure project root on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ============================================================
# FastMCP Server Instance
# ============================================================

bamboohr_mcp = FastMCP(
    "bamboohr-mcp",
    instructions=(
        "BambooHR MCP Server — provides tools for querying and managing "
        "employee data, leave requests, benefits, and org charts via "
        "the BambooHR REST API. Requires BAMBOOHR_API_KEY and "
        "BAMBOOHR_SUBDOMAIN environment variables. "
        "Use bamboohr_search_employees or bamboohr_get_employee to find "
        "employee IDs before calling employee-specific tools."
    ),
)


# ============================================================
# Connector Helpers
# ============================================================

_connector = None


def _get_connector():
    """Lazily create and cache the BambooHR connector.

    Returns:
        BambooHRConnector instance

    Raises:
        RuntimeError: If credentials are missing or invalid
    """
    global _connector
    if _connector is not None:
        return _connector

    api_key = os.environ.get("BAMBOOHR_API_KEY", "").strip()
    subdomain = os.environ.get("BAMBOOHR_SUBDOMAIN", "").strip()

    if not api_key or api_key in ("your-bamboohr-api-key", "not-set"):
        raise RuntimeError(
            "BAMBOOHR_API_KEY is not configured. "
            "Set it in your .env file or environment variables."
        )
    if not subdomain or subdomain in ("your-company-subdomain", "not-set"):
        raise RuntimeError(
            "BAMBOOHR_SUBDOMAIN is not configured. "
            "Set it in your .env file or environment variables."
        )

    from src.connectors.bamboohr import BambooHRConnector

    _connector = BambooHRConnector(api_key=api_key, subdomain=subdomain)
    logger.info("BambooHR connector initialized for subdomain '%s'", subdomain)
    return _connector


def _error_response(error: Exception) -> str:
    """Format error as a JSON response string."""
    return json.dumps(
        {
            "error": str(error),
            "hint": (
                "Check that BAMBOOHR_API_KEY and BAMBOOHR_SUBDOMAIN are set "
                "correctly in your environment."
            ),
        },
        indent=2,
    )


# ============================================================
# EMPLOYEE TOOLS
# ============================================================


@bamboohr_mcp.tool()
def bamboohr_get_employee(employee_id: str) -> str:
    """Retrieve a single employee's profile from BambooHR by ID.

    Returns name, email, department, job title, hire date, status, and manager.

    Args:
        employee_id: BambooHR employee ID (numeric string, or 'employee' for current API user)
    """
    try:
        connector = _get_connector()
        employee = connector.get_employee(employee_id)
        if employee is None:
            return json.dumps({"error": f"Employee {employee_id} not found"}, indent=2)
        return json.dumps(employee.model_dump(), indent=2, default=str)
    except Exception as e:
        return _error_response(e)


@bamboohr_mcp.tool()
def bamboohr_search_employees(
    department: str = "",
    status: str = "",
    location: str = "",
    job_title: str = "",
) -> str:
    """Search the BambooHR employee directory with optional filters.

    Returns a list of matching employees. Omit all filters to list everyone.

    Args:
        department: Filter by department name (exact match)
        status: Filter by status (active, inactive, on_leave, terminated)
        location: Filter by office location (exact match)
        job_title: Filter by job title (exact match)
    """
    try:
        connector = _get_connector()
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
        return json.dumps(
            {"employees": results, "count": len(results), "filters": filters},
            indent=2,
            default=str,
        )
    except Exception as e:
        return _error_response(e)


# ============================================================
# LEAVE MANAGEMENT TOOLS
# ============================================================


@bamboohr_mcp.tool()
def bamboohr_get_leave_balance(employee_id: str) -> str:
    """Get an employee's current leave balance from BambooHR.

    Returns PTO, sick, personal, and other leave type balances with
    total, used, pending, and available days.

    Args:
        employee_id: BambooHR employee ID
    """
    try:
        connector = _get_connector()
        balances = connector.get_leave_balance(employee_id)
        results = [b.model_dump() for b in balances]
        return json.dumps(
            {"employee_id": employee_id, "balances": results, "count": len(results)},
            indent=2,
            default=str,
        )
    except Exception as e:
        return _error_response(e)


@bamboohr_mcp.tool()
def bamboohr_get_leave_requests(employee_id: str, status: str = "") -> str:
    """Get leave requests for an employee from BambooHR.

    Args:
        employee_id: BambooHR employee ID
        status: Optional filter — pending, approved, denied, or cancelled
    """
    try:
        connector = _get_connector()
        requests = connector.get_leave_requests(employee_id, status=status if status else None)
        results = [r.model_dump() for r in requests]
        return json.dumps(
            {
                "employee_id": employee_id,
                "requests": results,
                "count": len(results),
            },
            indent=2,
            default=str,
        )
    except Exception as e:
        return _error_response(e)


@bamboohr_mcp.tool()
def bamboohr_submit_leave_request(
    employee_id: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    reason: str = "",
) -> str:
    """Submit a new leave request to BambooHR.

    Creates a pending request that requires manager approval in BambooHR.

    Args:
        employee_id: BambooHR employee ID
        leave_type: Type of leave — pto, sick, personal, unpaid, other
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        reason: Optional reason for the leave request
    """
    try:
        from datetime import datetime

        from src.connectors.hris_interface import LeaveRequest, LeaveType, LeaveStatus

        connector = _get_connector()

        # Map string to enum
        type_map = {
            "pto": LeaveType.PTO,
            "vacation": LeaveType.PTO,
            "sick": LeaveType.SICK,
            "personal": LeaveType.PERSONAL,
            "unpaid": LeaveType.UNPAID,
        }
        lt = type_map.get(leave_type.lower(), LeaveType.OTHER)

        request = LeaveRequest(
            employee_id=employee_id,
            leave_type=lt,
            start_date=datetime.fromisoformat(start_date),
            end_date=datetime.fromisoformat(end_date),
            status=LeaveStatus.PENDING,
            reason=reason,
            submitted_at=datetime.utcnow(),
        )
        result = connector.submit_leave_request(request)
        return json.dumps(
            {
                "request_id": result.id,
                "status": result.status.value,
                "employee_id": employee_id,
                "leave_type": lt.value,
                "start_date": start_date,
                "end_date": end_date,
                "message": "Leave request submitted to BambooHR and is pending approval.",
            },
            indent=2,
            default=str,
        )
    except Exception as e:
        return _error_response(e)


# ============================================================
# ORG CHART TOOLS
# ============================================================


@bamboohr_mcp.tool()
def bamboohr_get_org_chart(department: str = "") -> str:
    """Get the organization chart / hierarchy from BambooHR.

    Returns a tree of employees with their direct reports.

    Args:
        department: Optional department filter (returns only that department's subtree)
    """
    try:
        connector = _get_connector()
        nodes = connector.get_org_chart(department=department if department else None)

        def _serialize_node(node):
            return {
                "employee_id": node.employee_id,
                "name": node.name,
                "title": node.title,
                "department": node.department,
                "direct_reports": [_serialize_node(dr) for dr in node.direct_reports],
            }

        results = [_serialize_node(n) for n in nodes]
        return json.dumps(
            {"org_chart": results, "root_count": len(results)},
            indent=2,
            default=str,
        )
    except Exception as e:
        return _error_response(e)


# ============================================================
# BENEFITS TOOLS
# ============================================================


@bamboohr_mcp.tool()
def bamboohr_get_benefits(employee_id: str) -> str:
    """Get benefits plan enrollments for an employee from BambooHR.

    Returns health, dental, vision, 401k, life insurance, and other plans.

    Args:
        employee_id: BambooHR employee ID
    """
    try:
        connector = _get_connector()
        plans = connector.get_benefits(employee_id)
        results = [p.model_dump() for p in plans]
        return json.dumps(
            {"employee_id": employee_id, "benefits": results, "count": len(results)},
            indent=2,
            default=str,
        )
    except Exception as e:
        return _error_response(e)


# ============================================================
# HEALTH CHECK TOOL
# ============================================================


@bamboohr_mcp.tool()
def bamboohr_health_check() -> str:
    """Check connectivity to the BambooHR API.

    Returns the connection status and configured subdomain.
    Useful for verifying credentials before running other tools.
    """
    try:
        connector = _get_connector()
        healthy = connector.health_check()
        subdomain = os.environ.get("BAMBOOHR_SUBDOMAIN", "unknown")
        return json.dumps(
            {
                "status": "healthy" if healthy else "unhealthy",
                "subdomain": subdomain,
                "message": (
                    f"Successfully connected to BambooHR ({subdomain}.bamboohr.com)"
                    if healthy
                    else "Failed to connect to BambooHR. Check API key and subdomain."
                ),
            },
            indent=2,
        )
    except Exception as e:
        return _error_response(e)


# ============================================================
# RESOURCES
# ============================================================


@bamboohr_mcp.resource("bamboohr://status")
def resource_bamboohr_status() -> str:
    """BambooHR connection status and configuration summary."""
    subdomain = os.environ.get("BAMBOOHR_SUBDOMAIN", "not-set")
    has_key = bool(
        os.environ.get("BAMBOOHR_API_KEY", "").strip()
        and os.environ.get("BAMBOOHR_API_KEY", "") != "your-bamboohr-api-key"
    )
    return json.dumps(
        {
            "subdomain": subdomain,
            "api_key_configured": has_key,
            "base_url": f"https://api.bamboohr.com/api/gateway.php/{subdomain}/v1",
        },
        indent=2,
    )


@bamboohr_mcp.resource("bamboohr://employees")
def resource_bamboohr_employees() -> str:
    """Full employee directory from BambooHR."""
    return bamboohr_search_employees()


# ============================================================
# PROMPTS
# ============================================================


@bamboohr_mcp.prompt()
def bamboohr_employee_lookup(employee_name: str) -> str:
    """Look up an employee in BambooHR by name and get their full profile."""
    return (
        f"I need to find {employee_name} in BambooHR. "
        "Steps:\n"
        "1. Use bamboohr_search_employees to find matching employees\n"
        "2. Use bamboohr_get_employee with the ID to get full profile\n"
        "3. Optionally check their leave balance and benefits\n\n"
        f"Please search for: {employee_name}"
    )


@bamboohr_mcp.prompt()
def bamboohr_leave_workflow(employee_name: str, leave_type: str = "pto") -> str:
    """Guide through submitting a leave request in BambooHR."""
    return (
        f"I need to help {employee_name} submit a {leave_type} leave request "
        "through BambooHR.\n\n"
        "Steps:\n"
        "1. Search for the employee using bamboohr_search_employees\n"
        "2. Check their current leave balance with bamboohr_get_leave_balance\n"
        "3. Submit the request with bamboohr_submit_leave_request\n"
        "4. Confirm the request is pending\n\n"
        "What are the requested dates?"
    )


# ============================================================
# Entry Point
# ============================================================


def main():
    """Run the BambooHR MCP server standalone."""
    import argparse

    parser = argparse.ArgumentParser(description="BambooHR MCP Server")
    parser.add_argument(
        "--transport",
        "-t",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument("--port", "-p", type=int, default=8090, help="Port for HTTP transport")
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP transport")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    logger.info("Starting BambooHR MCP server — transport=%s", args.transport)

    if args.transport == "stdio":
        bamboohr_mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        bamboohr_mcp.run(transport="streamable-http", host=args.host, port=args.port)
    elif args.transport == "sse":
        bamboohr_mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
