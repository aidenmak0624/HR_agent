"""SQLAlchemy database module with async support and connection pooling."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class TimestampMixin:
    """Mixin for timestamp columns (created_at, updated_at)."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Employee(Base, TimestampMixin):
    """Employee model representing users in the system.

    Attributes:
        id: Primary key
        hris_id: External HRIS system ID
        hris_source: Source system (e.g., 'bamboohr', 'workday')
        first_name: Employee first name
        last_name: Employee last name
        email: Employee email address (unique)
        department: Department name
        role_level: User role level (employee/manager/hr_generalist/hr_admin)
        manager_id: Self-referencing FK to manager
        hire_date: Employment start date
        status: Employment status (active/inactive/terminated)
    """

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    hris_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hris_source: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    role_level: Mapped[str] = mapped_column(String(50), nullable=False)
    manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    hire_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<Employee(id={self.id}, email={self.email}, role={self.role_level})>"


class AuthSession(Base, TimestampMixin):
    """Authentication session model for tracking user sessions.

    Attributes:
        id: Primary key
        user_id: FK to Employee
        token_hash: Hashed JWT token for verification
        role_level: User role at time of session creation
        ip_address: Client IP address
        user_agent: Client user agent string
        expires_at: Session expiration timestamp
        revoked_at: Session revocation timestamp (if revoked)
    """

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role_level: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(512), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<AuthSession(user_id={self.user_id}, expires_at={self.expires_at})>"


class AuditLog(Base):
    """Audit log model for tracking user actions.

    Attributes:
        id: Primary key
        user_id: FK to Employee
        action: Action type (create/read/update/delete)
        resource_type: Type of resource affected
        resource_id: ID of affected resource
        details: JSON details of the action
        ip_address: Client IP address
        timestamp: Action timestamp
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<AuditLog(user_id={self.user_id}, action={self.action}, resource={self.resource_type})>"


class Conversation(Base, TimestampMixin):
    """Conversation model for tracking agent interactions.

    Attributes:
        id: Primary key
        user_id: FK to Employee
        agent_type: Type of agent (benefits/payroll/leave/general)
        query: User's original query
        response_summary: Summary of the response provided
        confidence_score: Agent's confidence in response (0.0-1.0)
        tools_used: JSON array of tools/APIs called
        started_at: Conversation start timestamp
        completed_at: Conversation completion timestamp
        resolved: Whether the issue was resolved
    """

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    query: Mapped[str] = mapped_column(String(2000), nullable=False)
    response_summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    confidence_score: Mapped[float] = mapped_column(default=0.0, nullable=False)
    tools_used: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved: Mapped[bool] = mapped_column(default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<Conversation(user_id={self.user_id}, agent={self.agent_type}, resolved={self.resolved})>"


class ConversationMessage(Base):
    """Conversation message model for tracking message history.

    Attributes:
        id: Primary key
        conversation_id: FK to Conversation
        role: Message role (user/assistant/tool)
        content: Message content
        tool_call: JSON details of tool calls (if any)
        timestamp: Message timestamp
    """

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(String(5000), nullable=False)
    tool_call: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ConversationMessage(conversation_id={self.conversation_id}, role={self.role})>"


class LeaveRequest(Base, TimestampMixin):
    """Leave request model for tracking employee leave applications."""

    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    leave_type: Mapped[str] = mapped_column(String(50), nullable=False)  # vacation/sick/personal
    start_date: Mapped[str] = mapped_column(String(20), nullable=False)  # YYYY-MM-DD
    end_date: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending/approved/rejected
    approved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<LeaveRequest(id={self.id}, employee_id={self.employee_id}, type={self.leave_type}, status={self.status})>"


class LeaveBalance(Base, TimestampMixin):
    """Leave balance model tracking available leave days per employee."""

    __tablename__ = "leave_balances"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False, unique=True
    )
    vacation_total: Mapped[int] = mapped_column(default=15, nullable=False)
    vacation_used: Mapped[int] = mapped_column(default=0, nullable=False)
    sick_total: Mapped[int] = mapped_column(default=10, nullable=False)
    sick_used: Mapped[int] = mapped_column(default=0, nullable=False)
    personal_total: Mapped[int] = mapped_column(default=5, nullable=False)
    personal_used: Mapped[int] = mapped_column(default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<LeaveBalance(employee_id={self.employee_id})>"


class GeneratedDocument(Base, TimestampMixin):
    """Generated document model for HR document tracking."""

    __tablename__ = "generated_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    template_id: Mapped[str] = mapped_column(String(50), nullable=False)
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="finalized", nullable=False)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<GeneratedDocument(id={self.id}, template={self.template_name})>"


class BenefitsPlan(Base, TimestampMixin):
    """Benefits plan available for enrollment."""

    __tablename__ = "benefits_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    plan_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # medical/dental/vision/life/retirement
    provider: Mapped[str] = mapped_column(String(200), nullable=False)
    premium_monthly: Mapped[float] = mapped_column(default=0.0, nullable=False)
    coverage_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<BenefitsPlan(id={self.id}, name={self.name}, type={self.plan_type})>"


class BenefitsEnrollment(Base, TimestampMixin):
    """Employee enrollment in a benefits plan."""

    __tablename__ = "benefits_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("benefits_plans.id"), nullable=False)
    coverage_level: Mapped[str] = mapped_column(String(50), default="employee", nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="active", nullable=False
    )  # active/waived/terminated
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<BenefitsEnrollment(employee_id={self.employee_id}, plan_id={self.plan_id}, status={self.status})>"


class OnboardingChecklist(Base, TimestampMixin):
    """Onboarding checklist item for new employees."""

    __tablename__ = "onboarding_checklists"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    task_name: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # documentation/it_setup/training/compliance
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )  # pending/in_progress/completed
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<OnboardingChecklist(employee_id={self.employee_id}, task={self.task_name}, status={self.status})>"


class PerformanceReview(Base, TimestampMixin):
    """Performance review record for an employee."""

    __tablename__ = "performance_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    review_period: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "2025-H2"
    rating: Mapped[Optional[int]] = mapped_column(nullable=True)  # 1-5 scale
    strengths: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    areas_for_improvement: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="draft", nullable=False
    )  # draft/submitted/finalized

    def __repr__(self) -> str:
        return f"<PerformanceReview(employee_id={self.employee_id}, period={self.review_period}, rating={self.rating})>"


class PerformanceGoal(Base, TimestampMixin):
    """Performance goal for an employee."""

    __tablename__ = "performance_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="professional", nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="active", nullable=False
    )  # active/completed/cancelled
    target_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    progress_pct: Mapped[int] = mapped_column(default=0, nullable=False)  # 0-100

    def __repr__(self) -> str:
        return f"<PerformanceGoal(employee_id={self.employee_id}, title={self.title}, progress={self.progress_pct}%)>"


class EventLog(Base):
    """Persisted event log for the inter-agent event bus."""

    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<EventLog(type={self.event_type}, source={self.source})>"


# Database configuration — PostgreSQL preferred, SQLite fallback for local dev
import pathlib as _pathlib
import os as _os


def _resolve_database_url() -> str:
    """Resolve DATABASE_URL from environment, preferring PostgreSQL.

    Tests PostgreSQL connectivity before committing to it.
    Falls back to SQLite if PostgreSQL is unreachable.
    """
    url = _os.environ.get("DATABASE_URL", "")
    if url and ("postgresql" in url or "postgres" in url):
        # Heroku/Supabase style: postgres:// → postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)

        # Cloud SQL Unix socket connections (e.g. ?host=/cloudsql/...)
        # skip TCP check — the proxy socket is managed by Cloud Run
        if "/cloudsql/" in url:
            logger.info(f"Using Cloud SQL Unix socket connection")
            return url

        # TCP connectivity check — fall back to SQLite if unreachable
        try:
            import socket
            from urllib.parse import urlparse

            parsed = urlparse(url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            sock = socket.create_connection((host, port), timeout=3)
            sock.close()
            return url
        except (OSError, Exception):
            _host = url.split("@")[-1].split("/")[0] if "@" in url else "unknown"
            logger.warning(f"PostgreSQL at {_host} unreachable — falling back to SQLite")
    # Fallback to SQLite for local dev without PostgreSQL
    db_path = _os.environ.get("HR_DB_PATH", "")
    if not db_path:

        def _is_dir_truly_writable(dirpath):
            """Test actual write capability (os.access can lie on FUSE mounts)."""
            _probe = _os.path.join(str(dirpath), ".write_test_probe")
            try:
                with open(_probe, "w") as f:
                    f.write("ok")
                _os.remove(_probe)
                return True
            except (OSError, IOError):
                return False

        # Pick a writable location — prefer project dir, fall back to /tmp
        _project_dir = _pathlib.Path(__file__).resolve().parent.parent.parent
        _candidate = _project_dir / "hr_platform.db"
        if _is_dir_truly_writable(_project_dir):
            db_path = str(_candidate)
        else:
            # Ensure /tmp DB is writable; use unique name if existing one isn't
            _tmp_path = "/tmp/hr_platform.db"
            if _os.path.exists(_tmp_path) and not _os.access(_tmp_path, _os.W_OK):
                _tmp_path = f"/tmp/hr_platform_{_os.getuid()}.db"
            db_path = _tmp_path
    return f"sqlite:///{db_path}"


def _resolve_async_database_url(sync_url: str) -> str:
    """Convert sync URL to async driver variant."""
    if "postgresql" in sync_url:
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)


DATABASE_URL = _resolve_database_url()
ASYNC_DATABASE_URL = _resolve_async_database_url(DATABASE_URL)
_IS_POSTGRES = "postgresql" in DATABASE_URL

logger.info(f"Database backend: {'PostgreSQL' if _IS_POSTGRES else 'SQLite'}")

# Engine instances
engine = None
async_engine = None
SessionLocal = None
AsyncSessionLocal = None


def init_sync_engine(database_url: str = DATABASE_URL) -> None:
    """Initialize synchronous database engine with connection pooling.

    Args:
        database_url: Database connection URL
    """
    global engine, SessionLocal

    is_pg = "postgresql" in database_url
    connect_args = {} if is_pg else {"check_same_thread": False}

    pool_kwargs = (
        dict(
            poolclass=QueuePool,
            pool_size=20,
            max_overflow=40,
            pool_pre_ping=True,
            pool_recycle=300,  # Recycle connections every 5 min (prevents stale PG connections)
        )
        if is_pg
        else dict(
            pool_pre_ping=True,
        )
    )

    engine = create_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
        **pool_kwargs,
    )
    SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    logger.info(f"Initialized sync database engine: {'PostgreSQL' if is_pg else 'SQLite'}")


async def init_async_engine(database_url: str = ASYNC_DATABASE_URL) -> None:
    """Initialize asynchronous database engine with connection pooling.

    Args:
        database_url: Async database connection URL
    """
    global async_engine, AsyncSessionLocal

    is_pg = "postgresql" in database_url
    connect_args = {} if is_pg else {"check_same_thread": False}

    pool_kwargs = (
        dict(
            pool_size=20,
            max_overflow=40,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        if is_pg
        else dict(
            pool_pre_ping=True,
        )
    )

    async_engine = create_async_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
        **pool_kwargs,
    )
    AsyncSessionLocal = sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    logger.info(f"Initialized async database engine: {'PostgreSQL' if is_pg else 'SQLite'}")


def get_db() -> Session:
    """Get a synchronous database session.

    Returns:
        SQLAlchemy Session instance

    Raises:
        RuntimeError: If engine not initialized
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_sync_engine() first.")
    return SessionLocal()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Get an asynchronous database session.

    Yields:
        SQLAlchemy AsyncSession instance

    Raises:
        RuntimeError: If async engine not initialized
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Async database not initialized. Call init_async_engine() first.")

    async with AsyncSessionLocal() as session:
        yield session


def init_db(database_url: str = DATABASE_URL) -> None:
    """Create all database tables and indexes.

    Args:
        database_url: Database connection URL
    """
    init_sync_engine(database_url)
    if engine is None:
        raise RuntimeError("Failed to initialize database engine")

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

    # Create database indexes for performance
    try:
        from src.core.indexes import ensure_indexes

        ensure_indexes(engine)
    except Exception as e:
        logger.warning(f"Failed to create database indexes: {e}")


def _seed_new_tables(session, demo_employees) -> None:
    """Seed benefits, onboarding, performance tables for given employees."""
    from datetime import datetime

    # Seed benefits plans
    plans = [
        BenefitsPlan(
            name="Standard Medical PPO",
            plan_type="medical",
            provider="Blue Cross",
            premium_monthly=450.00,
            coverage_details={
                "deductible": 1500,
                "copay": 30,
                "coinsurance": "80/20",
                "oop_max": 6000,
            },
        ),
        BenefitsPlan(
            name="Premium Medical PPO",
            plan_type="medical",
            provider="Blue Cross",
            premium_monthly=750.00,
            coverage_details={
                "deductible": 500,
                "copay": 15,
                "coinsurance": "90/10",
                "oop_max": 3000,
            },
        ),
        BenefitsPlan(
            name="Dental Plus",
            plan_type="dental",
            provider="Delta Dental",
            premium_monthly=45.00,
            coverage_details={
                "preventive": "100%",
                "basic": "80%",
                "major": "50%",
                "annual_max": 2000,
            },
        ),
        BenefitsPlan(
            name="Vision Care",
            plan_type="vision",
            provider="VSP",
            premium_monthly=15.00,
            coverage_details={"exam_copay": 10, "frames_allowance": 200, "contacts_allowance": 150},
        ),
        BenefitsPlan(
            name="401(k) Retirement",
            plan_type="retirement",
            provider="Fidelity",
            premium_monthly=0.0,
            coverage_details={"match_pct": 4, "vesting_years": 3, "max_contribution": 23000},
        ),
    ]
    for plan in plans:
        session.add(plan)
    session.flush()

    # Enroll demo employees in some plans
    if len(demo_employees) >= 3:
        enrollments = [
            BenefitsEnrollment(
                employee_id=demo_employees[0].id,
                plan_id=plans[0].id,
                coverage_level="employee",
                status="active",
            ),
            BenefitsEnrollment(
                employee_id=demo_employees[0].id,
                plan_id=plans[2].id,
                coverage_level="employee",
                status="active",
            ),
            BenefitsEnrollment(
                employee_id=demo_employees[1].id,
                plan_id=plans[1].id,
                coverage_level="family",
                status="active",
            ),
            BenefitsEnrollment(
                employee_id=demo_employees[1].id,
                plan_id=plans[4].id,
                coverage_level="employee",
                status="active",
            ),
            BenefitsEnrollment(
                employee_id=demo_employees[2].id,
                plan_id=plans[0].id,
                coverage_level="employee_spouse",
                status="active",
            ),
        ]
    else:
        enrollments = [
            BenefitsEnrollment(
                employee_id=demo_employees[0].id,
                plan_id=plans[0].id,
                coverage_level="employee",
                status="active",
            ),
            BenefitsEnrollment(
                employee_id=demo_employees[0].id,
                plan_id=plans[2].id,
                coverage_level="employee",
                status="active",
            ),
        ]
    for enr in enrollments:
        session.add(enr)

    # Seed onboarding checklists for first employee (newest hire)
    onboarding_tasks = [
        (
            "Complete I-9 Form",
            "documentation",
            "Submit identity and employment eligibility documents",
        ),
        (
            "Sign Employee Handbook",
            "documentation",
            "Review and digitally sign the employee handbook",
        ),
        ("Set Up Workstation", "it_setup", "Configure laptop, email, Slack, and VPN access"),
        ("Enroll in Benefits", "compliance", "Select health, dental, and vision plans"),
        (
            "Complete Security Training",
            "training",
            "Mandatory information security awareness training",
        ),
        ("Meet Your Buddy", "social", "Schedule intro coffee chat with assigned buddy"),
        ("Complete Tax Forms", "documentation", "Submit W-4 and state tax withholding forms"),
        ("Team Introduction Meeting", "social", "Attend team standup and introduce yourself"),
    ]
    for i, (name, cat, desc) in enumerate(onboarding_tasks):
        status = "completed" if i < 4 else "pending"
        session.add(
            OnboardingChecklist(
                employee_id=demo_employees[0].id,
                task_name=name,
                category=cat,
                description=desc,
                status=status,
                completed_at=datetime.utcnow() if status == "completed" else None,
            )
        )

    # Seed performance reviews
    if len(demo_employees) >= 2:
        reviews = [
            PerformanceReview(
                employee_id=demo_employees[0].id,
                reviewer_id=demo_employees[1].id,
                review_period="2025-H2",
                rating=4,
                status="finalized",
                strengths="Strong technical skills, great team collaboration",
                areas_for_improvement="Could improve documentation practices",
                comments="John has exceeded expectations in his first year",
            ),
        ]
        if len(demo_employees) >= 3:
            reviews.append(
                PerformanceReview(
                    employee_id=demo_employees[1].id,
                    reviewer_id=demo_employees[2].id,
                    review_period="2025-H2",
                    rating=5,
                    status="finalized",
                    strengths="Excellent leadership, mentoring junior engineers",
                    areas_for_improvement="Delegate more to grow team autonomy",
                    comments="Sarah is a top-performing engineering manager",
                )
            )
        for rev in reviews:
            session.add(rev)

    # Seed performance goals
    goals = [
        PerformanceGoal(
            employee_id=demo_employees[0].id,
            title="Complete AWS Solutions Architect Cert",
            description="Pass the AWS Solutions Architect Associate exam by Q2",
            category="professional",
            status="active",
            progress_pct=60,
            target_date=datetime(2026, 6, 30),
        ),
        PerformanceGoal(
            employee_id=demo_employees[0].id,
            title="Lead Feature X Release",
            description="Own end-to-end delivery of Feature X including testing and deployment",
            category="deliverable",
            status="active",
            progress_pct=35,
            target_date=datetime(2026, 4, 15),
        ),
        PerformanceGoal(
            employee_id=demo_employees[0].id,
            title="Improve Code Review Turnaround",
            description="Reduce average code review time from 48h to 24h",
            category="process",
            status="active",
            progress_pct=70,
            target_date=datetime(2026, 3, 31),
        ),
    ]
    if len(demo_employees) >= 2:
        goals.append(
            PerformanceGoal(
                employee_id=demo_employees[1].id,
                title="Grow Engineering Team",
                description="Hire 3 senior engineers and establish mentoring program",
                category="leadership",
                status="active",
                progress_pct=45,
                target_date=datetime(2026, 12, 31),
            )
        )
    for goal in goals:
        session.add(goal)


def seed_demo_data() -> None:
    """Seed database with demo accounts and leave balances.

    Creates 3 demo employees and their leave balances if they don't already exist.
    All demo accounts use password 'demo123'.
    """
    import bcrypt

    if SessionLocal is None:
        logger.warning("Cannot seed data — database not initialized")
        return

    session = SessionLocal()
    try:
        # Check if demo data already exists
        existing = session.query(Employee).filter_by(email="john.smith@company.com").first()
        if existing:
            # Check if new tables need seeding (added after initial seed)
            needs_benefits = session.query(BenefitsPlan).count() == 0
            needs_onboarding = session.query(OnboardingChecklist).count() == 0
            needs_reviews = session.query(PerformanceReview).count() == 0
            needs_goals = session.query(PerformanceGoal).count() == 0
            if not (needs_benefits or needs_onboarding or needs_reviews or needs_goals):
                logger.info("Demo data already seeded")
                return
            logger.info("Seeding new tables for existing employees...")
            demo_employees = [existing]
            # Fetch the other demo employees
            sarah = session.query(Employee).filter_by(email="sarah.chen@company.com").first()
            emily = session.query(Employee).filter_by(email="emily.rodriguez@company.com").first()
            if sarah:
                demo_employees.append(sarah)
            if emily:
                demo_employees.append(emily)
            # Jump to seeding new tables
            _seed_new_tables(session, demo_employees)
            session.commit()
            logger.info("✅ New tables seeded for existing employees")
            return

        password_hash = bcrypt.hashpw("demo123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        demo_employees = [
            Employee(
                hris_id="EMP-2024-001",
                hris_source="internal",
                first_name="John",
                last_name="Smith",
                email="john.smith@company.com",
                department="Engineering",
                role_level="employee",
                hire_date=datetime(2023, 1, 15),
                status="active",
                password_hash=password_hash,
            ),
            Employee(
                hris_id="MGR-2024-010",
                hris_source="internal",
                first_name="Sarah",
                last_name="Chen",
                email="sarah.chen@company.com",
                department="Engineering",
                role_level="manager",
                hire_date=datetime(2021, 6, 1),
                status="active",
                password_hash=password_hash,
            ),
            Employee(
                hris_id="HRA-2024-003",
                hris_source="internal",
                first_name="Emily",
                last_name="Rodriguez",
                email="emily.rodriguez@company.com",
                department="Human Resources",
                role_level="hr_admin",
                hire_date=datetime(2020, 3, 10),
                status="active",
                password_hash=password_hash,
            ),
        ]

        for emp in demo_employees:
            session.add(emp)
        session.flush()  # Get IDs assigned

        # Create leave balances
        leave_defaults = [
            (demo_employees[0].id, 15, 5, 10, 2, 5, 1),  # John
            (demo_employees[1].id, 18, 3, 10, 1, 5, 0),  # Sarah (more vacation as manager)
            (demo_employees[2].id, 18, 4, 10, 1, 5, 2),  # Emily
        ]

        for emp_id, vt, vu, st, su, pt, pu in leave_defaults:
            balance = LeaveBalance(
                employee_id=emp_id,
                vacation_total=vt,
                vacation_used=vu,
                sick_total=st,
                sick_used=su,
                personal_total=pt,
                personal_used=pu,
            )
            session.add(balance)

        # Seed new tables (benefits, onboarding, performance)
        _seed_new_tables(session, demo_employees)

        session.commit()
        logger.info(
            "✅ Demo data seeded: 3 employees + leave balances + benefits + onboarding + performance"
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to seed demo data: {e}")
    finally:
        session.close()


async def health_check() -> bool:
    """Verify database connection is healthy.

    Returns:
        True if connection is healthy, False otherwise
    """
    try:
        session = get_db()
        # Simple query to verify connection
        session.execute("SELECT 1")
        session.close()
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
