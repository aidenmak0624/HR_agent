"""Alembic migration environment configuration.

This script runs every time the alembic command is invoked and sets up
the SQLAlchemy engine and logger before migrations are executed.
"""

from __future__ import annotations

import sys
import os
import logging
from logging.config import fileConfig

# Add project root to Python path so 'src' and 'config' packages are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from config.settings import get_settings
from src.core.database import Base

# Import all models to ensure they're registered with Base
from src.core.database import (
    Employee,
    AuthSession,
    AuditLog,
    Conversation,
    ConversationMessage,
)
from src.repositories.workflow_repository import WorkflowModel, WorkflowStepModel
from src.repositories.notification_repository import NotificationModel, NotificationPreferenceModel
from src.repositories.gdpr_repository import ConsentRecordModel, DSARRequestModel, RetentionPolicyModel
from src.repositories.document_repository import DocumentTemplateModel, GeneratedDocumentModel
from src.repositories.bias_repository import BiasIncidentModel, BiasAuditReportModel
from src.repositories.dashboard_repository import DashboardModel, DashboardWidgetModel, MetricSnapshotModel

# Get Alembic config
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# Set the target metadata for autogenerate support
target_metadata = Base.metadata

# Get database URL from settings
settings = get_settings()
database_url = settings.get_database_url()

# Configure SQLAlchemy engine
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = database_url

    # Use NullPool for SQLite (QueuePool can cause issues)
    poolclass = pool.NullPool if database_url.startswith("sqlite") else pool.QueuePool

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=poolclass,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
