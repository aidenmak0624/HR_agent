"""Database index creation and management.

Creates indexes on frequently queried columns for performance optimization.
Uses SQLAlchemy text() to execute CREATE INDEX IF NOT EXISTS statements.
"""

import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def ensure_indexes(engine: Engine) -> None:
    """Create indexes on frequently queried columns.

    Args:
        engine: SQLAlchemy engine instance
    """
    with engine.connect() as connection:
        # Employee indexes
        indexes = [
            # Employees table
            ("idx_employees_email", "employees", "email", "UNIQUE"),
            ("idx_employees_department", "employees", "department", ""),
            ("idx_employees_manager_id", "employees", "manager_id", ""),
            ("idx_employees_role_level", "employees", "role_level", ""),
            ("idx_employees_status", "employees", "status", ""),

            # Leave requests table (if exists)
            ("idx_leave_requests_employee_id", "leave_requests", "employee_id", ""),
            ("idx_leave_requests_status", "leave_requests", "status", ""),
            ("idx_leave_requests_created_at", "leave_requests", "created_at", ""),

            # Leave balances table (if exists)
            ("idx_leave_balances_employee_id", "leave_balances", "employee_id", "UNIQUE"),

            # Auth sessions table (if exists)
            ("idx_auth_sessions_user_id", "auth_sessions", "user_id", ""),
            ("idx_auth_sessions_expires_at", "auth_sessions", "expires_at", ""),

            # Additional useful indexes
            ("idx_employees_hire_date", "employees", "hire_date", ""),
            ("idx_employees_created_at", "employees", "created_at", ""),
        ]

        for index_name, table_name, column_name, unique_flag in indexes:
            try:
                # Build CREATE INDEX statement
                unique_str = "UNIQUE " if unique_flag == "UNIQUE" else ""
                sql = f"""
                    CREATE {unique_str}INDEX IF NOT EXISTS {index_name}
                    ON {table_name}({column_name})
                """

                connection.execute(text(sql))
                logger.info(f"✅ Index created: {index_name} on {table_name}.{column_name}")

            except Exception as e:
                # Log but don't fail - index might already exist
                logger.warning(f"⚠️  Could not create index {index_name}: {e}")

        connection.commit()
        logger.info("✅ Database indexes ensured")


def drop_indexes(engine: Engine) -> None:
    """Drop all created indexes (useful for cleanup during testing).

    Args:
        engine: SQLAlchemy engine instance
    """
    with engine.connect() as connection:
        index_names = [
            "idx_employees_email",
            "idx_employees_department",
            "idx_employees_manager_id",
            "idx_employees_role_level",
            "idx_employees_status",
            "idx_leave_requests_employee_id",
            "idx_leave_requests_status",
            "idx_leave_requests_created_at",
            "idx_leave_balances_employee_id",
            "idx_auth_sessions_user_id",
            "idx_auth_sessions_expires_at",
            "idx_employees_hire_date",
            "idx_employees_created_at",
        ]

        for index_name in index_names:
            try:
                sql = f"DROP INDEX IF EXISTS {index_name}"
                connection.execute(text(sql))
                logger.info(f"✅ Index dropped: {index_name}")
            except Exception as e:
                logger.warning(f"⚠️  Could not drop index {index_name}: {e}")

        connection.commit()
        logger.info("✅ All indexes dropped")
