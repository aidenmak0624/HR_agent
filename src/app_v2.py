"""
Flask Application v2 - HR Multi-Agent Platform
Iteration 3, Wave 2: APP INTEGRATION
Main entry point with multi-agent system integration, RAG, and API v2
"""

# Fix sys.path when running as `python src/app_v2.py`:
# Python adds `src/` to sys.path, which causes `src/platform/` to shadow
# the stdlib `platform` module. Replace it with the project root instead.
import sys as _sys, os as _os

_project_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _project_root not in _sys.path:
    _sys.path.insert(0, _project_root)
# Remove bare 'src/' from path if present (avoids platform shadowing)
_src_dir = _os.path.join(_project_root, "src")
if _src_dir in _sys.path:
    _sys.path.remove(_src_dir)

from flask import Flask, jsonify, g, render_template
from flask_cors import CORS
import logging
import os
from dotenv import load_dotenv
from functools import wraps
import time
import uuid

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ==================== FLASK APP CREATION ====================

# Resolve paths for frontend templates and static files
_app_root = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_app_root)
_template_dir = os.path.join(_project_root, "frontend", "templates")
_static_dir = os.path.join(_project_root, "frontend", "static")

app = Flask(
    __name__,
    template_folder=_template_dir,
    static_folder=_static_dir,
)

# Set configuration
app.config["JSON_SORT_KEYS"] = False
app.config["PROPAGATE_EXCEPTIONS"] = True

# ==================== MIDDLEWARE REGISTRATION ====================

# Initialize security and production hardening middleware
try:
    from src.middleware.request_logger import setup_structured_logging

    setup_structured_logging(app)
    logger.info("✅ Structured request logging initialized")
except Exception as e:
    logger.warning(f"⚠️  Could not initialize structured logging: {e}")

try:
    from src.middleware.sanitizer import setup_request_sanitization

    setup_request_sanitization(app)
    logger.info("✅ Request input sanitization initialized")
except Exception as e:
    logger.warning(f"⚠️  Could not initialize sanitization: {e}")

try:
    from src.middleware.security_headers import SecurityHeadersMiddleware

    security_headers_mw = SecurityHeadersMiddleware()

    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        headers = security_headers_mw.get_headers()
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value
        return response

    logger.info("✅ Security headers middleware initialized")
except Exception as e:
    logger.warning(f"⚠️  Could not initialize security headers: {e}")

# ==================== CORS CONFIGURATION ====================

CORS(
    app,
    resources={
        r"/api/v2/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    },
)

# ==================== SERVICE INITIALIZATION ====================


def init_services():
    """Initialize all backend services on app startup.

    Runs entirely in a background daemon thread so the Flask server
    starts immediately and can answer health checks while services
    come up.  No join/timeout — services init at their own pace.
    """
    import threading

    def _init_worker():
        try:
            from src.services.agent_service import AgentService

            app.agent_service = AgentService()
            logger.info("✅ Agent service initialized")
        except Exception as e:
            logger.error(f"❌ Agent service init failed: {e}")
            app.agent_service = None

        try:
            from src.services.llm_service import LLMService

            app.llm_service = LLMService()
            logger.info("✅ LLM service initialized")
        except Exception as e:
            logger.error(f"❌ LLM service init failed: {e}")
            app.llm_service = None

        try:
            from src.services.rag_service import RAGService

            app.rag_service = RAGService()
            logger.info("✅ RAG service initialized")
        except Exception as e:
            logger.error(f"❌ RAG service init failed: {e}")
            app.rag_service = None

        logger.info("✅ All background service initialization completed")

    logger.info("Launching service init in background (non-blocking)...")

    # Set defaults so the app can serve immediately
    app.agent_service = None
    app.llm_service = None
    app.rag_service = None

    init_thread = threading.Thread(target=_init_worker, daemon=True)
    init_thread.start()
    # Don't join — let the thread run in the background


# ==================== HEALTH CHECKS ====================


def health_check_database() -> bool:
    """Check database connectivity."""
    try:
        from src.core.database import SessionLocal

        if SessionLocal is None:
            return False
        session = SessionLocal()
        try:
            from sqlalchemy import text

            session.execute(text("SELECT 1"))
            return True
        finally:
            session.close()
    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")
        return False


def health_check_redis() -> bool:
    """Check Redis connectivity."""
    try:
        import redis  # type: ignore[import-untyped]
        from config.settings import get_settings

        settings = get_settings()
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        client.ping()
        logger.info("✅ Redis health check passed")
        return True
    except Exception as e:
        logger.warning(f"⚠️  Redis health check failed (optional): {e}")
        return False


def health_check_llm() -> bool:
    """Check LLM provider availability."""
    try:
        from src.services.llm_service import LLMService

        service = LLMService()
        is_available = service.is_available()
        if is_available:
            logger.info("✅ LLM provider health check passed")
        else:
            logger.warning("⚠️  LLM provider not available")
        return is_available
    except Exception as e:
        logger.warning(f"⚠️  LLM health check failed (optional): {e}")
        return False


# ==================== MIDDLEWARE ====================


@app.before_request
def before_request():
    """Middleware to run before each request."""
    g.request_id = str(uuid.uuid4())
    g.request_start_time = time.time()

    from flask import request as req

    # Skip ALL heavy middleware for health checks — must respond fast
    if req.path == "/api/v2/health":
        g.user_context = {"user_id": "healthcheck", "role": "system", "department": "system"}
        g.rate_limit_remaining = 999
        return  # Skip auth, rate limiting, DB lookups

    # Skip auth for login page, static files, and auth API endpoints
    skip_auth_paths = ["/login", "/static/", "/api/v2/auth/", "/api/v2/notifications/stream"]
    current_path = req.path

    if any(current_path.startswith(p) for p in skip_auth_paths):
        # Still set default user context for API calls
        g.user_context = {"user_id": "anonymous", "role": "employee", "department": "unknown"}
    else:
        # Check for auth token in cookie or header
        # For browser pages, check localStorage via a simple mechanism
        # For API calls, check X-User-Role header
        pass

    # --- Rate Limiting Check ---
    try:
        from src.middleware.rate_limiter import get_rate_limiter

        rate_limiter = get_rate_limiter()
        client_ip = (
            req.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or req.remote_addr
            or "unknown"
        )

        # Skip rate limiting for localhost / testing and static files
        if client_ip in ("127.0.0.1", "::1", "localhost") or req.path.startswith("/static/"):
            g.rate_limit_remaining = 999
        else:
            # Determine rate limit based on endpoint
            limit = 30 if "/api/v2/auth/" in req.path else 200
            is_allowed, remaining = rate_limiter.is_allowed(client_ip, limit=limit)

            if not is_allowed:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                from flask import jsonify

                response = jsonify(
                    {
                        "success": False,
                        "error": "Rate limit exceeded. Please try again later.",
                        "retry_after": 60,
                    }
                )
                response.status_code = 429
                response.headers["Retry-After"] = "60"
                return response

            # Store remaining requests in g for use in response headers
            g.rate_limit_remaining = remaining

    except Exception as e:
        logger.warning(f"Error in rate limit check: {e}")
        # Continue without rate limiting if there's an error

    # --- Resolve authenticated user from token or role header ---
    auth_header = req.headers.get("Authorization", "")
    custom_role = req.headers.get("X-User-Role", "").strip().lower()

    # Default context
    g.user_context = {"user_id": "unknown", "role": "employee", "department": "Engineering"}

    # Try to verify JWT Bearer token
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        try:
            from src.middleware.auth import AuthService, AuthError

            auth_svc = AuthService()
            payload = auth_svc.verify_token(token)
            # JWT verified — populate context from token claims
            user_id = payload.get("user_id", "unknown")
            g.user_context = {
                "user_id": user_id,
                "role": payload.get("role", "employee"),
                "department": payload.get("department", "Engineering"),
                "employee_id": int(user_id) if user_id.isdigit() else None,
                "email": payload.get("email", ""),
                "name": "",  # filled from DB below if available
            }
            # Optionally enrich with employee name from DB
            try:
                from src.core.database import SessionLocal, Employee

                if SessionLocal and g.user_context.get("employee_id"):
                    db = SessionLocal()
                    try:
                        emp = db.query(Employee).filter_by(id=g.user_context["employee_id"]).first()
                        if emp:
                            g.user_context["name"] = f"{emp.first_name} {emp.last_name}"
                    finally:
                        db.close()
            except Exception:
                pass
        except Exception:
            # JWT verification failed — fall back to legacy token_{id}_{ts} format
            parts = token.split("_")
            if len(parts) >= 2:
                try:
                    emp_id = int(parts[1])
                    from src.core.database import SessionLocal, Employee

                    if SessionLocal:
                        db = SessionLocal()
                        try:
                            emp = db.query(Employee).filter_by(id=emp_id).first()
                            if emp:
                                g.user_context = {
                                    "user_id": str(emp.id),
                                    "role": emp.role_level,
                                    "department": emp.department,
                                    "employee_id": emp.id,
                                    "email": emp.email,
                                    "name": f"{emp.first_name} {emp.last_name}",
                                }
                        finally:
                            db.close()
                except (ValueError, IndexError):
                    logger.debug("Could not parse employee id from legacy token")

    # X-User-Role header can override role (for the account-switcher UI)
    if custom_role and custom_role in ("employee", "manager", "hr_admin"):
        g.user_context["role"] = custom_role


@app.after_request
def after_request(response):
    """Middleware to run after each request."""
    elapsed_ms = (time.time() - g.request_start_time) * 1000
    request_id = g.request_id

    logger.info(f"REQUEST {request_id}: {elapsed_ms:.1f}ms " f"{response.status_code}")

    response.headers["X-Request-ID"] = request_id

    # Add rate limit headers if available
    if hasattr(g, "rate_limit_remaining"):
        response.headers["X-RateLimit-Remaining"] = str(g.rate_limit_remaining)
        response.headers["X-RateLimit-Limit"] = "60"

    return response


# ==================== ERROR HANDLERS ====================


@app.errorhandler(404)
def handle_404(error):
    """Handle 404 Not Found errors."""
    return jsonify({"success": False, "error": "Endpoint not found", "status": 404}), 404


@app.errorhandler(500)
def handle_500(error):
    """Handle 500 Internal Server errors."""
    request_id = g.get("request_id", "unknown")
    logger.error(f"500 error in request {request_id}: {error}")

    return (
        jsonify(
            {
                "success": False,
                "error": "Internal server error",
                "request_id": request_id,
                "status": 500,
            }
        ),
        500,
    )


# ==================== ROUTES ====================

# --- Frontend Page Routes ---


@app.route("/", methods=["GET"])
def root():
    """Serve the dashboard (main page)."""
    return render_template("dashboard.html", current_page="dashboard", user="Guest")


@app.route("/dashboard", methods=["GET"])
def dashboard_page():
    """Dashboard page."""
    return render_template("dashboard.html", current_page="dashboard", user="Guest")


@app.route("/chat", methods=["GET"])
def chat_page():
    """Chat page."""
    return render_template("chat.html", current_page="chat", user="Guest")


@app.route("/leave", methods=["GET"])
def leave_page():
    """Leave management page."""
    return render_template("leave.html", current_page="leave", user="Guest")


@app.route("/workflows", methods=["GET"])
def workflows_page():
    """Workflows page."""
    return render_template("workflows.html", current_page="workflows", user="Guest")


@app.route("/directory", methods=["GET"])
def directory_page():
    """Employee directory page."""
    return render_template("directory.html", current_page="directory", user="Guest")


@app.route("/documents", methods=["GET"])
def documents_page():
    """Documents page."""
    return render_template("documents.html", current_page="documents", user="Guest")


@app.route("/analytics", methods=["GET"])
def analytics_page():
    """Analytics page."""
    return render_template("analytics.html", current_page="analytics", user="Guest")


@app.route("/settings", methods=["GET"])
def settings_page():
    """Settings page."""
    return render_template("settings.html", current_page="settings", user="Guest")


@app.route("/login", methods=["GET"])
def login_page():
    """Login page."""
    return render_template("login.html")


# --- Account / Profile API Endpoints ---


@app.route("/api/v2/profile", methods=["GET"])
def get_profile():
    """Get the current user's profile (based on role switcher or token)."""
    role = g.user_context.get("role", "employee")
    # Map role to demo employee
    role_to_email = {
        "employee": "john.smith@company.com",
        "manager": "sarah.chen@company.com",
        "hr_admin": "emily.rodriguez@company.com",
    }
    email = role_to_email.get(role, "john.smith@company.com")
    try:
        from src.core.database import SessionLocal, Employee

        if SessionLocal:
            db = SessionLocal()
            try:
                emp = db.query(Employee).filter_by(email=email).first()
                if emp:
                    return jsonify(
                        {
                            "success": True,
                            "data": {
                                "id": emp.id,
                                "first_name": emp.first_name,
                                "last_name": emp.last_name,
                                "email": emp.email,
                                "department": emp.department,
                                "role_level": emp.role_level,
                                "hris_id": emp.hris_id,
                                "status": emp.status,
                            },
                        }
                    )
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
    return jsonify({"success": False, "error": "Profile not found"}), 404


@app.route("/api/v2/profile", methods=["PUT"])
def update_profile():
    """Update the current user's profile."""
    from flask import request as req

    data = req.get_json() or {}
    role = g.user_context.get("role", "employee")
    role_to_email = {
        "employee": "john.smith@company.com",
        "manager": "sarah.chen@company.com",
        "hr_admin": "emily.rodriguez@company.com",
    }
    email = role_to_email.get(role, "john.smith@company.com")
    try:
        from src.core.database import SessionLocal, Employee

        if SessionLocal:
            db = SessionLocal()
            try:
                emp = db.query(Employee).filter_by(email=email).first()
                if emp:
                    if "first_name" in data:
                        emp.first_name = data["first_name"]
                    if "last_name" in data:
                        emp.last_name = data["last_name"]
                    if "department" in data:
                        emp.department = data["department"]
                    db.commit()
                    return jsonify({"success": True, "message": "Profile updated successfully"})
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
    return jsonify({"success": False, "error": "Failed to update profile"}), 500


@app.route("/api/v2/employees", methods=["GET"])
def list_employees():
    """List all employees (HR Admin only). Always returns fresh data."""
    role = g.user_context.get("role", "employee")
    if role != "hr_admin":
        return jsonify({"success": False, "error": "Access denied. HR Admin role required."}), 403
    try:
        from src.core.database import SessionLocal, Employee

        if SessionLocal:
            db = SessionLocal()
            try:
                employees = db.query(Employee).all()
                resp = jsonify(
                    {
                        "success": True,
                        "data": [
                            {
                                "id": e.id,
                                "first_name": e.first_name,
                                "last_name": e.last_name,
                                "email": e.email,
                                "department": e.department,
                                "role_level": e.role_level,
                                "hris_id": e.hris_id,
                                "status": e.status,
                            }
                            for e in employees
                        ],
                    }
                )
                resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                return resp
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Error listing employees: {e}")
    return jsonify({"success": False, "error": "Failed to list employees"}), 500


@app.route("/api/v2/employees/<int:emp_id>", methods=["PUT"])
def update_employee(emp_id):
    """Update an employee's details (HR Admin only)."""
    role = g.user_context.get("role", "employee")
    if role != "hr_admin":
        return jsonify({"success": False, "error": "Access denied. HR Admin role required."}), 403
    from flask import request as req

    data = req.get_json() or {}
    try:
        from src.core.database import SessionLocal, Employee

        if SessionLocal:
            db = SessionLocal()
            try:
                emp = db.query(Employee).filter_by(id=emp_id).first()
                if not emp:
                    return jsonify({"success": False, "error": "Employee not found"}), 404
                if "first_name" in data:
                    emp.first_name = data["first_name"]
                if "last_name" in data:
                    emp.last_name = data["last_name"]
                if "email" in data:
                    emp.email = data["email"]
                if "department" in data:
                    emp.department = data["department"]
                if "role_level" in data and data["role_level"] in (
                    "employee",
                    "manager",
                    "hr_admin",
                ):
                    emp.role_level = data["role_level"]
                if "status" in data and data["status"] in ("active", "inactive"):
                    emp.status = data["status"]
                db.commit()
                return jsonify(
                    {"success": True, "message": f"Employee {emp_id} updated successfully"}
                )
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Error updating employee {emp_id}: {e}")
    return jsonify({"success": False, "error": "Failed to update employee"}), 500


# --- Documents API ---


@app.route("/api/v2/documents/recent", methods=["GET"])
def get_recent_documents():
    """Get recent generated documents from DB."""
    try:
        from src.core.database import SessionLocal, GeneratedDocument, Employee

        if SessionLocal:
            db = SessionLocal()
            try:
                docs = (
                    db.query(GeneratedDocument)
                    .order_by(GeneratedDocument.id.desc())
                    .limit(20)
                    .all()
                )
                result = []
                for doc in docs:
                    emp = db.query(Employee).filter_by(id=doc.employee_id).first()
                    emp_name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"
                    file_name = (
                        f"{doc.template_name.replace(' ', '_')}_{emp_name.replace(' ', '_')}.pdf"
                    )
                    result.append(
                        {
                            "id": doc.id,
                            "file_name": file_name,
                            "employee_name": emp_name,
                            "template_name": doc.template_name,
                            "status": doc.status,
                            "created_at": doc.created_at.isoformat() if doc.created_at else None,
                        }
                    )
                return jsonify({"success": True, "data": result})
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Recent documents error: {e}")
    return jsonify({"success": True, "data": []})


@app.route("/api/v2/employees/names", methods=["GET"])
def list_employee_names():
    """List employee names for dropdowns (any authenticated role)."""
    try:
        from src.core.database import SessionLocal, Employee

        if SessionLocal:
            db = SessionLocal()
            try:
                employees = (
                    db.query(Employee)
                    .filter_by(status="active")
                    .order_by(Employee.first_name)
                    .all()
                )
                return jsonify(
                    {
                        "success": True,
                        "data": [
                            {"id": e.id, "first_name": e.first_name, "last_name": e.last_name}
                            for e in employees
                        ],
                    }
                )
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Employee names error: {e}")
    return jsonify({"success": True, "data": []})


# --- Workflows API ---


@app.route("/api/v2/workflows/active", methods=["GET"])
def get_active_workflows():
    """Get all leave requests as active workflows (real DB data)."""
    try:
        from src.core.database import SessionLocal, Employee
        from src.core.database import LeaveRequest as LR

        if SessionLocal:
            db = SessionLocal()
            try:
                requests = db.query(LR).order_by(LR.id.desc()).limit(20).all()
                workflows = []
                for req in requests:
                    emp = db.query(Employee).filter_by(id=req.employee_id).first()
                    name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"

                    # Build timeline steps
                    steps = [
                        {
                            "title": "Request Submitted",
                            "status": "completed",
                            "date": req.created_at.strftime("%b %d") if req.created_at else "",
                        }
                    ]

                    if req.status == "pending":
                        steps.append(
                            {
                                "title": "Manager Approval",
                                "status": "in-progress",
                                "date": "Awaiting review",
                            }
                        )
                        steps.append(
                            {"title": "HR Approval", "status": "pending", "date": "Pending"}
                        )
                        wf_status = "in-progress"
                    elif req.status == "approved":
                        steps.append(
                            {
                                "title": "Manager Approval",
                                "status": "completed",
                                "date": req.approved_at.strftime("%b %d")
                                if req.approved_at
                                else "Done",
                            }
                        )
                        steps.append(
                            {"title": "HR Approval", "status": "completed", "date": "Approved"}
                        )
                        wf_status = "completed"
                    elif req.status == "rejected":
                        steps.append(
                            {"title": "Manager Review", "status": "completed", "date": "Reviewed"}
                        )
                        steps.append({"title": "Rejected", "status": "rejected", "date": "Denied"})
                        wf_status = "rejected"
                    else:
                        wf_status = "pending"

                    leave_label = {
                        "vacation": "Vacation",
                        "sick": "Sick Leave",
                        "personal": "Personal",
                    }.get(req.leave_type, req.leave_type)
                    workflows.append(
                        {
                            "id": req.id,
                            "title": f"{leave_label} — {name}",
                            "type": "Leave Request",
                            "status": wf_status,
                            "detail": f"{req.start_date} to {req.end_date}",
                            "steps": steps,
                        }
                    )

                return jsonify({"success": True, "data": workflows})
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Active workflows error: {e}")
    return jsonify({"success": True, "data": []})


# --- API Info Endpoint ---


@app.route("/api", methods=["GET"])
def api_info():
    """API overview endpoint."""
    return jsonify(
        {
            "message": "HR Multi-Agent Platform v2",
            "status": "running",
            "version": "2.0.0",
            "endpoints": {
                "v2_health": "/api/v2/health",
                "v2_query": "/api/v2/query",
                "v2_metrics": "/api/v2/metrics",
                "v2_agents": "/api/v2/agents",
                "v2_rag_stats": "/api/v2/rag/stats",
                "v2_rag_ingest": "/api/v2/rag/ingest",
            },
        }
    )


@app.route("/api/v2/health", methods=["GET"])
def health():
    """Health check endpoint.

    Always returns 200 so Cloud Run keeps the service routable.
    The 'status' field communicates actual readiness to callers.
    """
    from src.core.database import SessionLocal

    # Quick check: is the DB engine even initialized yet?
    if SessionLocal is None:
        return (
            jsonify(
                {
                    "success": True,
                    "status": "starting",
                    "message": "Database still initializing",
                    "checks": {
                        "database": "initializing",
                        "redis": "unknown",
                        "llm": "unknown",
                    },
                }
            ),
            200,
        )  # Return 200 so Cloud Run doesn't mark us as down

    db_ok = health_check_database()

    # Redis and LLM are optional — don't block health on them
    status = "healthy" if db_ok else "degraded"

    return (
        jsonify(
            {
                "success": True,
                "status": status,
                "checks": {
                    "database": "ok" if db_ok else "failed",
                    "redis": "skipped",
                    "llm": "skipped",
                },
            }
        ),
        200,
    )


# ==================== API V2 BLUEPRINT REGISTRATION ====================


def register_api_v2():
    """Register API v2 blueprint."""
    from src.platform_services.api_gateway import APIGateway

    api = APIGateway()
    blueprint = api.get_blueprint()
    app.register_blueprint(blueprint)

    # Store API gateway for service access
    app.api_gateway = api

    logger.info("✅ API v2 blueprint registered at /api/v2/")


# ==================== LEGACY BLUEPRINT REGISTRATION ====================


def register_legacy_api():
    """Register legacy API blueprint for backward compatibility."""
    try:
        from src.api.routes import agent_routes

        app.register_blueprint(agent_routes.bp)
        logger.info("✅ Legacy API blueprint registered for backward compatibility")
    except Exception as e:
        logger.warning(f"⚠️  Legacy API not available: {e}")


# ==================== STARTUP BANNER ====================


def print_startup_banner():
    """Print startup banner with endpoint information."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║         HR Multi-Agent Platform v2 - Wave 2                   ║
║              APP INTEGRATION (Iteration 3)                     ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Server starting on http://localhost:5050                    ║
║                                                               ║
║  ✅ CORE ENDPOINTS (v2 API)                                  ║
║     POST   /api/v2/query          - Multi-agent query         ║
║     GET    /api/v2/metrics        - Agent metrics & stats     ║
║     GET    /api/v2/agents         - List available agents     ║
║     GET    /api/v2/health         - System health check       ║
║                                                               ║
║  📚 RAG ENDPOINTS (v2 API)                                   ║
║     GET    /api/v2/rag/stats      - Collection statistics     ║
║     POST   /api/v2/rag/ingest     - Ingest documents         ║
║                                                               ║
║  🔄 AUTHENTICATION                                            ║
║     POST   /api/v2/auth/token     - Generate JWT token        ║
║     POST   /api/v2/auth/refresh   - Refresh token             ║
║                                                               ║
║  🏥 HEALTH & STATUS                                          ║
║     GET    /                      - API overview              ║
║     GET    /api/v2/health         - System health             ║
║                                                               ║
║  ⚙️  SERVICE ARCHITECTURE                                    ║
║     - AgentService: Multi-agent orchestration                ║
║     - LLMService: LLM provider integration (Google Gemini)    ║
║     - RAGService: Document retrieval & search                 ║
║     - RouterAgent: Intent classification & dispatch           ║
║     - APIGateway: Rate limiting & request handling            ║
║                                                               ║
╠═══════════════════════════════════════════════════════════════╣
║  Running on port 5050                                          ║
║  Debug: False | CORS: Enabled for v2 endpoints               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)


# ==================== APP INITIALIZATION ====================

_app_initialized = False  # Guard against double initialization


def create_app():
    """Factory function to create and configure Flask app.

    Safe to call multiple times — blueprints and services are only
    registered once thanks to the _app_initialized guard.
    """
    global _app_initialized

    if _app_initialized:
        logger.debug("App already initialized, returning existing app")
        return app

    logger.info("Starting HR Multi-Agent Platform v2...")

    # Initialize services
    try:
        init_services()
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # Continue anyway - services may initialize lazily

    # Initialize database and seed demo data
    try:
        from src.core.database import init_db, seed_demo_data

        init_db()
        seed_demo_data()
        # Expanded org (67 employees across 7 departments)
        from src.core.seed_org import seed_expanded_org

        seed_expanded_org()
        logger.info("✅ Database initialized and seeded (expanded org)")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    # Register API blueprints
    register_api_v2()
    register_legacy_api()

    # Print startup banner
    print_startup_banner()

    _app_initialized = True
    return app


# ==================== MAIN ENTRY POINT ====================

if __name__ == "__main__":
    # Verify environment
    if not os.getenv("GOOGLE_API_KEY"):
        logger.warning("⚠️  WARNING: GOOGLE_API_KEY not found in environment!")
        logger.warning("Create a .env file with: GOOGLE_API_KEY=your-key-here")

    # Initialize app (registers blueprints, seeds DB, etc.)
    create_app()

    # Print URL map
    logger.info("\n=== URL MAP ===")
    for rule in app.url_map.iter_rules():
        logger.info(f"{rule.rule:40} {rule.methods}")
    logger.info("===============\n")

    # Start Flask server
    app.run(
        host="0.0.0.0",
        port=5050,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
