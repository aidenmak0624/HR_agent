"""
API-001: API Gateway v2
Flask-based API Gateway for HR multi-agent platform with rate limiting,
request validation, authentication, and comprehensive error handling.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from collections import defaultdict

from flask import Blueprint, request, jsonify, g, current_app
from functools import wraps

logger = logging.getLogger(__name__)


class APIVersion(str, Enum):
    """API version enumeration."""

    V1 = "v1"
    V2 = "v2"


@dataclass
class RateLimiterBucket:
    """Token bucket for rate limiting."""

    capacity: int = 60
    tokens: float = field(default_factory=lambda: 60)
    last_refill: datetime = field(default_factory=datetime.utcnow)

    def refill(self) -> None:
        now = datetime.utcnow()
        elapsed = (now - self.last_refill).total_seconds()
        self.tokens = min(self.capacity, self.tokens + elapsed)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        self.refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate_limit_per_minute: int = 60):
        self.rate_limit_per_minute = rate_limit_per_minute
        self.buckets: Dict[str, RateLimiterBucket] = defaultdict(
            lambda: RateLimiterBucket(capacity=rate_limit_per_minute)
        )

    def is_allowed(self, identifier: str) -> bool:
        bucket = self.buckets[identifier]
        return bucket.consume(1)

    def get_remaining(self, identifier: str) -> int:
        bucket = self.buckets[identifier]
        bucket.refill()
        return int(bucket.tokens)


@dataclass
class APIRequest:
    """Parsed API request."""

    method: str
    endpoint: str
    user_id: Optional[str]
    user_role: Optional[str]
    body: Dict[str, Any]
    query_params: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class APIResponse:
    """Standard API response."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class APIGateway:
    """API Gateway for HR platform."""

    def __init__(self, rate_limit_per_minute: int = 60):
        self.blueprint = Blueprint("api_v2", __name__, url_prefix="/api/v2")
        self.rate_limiter = RateLimiter(rate_limit_per_minute)
        self.request_log: List[Dict[str, Any]] = []
        self.api_keys: Dict[str, Dict[str, Any]] = {}
        self._register_routes()

    def _register_routes(self) -> None:
        """Register API routes."""
        self.blueprint.route("/health", methods=["GET"])(self._health_check)
        self.blueprint.route("/query", methods=["POST"])(self._rate_limit_middleware(self._query))
        # Auth endpoints (no rate limit)
        self.blueprint.route("/auth/token", methods=["POST"])(self._auth_token)
        self.blueprint.route("/auth/refresh", methods=["POST"])(self._auth_refresh)
        self.blueprint.route("/auth/login", methods=["POST"])(self._auth_login)
        self.blueprint.route("/auth/register", methods=["POST"])(self._auth_register)
        # Leave endpoints
        self.blueprint.route("/metrics", methods=["GET"])(
            self._rate_limit_middleware(self._get_metrics)
        )
        self.blueprint.route("/leave/balance", methods=["GET"])(
            self._rate_limit_middleware(self._get_leave_balance)
        )
        self.blueprint.route("/leave/request", methods=["POST"])(
            self._rate_limit_middleware(self._submit_leave_request)
        )
        self.blueprint.route("/documents/templates", methods=["GET"])(
            self._rate_limit_middleware(self._list_templates)
        )
        self.blueprint.route("/documents/generate", methods=["POST"])(
            self._rate_limit_middleware(self._generate_document)
        )
        # Wave 2
        self.blueprint.route("/agents", methods=["GET"])(
            self._rate_limit_middleware(self._list_agents)
        )
        self.blueprint.route("/rag/stats", methods=["GET"])(
            self._rate_limit_middleware(self._rag_stats)
        )
        self.blueprint.route("/rag/ingest", methods=["POST"])(
            self._rate_limit_middleware(self._rag_ingest)
        )
        # Wave 3
        self.blueprint.route("/leave/history", methods=["GET"])(
            self._rate_limit_middleware(self._get_leave_history)
        )
        self.blueprint.route("/workflows/pending", methods=["GET"])(
            self._rate_limit_middleware(self._get_pending_approvals)
        )
        self.blueprint.route("/workflows/approve", methods=["POST"])(
            self._rate_limit_middleware(self._approve_request)
        )
        self.blueprint.route("/workflows/reject", methods=["POST"])(
            self._rate_limit_middleware(self._reject_request)
        )
        self.blueprint.route("/metrics/export", methods=["GET"])(
            self._rate_limit_middleware(self._export_metrics)
        )
        # Wave 4 – Profile & Employee Management
        self.blueprint.route("/profile", methods=["GET"])(
            self._rate_limit_middleware(self._get_profile)
        )
        self.blueprint.route("/profile", methods=["PUT"])(
            self._rate_limit_middleware(self._update_profile)
        )
        self.blueprint.route("/employees", methods=["GET"])(
            self._rate_limit_middleware(self._list_employees)
        )
        self.blueprint.route("/employees/<int:employee_id>", methods=["PUT"])(
            self._rate_limit_middleware(self._update_employee)
        )
        # Wave 5 – Benefits, Onboarding, Performance, Events
        self.blueprint.route("/notifications/stream", methods=["GET"])(
            self._sse_notification_stream
        )
        self.blueprint.route("/notifications", methods=["GET"])(
            self._rate_limit_middleware(self._get_notifications)
        )
        self.blueprint.route("/events", methods=["GET"])(
            self._rate_limit_middleware(self._get_events)
        )
        self.blueprint.route("/benefits/plans", methods=["GET"])(
            self._rate_limit_middleware(self._get_benefits_plans)
        )
        self.blueprint.route("/benefits/enrollments", methods=["GET"])(
            self._rate_limit_middleware(self._get_benefits_enrollments)
        )
        self.blueprint.route("/onboarding/checklist", methods=["GET"])(
            self._rate_limit_middleware(self._get_onboarding_checklist)
        )
        self.blueprint.route("/performance/reviews", methods=["GET"])(
            self._rate_limit_middleware(self._get_performance_reviews)
        )
        self.blueprint.route("/performance/goals", methods=["GET"])(
            self._rate_limit_middleware(self._get_performance_goals)
        )
        # Wave 6 - Chat History & Documents
        self.blueprint.route("/chat/history", methods=["GET"])(
            self._rate_limit_middleware(self._get_chat_history)
        )
        self.blueprint.route("/chat/history", methods=["POST"])(
            self._rate_limit_middleware(self._save_chat_history)
        )
        self.blueprint.route("/documents/upload", methods=["POST"])(
            self._rate_limit_middleware(self._upload_document)
        )

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------

    def _rate_limit_middleware(self, f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip rate limiting for localhost (development/testing)
            client_ip = request.remote_addr or ""
            if client_ip in ("127.0.0.1", "::1", "localhost"):
                return f(*args, **kwargs)
            user_id = g.get("current_user", {}).get("user_id", "anonymous")
            if not self.rate_limiter.is_allowed(user_id):
                response = APIResponse(
                    success=False, error="Rate limit exceeded", metadata={"retry_after": 60}
                )
                return jsonify(response.to_dict()), 429
            remaining = self.rate_limiter.get_remaining(user_id)
            result = f(*args, **kwargs)
            if isinstance(result, tuple):
                response_data, status_code = result
                if hasattr(response_data, "headers"):
                    response_data.headers["X-RateLimit-Remaining"] = str(remaining)
            return result

        return decorated_function

    # ------------------------------------------------------------------
    # DB Helper
    # ------------------------------------------------------------------

    def _get_db_session(self):
        """Get a database session, or None if DB not initialized."""
        try:
            from src.core.database import SessionLocal

            if SessionLocal is None:
                return None
            return SessionLocal()
        except Exception:
            return None

    def _get_current_employee(self, session):
        """Look up the current Employee from the database based on user context.

        Returns (Employee, role_str) or (None, role_str) if not found.
        Uses the employee_id resolved from the Bearer token in before_request.
        Falls back to role-based demo accounts for backward compatibility.
        """
        from src.core.database import Employee

        user_context = g.get("user_context") or {}
        role = user_context.get("role", "employee")

        # Primary: look up by employee_id from token
        emp_id = user_context.get("employee_id")
        if emp_id:
            employee = session.query(Employee).filter_by(id=emp_id).first()
            if employee:
                return employee, role

        # Secondary: look up by email from context
        email = user_context.get("email")
        if email:
            employee = session.query(Employee).filter_by(email=email).first()
            if employee:
                return employee, role

        # Fallback: map roles to demo accounts (backward compat)
        role_email_map = {
            "employee": "john.smith@company.com",
            "manager": "sarah.chen@company.com",
            "hr_admin": "emily.rodriguez@company.com",
        }
        email = role_email_map.get(role, "john.smith@company.com")
        employee = session.query(Employee).filter_by(email=email).first()
        return employee, role

    # ------------------------------------------------------------------
    # Auth Endpoints
    # ------------------------------------------------------------------

    def _auth_login(self):
        """Authenticate user with email/password and return JWT."""
        try:
            import bcrypt
            from src.core.database import Employee

            data = request.get_json() or {}
            email = data.get("email", "").strip().lower()
            password = data.get("password", "")

            if not email or not password:
                return (
                    jsonify(
                        APIResponse(
                            success=False, error="Email and password are required"
                        ).to_dict()
                    ),
                    400,
                )

            session = self._get_db_session()
            if session is None:
                return (
                    jsonify(APIResponse(success=False, error="Database not available").to_dict()),
                    503,
                )

            try:
                employee = session.query(Employee).filter_by(email=email).first()
                if not employee or not employee.password_hash:
                    return (
                        jsonify(
                            APIResponse(success=False, error="Invalid email or password").to_dict()
                        ),
                        401,
                    )

                if not bcrypt.checkpw(
                    password.encode("utf-8"), employee.password_hash.encode("utf-8")
                ):
                    return (
                        jsonify(
                            APIResponse(success=False, error="Invalid email or password").to_dict()
                        ),
                        401,
                    )

                # Map role_level to badge
                badge_map = {
                    "employee": "EMP",
                    "manager": "MGR",
                    "hr_admin": "HR",
                    "hr_generalist": "HRG",
                }

                # Generate real JWT tokens
                from src.middleware.auth import AuthService

                auth_svc = AuthService()
                tokens = auth_svc.generate_token(
                    user_id=str(employee.id),
                    email=employee.email,
                    role=employee.role_level,
                    department=employee.department,
                )

                user_data = {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "expires_in": AuthService.ACCESS_TOKEN_TTL,
                    "token_type": "Bearer",
                    "user": {
                        "id": employee.id,
                        "name": f"{employee.first_name} {employee.last_name}",
                        "email": employee.email,
                        "role": employee.role_level,
                        "title": employee.role_level.replace("_", " ").title(),
                        "badge": badge_map.get(employee.role_level, "EMP"),
                        "department": employee.department,
                    },
                }

                return jsonify(APIResponse(success=True, data=user_data).to_dict()), 200
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Login error: {e}")
            return jsonify(APIResponse(success=False, error="Login failed").to_dict()), 500

    def _auth_register(self):
        """Register a new employee account."""
        try:
            import bcrypt
            from src.core.database import Employee, LeaveBalance

            data = request.get_json() or {}
            first_name = data.get("first_name", "").strip()
            last_name = data.get("last_name", "").strip()
            email = data.get("email", "").strip().lower()
            password = data.get("password", "")
            department = data.get("department", "Engineering")

            if not first_name or not last_name or not email or not password:
                return (
                    jsonify(APIResponse(success=False, error="All fields are required").to_dict()),
                    400,
                )

            if len(password) < 6:
                return (
                    jsonify(
                        APIResponse(
                            success=False, error="Password must be at least 6 characters"
                        ).to_dict()
                    ),
                    400,
                )

            session = self._get_db_session()
            if session is None:
                return (
                    jsonify(APIResponse(success=False, error="Database not available").to_dict()),
                    503,
                )

            try:
                # Check if email already exists
                existing = session.query(Employee).filter_by(email=email).first()
                if existing:
                    return (
                        jsonify(
                            APIResponse(
                                success=False, error="An account with this email already exists"
                            ).to_dict()
                        ),
                        409,
                    )

                password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
                    "utf-8"
                )

                new_employee = Employee(
                    hris_id=f"EMP-{int(time.time())}",
                    hris_source="self_registration",
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    department=department,
                    role_level="employee",
                    hire_date=datetime.utcnow(),
                    status="active",
                    password_hash=password_hash,
                )
                session.add(new_employee)
                session.flush()

                # Create default leave balance
                balance = LeaveBalance(
                    employee_id=new_employee.id,
                    vacation_total=15,
                    vacation_used=0,
                    sick_total=10,
                    sick_used=0,
                    personal_total=5,
                    personal_used=0,
                )
                session.add(balance)
                session.commit()

                badge_map = {"employee": "EMP", "manager": "MGR", "hr_admin": "HR"}
                from src.middleware.auth import AuthService

                auth_svc = AuthService()
                tokens = auth_svc.generate_token(
                    user_id=str(new_employee.id),
                    email=new_employee.email,
                    role=new_employee.role_level,
                    department=new_employee.department,
                )

                user_data = {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "expires_in": AuthService.ACCESS_TOKEN_TTL,
                    "token_type": "Bearer",
                    "user": {
                        "id": new_employee.id,
                        "name": f"{new_employee.first_name} {new_employee.last_name}",
                        "email": new_employee.email,
                        "role": new_employee.role_level,
                        "title": "Employee",
                        "badge": "EMP",
                        "department": new_employee.department,
                    },
                }

                return jsonify(APIResponse(success=True, data=user_data).to_dict()), 201
            except Exception as inner_e:
                session.rollback()
                raise inner_e
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Registration error: {e}")
            return jsonify(APIResponse(success=False, error="Registration failed").to_dict()), 500

    def _auth_token(self):
        """Generate authentication token via user_id + password."""
        try:
            import bcrypt
            from src.core.database import Employee
            from src.middleware.auth import AuthService

            data = request.get_json() or {}
            user_id = data.get("user_id")
            password = data.get("password")
            if not user_id or not password:
                return (
                    jsonify(
                        APIResponse(success=False, error="user_id and password required").to_dict()
                    ),
                    400,
                )

            session = self._get_db_session()
            if session is None:
                return (
                    jsonify(APIResponse(success=False, error="Database not available").to_dict()),
                    503,
                )

            try:
                employee = session.query(Employee).filter_by(id=int(user_id)).first()
                if not employee or not employee.password_hash:
                    return (
                        jsonify(APIResponse(success=False, error="Invalid credentials").to_dict()),
                        401,
                    )

                if not bcrypt.checkpw(
                    password.encode("utf-8"), employee.password_hash.encode("utf-8")
                ):
                    return (
                        jsonify(APIResponse(success=False, error="Invalid credentials").to_dict()),
                        401,
                    )

                auth_svc = AuthService()
                tokens = auth_svc.generate_token(
                    user_id=str(employee.id),
                    email=employee.email,
                    role=employee.role_level,
                    department=employee.department,
                )
                token_data = {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "expires_in": AuthService.ACCESS_TOKEN_TTL,
                    "token_type": "Bearer",
                }
                return jsonify(APIResponse(success=True, data=token_data).to_dict()), 200
            finally:
                session.close()
        except Exception as e:
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _auth_refresh(self):
        """Refresh authentication token using a valid refresh JWT."""
        try:
            from src.middleware.auth import AuthService, AuthError

            data = request.get_json() or {}
            refresh_token = data.get("refresh_token")
            if not refresh_token:
                return (
                    jsonify(APIResponse(success=False, error="refresh_token required").to_dict()),
                    400,
                )

            auth_svc = AuthService()
            try:
                token_data = auth_svc.refresh_token(refresh_token)
                token_data["expires_in"] = AuthService.ACCESS_TOKEN_TTL
                return jsonify(APIResponse(success=True, data=token_data).to_dict()), 200
            except AuthError as ae:
                return jsonify(APIResponse(success=False, error=str(ae)).to_dict()), 401
        except Exception as e:
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    # ------------------------------------------------------------------
    # Health & Query
    # ------------------------------------------------------------------

    def _health_check(self):
        response = APIResponse(success=True, data={"status": "healthy", "version": "2.0"})
        return jsonify(response.to_dict()), 200

    def _query(self):
        """Main agent query endpoint.

        Strategy:
        1. Try static keyword fallback FIRST — it handles greetings,
           capabilities, identity, thanks, goodbye AND detailed HR domain
           answers with correct agent_type and high confidence.
        2. Only delegate to the live agent service when the static fallback
           has no match (returns None).  This keeps the chatbot responsive
           even when the LLM/RAG layer is in degraded mode.
        """
        try:
            data = request.get_json() or {}
            query = data.get("query", "")
            if not query:
                return jsonify(APIResponse(success=False, error="Query is required").to_dict()), 400

            user_context = g.get("user_context") or {
                "user_id": "unknown",
                "role": "employee",
                "department": "unknown",
            }
            # Merge frontend-supplied user info into context
            if data.get("user_name"):
                user_context["name"] = data["user_name"]
            if data.get("user_role"):
                user_context["role"] = data["user_role"]
            conversation_history = data.get("conversation_history", [])

            # --- 1. Static keyword matching (always tried first) ---
            result = self._static_query_fallback(query, user_context)

            # --- 2. Agent service (only if static fallback didn't match) ---
            if result is None:
                agent_service = current_app.agent_service
                if agent_service is not None:
                    try:
                        result = agent_service.process_query(
                            query=query,
                            user_context=user_context,
                            conversation_history=conversation_history,
                        )
                    except Exception as svc_err:
                        logger.warning(f"Agent service error, using generic fallback: {svc_err}")
                        result = None

            # --- 3. Ultimate fallback (nothing matched) ---
            if result is None:
                result = {
                    "answer": "I appreciate your question. I'm the HR Intelligence Assistant and I can help "
                    "with leave management, benefits, company policies, payroll, onboarding, and document "
                    "generation. Could you please rephrase your question or ask about one of these topics?",
                    "agent_type": "general_assistant",
                    "confidence": 0.50,
                    "request_id": f"fallback_{int(time.time())}",
                    "execution_time_ms": 1,
                    "reasoning_trace": [
                        "No keyword match",
                        "No agent service match",
                        "Generic fallback",
                    ],
                }

            response = APIResponse(
                success=True,
                data=result,
                metadata={
                    "execution_time_ms": result.get("execution_time_ms", 0),
                    "request_id": result.get("request_id", "unknown"),
                },
            )
            self._log_request("POST", "/api/v2/query", True)
            return jsonify(response.to_dict()), 200

        except Exception as e:
            logger.error(f"Query endpoint error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _static_query_fallback(self, query, user_context=None):
        """Provide intelligent static responses when agent service is unavailable."""
        query_lower = query.lower().strip()

        # ------ Conversational / greeting responses (Phase D) ------
        greeting_keywords = [
            "hello",
            "hi",
            "hey",
            "greetings",
            "good morning",
            "good afternoon",
            "good evening",
            "what's up",
            "whats up",
            "howdy",
            "sup",
        ]
        if any(
            kw == query_lower
            or query_lower.startswith(kw + " ")
            or query_lower.startswith(kw + ",")
            or query_lower.startswith(kw + "!")
            for kw in greeting_keywords
        ):
            # Personalize greeting with user's name and role
            user_name = (user_context or {}).get("name", "")
            user_role = (user_context or {}).get("role", "employee")
            role_labels = {"employee": "Employee", "manager": "Manager", "hr_admin": "HR Admin"}
            first_name = user_name.split()[0] if user_name else ""
            greeting = f"Hello, {first_name}!" if first_name else "Hello!"
            role_note = (
                f" I see you're signed in as **{role_labels.get(user_role, 'Employee')}**."
                if user_role
                else ""
            )
            return {
                "answer": f"{greeting}{role_note} I'm your HR Intelligence Assistant. I can help you with:\n\n"
                "• Leave requests and balances\n"
                "• Employee benefits information\n"
                "• Company policies and guidelines\n"
                "• Payroll and compensation questions\n"
                "• Document generation\n"
                "• Onboarding information\n\n"
                "What would you like to know?",
                "agent_type": "general_assistant",
                "confidence": 0.95,
                "request_id": f"static_{int(time.time())}",
                "execution_time_ms": 3,
                "reasoning_trace": [
                    "Greeting detected",
                    f"User: {user_name or 'unknown'}, Role: {user_role}",
                    "Showing personalized assistant capabilities",
                ],
            }

        capability_keywords = [
            "what do you do",
            "what can you do",
            "capabilities",
            "help me",
            "how can you help",
            "what can you help",
            "what are you capable",
        ]
        if any(kw in query_lower for kw in capability_keywords):
            return {
                "answer": "I'm an AI-powered HR assistant with multiple specialized agents. Here's what I can help with:\n\n"
                "🏖️ **Leave Management** — Check your leave balance, submit leave requests, and understand leave policies.\n"
                "   Try: 'How many vacation days do I have?' or 'I want to take sick leave'\n\n"
                "💰 **Benefits** — Health insurance, 401(k), dental/vision plans, wellness programs.\n"
                "   Try: 'What health plans are available?' or 'Tell me about the 401k'\n\n"
                "📋 **Company Policies** — Remote work, dress code, working hours, overtime.\n"
                "   Try: 'What is the remote work policy?' or 'What are the office hours?'\n\n"
                "💵 **Payroll** — Pay schedules, direct deposit, tax forms, deductions.\n"
                "   Try: 'When is the next pay day?' or 'How do I update direct deposit?'\n\n"
                "📄 **Documents** — Generate employment certificates, offer letters, and more.\n"
                "   Try: 'I need an employment certificate'\n\n"
                "🎓 **Onboarding** — New hire guides, orientation schedules, setup checklists.\n"
                "   Try: 'I'm a new employee, what should I do?'\n\n"
                "Just ask me anything HR-related!",
                "agent_type": "general_assistant",
                "confidence": 0.95,
                "request_id": f"static_{int(time.time())}",
                "execution_time_ms": 3,
                "reasoning_trace": [
                    "Capability/help query detected",
                    "Showing detailed agent capabilities with examples",
                ],
            }

        identity_keywords = [
            "who are you",
            "what are you",
            "about yourself",
            "introduce yourself",
            "who is this",
            "your name",
            "what is your name",
        ]
        if any(kw in query_lower for kw in identity_keywords):
            return {
                "answer": "I'm the HR Intelligence Assistant, powered by multiple specialized AI agents. "
                "I was designed to help employees, managers, and HR administrators with a wide range of "
                "human resources tasks — from answering policy questions to processing leave requests "
                "and generating documents.\n\n"
                "I have specialized knowledge in leave management, benefits, company policies, "
                "payroll, onboarding, and document generation. My goal is to make HR processes "
                "faster and more accessible for everyone in the organization.",
                "agent_type": "general_assistant",
                "confidence": 0.90,
                "request_id": f"static_{int(time.time())}",
                "execution_time_ms": 3,
                "reasoning_trace": ["Identity query detected", "Providing assistant description"],
            }

        thanks_keywords = ["thank", "thanks", "thank you", "thx", "appreciate"]
        if any(kw in query_lower for kw in thanks_keywords):
            return {
                "answer": "You're welcome! Is there anything else I can help you with? "
                "I'm here to assist with leave requests, benefits questions, company policies, "
                "payroll inquiries, and more.",
                "agent_type": "general_assistant",
                "confidence": 0.95,
                "request_id": f"static_{int(time.time())}",
                "execution_time_ms": 2,
                "reasoning_trace": [
                    "Gratitude expression detected",
                    "Offering continued assistance",
                ],
            }

        goodbye_keywords = ["bye", "goodbye", "see you", "good night", "take care"]
        if any(kw in query_lower for kw in goodbye_keywords):
            return {
                "answer": "Goodbye! Feel free to come back anytime you need HR assistance. Have a great day!",
                "agent_type": "general_assistant",
                "confidence": 0.95,
                "request_id": f"static_{int(time.time())}",
                "execution_time_ms": 2,
                "reasoning_trace": ["Farewell detected", "Closing conversation"],
            }

        # ------ HR domain-specific responses (real company data) ------
        static_responses = {
            # --- LEAVE & PTO ---
            "leave": {
                "answer": "TechNova PTO Policy:\n\n"
                "• Vacation: 15 days/year (0-2 yrs), 20 days (2-5 yrs), 25 days (5+ yrs or manager level)\n"
                "• Sick Leave: 10 days/year (available from Day 1; medical cert required for 3+ consecutive days)\n"
                "• Personal Days: 3 days (employee), 5 days (manager+)\n"
                "• Carryover: Up to 5 unused vacation days roll into the next year\n"
                "• Tenure Bonus: +1 vacation day per 2 years of service (max +5)\n\n"
                "Submit requests via the HR portal. Requests for 3+ days need 2 weeks notice.\n"
                "Contact: leave@technova.com | ext. 2110",
                "agent_type": "leave_agent",
                "confidence": 0.90,
            },
            "benefit": {
                "answer": "TechNova Benefits Summary (2026):\n\n"
                "Health Insurance (3 plans):\n"
                "• PPO: $180/mo employee ($520 family), $500 deductible, BCBS network\n"
                "• HMO: $120/mo employee ($380 family), $250 deductible, Kaiser network\n"
                "• HDHP+HSA: $75/mo employee ($240 family), $1,600 deductible, TechNova contributes $750/$1,500 to HSA\n\n"
                "Retirement: 401(k) via Fidelity — dollar-for-dollar match on first 4%, plus 50¢ on next 2% (max 5% match). Auto-enrolled at 6%.\n\n"
                "Other: Dental (100% preventive), Vision ($10 copay), Life Insurance (2x salary), STD/LTD (60% salary), "
                "EAP (8 free sessions), $7,500 tuition reimbursement, $75/mo gym subsidy, $500 wellness stipend.\n\n"
                "Open enrollment: November 1-15. Contact: benefits@technova.com | ext. 2105",
                "agent_type": "benefits_agent",
                "confidence": 0.90,
            },
            "insurance": {
                "answer": "TechNova Health Insurance Plans (2026):\n\n"
                "PPO (Blue Cross Blue Shield):\n"
                "• Premium: $180/mo employee, $520/mo family (TechNova pays 82%/76%)\n"
                "• Deductible: $500 individual / $1,000 family\n"
                "• Copays: $25 PCP, $50 specialist, $75 urgent care, $250 ER\n"
                "• Out-of-pocket max: $4,000 individual / $8,000 family\n\n"
                "HMO (Kaiser Permanente):\n"
                "• Premium: $120/mo employee, $380/mo family (TechNova pays 85%/80%)\n"
                "• Deductible: $250/$500. Copays: $20 PCP, $40 specialist (referral required)\n\n"
                "HDHP with HSA:\n"
                "• Premium: $75/mo employee, $240/mo family (TechNova pays 90%/85%)\n"
                "• Deductible: $1,600/$3,200. TechNova HSA contribution: $750/$1,500/year\n"
                "• HSA limit (2026): $4,300 individual / $8,550 family\n\n"
                "All plans: Preventive care 100% covered. Rx: $10 generic / $35 brand / $60 non-preferred.\n"
                "Dental: Delta Dental PPO ($25/mo, TechNova pays 100%). Vision: VSP ($10/mo, TechNova pays 100%).",
                "agent_type": "benefits_agent",
                "confidence": 0.92,
            },
            "401k": {
                "answer": "TechNova 401(k) Retirement Plan:\n\n"
                "• Provider: Fidelity Investments\n"
                "• Match: Dollar-for-dollar on first 4% + 50¢ on next 2% = up to 5% employer match\n"
                "• Auto-enrollment: 6% contribution rate (to maximize the match)\n"
                "• 2026 limit: $24,500/year ($32,000 if age 50+)\n"
                "• Vesting: Your contributions 100% vested immediately; employer match 3-year graded (33%/67%/100%)\n"
                "• Roth 401(k) option available\n"
                "• Investments: Target date funds, S&P 500 index (0.015% expense ratio), total market, international, bond, small cap\n"
                "• Loans: Up to 50% of vested balance (max $50,000), repay over 1-5 years at Prime+1%\n\n"
                "ESPP: 15% discount, up to 15% of salary, semi-annual purchase periods.\n"
                "Contact: benefits@technova.com | Fidelity: 1-800-343-3548",
                "agent_type": "benefits_agent",
                "confidence": 0.92,
            },
            "retirement": {
                "answer": "TechNova 401(k) Retirement Plan:\n\n"
                "• Provider: Fidelity Investments\n"
                "• Match: Dollar-for-dollar on first 4% + 50¢ on next 2% = up to 5% employer match\n"
                "• Auto-enrollment: 6% contribution rate (to maximize the match)\n"
                "• 2026 limit: $24,500/year ($32,000 if age 50+)\n"
                "• Vesting: Your contributions always yours; employer match 3-year graded\n"
                "• Roth 401(k) option available\n\n"
                "ESPP: 15% discount, up to 15% of salary.\n"
                "RSUs: 4-year vesting with 1-year cliff (25% at year 1, then quarterly).\n"
                "Contact: benefits@technova.com | equity@technova.com",
                "agent_type": "benefits_agent",
                "confidence": 0.90,
            },
            # --- EMPLOYMENT LAW ---
            "fmla": {
                "answer": "FMLA (Family and Medical Leave Act) at TechNova:\n\n"
                "Eligibility: 12+ months employed AND 1,250+ hours worked in the past 12 months.\n\n"
                "Entitlement: Up to 12 weeks (480 hours) of unpaid, job-protected leave per rolling 12-month period for:\n"
                "• Birth/adoption/foster placement of a child\n"
                "• Care of spouse, child, or parent with serious health condition\n"
                "• Your own serious health condition\n"
                "• Military family qualifying exigency\n\n"
                "Key details:\n"
                "• Health insurance continues during FMLA leave\n"
                "• You may substitute accrued paid leave (vacation/sick) concurrently\n"
                "• 30 days advance notice for foreseeable leave\n"
                "• Medical certification required within 15 calendar days\n"
                "• Job restoration to same or equivalent position upon return\n\n"
                "To request: Contact HR at hr@technova.com or ext. 2100",
                "agent_type": "policy_agent",
                "confidence": 0.93,
            },
            "family medical leave": {
                "answer": "FMLA (Family and Medical Leave Act) at TechNova:\n\n"
                "Eligibility: 12+ months employed AND 1,250+ hours worked in the past 12 months.\n\n"
                "Entitlement: 12 weeks unpaid, job-protected leave for serious health conditions, "
                "birth/adoption, or care of family members.\n\n"
                "Your health insurance continues during leave. You can use accrued PTO concurrently.\n"
                "Contact HR at hr@technova.com | ext. 2100 to start the process.",
                "agent_type": "policy_agent",
                "confidence": 0.93,
            },
            "ada": {
                "answer": "ADA Reasonable Accommodations at TechNova:\n\n"
                "TechNova complies with the Americans with Disabilities Act for all qualified individuals.\n\n"
                "Interactive Process:\n"
                "1. Request an accommodation (verbal or written — you don't need to say 'ADA')\n"
                "2. HR schedules an interactive meeting within 5 business days\n"
                "3. Together we identify effective accommodations\n"
                "4. Implementation and 30-day follow-up\n\n"
                "Common accommodations: Modified schedules, ergonomic equipment, assistive technology, "
                "remote work, job restructuring, modified break schedules.\n\n"
                "All medical information is kept confidential in a separate file.\n"
                "Contact: ADA Coordinator at hr@technova.com | ext. 2100",
                "agent_type": "policy_agent",
                "confidence": 0.90,
            },
            "accommodation": {
                "answer": "Requesting a Workplace Accommodation at TechNova:\n\n"
                "You can request an accommodation at any time. Simply explain that you need an adjustment "
                "due to a medical condition — you don't need to use the words 'ADA' or 'reasonable accommodation.'\n\n"
                "Steps:\n"
                "1. Speak with your manager or contact HR directly\n"
                "2. HR initiates the interactive process within 5 business days\n"
                "3. Medical documentation may be requested\n"
                "4. Accommodation selected and implemented\n"
                "5. Follow-up in 30 days to assess effectiveness\n\n"
                "Common accommodations include flexible hours, ergonomic furniture, assistive technology, "
                "modified duties, or remote work arrangements.\n"
                "Contact: hr@technova.com | ext. 2100",
                "agent_type": "policy_agent",
                "confidence": 0.88,
            },
            "disability": {
                "answer": "TechNova Disability Benefits and Accommodations:\n\n"
                "Short-Term Disability (STD): 60% of base salary, 7-day waiting period, up to 26 weeks. Company-paid.\n"
                "Long-Term Disability (LTD): 60% of base salary (up to $15,000/mo), begins after STD. Company-paid.\n\n"
                "ADA Accommodations: TechNova provides reasonable accommodations to qualified individuals with disabilities. "
                "Contact HR to start the interactive process.\n\n"
                "FMLA: Up to 12 weeks unpaid, job-protected leave may also be available for serious health conditions.\n\n"
                "Contact: hr@technova.com | ext. 2100 | EAP: 1-800-555-0199 (24/7)",
                "agent_type": "benefits_agent",
                "confidence": 0.88,
            },
            "discrimination": {
                "answer": "TechNova Anti-Discrimination Policy:\n\n"
                "We prohibit discrimination based on race, color, religion, sex (including pregnancy, sexual orientation, "
                "gender identity), national origin, age (40+), disability, genetic information, and veteran status.\n\n"
                "Reporting options:\n"
                "• Your manager (if not the source)\n"
                "• HR: hr@technova.com | ext. 2100\n"
                "• VP People Ops: emily.rodriguez@technova.com\n"
                "• Anonymous Ethics Hotline: 1-800-555-0188 (24/7)\n\n"
                "Investigations are prompt, thorough, and confidential. Retaliation is strictly prohibited.\n"
                "You may also file externally with the EEOC: www.eeoc.gov | 1-800-669-4000",
                "agent_type": "policy_agent",
                "confidence": 0.92,
            },
            "harassment": {
                "answer": "TechNova Anti-Harassment Policy:\n\n"
                "Harassment based on any protected characteristic is strictly prohibited. This includes:\n"
                "• Offensive jokes, slurs, or epithets\n"
                "• Unwanted sexual advances or requests for favors\n"
                "• Physical threats, intimidation, or assault\n"
                "• Offensive images, emails, or messages\n\n"
                "Report through ANY of these channels:\n"
                "1. Your manager\n"
                "2. HR: hr@technova.com | ext. 2100\n"
                "3. Anonymous Ethics Hotline: 1-800-555-0188 (24/7)\n\n"
                "Investigations completed within 20-30 business days. Retaliation is itself a terminable offense.\n"
                "All employees complete anti-harassment training within 30 days of hire, with annual refreshers.",
                "agent_type": "policy_agent",
                "confidence": 0.92,
            },
            "overtime": {
                "answer": "TechNova Overtime Policy (FLSA Compliance):\n\n"
                "Non-exempt employees earn 1.5x their regular rate for hours over 40/week.\n\n"
                "Key details:\n"
                "• Workweek: Monday through Sunday\n"
                "• Overtime must be pre-approved by your manager\n"
                "• Unauthorized overtime is still paid but may result in counseling\n"
                "• Comp time in lieu of overtime is NOT allowed (per FLSA)\n"
                "• Exempt threshold: $684/week ($35,568/year) federal minimum\n\n"
                "Exempt employees (salaried managers, senior engineers, professionals) are not eligible for overtime.\n"
                "Questions about your classification? Contact payroll@technova.com | ext. 2200",
                "agent_type": "payroll_agent",
                "confidence": 0.88,
            },
            "cobra": {
                "answer": "COBRA Continuation Coverage at TechNova:\n\n"
                "If you lose health coverage due to termination or reduction in hours, you can continue group health insurance:\n\n"
                "• Duration: 18 months (36 months for death/divorce/Medicare)\n"
                "• Cost: 102% of full premium (employer + employee share + 2% admin)\n"
                "• Approximate monthly costs: Employee $750 | +Spouse $1,450 | Family $2,100\n"
                "• Election period: 60 days from qualifying event\n"
                "• First payment due: 45 days after election\n\n"
                "Alternatives to consider: Healthcare.gov marketplace (may have subsidies), "
                "spouse's employer plan, or Medicaid if eligible.\n"
                "Contact: benefits@technova.com | ext. 2105",
                "agent_type": "benefits_agent",
                "confidence": 0.88,
            },
            # --- COMPANY POLICIES ---
            "policy": {
                "answer": "TechNova Company Policies Overview:\n\n"
                "• Remote Work: Hybrid model — Tue/Wed/Thu in-office, Mon/Fri remote. Core hours 10am-4pm.\n"
                "• Dress Code: Business casual (Tue-Thu in office); professional for client meetings.\n"
                "• Working Hours: Flexible 7am-10am start, 4pm-7pm end; 40 hrs/week standard.\n"
                "• Code of Conduct: Annual acknowledgment required. Covers ethics, conflicts of interest, gifts, IP.\n"
                "• Performance Reviews: Bi-annual (March & September) + monthly 1-on-1s.\n"
                "• Anti-Harassment: Zero tolerance. Anonymous hotline: 1-800-555-0188.\n\n"
                "Ask about any specific policy for details! Full handbook on the HR portal.",
                "agent_type": "policy_agent",
                "confidence": 0.85,
            },
            "remote": {
                "answer": "TechNova Remote Work Policy:\n\n"
                "• Hybrid model: 3 days in-office (Tue/Wed/Thu), 2 days remote (Mon/Fri)\n"
                "• Eligibility: After 6 months with satisfactory performance\n"
                "• Core hours: 10:00 AM - 4:00 PM local time (must be available)\n"
                "• Flex window: Start 7-10am, end 4-7pm\n\n"
                "Home office support:\n"
                "• $1,000 one-time setup allowance (desk, chair, monitor)\n"
                "• $50/month ongoing home office stipend\n"
                "• $75/month internet reimbursement\n"
                "• Company laptop, monitor, keyboard, mouse, headset provided\n\n"
                "Requirements: Minimum 25 Mbps internet, dedicated workspace, VPN for all remote work.\n"
                "International remote: Max 4 weeks/year, requires HR/Legal approval 30 days in advance.\n"
                "Contact: hr@technova.com | ext. 2100",
                "agent_type": "policy_agent",
                "confidence": 0.90,
            },
            "performance review": {
                "answer": "TechNova Performance Review Process:\n\n"
                "• Formal reviews: March (mid-year) and September (annual)\n"
                "• Monthly 1-on-1s required between manager and each direct report\n"
                "• 360-degree feedback collected annually in August\n\n"
                "Rating Scale: 1 (Does Not Meet) through 5 (Exceptional)\n\n"
                "Merit Increases (effective January 1):\n"
                "• Rating 1: 0% (placed on PIP)\n"
                "• Rating 2: 0-2%\n"
                "• Rating 3: 3-5%\n"
                "• Rating 4: 5-7%\n"
                "• Rating 5: 7-10% + potential equity refresh\n"
                "• Promotions: 10-15% above current base\n\n"
                "Set 3-5 OKRs each half-year. Self-assessment due 2 weeks before review.\n"
                "Contact: hr@technova.com | ext. 2100",
                "agent_type": "policy_agent",
                "confidence": 0.88,
            },
            "pip": {
                "answer": "Performance Improvement Plan (PIP) at TechNova:\n\n"
                "A PIP is part of our progressive discipline process — it's a formal, structured plan "
                "to help employees meet performance expectations.\n\n"
                "Progressive Discipline Steps:\n"
                "1. Verbal Counseling (documented, not in personnel file)\n"
                "2. Written Warning (placed in personnel file)\n"
                "3. PIP: 30/60/90-day plan with specific measurable goals and weekly check-ins\n"
                "4. Termination (if PIP goals not met)\n\n"
                "PIP outcomes: Successful (closed, 90-day monitoring), partial improvement (may extend once), "
                "or unsuccessful (may lead to demotion, reassignment, or termination).\n\n"
                "Gross misconduct (theft, violence, harassment) may bypass progressive steps.\n"
                "Contact: hr@technova.com | ext. 2100",
                "agent_type": "policy_agent",
                "confidence": 0.85,
            },
            "code of conduct": {
                "answer": "TechNova Code of Conduct highlights:\n\n"
                "Core Values: Integrity, Respect, Innovation, Accountability, Collaboration.\n\n"
                "Key policies:\n"
                "• Conflicts of interest: Disclose outside employment, investments in competitors/vendors\n"
                "• Gifts: Accept up to $100; report anything over $100 to manager/HR\n"
                "• Confidentiality: Protect proprietary info; follow data classification (Public/Internal/Confidential/Restricted)\n"
                "• IP: All work product belongs to TechNova per your Invention Assignment Agreement\n"
                "• Social media: Personal views only; don't share confidential info\n"
                "• Drug-free workplace: No impairment during work hours\n\n"
                "Annual acknowledgment required. Report violations: Ethics Hotline 1-800-555-0188 (anonymous, 24/7).",
                "agent_type": "policy_agent",
                "confidence": 0.85,
            },
            # --- PAYROLL ---
            "payroll": {
                "answer": "TechNova Payroll Information:\n\n"
                "• Salaried employees: Semi-monthly (15th and last business day) — 24 pay periods/year\n"
                "• Hourly employees: Bi-weekly (every other Friday) — 26 pay periods/year\n"
                "• Direct deposit: Recommended; split across up to 3 accounts\n"
                "• Pay stubs: Available on ADP Workforce Now within 2 days of pay date\n"
                "• W-2 forms: Distributed by January 31 each year\n\n"
                "Deductions: Federal/state income tax, Social Security (6.2%), Medicare (1.45%), "
                "plus pre-tax deductions for 401(k), health premiums, FSA/HSA.\n\n"
                "Mileage reimbursement: $0.70/mile (2026 IRS rate).\n"
                "Contact: payroll@technova.com | ext. 2200",
                "agent_type": "payroll_agent",
                "confidence": 0.88,
            },
            "salary": {
                "answer": "TechNova Compensation Information:\n\n"
                "• Annual reviews: September (annual cycle)\n"
                "• Merit increases effective January 1:\n"
                "  - Meets expectations: 3-5%\n"
                "  - Exceeds: 5-7%\n"
                "  - Exceptional: 7-10% + equity refresh\n"
                "  - Promotion: 10-15% above current base\n"
                "• Market adjustments reviewed annually\n\n"
                "Exempt salary threshold (federal): $684/week ($35,568/year).\n"
                "TechNova minimum starting wage: $22.00/hour.\n\n"
                "For your specific compensation, check your pay stubs on ADP.\n"
                "Contact: payroll@technova.com | ext. 2200",
                "agent_type": "payroll_agent",
                "confidence": 0.82,
            },
            "tax": {
                "answer": "Tax and Withholding at TechNova:\n\n"
                "• Form W-4: Complete at hire; update anytime your situation changes (marriage, new dependents, etc.)\n"
                "• State taxes: Withheld based on your work state. No state tax in: AK, FL, NV, NH, SD, TN, TX, WA, WY\n"
                "• FICA: Social Security 6.2% (up to $168,600) + Medicare 1.45% (no cap)\n"
                "• Additional Medicare: 0.9% on earnings over $200,000\n"
                "• Pre-tax deductions: 401(k), health premiums, FSA/HSA reduce taxable income\n\n"
                "W-2 forms available by January 31 on ADP portal and mailed to your address.\n"
                "Use the IRS Tax Withholding Estimator at irs.gov to verify your W-4.\n"
                "Contact: payroll@technova.com | ext. 2200",
                "agent_type": "payroll_agent",
                "confidence": 0.85,
            },
            "direct deposit": {
                "answer": "Setting Up Direct Deposit at TechNova:\n\n"
                "1. Log into ADP Workforce Now (payroll portal)\n"
                "2. Go to Pay > Direct Deposit\n"
                "3. Enter bank routing number and account number\n"
                "4. You can split deposits across up to 3 accounts\n"
                "5. Changes take effect in 1-2 pay cycles\n\n"
                "New employees: Complete the Direct Deposit Authorization Form during onboarding.\n"
                "Paper checks available upon request but may take 1-2 extra business days.\n"
                "Contact: payroll@technova.com | ext. 2200",
                "agent_type": "payroll_agent",
                "confidence": 0.85,
            },
            "pay": {
                "answer": "TechNova Pay Schedule:\n\n"
                "• Salaried: Semi-monthly (15th and last business day) — 24 periods/year\n"
                "• Hourly: Bi-weekly (every other Friday) — 26 periods/year\n"
                "• If pay date falls on weekend/holiday, paid on preceding business day\n"
                "• Direct deposit recommended; paper checks available\n"
                "• Pay stubs on ADP Workforce Now within 2 days of pay date\n\n"
                "Contact: payroll@technova.com | ext. 2200",
                "agent_type": "payroll_agent",
                "confidence": 0.82,
            },
            "workers comp": {
                "answer": "Workers' Compensation at TechNova:\n\n"
                "All employees are covered from Day 1 for work-related injuries and illnesses.\n\n"
                "If injured at work:\n"
                "1. Seek medical attention immediately (call 911 for emergencies)\n"
                "2. Report to your manager within 24 hours\n"
                "3. Complete an Incident Report Form on the HR portal\n"
                "4. HR files the claim with our insurance carrier\n"
                "5. Follow your doctor's treatment plan\n"
                "6. Return-to-work clearance required\n\n"
                "Coverage includes: Medical bills, lost wages (typically 66.7% of average weekly wage), "
                "rehabilitation, and death benefits.\n"
                "Remote workers: Work-related injuries during work hours may be covered.\n"
                "Contact: hr@technova.com | ext. 2100",
                "agent_type": "policy_agent",
                "confidence": 0.85,
            },
            # --- LEAVE TYPES ---
            "vacation": {
                "answer": "TechNova Vacation Policy:\n\n"
                "• 0-2 years tenure: 15 days/year (1.25 days/month)\n"
                "• 2-5 years: 20 days/year (1.67 days/month)\n"
                "• 5+ years or manager level: 25 days/year (2.08 days/month)\n"
                "• Tenure bonus: +1 day per 2 years of service (max +5 extra days)\n"
                "• Carryover: Up to 5 unused days into next year\n"
                "• Payout: Accrued unused vacation paid out upon separation\n\n"
                "Request via HR portal. 2 weeks notice for 3+ days. Check Leave page for your balance.",
                "agent_type": "leave_agent",
                "confidence": 0.90,
            },
            "sick leave": {
                "answer": "TechNova Sick Leave Policy:\n\n"
                "• 10 paid sick days per year (available from Day 1)\n"
                "• Use for: Personal illness, medical appointments, care of ill family, mental health days\n"
                "• Medical certificate required for 3+ consecutive sick days\n"
                "• Sick days do NOT carry over or pay out upon separation\n"
                "• Extended illness? Short-term disability kicks in after 7 days (60% of salary, up to 26 weeks)\n\n"
                "Additionally, you may take up to 2 mental health days per quarter (8/year, separate from sick leave).\n"
                "Submit through the Leave page. Contact: leave@technova.com | ext. 2110",
                "agent_type": "leave_agent",
                "confidence": 0.90,
            },
            "sick": {
                "answer": "TechNova Sick Leave Policy:\n\n"
                "• 10 paid sick days per year (available from Day 1)\n"
                "• Use for: Personal illness, medical appointments, care of ill family, mental health days\n"
                "• Medical certificate required for 3+ consecutive sick days\n"
                "• Sick days do NOT carry over or pay out upon separation\n"
                "• Extended illness? Short-term disability kicks in after 7 days (60% of salary, up to 26 weeks)\n\n"
                "Additionally, you may take up to 2 mental health days per quarter (8/year, separate from sick leave).\n"
                "Submit through the Leave page. Contact: leave@technova.com | ext. 2110",
                "agent_type": "leave_agent",
                "confidence": 0.90,
            },
            "pto": {
                "answer": "TechNova Paid Time Off (PTO) Summary:\n\n"
                "Vacation: 15 days (0-2 yrs), 20 days (2-5 yrs), 25 days (5+ yrs/manager). +1 day per 2 yrs tenure.\n"
                "Sick: 10 days/year. Personal: 3 days (employee), 5 days (manager+).\n"
                "Holidays: 10 company holidays + 2 floating + winter office closure (Dec 26-Jan 1).\n"
                "Mental health days: 2 per quarter (separate from sick leave).\n"
                "Carryover: Up to 5 vacation days. Sick/personal do not carry over.\n\n"
                "Check the Leave page for your current balance and to submit requests.",
                "agent_type": "leave_agent",
                "confidence": 0.90,
            },
            "parental": {
                "answer": "TechNova Parental Leave:\n\n"
                "• Birth parent: 16 weeks fully paid (may start up to 4 weeks before due date)\n"
                "• Non-birth parent: 8 weeks fully paid\n"
                "• Adoption/foster: 16 weeks (primary caregiver), 8 weeks (secondary)\n"
                "• Adoption assistance: Up to $10,000 reimbursement for qualified expenses\n"
                "• Gradual return option: 4 additional weeks at reduced schedule with full pay\n\n"
                "Eligibility: 6+ months of employment. Available regardless of gender or marital status.\n"
                "Must be taken within 12 months of birth/placement.\n"
                "Additional unpaid FMLA leave (12 weeks) may also be available.\n"
                "Contact: leave@technova.com | hr@technova.com",
                "agent_type": "policy_agent",
                "confidence": 0.90,
            },
            "bereavement": {
                "answer": "TechNova Bereavement Leave:\n\n"
                "• Immediate family (spouse, child, parent, sibling): 5 paid days\n"
                "• Extended family (grandparent, in-law, aunt, uncle): 3 paid days\n"
                "• Close friend or colleague: 1 paid day\n"
                "• Additional unpaid leave available upon request\n\n"
                "Notify your manager as soon as possible. No formal documentation required.\n"
                "Contact: leave@technova.com | hr@technova.com | EAP: 1-800-555-0199 (24/7)",
                "agent_type": "leave_agent",
                "confidence": 0.85,
            },
            # --- BENEFITS DETAILS ---
            "dental": {
                "answer": "TechNova Dental Coverage (Delta Dental PPO):\n\n"
                "• Premium: $25/month employee-only (TechNova pays 100%); $65/month family (TechNova pays 75%)\n"
                "• Preventive (cleanings, exams, X-rays): 100% covered, 2 visits/year\n"
                "• Basic procedures (fillings, extractions): 80% after $50 deductible\n"
                "• Major procedures (crowns, bridges, root canals): 50% after $50 deductible\n"
                "• Orthodontia (children under 19): 50% covered, $2,000 lifetime max\n"
                "• Annual maximum benefit: $2,000 per person\n\n"
                "Contact: benefits@technova.com | ext. 2105",
                "agent_type": "benefits_agent",
                "confidence": 0.88,
            },
            "vision": {
                "answer": "TechNova Vision Coverage (VSP Vision Care):\n\n"
                "• Premium: $10/month employee-only (TechNova pays 100%); $25/month family (TechNova pays 80%)\n"
                "• Eye exam: $10 copay, 1 per year\n"
                "• Eyeglass frames: $175 allowance every 24 months\n"
                "• Lenses: Covered in full (single vision, bifocal, or progressive)\n"
                "• Contact lenses: $175/year allowance (in lieu of glasses)\n"
                "• LASIK: 15% discount through VSP network providers\n\n"
                "Contact: benefits@technova.com | ext. 2105",
                "agent_type": "benefits_agent",
                "confidence": 0.88,
            },
            "hsa": {
                "answer": "Health Savings Account (HSA) at TechNova:\n\n"
                "Available to employees enrolled in the HDHP (High Deductible Health Plan).\n\n"
                "• TechNova contribution: $750/year (individual) or $1,500/year (family)\n"
                "• 2026 employee contribution limits: $4,300 individual / $8,550 family\n"
                "• Catch-up (age 55+): Additional $1,150\n"
                "• Funds roll over year to year — no use-it-or-lose-it\n"
                "• HSA is portable — it's yours even if you leave TechNova\n"
                "• Triple tax advantage: Contributions pre-tax, growth tax-free, qualified withdrawals tax-free\n\n"
                "Use for: Copays, prescriptions, dental, vision, OTC medications.\n"
                "Note: Cannot have both HSA and Health Care FSA simultaneously.\n"
                "Contact: benefits@technova.com | ext. 2105",
                "agent_type": "benefits_agent",
                "confidence": 0.88,
            },
            "fsa": {
                "answer": "Flexible Spending Accounts (FSA) at TechNova:\n\n"
                "Health Care FSA (for PPO/HMO enrollees):\n"
                "• 2026 limit: $3,400/year\n"
                "• Use for: Copays, prescriptions, dental, vision, OTC meds\n"
                "• Use-it-or-lose-it (grace period through March 15)\n"
                "• Cannot combine with HSA\n\n"
                "Dependent Care FSA:\n"
                "• 2026 limit: $7,500/year (historic increase from $5,000)\n"
                "• Use for: Daycare, preschool, after-school care, elder care, summer day camps\n"
                "• Eligibility: Must have dependent under 13 or disabled dependent\n\n"
                "Both reduce your taxable income. Enroll during open enrollment or within 30 days of hire.\n"
                "Contact: benefits@technova.com | ext. 2105",
                "agent_type": "benefits_agent",
                "confidence": 0.88,
            },
            "eap": {
                "answer": "Employee Assistance Program (EAP) at TechNova:\n\n"
                "Free, confidential support through ComPsych for employees and household members.\n\n"
                "Services:\n"
                "• Mental health counseling: 8 free sessions per issue per year\n"
                "• Financial counseling: Budgeting, debt management, retirement planning\n"
                "• Legal consultation: 30-minute consultation + 25% discount on retained services\n"
                "• Work-life resources: Child/elder care referrals, moving assistance\n"
                "• Crisis support: 24/7 hotline\n"
                "• Substance abuse assessment and referral\n\n"
                "100% confidential — TechNova never receives individual usage data.\n"
                "Phone: 1-800-555-0199 (24/7) | Online: guidanceresources.com (code: TECHNOVA)",
                "agent_type": "benefits_agent",
                "confidence": 0.90,
            },
            "counseling": {
                "answer": "TechNova provides free mental health support through our EAP:\n\n"
                "• 8 free counseling sessions per issue per year\n"
                "• In-person, phone, or video sessions available\n"
                "• 100% confidential — TechNova never knows you used it\n"
                "• Available to employees AND household members\n"
                "• Also covers financial counseling, legal consultations, and crisis support\n\n"
                "Additionally, you have up to 2 mental health days per quarter (8/year) — no documentation needed.\n"
                "EAP: 1-800-555-0199 (24/7) | guidanceresources.com (code: TECHNOVA)",
                "agent_type": "benefits_agent",
                "confidence": 0.88,
            },
            "tuition": {
                "answer": "TechNova Tuition Reimbursement & Professional Development:\n\n"
                "• Tuition reimbursement: Up to $7,500/year for degree programs, certifications, and approved courses\n"
                "• Requirements: Manager approval, minimum grade of B, work-related\n"
                "• Service agreement: 1-year commitment for reimbursements over $3,000\n\n"
                "Certification bonuses:\n"
                "• AWS/GCP/Azure: $1,000 | PMP: $750 | SHRM-CP/SCP: $750 | CPA/CFA: $1,500 | Other: $500\n\n"
                "Learning platforms: LinkedIn Learning (all employees), Coursera for Business, O'Reilly (engineering).\n"
                "Conference budget available per department. Contact: learning@technova.com",
                "agent_type": "benefits_agent",
                "confidence": 0.85,
            },
            "training": {
                "answer": "TechNova Professional Development:\n\n"
                "• $7,500/year tuition reimbursement for approved courses\n"
                "• LinkedIn Learning: Unlimited access for all employees\n"
                "• 1-2 conferences/year with manager approval\n"
                "• Monthly internal Tech Talks and Lunch & Learns\n"
                "• Certification bonuses: $500-$1,500 per approved cert\n"
                "• Quarterly hackathons (Engineering-led, all welcome)\n\n"
                "Required training (within 30 days of hire):\n"
                "1. Anti-Harassment Training (90 min)\n"
                "2. Data Security & Privacy (60 min)\n"
                "3. Code of Conduct Acknowledgment (30 min)\n"
                "4. Workplace Safety (30 min)\n\n"
                "Contact: learning@technova.com",
                "agent_type": "policy_agent",
                "confidence": 0.85,
            },
            "commuter": {
                "answer": "TechNova Commuter Benefits (2026):\n\n"
                "• Pre-tax transit: Up to $340/month for public transit passes and vanpools\n"
                "• Pre-tax parking: Up to $340/month for qualified paid parking\n"
                "• Bike commuter benefit: $50/month reimbursement for bike maintenance/accessories\n"
                "• Tax savings: Approximately 25-35% depending on your tax bracket\n\n"
                "Enroll via the HR portal. Contact: benefits@technova.com | ext. 2105",
                "agent_type": "benefits_agent",
                "confidence": 0.82,
            },
            "wellness": {
                "answer": "TechNova Wellness Program:\n\n"
                "• Gym membership subsidy: $75/month reimbursement\n"
                "• Annual wellness stipend: $500 for health-related purchases (fitness equipment, ergonomic supplies, meditation apps)\n"
                "• Mental health days: 2 per quarter (8/year, no documentation needed)\n"
                "• EAP: 8 free counseling sessions per issue\n"
                "• Wellness incentive: $25/month premium discount for completing annual health assessment\n\n"
                "HQ amenities: Standing desks, healthy snacks, quiet rooms, mother's room.\n"
                "Contact: wellness@technova.com | benefits@technova.com",
                "agent_type": "benefits_agent",
                "confidence": 0.85,
            },
            # --- ONBOARDING ---
            "onboard": {
                "answer": "TechNova New Employee Onboarding:\n\n"
                "Before Day 1: Complete I-9, W-4, direct deposit, benefits enrollment, background check, sign NDA/Code of Conduct.\n\n"
                "Day 1: 9am welcome, HR orientation, I-9 verification, IT setup (laptop, Google Workspace, Slack, VPN), team lunch, meet your onboarding buddy.\n\n"
                "Week 1: Complete required training (anti-harassment, data security, code of conduct, safety). Set 1-on-1 cadence with manager.\n\n"
                "First 30 days: Set OKRs, shadow colleagues, attend company all-hands, enroll in benefits.\n\n"
                "First 90 days: Deliver first project, 90-day check-in, join an ERG.\n\n"
                "Systems: Google Workspace, Slack, BambooHR, ADP, Jira/Asana, GitHub, 1Password.\n"
                "Contact: onboarding@technova.com | IT: it@technova.com | ext. 3000",
                "agent_type": "onboarding_agent",
                "confidence": 0.88,
            },
            "new employee": {
                "answer": "Welcome to TechNova! Here's your getting-started guide:\n\n"
                "1. Complete pre-hire paperwork (I-9, W-4, direct deposit, NDA)\n"
                "2. Day 1: HR orientation, IT setup, team introductions, buddy assignment\n"
                "3. Week 1: Required training, 1-on-1 with manager, explore systems\n"
                "4. Month 1: Set OKRs, enroll in benefits (30-day deadline), shadow colleagues\n"
                "5. Month 3: Deliver first project, 90-day check-in\n\n"
                "Key systems: Slack (#general, #your-department), Google Workspace, BambooHR (HR portal), ADP (payroll).\n"
                "Onboarding buddy will reach out before your first day!\n"
                "Contact: onboarding@technova.com | it@technova.com | ext. 3000",
                "agent_type": "onboarding_agent",
                "confidence": 0.88,
            },
            "first day": {
                "answer": "Your First Day at TechNova:\n\n"
                "8:30 AM — Arrive at office (or log into virtual onboarding)\n"
                "9:00 AM — Welcome from your hiring manager\n"
                "9:30 AM — HR orientation: Company overview, benefits walkthrough, I-9 verification, badge/access card\n"
                "10:30 AM — IT setup: Laptop, email (Google Workspace), Slack, VPN, 1Password\n"
                "12:00 PM — Team lunch (company-sponsored)\n"
                "1:00 PM — Meet your onboarding buddy\n"
                "1:30 PM — Department orientation: Role expectations, 30/60/90 day goals, key stakeholders\n"
                "3:00 PM — Self-paced: Required online training modules\n"
                "4:30 PM — Day 1 check-in with your manager\n\n"
                "Bring: Photo ID and documents for I-9 verification.\n"
                "Contact: onboarding@technova.com",
                "agent_type": "onboarding_agent",
                "confidence": 0.88,
            },
            "orientation": {
                "answer": "TechNova New Employee Orientation:\n\n"
                "Day 1 AM: Company overview, mission, values, HR orientation, benefits enrollment walkthrough, I-9 verification.\n"
                "Day 1 PM: IT setup, department intro, meet your buddy, start required training.\n"
                "Week 1: Complete all compliance training, set 1-on-1 cadence, meet key stakeholders.\n"
                "30-day check-in: Review progress on OKRs with your manager.\n"
                "90-day check-in: Performance review, join ERG, provide onboarding feedback.\n\n"
                "Required training (within 30 days): Anti-harassment (90 min), Data security (60 min), "
                "Code of conduct (30 min), Workplace safety (30 min).\n"
                "Contact: onboarding@technova.com",
                "agent_type": "onboarding_agent",
                "confidence": 0.85,
            },
            # --- OTHER ---
            "document": {
                "answer": "TechNova HR Document Services:\n\n"
                "Available templates:\n"
                "• Employment Certificate / Verification Letter\n"
                "• Offer Letter\n"
                "• Promotion Letter\n"
                "• Experience Letter\n"
                "• Separation Letter\n"
                "• Salary Slip\n\n"
                "Go to the Documents page to generate any of these.\n"
                "For official records requests, contact: hr@technova.com | ext. 2100",
                "agent_type": "hr_agent",
                "confidence": 0.82,
            },
            "certificate": {
                "answer": "To request an employment certificate or verification letter:\n\n"
                "Self-service: Go to Documents page > Employment Certificate > Generate.\n"
                "Official requests: Contact hr@technova.com for signed/sealed letters.\n"
                "Processing time: Self-service instant; official letters 2-3 business days.\n\n"
                "Other available documents: Offer letters, promotion letters, experience letters, salary slips.",
                "agent_type": "hr_agent",
                "confidence": 0.82,
            },
            "letter": {
                "answer": "TechNova HR letter templates:\n\n"
                "• Offer Letter • Employment Certificate • Promotion Letter\n"
                "• Reference Letter • Experience Letter • Separation Letter\n\n"
                "Generate via the Documents page. Official signed copies: contact hr@technova.com | ext. 2100",
                "agent_type": "hr_agent",
                "confidence": 0.80,
            },
            "record": {
                "answer": "Employee Records at TechNova:\n\n"
                "• Personnel files: Maintained by HR; you may review yours with 24 hours notice\n"
                "• Pay stubs: ADP Workforce Now (payroll portal)\n"
                "• Tax documents (W-2): ADP portal + mailed by January 31\n"
                "• Performance reviews: Available from your manager\n"
                "• Medical records: Kept in separate confidential files\n"
                "• Retention: Minimum 3 years post-separation (7 years for payroll/tax)\n\n"
                "Contact: hr@technova.com | ext. 2100",
                "agent_type": "hr_agent",
                "confidence": 0.80,
            },
            "safety": {
                "answer": "TechNova Workplace Safety:\n\n"
                "• Ergonomic assessments: Free for all employees (remote included via virtual consultation)\n"
                "• Report unsafe conditions to facilities@technova.com immediately\n"
                "• Incident reporting: Within 24 hours, complete form on HR portal\n"
                "• AED locations: Main lobby, 2nd floor break room, gym\n"
                "• Remote worker safety: $1,000 home office stipend for ergonomic equipment\n\n"
                "Emergency: Fire (evacuate via nearest exit), Medical (call 911), Active threat (Run/Hide/Fight)\n\n"
                "Contact: safety@technova.com | facilities@technova.com | ext. 4000",
                "agent_type": "policy_agent",
                "confidence": 0.85,
            },
            "security": {
                "answer": "TechNova Information Security Requirements:\n\n"
                "• Strong passwords: Minimum 12 characters via 1Password (mandatory)\n"
                "• MFA: Required on all company accounts\n"
                "• VPN: Required for all remote access\n"
                "• Lock screen: Ctrl+L / Cmd+L when away\n"
                "• Data classification: Public / Internal / Confidential / Restricted\n"
                "• No company data on personal cloud storage\n"
                "• Report suspected breaches immediately to security@technova.com\n\n"
                "Contact: security@technova.com | IT Help Desk: it@technova.com | ext. 3000",
                "agent_type": "policy_agent",
                "confidence": 0.85,
            },
            "hour": {
                "answer": "TechNova Working Hours:\n\n"
                "• Core hours: 10:00 AM - 4:00 PM (must be available)\n"
                "• Flexible start: Between 7:00 AM and 10:00 AM\n"
                "• Flexible end: Between 4:00 PM and 7:00 PM\n"
                "• Standard work week: 40 hours\n"
                "• Overtime (non-exempt): 1.5x rate, requires manager pre-approval\n"
                "• Hybrid schedule: In-office Tue/Wed/Thu, remote Mon/Fri\n\n"
                "Breaks: 30-min unpaid lunch (6+ hr shifts), two 15-min paid breaks per 8-hr shift.\n"
                "Nursing parents: Reasonable break time + private non-bathroom space (per PUMP Act).",
                "agent_type": "policy_agent",
                "confidence": 0.85,
            },
            "dress": {
                "answer": "TechNova Dress Code:\n\n"
                "• Office days (Tue-Thu): Business casual (collared shirts, blouses, slacks, clean denim)\n"
                "• Remote/Fridays: No formal code; professional attire for video meetings with clients\n"
                "• Client meetings: Business professional (suit/blazer recommended)\n"
                "• Not acceptable: Athletic wear, flip-flops, tank tops, torn clothing, offensive graphics\n\n"
                "When in doubt, business casual is always appropriate.",
                "agent_type": "policy_agent",
                "confidence": 0.82,
            },
            "pet": {
                "answer": "TechNova Pet Policy:\n\n"
                "• Pets are generally not permitted in the office\n"
                "• Service animals always welcome with documentation\n"
                "• Occasional 'Bring Your Dog' days coordinated by department\n"
                "• Allergies and safety are prioritized\n\n"
                "Check with your office manager for location-specific events.",
                "agent_type": "policy_agent",
                "confidence": 0.75,
            },
            "holiday": {
                "answer": "TechNova 2026 Holiday Schedule:\n\n"
                "• New Year's Day — Jan 1\n"
                "• Martin Luther King Jr. Day — Jan 19\n"
                "• Presidents' Day — Feb 16\n"
                "• Memorial Day — May 25\n"
                "• Independence Day — Jul 4 (observed Jul 3 if Saturday)\n"
                "• Labor Day — Sep 7\n"
                "• Thanksgiving — Nov 26\n"
                "• Day After Thanksgiving — Nov 27\n"
                "• Christmas Eve — Dec 24\n"
                "• Christmas Day — Dec 25\n\n"
                "Plus: 2 floating holidays/year (use at your discretion).\n"
                "Winter Office Closure: Dec 26 - Jan 1 (paid, in addition to PTO).",
                "agent_type": "policy_agent",
                "confidence": 0.90,
            },
            "calendar": {
                "answer": "TechNova 2026 Company Calendar:\n\n"
                "• 10 paid holidays + 2 floating holidays + winter closure (Dec 26-Jan 1)\n"
                "• Open enrollment: November 1-15\n"
                "• Performance reviews: March (mid-year) and September (annual)\n"
                "• Company all-hands: First Monday of each month\n"
                "• Quarterly town halls: January, April, July, October\n"
                "• Annual company retreat: September\n"
                "• Hackathons: Quarterly\n"
                "• 401(k) auto-enrollment: Immediate upon hire\n\n"
                "Full calendar available on the HR portal.",
                "agent_type": "policy_agent",
                "confidence": 0.85,
            },
            "background check": {
                "answer": "TechNova Background Check Policy:\n\n"
                "All new hires undergo a background check after receiving a conditional offer.\n\n"
                "Process (FCRA compliant):\n"
                "1. Written consent obtained before ordering the check\n"
                "2. Checks may include: Criminal history, education, employment, certifications\n"
                "3. If potentially adverse: Pre-adverse action notice + copy of report\n"
                "4. You have 5 business days to respond\n"
                "5. Final adverse action notice if decision stands\n\n"
                "We conduct individualized assessments considering the nature of any offense, "
                "time elapsed, and relevance to the position.\n"
                "Contact: hr@technova.com | ext. 2100",
                "agent_type": "hr_agent",
                "confidence": 0.82,
            },
            "i-9": {
                "answer": "Form I-9 (Employment Eligibility Verification):\n\n"
                "Required for ALL new employees regardless of citizenship.\n"
                "• Section 1: Complete no later than your first day of work\n"
                "• Section 2: TechNova HR completes within 3 business days of start\n\n"
                "Bring valid ID documents on Day 1:\n"
                "• List A (one document): US Passport, Permanent Resident Card, or Employment Authorization Document\n"
                "• OR List B + C (two documents): Driver's License + Social Security Card\n\n"
                "TechNova uses E-Verify for electronic confirmation.\n"
                "Records retained: 3 years from hire or 1 year after termination (whichever is later).\n"
                "Contact: hr@technova.com | ext. 2100",
                "agent_type": "hr_agent",
                "confidence": 0.85,
            },
            "sabbatical": {
                "answer": "TechNova Sabbatical Program:\n\n"
                "• Eligibility: After 7 years of continuous employment\n"
                "• Duration: 4 weeks fully paid\n"
                "• Frequency: Once every 7 years\n"
                "• Must be taken as a single continuous block\n\n"
                "Coordinate with your manager at least 3 months in advance.\n"
                "Contact: hr@technova.com | ext. 2100",
                "agent_type": "leave_agent",
                "confidence": 0.82,
            },
            "stock": {
                "answer": "TechNova Equity Compensation:\n\n"
                "RSUs (Senior engineers, managers, directors+):\n"
                "• 4-year vesting with 1-year cliff\n"
                "• Year 1: 25% vests at anniversary\n"
                "• Years 2-4: 6.25% vests quarterly\n"
                "• Taxed as ordinary income upon vesting\n\n"
                "ESPP (all employees after 6 months):\n"
                "• 15% discount from fair market value\n"
                "• Up to 15% of base salary ($25,000/year max)\n"
                "• Semi-annual purchase periods (Jan 1, Jul 1)\n"
                "• Lookback provision: Lower of start/end price minus 15%\n\n"
                "Contact: equity@technova.com | benefits@technova.com",
                "agent_type": "benefits_agent",
                "confidence": 0.85,
            },
            "expense": {
                "answer": "TechNova Expense Reimbursement:\n\n"
                "• Submit within 30 days of incurring the expense\n"
                "• Receipts required for expenses over $25\n"
                "• Manager approval required\n"
                "• Reimbursed within 2 pay cycles of approval\n"
                "• Mileage: $0.70/mile (2026 IRS rate)\n\n"
                "Common reimbursable: Business travel, client entertainment (pre-approved), "
                "professional development, home office supplies.\n"
                "Corporate credit cards available for managers+ and frequent travelers.\n"
                "Contact: expense@technova.com",
                "agent_type": "payroll_agent",
                "confidence": 0.80,
            },
            "erg": {
                "answer": "TechNova Employee Resource Groups (ERGs):\n\n"
                "• Women in Tech\n"
                "• Black Professionals Network\n"
                "• LGBTQ+ Alliance\n"
                "• Asian Pacific Islander Network\n"
                "• Parents and Caregivers\n"
                "• Veterans Network\n"
                "• Neurodiversity Alliance\n\n"
                "Join via the HR portal or Slack (#erg-directory).\n"
                "All employees welcome to join any ERG!",
                "agent_type": "hr_agent",
                "confidence": 0.80,
            },
            # --- LEAVE ALIASES (common natural-language phrases) ---
            "request time off": {
                "answer": "How to Request Time Off at TechNova:\n\n"
                "1. Go to the **Leave** page in the sidebar\n"
                "2. Click **New Request**\n"
                "3. Select leave type (Vacation, Sick, or Personal)\n"
                "4. Choose your start and end dates\n"
                "5. Add any notes and submit\n\n"
                "Your manager will be notified automatically for approval.\n\n"
                "Advance notice requirements:\n"
                "• 1-2 days off: 48 hours notice\n"
                "• 3+ days off: 2 weeks notice\n"
                "• Extended leave (2+ weeks): 30 days notice\n\n"
                "PTO Summary: Vacation (15-25 days based on tenure), "
                "Sick (10 days), Personal (3-5 days).\n"
                "Contact: leave@technova.com | ext. 2110",
                "agent_type": "leave_agent",
                "confidence": 0.92,
            },
            "time off": {
                "answer": "TechNova Time Off Policy:\n\n"
                "• Vacation: 15 days/year (0-2 yrs), 20 days (2-5 yrs), 25 days (5+ yrs or manager level)\n"
                "• Sick Leave: 10 days/year (available from Day 1)\n"
                "• Personal Days: 3 days (employee), 5 days (manager+)\n"
                "• Mental Health Days: 2 per quarter (separate from sick leave)\n"
                "• Holidays: 10 company holidays + 2 floating + winter closure (Dec 26-Jan 1)\n"
                "• Carryover: Up to 5 unused vacation days roll into the next year\n\n"
                "To request time off, visit the **Leave** page and submit a new request.\n"
                "Contact: leave@technova.com | ext. 2110",
                "agent_type": "leave_agent",
                "confidence": 0.90,
            },
            "request leave": {
                "answer": "How to Request Leave at TechNova:\n\n"
                "1. Navigate to the **Leave** page from the sidebar\n"
                "2. Click **New Request** to start a leave request\n"
                "3. Select the type of leave (Vacation, Sick, Personal)\n"
                "4. Pick your start and end dates\n"
                "5. Submit for manager approval\n\n"
                "Leave balances: Vacation (15-25 days), Sick (10 days), Personal (3-5 days).\n"
                "For extended leave (FMLA, parental), contact HR directly.\n"
                "Contact: leave@technova.com | ext. 2110",
                "agent_type": "leave_agent",
                "confidence": 0.90,
            },
            "day off": {
                "answer": "TechNova Time Off Policy:\n\n"
                "• Vacation: 15-25 days/year (based on tenure)\n"
                "• Sick Leave: 10 days/year\n"
                "• Personal Days: 3 days (employee), 5 days (manager+)\n"
                "• Mental Health Days: 2 per quarter\n\n"
                "To request a day off, go to the **Leave** page and submit a new request.\n"
                "Your manager will be notified for approval.\n"
                "Contact: leave@technova.com | ext. 2110",
                "agent_type": "leave_agent",
                "confidence": 0.88,
            },
            "take leave": {
                "answer": "To take leave at TechNova:\n\n"
                "1. Go to the **Leave** page\n"
                "2. Click **New Request**\n"
                "3. Select leave type and dates\n"
                "4. Submit for manager approval\n\n"
                "Available leave: Vacation (15-25 days), Sick (10 days), Personal (3-5 days).\n"
                "Contact: leave@technova.com | ext. 2110",
                "agent_type": "leave_agent",
                "confidence": 0.88,
            },
        }

        # Find matching response by keyword (longer keywords first for specificity)
        for keyword, resp in sorted(
            static_responses.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if keyword in query_lower:
                resp["request_id"] = f"static_{int(time.time())}"
                resp["execution_time_ms"] = 5
                resp["reasoning_trace"] = [
                    "Static knowledge base match",
                    f"Matched keyword: '{keyword}'",
                ]
                return resp

        # No keyword match — return None so _query() can try the agent service
        return None

    # ------------------------------------------------------------------
    # Leave Endpoints (DB-wired)
    # ------------------------------------------------------------------

    def _get_leave_balance(self):
        """Get employee leave balance from database."""
        try:
            session = self._get_db_session()
            if session is None:
                # Fallback to mock data
                return (
                    jsonify(
                        APIResponse(
                            success=True,
                            data={
                                "employee_id": "unknown",
                                "vacation": {"available": 15, "used": 5, "pending": 2},
                                "sick": {"available": 10, "used": 2, "pending": 0},
                                "personal": {"available": 5, "used": 1, "pending": 0},
                            },
                        ).to_dict()
                    ),
                    200,
                )

            try:
                from src.core.database import LeaveBalance, LeaveRequest

                employee, role = self._get_current_employee(session)

                if not employee:
                    return (
                        jsonify(
                            APIResponse(
                                success=True,
                                data={
                                    "employee_id": "unknown",
                                    "vacation": {"available": 15, "used": 5, "pending": 0},
                                    "sick": {"available": 10, "used": 2, "pending": 0},
                                    "personal": {"available": 5, "used": 1, "pending": 0},
                                },
                            ).to_dict()
                        ),
                        200,
                    )

                balance = session.query(LeaveBalance).filter_by(employee_id=employee.id).first()

                # Count pending requests by type
                pending_vacation = (
                    session.query(LeaveRequest)
                    .filter_by(employee_id=employee.id, leave_type="vacation", status="pending")
                    .count()
                )
                pending_sick = (
                    session.query(LeaveRequest)
                    .filter_by(employee_id=employee.id, leave_type="sick", status="pending")
                    .count()
                )
                pending_personal = (
                    session.query(LeaveRequest)
                    .filter_by(employee_id=employee.id, leave_type="personal", status="pending")
                    .count()
                )

                if balance:
                    balance_data = {
                        "employee_id": str(employee.id),
                        "vacation": {
                            "available": balance.vacation_total - balance.vacation_used,
                            "used": balance.vacation_used,
                            "pending": pending_vacation,
                        },
                        "sick": {
                            "available": balance.sick_total - balance.sick_used,
                            "used": balance.sick_used,
                            "pending": pending_sick,
                        },
                        "personal": {
                            "available": balance.personal_total - balance.personal_used,
                            "used": balance.personal_used,
                            "pending": pending_personal,
                        },
                    }
                else:
                    balance_data = {
                        "employee_id": str(employee.id),
                        "vacation": {"available": 15, "used": 0, "pending": 0},
                        "sick": {"available": 10, "used": 0, "pending": 0},
                        "personal": {"available": 5, "used": 0, "pending": 0},
                    }

                return jsonify(APIResponse(success=True, data=balance_data).to_dict()), 200
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Leave balance error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _submit_leave_request(self):
        """Submit leave request to database."""
        try:
            data = request.get_json() or {}
            required_fields = ["start_date", "end_date", "leave_type"]
            missing = [f for f in required_fields if f not in data]
            if missing:
                return (
                    jsonify(
                        APIResponse(
                            success=False, error=f"Missing required fields: {missing}"
                        ).to_dict()
                    ),
                    400,
                )

            session = self._get_db_session()
            if session is None:
                # Fallback to mock
                return (
                    jsonify(
                        APIResponse(
                            success=True,
                            data={
                                "request_id": f"req_{int(time.time())}",
                                "status": "submitted",
                                "leave_type": data["leave_type"],
                                "start_date": data["start_date"],
                                "end_date": data["end_date"],
                            },
                        ).to_dict()
                    ),
                    201,
                )

            try:
                from src.core.database import LeaveRequest as LR

                employee, role = self._get_current_employee(session)

                emp_id = employee.id if employee else 1

                leave_req = LR(
                    employee_id=emp_id,
                    leave_type=data["leave_type"],
                    start_date=data["start_date"],
                    end_date=data["end_date"],
                    reason=data.get("reason", ""),
                    status="pending",
                )
                session.add(leave_req)
                session.commit()

                request_data = {
                    "request_id": str(leave_req.id),
                    "status": "pending",
                    "employee_id": str(emp_id),
                    "leave_type": data["leave_type"],
                    "start_date": data["start_date"],
                    "end_date": data["end_date"],
                    "reason": data.get("reason", ""),
                }

                # Publish event
                try:
                    from src.core.event_bus import EventBus, Event, LEAVE_SUBMITTED

                    EventBus.instance().publish(
                        Event(
                            type=LEAVE_SUBMITTED,
                            source="api_gateway",
                            payload=request_data,
                        )
                    )
                except Exception:
                    pass  # Event bus is best-effort

                # Emit real-time notification
                emp_name = g.user_context.get("name", "An employee")
                APIGateway.broadcast_notification(
                    str(emp_id),
                    "Leave Request Submitted",
                    f"Your {data['leave_type']} request ({data['start_date']} to {data['end_date']}) is pending approval.",
                    "leave",
                )
                # Notify the employee's manager (if known)
                if employee and employee.manager_id:
                    APIGateway.broadcast_notification(
                        str(employee.manager_id),
                        "New Leave Request",
                        f"{emp_name} submitted a {data['leave_type']} request for {data['start_date']} to {data['end_date']}.",
                        "leave",
                    )

                self._log_request("POST", "/api/v2/leave/request", True)
                return jsonify(APIResponse(success=True, data=request_data).to_dict()), 201
            except Exception as inner_e:
                session.rollback()
                raise inner_e
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Submit leave error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _get_leave_history(self):
        """Get leave request history from database."""
        try:
            session = self._get_db_session()
            if session is None:
                # Fallback mock
                return (
                    jsonify(
                        APIResponse(
                            success=True,
                            data={
                                "history": [
                                    {
                                        "request_id": "req_001",
                                        "type": "Vacation",
                                        "start_date": "2024-01-15",
                                        "end_date": "2024-01-19",
                                        "status": "Approved",
                                        "requested_date": "2024-01-02",
                                    },
                                    {
                                        "request_id": "req_002",
                                        "type": "Sick Leave",
                                        "start_date": "2024-02-10",
                                        "end_date": "2024-02-11",
                                        "status": "Approved",
                                        "requested_date": "2024-02-10",
                                    },
                                ]
                            },
                        ).to_dict()
                    ),
                    200,
                )

            try:
                from src.core.database import LeaveRequest as LR

                employee, role = self._get_current_employee(session)

                if not employee:
                    return jsonify(APIResponse(success=True, data={"history": []}).to_dict()), 200

                requests = (
                    session.query(LR)
                    .filter_by(employee_id=employee.id)
                    .order_by(LR.id.desc())
                    .all()
                )

                type_display = {
                    "vacation": "Vacation",
                    "sick": "Sick Leave",
                    "personal": "Personal",
                }
                status_display = {
                    "pending": "Pending",
                    "approved": "Approved",
                    "rejected": "Rejected",
                }

                history = []
                for req in requests:
                    history.append(
                        {
                            "request_id": str(req.id),
                            "type": type_display.get(req.leave_type, req.leave_type),
                            "start_date": req.start_date,
                            "end_date": req.end_date,
                            "status": status_display.get(req.status, req.status),
                            "requested_date": (
                                req.created_at.strftime("%Y-%m-%d") if req.created_at else ""
                            ),
                        }
                    )

                return jsonify(APIResponse(success=True, data={"history": history}).to_dict()), 200
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Leave history error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    # ------------------------------------------------------------------
    # Workflow Endpoints (DB-wired + role enforcement)
    # ------------------------------------------------------------------

    def _get_pending_approvals(self):
        """Get pending workflow approvals (manager/HR only)."""
        try:
            user_context = g.get("user_context") or {}
            user_role = user_context.get("role", "employee")

            if user_role == "employee":
                return (
                    jsonify(
                        APIResponse(
                            success=False, error="Access denied: manager or HR role required"
                        ).to_dict()
                    ),
                    403,
                )

            session = self._get_db_session()
            if session is None:
                return (
                    jsonify(
                        APIResponse(
                            success=True,
                            data={
                                "pending": [
                                    {
                                        "request_id": "leave-001",
                                        "type": "Leave Request",
                                        "requester": "Alice Johnson",
                                        "detail": "5 days vacation",
                                        "requested_date": "2024-03-01",
                                        "priority": "high",
                                    },
                                ],
                                "count": 1,
                            },
                        ).to_dict()
                    ),
                    200,
                )

            try:
                from src.core.database import LeaveRequest as LR, Employee

                pending_reqs = (
                    session.query(LR).filter_by(status="pending").order_by(LR.id.desc()).all()
                )

                pending_list = []
                for req in pending_reqs:
                    emp = session.query(Employee).filter_by(id=req.employee_id).first()
                    requester_name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"

                    from datetime import datetime as dt

                    try:
                        start = dt.strptime(req.start_date, "%Y-%m-%d")
                        end = dt.strptime(req.end_date, "%Y-%m-%d")
                        days = (end - start).days + 1
                    except:
                        days = 1

                    type_display = {
                        "vacation": "Vacation",
                        "sick": "Sick Leave",
                        "personal": "Personal",
                    }

                    pending_list.append(
                        {
                            "request_id": str(req.id),
                            "type": "Leave Request",
                            "requester": requester_name,
                            "detail": f"{days} days {type_display.get(req.leave_type, req.leave_type)} — {req.start_date} to {req.end_date}",
                            "requested_date": (
                                req.created_at.strftime("%Y-%m-%d") if req.created_at else ""
                            ),
                            "priority": "high" if days >= 5 else "medium" if days >= 3 else "low",
                        }
                    )

                return (
                    jsonify(
                        APIResponse(
                            success=True, data={"pending": pending_list, "count": len(pending_list)}
                        ).to_dict()
                    ),
                    200,
                )
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Pending approvals error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _approve_request(self):
        """Approve a workflow request (manager/HR only)."""
        try:
            user_context = g.get("user_context") or {}
            user_role = user_context.get("role", "employee")
            if user_role == "employee":
                return (
                    jsonify(
                        APIResponse(
                            success=False, error="Access denied: manager or HR role required"
                        ).to_dict()
                    ),
                    403,
                )

            data = request.get_json() or {}
            request_id = data.get("request_id")
            if not request_id:
                return (
                    jsonify(APIResponse(success=False, error="request_id required").to_dict()),
                    400,
                )

            # Check if request_id is a numeric DB id or a demo string id
            try:
                numeric_id = int(request_id)
            except (ValueError, TypeError):
                numeric_id = None

            session = self._get_db_session()
            if session is None or numeric_id is None:
                return (
                    jsonify(
                        APIResponse(
                            success=True,
                            data={
                                "request_id": request_id,
                                "status": "approved",
                                "approved_by": user_context.get("name", "manager"),
                                "approved_at": datetime.utcnow().isoformat(),
                            },
                        ).to_dict()
                    ),
                    200,
                )

            try:
                from src.core.database import LeaveRequest as LR, LeaveBalance

                leave_req = session.query(LR).filter_by(id=numeric_id).first()
                if not leave_req:
                    return (
                        jsonify(APIResponse(success=False, error="Request not found").to_dict()),
                        404,
                    )

                employee, role = self._get_current_employee(session)
                approver_id = employee.id if employee else None

                leave_req.status = "approved"
                leave_req.approved_by = approver_id
                leave_req.approved_at = datetime.utcnow()

                # Update leave balance (deduct from available)
                balance = (
                    session.query(LeaveBalance).filter_by(employee_id=leave_req.employee_id).first()
                )
                if balance:
                    from datetime import datetime as dt

                    try:
                        start = dt.strptime(leave_req.start_date, "%Y-%m-%d")
                        end = dt.strptime(leave_req.end_date, "%Y-%m-%d")
                        days = (end - start).days + 1
                    except:
                        days = 1

                    if leave_req.leave_type == "vacation":
                        balance.vacation_used += days
                    elif leave_req.leave_type == "sick":
                        balance.sick_used += days
                    elif leave_req.leave_type == "personal":
                        balance.personal_used += days

                session.commit()

                approve_data = {
                    "request_id": request_id,
                    "status": "approved",
                    "approved_by": str(approver_id),
                    "approved_at": datetime.utcnow().isoformat(),
                }
                # Publish event
                try:
                    from src.core.event_bus import EventBus, Event, LEAVE_APPROVED

                    EventBus.instance().publish(
                        Event(
                            type=LEAVE_APPROVED,
                            source="api_gateway",
                            payload=approve_data,
                        )
                    )
                except Exception:
                    pass

                # Real-time notification to the employee who requested leave
                approver_name = user_context.get("name", "Your manager")
                APIGateway.broadcast_notification(
                    str(leave_req.employee_id),
                    "Leave Request Approved",
                    f"{approver_name} approved your {leave_req.leave_type} request ({leave_req.start_date} to {leave_req.end_date}).",
                    "leave",
                )

                return jsonify(APIResponse(success=True, data=approve_data).to_dict()), 200
            except Exception as inner_e:
                session.rollback()
                raise inner_e
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Approve request error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _reject_request(self):
        """Reject a workflow request (manager/HR only)."""
        try:
            user_context = g.get("user_context") or {}
            user_role = user_context.get("role", "employee")
            if user_role == "employee":
                return (
                    jsonify(
                        APIResponse(
                            success=False, error="Access denied: manager or HR role required"
                        ).to_dict()
                    ),
                    403,
                )

            data = request.get_json() or {}
            request_id = data.get("request_id")
            reason = data.get("reason", "")
            if not request_id:
                return (
                    jsonify(APIResponse(success=False, error="request_id required").to_dict()),
                    400,
                )

            # Check if request_id is a numeric DB id or a demo string id
            try:
                numeric_id = int(request_id)
            except (ValueError, TypeError):
                numeric_id = None

            session = self._get_db_session()
            if session is None or numeric_id is None:
                return (
                    jsonify(
                        APIResponse(
                            success=True,
                            data={
                                "request_id": request_id,
                                "status": "rejected",
                                "rejected_by": user_context.get("name", "manager"),
                                "rejected_at": datetime.utcnow().isoformat(),
                                "reason": reason,
                            },
                        ).to_dict()
                    ),
                    200,
                )

            try:
                from src.core.database import LeaveRequest as LR

                leave_req = session.query(LR).filter_by(id=numeric_id).first()
                if not leave_req:
                    return (
                        jsonify(APIResponse(success=False, error="Request not found").to_dict()),
                        404,
                    )

                employee, role = self._get_current_employee(session)

                leave_req.status = "rejected"
                session.commit()

                reject_data = {
                    "request_id": request_id,
                    "status": "rejected",
                    "rejected_by": str(employee.id) if employee else "unknown",
                    "rejected_at": datetime.utcnow().isoformat(),
                    "reason": reason,
                }
                # Publish event
                try:
                    from src.core.event_bus import EventBus, Event, LEAVE_REJECTED

                    EventBus.instance().publish(
                        Event(
                            type=LEAVE_REJECTED,
                            source="api_gateway",
                            payload=reject_data,
                        )
                    )
                except Exception:
                    pass

                # Real-time notification to the employee who requested leave
                rejector_name = user_context.get("name", "Your manager")
                reason_text = f" Reason: {reason}" if reason else ""
                APIGateway.broadcast_notification(
                    str(leave_req.employee_id),
                    "Leave Request Rejected",
                    f"{rejector_name} rejected your {leave_req.leave_type} request ({leave_req.start_date} to {leave_req.end_date}).{reason_text}",
                    "leave",
                )

                return jsonify(APIResponse(success=True, data=reject_data).to_dict()), 200
            except Exception as inner_e:
                session.rollback()
                raise inner_e
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Reject request error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    # ------------------------------------------------------------------
    # Document Endpoints (DB-wired)
    # ------------------------------------------------------------------

    def _list_templates(self):
        """List document templates."""
        try:
            templates_data = {
                "templates": [
                    {"template_id": "t1", "name": "Offer Letter", "type": "offer_letter"},
                    {
                        "template_id": "t2",
                        "name": "Employment Contract",
                        "type": "employment_contract",
                    },
                    {
                        "template_id": "t3",
                        "name": "Termination Letter",
                        "type": "termination_letter",
                    },
                    {
                        "template_id": "t4",
                        "name": "Employment Certificate",
                        "type": "employment_certificate",
                    },
                    {"template_id": "t5", "name": "Promotion Letter", "type": "promotion_letter"},
                    {"template_id": "t6", "name": "Experience Letter", "type": "experience_letter"},
                ]
            }
            return jsonify(APIResponse(success=True, data=templates_data).to_dict()), 200
        except Exception as e:
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _generate_document(self):
        """Generate document from template and save to DB."""
        try:
            data = request.get_json() or {}
            if "template_id" not in data:
                return (
                    jsonify(APIResponse(success=False, error="template_id required").to_dict()),
                    400,
                )

            template_names = {
                "t1": "Offer Letter",
                "t2": "Employment Contract",
                "t3": "Termination Letter",
                "t4": "Employment Certificate",
                "t5": "Promotion Letter",
                "t6": "Experience Letter",
            }

            session = self._get_db_session()
            if session is None:
                return (
                    jsonify(
                        APIResponse(
                            success=True,
                            data={
                                "document_id": f"doc_{int(time.time())}",
                                "template_id": data["template_id"],
                                "status": "finalized",
                                "created_at": datetime.utcnow().isoformat(),
                            },
                        ).to_dict()
                    ),
                    201,
                )

            try:
                from src.core.database import Employee, GeneratedDocument

                # Use employee_id from request body (selected employee)
                # instead of the logged-in user
                requested_emp_id = data.get("employee_id")
                if requested_emp_id:
                    try:
                        target_emp = session.query(Employee).filter_by(id=int(requested_emp_id)).first()
                    except (ValueError, TypeError):
                        target_emp = None
                    emp_id = target_emp.id if target_emp else 1
                else:
                    employee, role = self._get_current_employee(session)
                    emp_id = employee.id if employee else 1

                doc = GeneratedDocument(
                    employee_id=emp_id,
                    template_id=data["template_id"],
                    template_name=template_names.get(data["template_id"], "Unknown Template"),
                    status="finalized",
                    parameters=data.get("parameters"),
                )
                session.add(doc)
                session.commit()

                doc_data = {
                    "document_id": str(doc.id),
                    "template_id": data["template_id"],
                    "template_name": doc.template_name,
                    "status": "finalized",
                    "created_at": (
                        doc.created_at.isoformat()
                        if doc.created_at
                        else datetime.utcnow().isoformat()
                    ),
                }

                self._log_request("POST", "/api/v2/documents/generate", True)
                return jsonify(APIResponse(success=True, data=doc_data).to_dict()), 201
            except Exception as inner_e:
                session.rollback()
                raise inner_e
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Generate document error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _get_metrics(self):
        """Get agent metrics with real DB data, scoped by user role.

        - Employee: sees own department headcount, own leave requests, no pending approvals
        - Manager: sees own department team data + pending approvals for team
        - HR Admin: sees company-wide data across all departments
        """
        try:
            user_context = g.get("user_context") or {}
            user_role = user_context.get("role", "employee")
            metrics = {}

            # --- Pull role-scoped numbers from DB ---
            try:
                from src.core.database import Employee, LeaveRequest

                session = self._get_db_session()

                # Get the current employee to know their department
                employee, _ = self._get_current_employee(session)
                user_dept = employee.department if employee else "Engineering"

                if user_role == "hr_admin":
                    # HR Admin: company-wide view
                    metrics["total_employees"] = session.query(Employee).count() or 0
                    metrics["open_leave_requests"] = (
                        session.query(LeaveRequest)
                        .filter(LeaveRequest.status.in_(["pending", "Pending"]))
                        .count()
                    )
                    metrics["pending_approvals"] = metrics["open_leave_requests"]
                    dept_counts = {}
                    for emp in session.query(Employee).all():
                        dept_counts[emp.department] = dept_counts.get(emp.department, 0) + 1
                    metrics["department_headcount"] = (
                        dept_counts
                        if dept_counts
                        else {
                            "Engineering": 45,
                            "Sales": 38,
                            "HR": 22,
                            "Finance": 28,
                            "Operations": 35,
                        }
                    )
                elif user_role == "manager":
                    # Manager: own department team data
                    dept_employees = session.query(Employee).filter_by(department=user_dept).all()
                    metrics["total_employees"] = len(dept_employees)
                    dept_emp_ids = [e.id for e in dept_employees]
                    metrics["open_leave_requests"] = (
                        (
                            session.query(LeaveRequest)
                            .filter(
                                LeaveRequest.employee_id.in_(dept_emp_ids),
                                LeaveRequest.status.in_(["pending", "Pending"]),
                            )
                            .count()
                        )
                        if dept_emp_ids
                        else 0
                    )
                    metrics["pending_approvals"] = metrics["open_leave_requests"]
                    dept_counts = {}
                    for emp in session.query(Employee).all():
                        dept_counts[emp.department] = dept_counts.get(emp.department, 0) + 1
                    metrics["department_headcount"] = (
                        dept_counts if dept_counts else {user_dept: len(dept_employees)}
                    )
                else:
                    # Employee: own data only
                    if employee:
                        metrics["total_employees"] = (
                            session.query(Employee).filter_by(department=user_dept).count()
                        )
                        metrics["open_leave_requests"] = (
                            session.query(LeaveRequest)
                            .filter_by(employee_id=employee.id)
                            .filter(LeaveRequest.status.in_(["pending", "Pending"]))
                            .count()
                        )
                    else:
                        metrics["total_employees"] = 0
                        metrics["open_leave_requests"] = 0
                    metrics["pending_approvals"] = 0  # Employees can't approve
                    metrics["department_headcount"] = {user_dept: metrics["total_employees"]}

                session.close()
            except Exception as db_err:
                logger.warning(f"DB metrics fallback: {db_err}")
                if user_role == "hr_admin":
                    metrics.setdefault("total_employees", 285)
                    metrics.setdefault("open_leave_requests", 3)
                    metrics.setdefault("pending_approvals", 5)
                elif user_role == "manager":
                    metrics.setdefault("total_employees", 45)
                    metrics.setdefault("open_leave_requests", 2)
                    metrics.setdefault("pending_approvals", 2)
                else:
                    metrics.setdefault("total_employees", 45)
                    metrics.setdefault("open_leave_requests", 1)
                    metrics.setdefault("pending_approvals", 0)

            # --- Merge agent stats if available (without overwriting role-scoped DB values) ---
            role_scoped_keys = {
                "total_employees",
                "open_leave_requests",
                "pending_approvals",
                "department_headcount",
            }
            try:
                agent_service = current_app.agent_service
                agent_stats = agent_service.get_agent_stats()
                if isinstance(agent_stats, dict):
                    for k, v in agent_stats.items():
                        if k not in role_scoped_keys:
                            metrics[k] = v
            except Exception:
                pass  # agent service may not be initialised yet

            # Ensure dashboard-critical keys always present (role-appropriate defaults)
            if user_role == "hr_admin":
                metrics.setdefault("total_employees", 285)
                metrics.setdefault("open_leave_requests", 3)
                metrics.setdefault("pending_approvals", 5)
                metrics.setdefault("queries_today", 24)
                metrics.setdefault(
                    "department_headcount",
                    {"Engineering": 45, "Sales": 38, "HR": 22, "Finance": 28, "Operations": 35},
                )
            elif user_role == "manager":
                metrics.setdefault("total_employees", 45)
                metrics.setdefault("open_leave_requests", 2)
                metrics.setdefault("pending_approvals", 2)
                metrics.setdefault("queries_today", 8)
                metrics.setdefault("department_headcount", {"Engineering": 45})
            else:
                metrics.setdefault("total_employees", 45)
                metrics.setdefault("open_leave_requests", 1)
                metrics.setdefault("pending_approvals", 0)
                metrics.setdefault("queries_today", 3)
                metrics.setdefault("department_headcount", {"Engineering": 45})

            metrics.setdefault("monthly_queries", [45, 52, 38, 65, 72, 58])
            # Include role in response so frontend knows the data scope
            metrics["role"] = user_role

            return jsonify(APIResponse(success=True, data=metrics).to_dict()), 200
        except Exception as e:
            logger.error(f"Metrics endpoint error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _export_metrics(self):
        """Export analytics metrics as CSV (HR admin only)."""
        try:
            user_context = g.get("user_context") or {}
            user_role = user_context.get("role", "employee")
            # Allow manager and hr_admin to export
            if user_role == "employee":
                return (
                    jsonify(
                        APIResponse(
                            success=False, error="Access denied: manager or HR role required"
                        ).to_dict()
                    ),
                    403,
                )

            import csv
            import io

            date_from = request.args.get("date_from", "2023-01-01")
            date_to = request.args.get("date_to", "2024-12-31")

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "Month",
                    "Department",
                    "Headcount",
                    "Turnover Rate",
                    "Leaves Used",
                    "Agent Queries",
                ]
            )
            months = [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]
            departments = ["Engineering", "Sales", "HR", "Finance", "Operations"]
            for month in months:
                for dept in departments:
                    writer.writerow([month, dept, 45, "2.5%", 12, 34])

            csv_content = output.getvalue()
            output.close()

            from flask import Response

            return Response(
                csv_content,
                mimetype="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=hr_analytics_{date_from}_to_{date_to}.csv"
                },
            )
        except Exception as e:
            logger.error(f"Export metrics error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    # ------------------------------------------------------------------
    # Wave 2: Multi-Agent Integration
    # ------------------------------------------------------------------

    def _list_agents(self):
        try:
            agent_service = current_app.agent_service
            agents = agent_service.get_available_agents()
            return (
                jsonify(
                    APIResponse(
                        success=True, data={"agents": agents, "count": len(agents)}
                    ).to_dict()
                ),
                200,
            )
        except Exception as e:
            logger.error(f"Agents endpoint error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _rag_stats(self):
        try:
            rag_service = current_app.rag_service
            stats = rag_service.get_collection_stats()
            return (
                jsonify(
                    APIResponse(
                        success=True, data={"collections": stats, "total_collections": len(stats)}
                    ).to_dict()
                ),
                200,
            )
        except Exception as e:
            logger.error(f"RAG stats endpoint error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _rag_ingest(self):
        try:
            data = request.get_json() or {}
            filepath = data.get("filepath")
            collection = data.get("collection", "hr_policies")
            doc_type = data.get("doc_type")
            if not filepath:
                return jsonify(APIResponse(success=False, error="filepath required").to_dict()), 400
            rag_service = current_app.rag_service
            result = rag_service.ingest_file(
                filepath=filepath, collection=collection, doc_type=doc_type
            )
            return (
                jsonify(APIResponse(success=result.get("success", False), data=result).to_dict()),
                200 if result.get("success") else 400,
            )
        except Exception as e:
            logger.error(f"RAG ingest endpoint error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    # ------------------------------------------------------------------
    # Profile & Employee Management (Wave 4)
    # ------------------------------------------------------------------

    def _serialize_employee(self, emp) -> Dict[str, Any]:
        """Serialize an Employee ORM object to a JSON-safe dict."""
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

    def _get_profile(self):
        """GET /api/v2/profile – Return current user's profile."""
        try:
            session = self._get_db_session()
            if not session:
                return (
                    jsonify(APIResponse(success=False, error="Database unavailable").to_dict()),
                    503,
                )

            employee, role = self._get_current_employee(session)
            if not employee:
                session.close()
                return jsonify(APIResponse(success=False, error="User not found").to_dict()), 404

            data = self._serialize_employee(employee)
            data["role"] = role
            session.close()
            self._log_request("GET", "/profile", True)
            return jsonify(APIResponse(success=True, data=data).to_dict()), 200
        except Exception as e:
            logger.error(f"Get profile error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _update_profile(self):
        """PUT /api/v2/profile – Update current user's profile fields."""
        try:
            session = self._get_db_session()
            if not session:
                return (
                    jsonify(APIResponse(success=False, error="Database unavailable").to_dict()),
                    503,
                )

            employee, role = self._get_current_employee(session)
            if not employee:
                session.close()
                return jsonify(APIResponse(success=False, error="User not found").to_dict()), 404

            data = request.get_json() or {}
            allowed_fields = ["first_name", "last_name", "department"]
            updated = []
            for field_name in allowed_fields:
                if field_name in data and data[field_name]:
                    setattr(employee, field_name, data[field_name])
                    updated.append(field_name)

            if not updated:
                session.close()
                return (
                    jsonify(
                        APIResponse(success=False, error="No valid fields to update").to_dict()
                    ),
                    400,
                )

            employee.updated_at = datetime.utcnow()
            session.commit()
            result = self._serialize_employee(employee)
            result["role"] = role
            session.close()
            self._log_request("PUT", "/profile", True)
            return (
                jsonify(
                    APIResponse(
                        success=True, data=result, metadata={"updated_fields": updated}
                    ).to_dict()
                ),
                200,
            )
        except Exception as e:
            logger.error(f"Update profile error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _list_employees(self):
        """GET /api/v2/employees – List all employees (HR admin only)."""
        try:
            from src.core.database import Employee

            user_context = g.get("user_context") or {}
            role = user_context.get("role") or request.headers.get("X-User-Role", "employee")
            if role not in ("hr_admin", "hr_generalist"):
                return (
                    jsonify(
                        APIResponse(
                            success=False, error="Forbidden: HR admin role required"
                        ).to_dict()
                    ),
                    403,
                )

            session = self._get_db_session()
            if not session:
                return (
                    jsonify(APIResponse(success=False, error="Database unavailable").to_dict()),
                    503,
                )

            employees = session.query(Employee).order_by(Employee.last_name).all()
            data = [self._serialize_employee(emp) for emp in employees]
            session.close()
            self._log_request("GET", "/employees", True)
            return (
                jsonify(
                    APIResponse(
                        success=True, data={"employees": data, "total": len(data)}
                    ).to_dict()
                ),
                200,
            )
        except Exception as e:
            logger.error(f"List employees error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _update_employee(self, employee_id: int):
        """PUT /api/v2/employees/<id> – Update an employee (HR admin only)."""
        try:
            from src.core.database import Employee

            user_context = g.get("user_context") or {}
            role = user_context.get("role") or request.headers.get("X-User-Role", "employee")
            if role not in ("hr_admin", "hr_generalist"):
                return (
                    jsonify(
                        APIResponse(
                            success=False, error="Forbidden: HR admin role required"
                        ).to_dict()
                    ),
                    403,
                )

            session = self._get_db_session()
            if not session:
                return (
                    jsonify(APIResponse(success=False, error="Database unavailable").to_dict()),
                    503,
                )

            employee = session.query(Employee).filter_by(id=employee_id).first()
            if not employee:
                session.close()
                return (
                    jsonify(
                        APIResponse(
                            success=False, error=f"Employee {employee_id} not found"
                        ).to_dict()
                    ),
                    404,
                )

            data = request.get_json() or {}
            allowed_fields = [
                "first_name",
                "last_name",
                "email",
                "department",
                "role_level",
                "status",
            ]
            updated = []
            for field_name in allowed_fields:
                if field_name in data and data[field_name] is not None:
                    setattr(employee, field_name, data[field_name])
                    updated.append(field_name)

            if not updated:
                session.close()
                return (
                    jsonify(
                        APIResponse(success=False, error="No valid fields to update").to_dict()
                    ),
                    400,
                )

            employee.updated_at = datetime.utcnow()
            session.commit()
            result = self._serialize_employee(employee)
            session.close()
            self._log_request("PUT", f"/employees/{employee_id}", True)
            return (
                jsonify(
                    APIResponse(
                        success=True, data=result, metadata={"updated_fields": updated}
                    ).to_dict()
                ),
                200,
            )
        except Exception as e:
            logger.error(f"Update employee error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    # ------------------------------------------------------------------
    # Wave 5.5 – Real-time Notifications (SSE)
    # ------------------------------------------------------------------

    # In-memory notification event bus (per-user queues)
    _notification_queues: Dict[str, list] = {}
    _notification_store: Dict[str, list] = {}  # persisted until read

    @classmethod
    def broadcast_notification(cls, user_id: str, title: str, detail: str, category: str = "info"):
        """Push a notification to a user's queue (called from approve/reject/leave)."""
        import json as _json

        notif = {
            "id": f"n_{int(time.time() * 1000)}",
            "title": title,
            "detail": detail,
            "category": category,
            "time": datetime.utcnow().isoformat(),
            "read": False,
        }
        # Store for polling fallback
        cls._notification_store.setdefault(user_id, []).append(notif)
        # Keep max 30 per user
        if len(cls._notification_store[user_id]) > 30:
            cls._notification_store[user_id] = cls._notification_store[user_id][-30:]

    def _get_notifications(self):
        """GET /api/v2/notifications – Fetch recent notifications for current user."""
        user_id = g.user_context.get("user_id", "unknown")
        notifs = self._notification_store.get(user_id, [])
        return jsonify(APIResponse(success=True, data={"notifications": notifs}).to_dict()), 200

    def _sse_notification_stream(self):
        """GET /api/v2/notifications/stream – SSE stream for real-time notifications."""
        from flask import Response, stream_with_context
        import json as _json

        # Support token via query parameter (EventSource can't set headers)
        user_id = g.user_context.get("user_id") if g.get("user_context") else None
        if not user_id:
            token = request.args.get("token")
            if token:
                try:
                    from src.middleware.auth import AuthService

                    payload = AuthService().verify_token(token)
                    user_id = payload.get("user_id", payload.get("sub", "unknown"))
                except Exception:
                    user_id = "unknown"
            else:
                user_id = "unknown"

        def generate():
            """Yield SSE events."""
            last_count = len(self._notification_store.get(user_id, []))
            # Send initial heartbeat
            yield f"data: {_json.dumps({'type': 'connected', 'user_id': user_id})}\n\n"

            timeout = 120  # seconds
            start = time.time()
            while (time.time() - start) < timeout:
                current = self._notification_store.get(user_id, [])
                if len(current) > last_count:
                    # New notifications since last check
                    new_notifs = current[last_count:]
                    for n in new_notifs:
                        yield f"data: {_json.dumps({'type': 'notification', 'payload': n})}\n\n"
                    last_count = len(current)
                else:
                    # Heartbeat every 15s to keep connection alive
                    yield f": heartbeat\n\n"
                time.sleep(2)

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # ------------------------------------------------------------------
    # Wave 5 – Benefits, Onboarding, Performance, Events
    # ------------------------------------------------------------------

    def _get_events(self):
        """GET /api/v2/events – List recent event log entries."""
        try:
            from src.core.database import EventLog

            session = self._get_db_session()
            if not session:
                return jsonify(APIResponse(success=True, data=[]).to_dict()), 200
            try:
                event_type = request.args.get("type")
                limit = min(int(request.args.get("limit", 50)), 200)
                q = session.query(EventLog).order_by(EventLog.created_at.desc())
                if event_type:
                    q = q.filter(EventLog.event_type == event_type)
                rows = q.limit(limit).all()
                data = [
                    {
                        "id": r.id,
                        "event_type": r.event_type,
                        "source": r.source,
                        "payload": r.payload or {},
                        "correlation_id": r.correlation_id,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ]
                return (
                    jsonify(
                        APIResponse(
                            success=True, data=data, metadata={"count": len(data)}
                        ).to_dict()
                    ),
                    200,
                )
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Get events error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _get_benefits_plans(self):
        """GET /api/v2/benefits/plans – List all active benefits plans."""
        try:
            from src.core.database import BenefitsPlan

            session = self._get_db_session()
            if not session:
                return jsonify(APIResponse(success=True, data=[]).to_dict()), 200
            try:
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
                return (
                    jsonify(
                        APIResponse(
                            success=True, data=data, metadata={"count": len(data)}
                        ).to_dict()
                    ),
                    200,
                )
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Get benefits plans error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _get_benefits_enrollments(self):
        """GET /api/v2/benefits/enrollments – List current employee's enrollments."""
        try:
            from src.core.database import BenefitsEnrollment, BenefitsPlan

            session = self._get_db_session()
            if not session:
                return jsonify(APIResponse(success=True, data=[]).to_dict()), 200
            try:
                employee, role = self._get_current_employee(session)
                if not employee:
                    return jsonify(APIResponse(success=True, data=[]).to_dict()), 200
                enrollments = (
                    session.query(BenefitsEnrollment).filter_by(employee_id=employee.id).all()
                )
                data = []
                for e in enrollments:
                    plan = session.query(BenefitsPlan).filter_by(id=e.plan_id).first()
                    data.append(
                        {
                            "id": e.id,
                            "plan_id": e.plan_id,
                            "plan_name": plan.name if plan else "Unknown",
                            "plan_type": plan.plan_type if plan else "unknown",
                            "coverage_level": e.coverage_level,
                            "status": e.status,
                            "enrolled_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
                        }
                    )
                return (
                    jsonify(
                        APIResponse(
                            success=True, data=data, metadata={"count": len(data)}
                        ).to_dict()
                    ),
                    200,
                )
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Get benefits enrollments error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _get_onboarding_checklist(self):
        """GET /api/v2/onboarding/checklist – List onboarding tasks for current employee."""
        try:
            from src.core.database import OnboardingChecklist

            session = self._get_db_session()
            if not session:
                return jsonify(APIResponse(success=True, data=[]).to_dict()), 200
            try:
                employee, role = self._get_current_employee(session)
                if not employee:
                    return jsonify(APIResponse(success=True, data=[]).to_dict()), 200
                tasks = session.query(OnboardingChecklist).filter_by(employee_id=employee.id).all()
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
                return (
                    jsonify(
                        APIResponse(
                            success=True, data=data, metadata={"count": len(data)}
                        ).to_dict()
                    ),
                    200,
                )
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Get onboarding checklist error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _get_performance_reviews(self):
        """GET /api/v2/performance/reviews – List reviews for current employee."""
        try:
            from src.core.database import PerformanceReview

            session = self._get_db_session()
            if not session:
                return jsonify(APIResponse(success=True, data=[]).to_dict()), 200
            try:
                employee, role = self._get_current_employee(session)
                if not employee:
                    return jsonify(APIResponse(success=True, data=[]).to_dict()), 200
                reviews = session.query(PerformanceReview).filter_by(employee_id=employee.id).all()
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
                return (
                    jsonify(
                        APIResponse(
                            success=True, data=data, metadata={"count": len(data)}
                        ).to_dict()
                    ),
                    200,
                )
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Get performance reviews error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _get_performance_goals(self):
        """GET /api/v2/performance/goals – List goals for current employee."""
        try:
            from src.core.database import PerformanceGoal

            session = self._get_db_session()
            if not session:
                return jsonify(APIResponse(success=True, data=[]).to_dict()), 200
            try:
                employee, role = self._get_current_employee(session)
                if not employee:
                    return jsonify(APIResponse(success=True, data=[]).to_dict()), 200
                goals = session.query(PerformanceGoal).filter_by(employee_id=employee.id).all()
                data = [
                    {
                        "id": gl.id,
                        "title": gl.title,
                        "description": gl.description,
                        "category": gl.category,
                        "status": gl.status,
                        "target_date": gl.target_date.isoformat() if gl.target_date else None,
                        "progress_pct": gl.progress_pct,
                    }
                    for gl in goals
                ]
                return (
                    jsonify(
                        APIResponse(
                            success=True, data=data, metadata={"count": len(data)}
                        ).to_dict()
                    ),
                    200,
                )
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Get performance goals error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _log_request(self, method: str, endpoint: str, success: bool) -> None:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": method,
            "endpoint": endpoint,
            "success": success,
        }
        self.request_log.append(log_entry)
        logger.info(f"API: {method} {endpoint} - {'OK' if success else 'FAILED'}")

    def get_request_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.request_log[-limit:]

    def get_blueprint(self) -> Blueprint:
        return self.blueprint

    # ------------------------------------------------------------------
    # Wave 6 – Chat History & Document Upload
    # ------------------------------------------------------------------

    def _get_chat_history(self):
        """GET /api/v2/chat/history – Retrieve user's chat conversation history."""
        try:
            from src.core.database import ChatConversation, ChatMessage

            session = self._get_db_session()
            if not session:
                # No database; return empty history
                return jsonify(APIResponse(success=True, data={"conversations": []}).to_dict()), 200
            try:
                employee, role = self._get_current_employee(session)
                if not employee:
                    return (
                        jsonify(APIResponse(success=True, data={"conversations": []}).to_dict()),
                        200,
                    )

                conversations = (
                    session.query(ChatConversation)
                    .filter_by(employee_id=employee.id)
                    .order_by(ChatConversation.created_at.desc())
                    .all()
                )

                data = []
                for conv in conversations:
                    messages = (
                        session.query(ChatMessage)
                        .filter_by(conversation_id=conv.id)
                        .order_by(ChatMessage.created_at.asc())
                        .all()
                    )

                    data.append(
                        {
                            "id": conv.id,
                            "title": conv.title,
                            "created_at": conv.created_at.isoformat() if conv.created_at else None,
                            "messages": [
                                {
                                    "id": msg.id,
                                    "role": msg.role,
                                    "content": msg.content,
                                    "timestamp": (
                                        msg.created_at.isoformat() if msg.created_at else None
                                    ),
                                }
                                for msg in messages
                            ],
                        }
                    )

                return (
                    jsonify(APIResponse(success=True, data={"conversations": data}).to_dict()),
                    200,
                )
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Get chat history error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _save_chat_history(self):
        """POST /api/v2/chat/history – Save a chat conversation."""
        try:
            from src.core.database import ChatConversation, ChatMessage

            data = request.get_json() or {}

            session = self._get_db_session()
            if not session:
                # No database; just acknowledge
                return jsonify(APIResponse(success=True, data={"saved": False}).to_dict()), 200

            try:
                employee, role = self._get_current_employee(session)
                if not employee:
                    return (
                        jsonify(APIResponse(success=False, error="Employee not found").to_dict()),
                        404,
                    )

                conversation_id = data.get("conversation_id")
                title = data.get("title", "Chat Conversation")
                messages = data.get("messages", [])

                # Find or create conversation
                conv = session.query(ChatConversation).filter_by(id=conversation_id).first()
                if not conv:
                    conv = ChatConversation(
                        id=conversation_id, employee_id=employee.id, title=title
                    )
                    session.add(conv)

                # Clear existing messages
                session.query(ChatMessage).filter_by(conversation_id=conversation_id).delete()

                # Add new messages
                for msg in messages:
                    chat_msg = ChatMessage(
                        conversation_id=conversation_id,
                        role=msg.get("role", "user"),
                        content=msg.get("content", ""),
                    )
                    session.add(chat_msg)

                session.commit()
                logger.info(f"Saved {len(messages)} messages for conversation {conversation_id}")
                return (
                    jsonify(
                        APIResponse(
                            success=True, data={"saved": True, "count": len(messages)}
                        ).to_dict()
                    ),
                    200,
                )
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Save chat history error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500

    def _upload_document(self):
        """POST /api/v2/documents/upload – Upload a document file."""
        try:
            import os
            from datetime import datetime
            from werkzeug.utils import secure_filename

            # Configuration
            UPLOAD_FOLDER = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "documents"
            )
            ALLOWED_EXTENSIONS = {"pdf", "docx", "jpg", "jpeg", "png", "gif"}
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

            # Ensure upload folder exists
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)

            if "file" not in request.files:
                return jsonify(APIResponse(success=False, error="No file provided").to_dict()), 400

            file = request.files["file"]
            if not file or file.filename == "":
                return jsonify(APIResponse(success=False, error="No file selected").to_dict()), 400

            # Validate file extension
            filename = secure_filename(file.filename)
            ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
            if ext not in ALLOWED_EXTENSIONS:
                return (
                    jsonify(
                        APIResponse(success=False, error=f"File type .{ext} not allowed").to_dict()
                    ),
                    400,
                )

            # Check file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            if file_size > MAX_FILE_SIZE:
                return (
                    jsonify(
                        APIResponse(success=False, error="File size exceeds 10MB limit").to_dict()
                    ),
                    400,
                )

            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            filepath = os.path.join(UPLOAD_FOLDER, unique_filename)

            # Save file
            file.save(filepath)

            logger.info(f"Document uploaded: {unique_filename} ({file_size} bytes)")

            return (
                jsonify(
                    APIResponse(
                        success=True,
                        data={
                            "filename": unique_filename,
                            "original_name": filename,
                            "size": file_size,
                            "uploaded_at": datetime.utcnow().isoformat(),
                            "url": f"/api/v2/documents/download/{unique_filename}",
                        },
                    ).to_dict()
                ),
                200,
            )

        except Exception as e:
            logger.error(f"Document upload error: {e}")
            return jsonify(APIResponse(success=False, error=str(e)).to_dict()), 500
