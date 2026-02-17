"""
HRIS-003: Custom Database HRIS Connector implementation.

This module implements the HRISConnector interface for external databases,
using SQLAlchemy for database abstraction and read-only SQL queries.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

from .hris_interface import (
    HRISConnector,
    Employee,
    LeaveBalance,
    LeaveRequest,
    OrgNode,
    BenefitsPlan,
    EmployeeStatus,
    LeaveType,
    LeaveStatus,
    PlanType,
    ConnectorError,
    ConnectionError,
    NotFoundError,
)

logger = logging.getLogger(__name__)


class CustomDBConnector(HRISConnector):
    """
    Custom Database HRIS Connector.

    Implements HRISConnector interface using SQLAlchemy for database
    abstraction. All queries are read-only with parameterized statements.
    """

    def __init__(self, connection_string: str, schema_mapping: Dict[str, str]):
        """
        Initialize Custom DB connector.

        Args:
            connection_string: SQLAlchemy connection string
                (e.g., 'postgresql://user:pass@localhost/hrdb')
            schema_mapping: Dictionary mapping unified field names to
                source table.column names. Should include:
                - employee_table: Source employee table name
                - id_column: Employee ID column name
                - first_name_column: First name column
                - last_name_column: Last name column
                - email_column: Email column
                - department_column: Department column
                - job_title_column: Job title column
                - manager_id_column: Manager ID column
                - hire_date_column: Hire date column
                - status_column: Status column
                - location_column: Location column
                - phone_column: Phone column
                - leave_balance_table: Leave balance table name
                - leave_requests_table: Leave requests table name
                - benefits_table: Benefits table name

        Raises:
            ValueError: If connection_string or schema_mapping is invalid
            ConnectionError: If unable to connect to database
        """
        if not connection_string:
            raise ValueError("connection_string cannot be empty")
        if not schema_mapping:
            raise ValueError("schema_mapping cannot be empty")

        self.connection_string = connection_string
        self.schema_mapping = schema_mapping

        try:
            self.engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                echo=False,
                connect_args={"timeout": 10},
            )

            # Register connection event for read-only transactions
            @event.listens_for(self.engine, "connect")
            def receive_connect(dbapi_connection, connection_record):
                """Set connection to read-only."""
                cursor = dbapi_connection.cursor()
                try:
                    # Try PostgreSQL syntax
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                    cursor.execute("SET TRANSACTION READ ONLY")
                except Exception:
                    # For other databases, attempt similar read-only setup
                    try:
                        cursor.execute("SET SESSION TRANSACTION READ ONLY")
                    except Exception:
                        logger.warning("Could not set read-only mode for connection")
                cursor.close()

            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info(f"Connected to database: {self.connection_string}")

        except SQLAlchemyError as e:
            logger.error(f"Failed to connect to database: {e}")
            raise ConnectionError(f"Failed to connect to database: {e}")

    def get_employee(self, employee_id: str) -> Optional[Employee]:
        """
        Retrieve employee from database.

        Args:
            employee_id: Employee ID

        Returns:
            Employee object or None if not found

        Raises:
            ConnectionError: If unable to connect to database
        """
        table = self.schema_mapping.get("employee_table")
        id_col = self.schema_mapping.get("id_column")

        if not table or not id_col:
            raise ConnectorError("schema_mapping missing employee_table or id_column")

        query = f"SELECT * FROM {table} WHERE {id_col} = :emp_id LIMIT 1"

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {"emp_id": employee_id})
                row = result.fetchone()

                if not row:
                    return None

                return self._map_employee_row(row)

        except SQLAlchemyError as e:
            logger.error(f"Database query failed: {e}")
            raise ConnectionError(f"Database query failed: {e}")

    def search_employees(self, filters: Dict[str, Any]) -> List[Employee]:
        """
        Search employees in database with filters.

        Args:
            filters: Filter dictionary (e.g., {"department": "Sales"})

        Returns:
            List of Employee objects

        Raises:
            ConnectionError: If unable to connect to database
        """
        table = self.schema_mapping.get("employee_table")
        if not table:
            raise ConnectorError("schema_mapping missing employee_table")

        # Build WHERE clause from filters
        where_conditions = []
        params = {}

        if filters.get("department"):
            dept_col = self.schema_mapping.get("department_column", "department")
            where_conditions.append(f"{dept_col} = :department")
            params["department"] = filters["department"]

        if filters.get("status"):
            status_col = self.schema_mapping.get("status_column", "status")
            where_conditions.append(f"{status_col} = :status")
            params["status"] = filters["status"]

        if filters.get("location"):
            loc_col = self.schema_mapping.get("location_column", "location")
            where_conditions.append(f"{loc_col} = :location")
            params["location"] = filters["location"]

        if filters.get("job_title"):
            title_col = self.schema_mapping.get("job_title_column", "job_title")
            where_conditions.append(f"{title_col} = :job_title")
            params["job_title"] = filters["job_title"]

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        query = f"SELECT * FROM {table} WHERE {where_clause}"

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params)
                rows = result.fetchall()

                employees = []
                for row in rows:
                    employees.append(self._map_employee_row(row))

                return employees

        except SQLAlchemyError as e:
            logger.error(f"Database query failed: {e}")
            raise ConnectionError(f"Database query failed: {e}")

    def get_leave_balance(self, employee_id: str) -> List[LeaveBalance]:
        """
        Get leave balance from database.

        Args:
            employee_id: Employee ID

        Returns:
            List of LeaveBalance objects

        Raises:
            ConnectionError: If unable to connect to database
        """
        table = self.schema_mapping.get("leave_balance_table")
        if not table:
            logger.warning("leave_balance_table not in schema_mapping")
            return []

        # Assume standard column names if not specified
        query = f"""
            SELECT * FROM {table}
            WHERE employee_id = :emp_id
        """

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {"emp_id": employee_id})
                rows = result.fetchall()

                balances = []
                for row in rows:
                    balance = LeaveBalance(
                        employee_id=employee_id,
                        leave_type=LeaveType(row[2].lower()) if len(row) > 2 else LeaveType.PTO,
                        total_days=float(row[3] or 0) if len(row) > 3 else 0.0,
                        used_days=float(row[4] or 0) if len(row) > 4 else 0.0,
                        pending_days=float(row[5] or 0) if len(row) > 5 else 0.0,
                        available_days=float(row[6] or 0) if len(row) > 6 else 0.0,
                    )
                    balances.append(balance)

                return balances

        except SQLAlchemyError as e:
            logger.error(f"Database query failed: {e}")
            raise ConnectionError(f"Database query failed: {e}")
        except (IndexError, ValueError) as e:
            logger.error(f"Error mapping leave balance row: {e}")
            return []

    def get_leave_requests(
        self, employee_id: str, status: Optional[str] = None
    ) -> List[LeaveRequest]:
        """
        Get leave requests from database.

        Args:
            employee_id: Employee ID
            status: Optional status filter

        Returns:
            List of LeaveRequest objects

        Raises:
            ConnectionError: If unable to connect to database
        """
        table = self.schema_mapping.get("leave_requests_table")
        if not table:
            logger.warning("leave_requests_table not in schema_mapping")
            return []

        where_clause = "employee_id = :emp_id"
        params = {"emp_id": employee_id}

        if status:
            where_clause += " AND status = :status"
            params["status"] = status

        query = f"SELECT * FROM {table} WHERE {where_clause}"

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params)
                rows = result.fetchall()

                requests_list = []
                for row in rows:
                    try:
                        request = LeaveRequest(
                            id=str(row[0]),  # id
                            employee_id=employee_id,
                            leave_type=LeaveType(row[2].lower()),  # leave_type
                            start_date=row[3],  # start_date
                            end_date=row[4],  # end_date
                            status=LeaveStatus(row[5].lower()),  # status
                            reason=row[6] if len(row) > 6 else None,  # reason
                            approver_id=row[7] if len(row) > 7 else None,  # approver_id
                            submitted_at=row[8] if len(row) > 8 else datetime.now(),  # submitted_at
                        )
                        requests_list.append(request)
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error mapping leave request row: {e}")

                return requests_list

        except SQLAlchemyError as e:
            logger.error(f"Database query failed: {e}")
            raise ConnectionError(f"Database query failed: {e}")

    def submit_leave_request(self, request: LeaveRequest) -> LeaveRequest:
        """
        Submit leave request (read-only connector - raises error).

        Args:
            request: LeaveRequest object

        Returns:
            Never returns due to read-only restriction

        Raises:
            ConnectorError: Always, as connector is read-only
        """
        raise ConnectorError("CustomDBConnector is read-only. Cannot submit leave requests.")

    def get_org_chart(self, department: Optional[str] = None) -> List[OrgNode]:
        """
        Get organization chart using recursive CTE.

        Args:
            department: Optional department filter

        Returns:
            List of OrgNode objects representing hierarchy

        Raises:
            ConnectionError: If unable to connect to database
        """
        table = self.schema_mapping.get("employee_table")
        id_col = self.schema_mapping.get("id_column")
        manager_col = self.schema_mapping.get("manager_id_column", "manager_id")
        first_name_col = self.schema_mapping.get("first_name_column", "first_name")
        last_name_col = self.schema_mapping.get("last_name_column", "last_name")
        title_col = self.schema_mapping.get("job_title_column", "job_title")
        dept_col = self.schema_mapping.get("department_column", "department")

        if not table or not id_col:
            raise ConnectorError("schema_mapping missing employee_table or id_column")

        # PostgreSQL recursive CTE for hierarchy
        # This needs to be adapted for other databases
        query = f"""
            WITH RECURSIVE org_tree AS (
                SELECT
                    {id_col},
                    {first_name_col},
                    {last_name_col},
                    {title_col},
                    {dept_col},
                    {manager_col},
                    0 as level
                FROM {table}
                WHERE {manager_col} IS NULL
                
                UNION ALL
                
                SELECT
                    e.{id_col},
                    e.{first_name_col},
                    e.{last_name_col},
                    e.{title_col},
                    e.{dept_col},
                    e.{manager_col},
                    ot.level + 1
                FROM {table} e
                INNER JOIN org_tree ot ON e.{manager_col} = ot.{id_col}
            )
            SELECT * FROM org_tree
            ORDER BY level, {id_col}
        """

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                rows = result.fetchall()

                # Build hierarchy from flat result
                node_map = {}
                for row in rows:
                    emp_id = str(row[0])
                    node = OrgNode(
                        employee_id=emp_id,
                        name=f"{row[1]} {row[2]}",
                        title=row[3] or "",
                        department=row[4] or "",
                        direct_reports=[],
                    )
                    node_map[emp_id] = node

                # Build parent-child relationships
                for row in rows:
                    emp_id = str(row[0])
                    manager_id = str(row[5]) if row[5] else None

                    if manager_id and manager_id in node_map:
                        node_map[manager_id].direct_reports.append(node_map[emp_id])

                # Get roots and apply department filter if needed
                roots = [
                    node
                    for node in node_map.values()
                    if not any(node in parent.direct_reports for parent in node_map.values())
                ]

                if department:
                    roots = [node for node in roots if node.department == department]

                return roots

        except SQLAlchemyError as e:
            logger.error(f"Database query failed: {e}")
            raise ConnectionError(f"Database query failed: {e}")

    def get_benefits(self, employee_id: str) -> List[BenefitsPlan]:
        """
        Get benefits plans from database.

        Args:
            employee_id: Employee ID

        Returns:
            List of BenefitsPlan objects

        Raises:
            ConnectionError: If unable to connect to database
        """
        table = self.schema_mapping.get("benefits_table")
        if not table:
            logger.warning("benefits_table not in schema_mapping")
            return []

        query = f"""
            SELECT * FROM {table}
            WHERE employee_id = :emp_id
        """

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {"emp_id": employee_id})
                rows = result.fetchall()

                plans = []
                for row in rows:
                    try:
                        plan = BenefitsPlan(
                            id=str(row[0]),  # id
                            name=row[1] or "",  # name
                            plan_type=PlanType(row[2].lower()),  # plan_type
                            coverage_level=row[3] or "Employee",  # coverage_level
                            employee_cost=float(row[4] or 0),  # employee_cost
                            employer_cost=float(row[5] or 0),  # employer_cost
                        )
                        plans.append(plan)
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error mapping benefits row: {e}")

                return plans

        except SQLAlchemyError as e:
            logger.error(f"Database query failed: {e}")
            raise ConnectionError(f"Database query failed: {e}")

    def health_check(self) -> bool:
        """
        Check if connector can reach database.

        Returns:
            True if healthy, False otherwise
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database health check passed")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def close(self) -> None:
        """Close database connection pool."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection pool closed")

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _map_employee_row(self, row: Any) -> Employee:
        """
        Map database row to Employee model.

        Args:
            row: SQLAlchemy row object

        Returns:
            Employee object

        Raises:
            ValueError: If required fields are missing
        """
        # Get column mapping, use reasonable defaults
        row_dict = dict(row._mapping)

        id_col = self.schema_mapping.get("id_column", "id")
        first_col = self.schema_mapping.get("first_name_column", "first_name")
        last_col = self.schema_mapping.get("last_name_column", "last_name")
        email_col = self.schema_mapping.get("email_column", "email")
        dept_col = self.schema_mapping.get("department_column", "department")
        title_col = self.schema_mapping.get("job_title_column", "job_title")
        manager_col = self.schema_mapping.get("manager_id_column", "manager_id")
        hire_col = self.schema_mapping.get("hire_date_column", "hire_date")
        status_col = self.schema_mapping.get("status_column", "status")
        loc_col = self.schema_mapping.get("location_column", "location")
        phone_col = self.schema_mapping.get("phone_column", "phone")

        # Extract values with fallbacks
        emp_id = str(row_dict.get(id_col, ""))
        hire_date = row_dict.get(hire_col)
        if not isinstance(hire_date, datetime):
            hire_date = datetime.now()

        return Employee(
            id=emp_id,
            hris_id=emp_id,
            first_name=row_dict.get(first_col, ""),
            last_name=row_dict.get(last_col, ""),
            email=row_dict.get(email_col, ""),
            department=row_dict.get(dept_col, ""),
            job_title=row_dict.get(title_col, ""),
            manager_id=row_dict.get(manager_col),
            hire_date=hire_date,
            status=EmployeeStatus(row_dict.get(status_col, "active").lower()),
            location=row_dict.get(loc_col, ""),
            phone=row_dict.get(phone_col),
        )
