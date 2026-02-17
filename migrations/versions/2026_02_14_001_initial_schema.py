"""Initial schema — all 15 core models.

Revision ID: 001_initial
Revises:
Create Date: 2026-02-14

This migration creates the full database schema for the HR Multi-Agent
Intelligence Platform, matching the SQLAlchemy models in src/core/database.py
and all repository models.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── employees (core user table) ───────────────────────
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hris_id", sa.String(255), nullable=False, unique=True),
        sa.Column("hris_source", sa.String(50), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("department", sa.String(255), nullable=False),
        sa.Column("role_level", sa.String(50), nullable=False),
        sa.Column("manager_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("hire_date", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_employees_email", "employees", ["email"])
    op.create_index("ix_employees_department", "employees", ["department"])

    # ── auth_sessions ─────────────────────────────────────
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("role_level", sa.String(50), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── audit_logs ────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── conversations ─────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("agent_type", sa.String(100), nullable=True),
        sa.Column("query", sa.String(2000), nullable=False),
        sa.Column("response_summary", sa.String(2000), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("tools_used", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── conversation_messages ─────────────────────────────
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_call", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── leave_requests ────────────────────────────────────
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("leave_type", sa.String(50), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── leave_balances ────────────────────────────────────
    op.create_table(
        "leave_balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("vacation_total", sa.Float(), nullable=False, server_default="15"),
        sa.Column("vacation_used", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sick_total", sa.Float(), nullable=False, server_default="10"),
        sa.Column("sick_used", sa.Float(), nullable=False, server_default="0"),
        sa.Column("personal_total", sa.Float(), nullable=False, server_default="5"),
        sa.Column("personal_used", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── generated_documents ───────────────────────────────
    op.create_table(
        "generated_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("template_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── benefits_plans ────────────────────────────────────
    op.create_table(
        "benefits_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_name", sa.String(200), nullable=False),
        sa.Column("plan_type", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(200), nullable=True),
        sa.Column("coverage_details", sa.JSON(), nullable=True),
        sa.Column("monthly_cost", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── benefits_enrollments ──────────────────────────────
    op.create_table(
        "benefits_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("benefits_plans.id"), nullable=False),
        sa.Column("coverage_level", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── onboarding_checklists ─────────────────────────────
    op.create_table(
        "onboarding_checklists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("task_name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── performance_reviews ───────────────────────────────
    op.create_table(
        "performance_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("review_period", sa.String(50), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("areas_for_improvement", sa.Text(), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── performance_goals ─────────────────────────────────
    op.create_table(
        "performance_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("progress_pct", sa.Float(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── event_logs ────────────────────────────────────────
    op.create_table(
        "event_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("correlation_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("event_logs")
    op.drop_table("performance_goals")
    op.drop_table("performance_reviews")
    op.drop_table("onboarding_checklists")
    op.drop_table("benefits_enrollments")
    op.drop_table("benefits_plans")
    op.drop_table("generated_documents")
    op.drop_table("leave_balances")
    op.drop_table("leave_requests")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
    op.drop_table("audit_logs")
    op.drop_table("auth_sessions")
    op.drop_index("ix_employees_department", "employees")
    op.drop_index("ix_employees_email", "employees")
    op.drop_table("employees")
