"""Base repository abstract class with generic ORM operations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, Generic, List, Optional, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import SessionLocal

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository for generic CRUD operations.

    Provides common database operations with automatic session management,
    error handling, and rollback on failure. Subclasses should implement
    model-specific logic.

    Type Parameters:
        T: The SQLAlchemy model type this repository manages
    """

    def __init__(self, model_class: type[T]) -> None:
        """
        Initialize repository with model class.

        Args:
            model_class: SQLAlchemy model class (e.g., WorkflowModel)
        """
        self.model_class = model_class
        logger.debug(f"Initialized {self.__class__.__name__} for {model_class.__name__}")

    @contextmanager
    def _get_session(self):
        """
        Context manager for database session.

        Yields:
            SQLAlchemy Session instance

        Raises:
            RuntimeError: If database not initialized
        """
        if SessionLocal is None:
            raise RuntimeError("Database not initialized. Call init_db() first.")

        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session error in {self.__class__.__name__}: {str(e)}")
            raise
        finally:
            session.close()

    def get(self, entity_id: int) -> Optional[T]:
        """
        Retrieve entity by ID.

        Args:
            entity_id: Primary key value

        Returns:
            Model instance or None if not found
        """
        try:
            with self._get_session() as session:
                stmt = select(self.model_class).where(self.model_class.id == entity_id)
                result = session.execute(stmt).scalar_one_or_none()
                return result
        except Exception as e:
            logger.error(f"Error getting {self.model_class.__name__} by ID {entity_id}: {str(e)}")
            return None

    def list(self, filters: Optional[Dict[str, Any]] = None, limit: int = 100, offset: int = 0) -> List[T]:
        """
        List entities with optional filters.

        Args:
            filters: Dictionary of column:value pairs for filtering
            limit: Maximum results to return
            offset: Number of results to skip

        Returns:
            List of model instances
        """
        try:
            with self._get_session() as session:
                stmt = select(self.model_class)

                if filters:
                    for key, value in filters.items():
                        if hasattr(self.model_class, key):
                            stmt = stmt.where(getattr(self.model_class, key) == value)

                stmt = stmt.limit(limit).offset(offset)
                results = session.execute(stmt).scalars().all()
                return results
        except Exception as e:
            logger.error(f"Error listing {self.model_class.__name__}: {str(e)}")
            return []

    def create(self, data: Dict[str, Any]) -> Optional[T]:
        """
        Create new entity.

        Args:
            data: Dictionary of field values

        Returns:
            Created model instance or None on error
        """
        try:
            with self._get_session() as session:
                entity = self.model_class(**data)
                session.add(entity)
                session.flush()
                logger.info(f"Created {self.model_class.__name__}: id={getattr(entity, 'id', 'unknown')}")
                return entity
        except Exception as e:
            logger.error(f"Error creating {self.model_class.__name__}: {str(e)}")
            return None

    def update(self, entity_id: int, data: Dict[str, Any]) -> Optional[T]:
        """
        Update entity by ID.

        Args:
            entity_id: Primary key value
            data: Dictionary of fields to update

        Returns:
            Updated model instance or None on error
        """
        try:
            with self._get_session() as session:
                entity = session.execute(
                    select(self.model_class).where(self.model_class.id == entity_id)
                ).scalar_one_or_none()

                if not entity:
                    logger.warning(f"{self.model_class.__name__} not found: id={entity_id}")
                    return None

                for key, value in data.items():
                    if hasattr(entity, key):
                        setattr(entity, key, value)

                session.flush()
                logger.info(f"Updated {self.model_class.__name__}: id={entity_id}")
                return entity
        except Exception as e:
            logger.error(f"Error updating {self.model_class.__name__} {entity_id}: {str(e)}")
            return None

    def delete(self, entity_id: int) -> bool:
        """
        Delete entity by ID.

        Args:
            entity_id: Primary key value

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_session() as session:
                entity = session.execute(
                    select(self.model_class).where(self.model_class.id == entity_id)
                ).scalar_one_or_none()

                if not entity:
                    logger.warning(f"{self.model_class.__name__} not found: id={entity_id}")
                    return False

                session.delete(entity)
                logger.info(f"Deleted {self.model_class.__name__}: id={entity_id}")
                return True
        except Exception as e:
            logger.error(f"Error deleting {self.model_class.__name__} {entity_id}: {str(e)}")
            return False

    def exists(self, entity_id: int) -> bool:
        """
        Check if entity exists.

        Args:
            entity_id: Primary key value

        Returns:
            True if entity exists, False otherwise
        """
        try:
            with self._get_session() as session:
                stmt = select(self.model_class).where(self.model_class.id == entity_id)
                result = session.execute(stmt).scalar_one_or_none()
                return result is not None
        except Exception as e:
            logger.error(f"Error checking existence of {self.model_class.__name__}: {str(e)}")
            return False

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count entities matching filters.

        Args:
            filters: Dictionary of column:value pairs for filtering

        Returns:
            Number of matching entities
        """
        try:
            with self._get_session() as session:
                from sqlalchemy import func
                stmt = select(func.count(self.model_class.id))

                if filters:
                    for key, value in filters.items():
                        if hasattr(self.model_class, key):
                            stmt = stmt.where(getattr(self.model_class, key) == value)

                result = session.execute(stmt).scalar()
                return result or 0
        except Exception as e:
            logger.error(f"Error counting {self.model_class.__name__}: {str(e)}")
            return 0
