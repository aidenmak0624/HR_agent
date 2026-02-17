"""Expanded org seed data — 70-employee tech company with realistic hierarchy.

Based on research of mid-size tech company structures (Stripe, HubSpot, Shopify).
Org: "TechNova Inc." — a 70-person B2B SaaS company.

Departments (7):
  Engineering (18), Sales (11), Customer Success (7), Product (3),
  Marketing (4), Human Resources (3), Finance & Ops (3), Executive (2)

Management layers:
  C-Suite → VP/Director → Manager → Senior IC → IC → Junior/Intern

Leave policy by seniority:
  C-Suite/VP:   20 vacation, 12 sick, 5 personal
  Director/Mgr: 18 vacation, 10 sick, 5 personal
  Senior IC:    15 vacation, 10 sick, 5 personal
  IC:           12 vacation, 10 sick, 3 personal
  Junior/Intern: 10 vacation, 8 sick, 3 personal
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── Org chart: list of (hris_id, first, last, email, dept, role_level, manager_hris_id, hire_date)
# manager_hris_id = None → top-level (CEO)

ORG_CHART = [
    # ────────────── EXECUTIVE ──────────────
    (
        "EXEC-001",
        "Michael",
        "Chang",
        "michael.chang@company.com",
        "Executive",
        "hr_admin",
        None,
        "2018-01-10",
    ),
    (
        "EXEC-002",
        "Lisa",
        "Park",
        "lisa.park@company.com",
        "Executive",
        "hr_admin",
        "EXEC-001",
        "2018-06-15",
    ),
    # ────────────── ENGINEERING (18) ──────────────
    (
        "ENG-001",
        "Sarah",
        "Chen",
        "sarah.chen@company.com",
        "Engineering",
        "manager",
        "EXEC-001",
        "2019-03-01",
    ),  # VP Engineering
    (
        "ENG-002",
        "David",
        "Kim",
        "david.kim@company.com",
        "Engineering",
        "manager",
        "ENG-001",
        "2020-01-15",
    ),  # EM - Backend
    (
        "ENG-003",
        "Maria",
        "Santos",
        "maria.santos@company.com",
        "Engineering",
        "manager",
        "ENG-001",
        "2020-04-01",
    ),  # EM - Frontend
    (
        "ENG-004",
        "James",
        "Wilson",
        "james.wilson@company.com",
        "Engineering",
        "employee",
        "ENG-002",
        "2020-06-15",
    ),  # Senior BE
    (
        "ENG-005",
        "Priya",
        "Sharma",
        "priya.sharma@company.com",
        "Engineering",
        "employee",
        "ENG-002",
        "2021-01-10",
    ),  # BE
    (
        "ENG-006",
        "Alex",
        "Nguyen",
        "alex.nguyen@company.com",
        "Engineering",
        "employee",
        "ENG-002",
        "2021-08-01",
    ),  # BE
    (
        "ENG-007",
        "Chris",
        "Taylor",
        "chris.taylor@company.com",
        "Engineering",
        "employee",
        "ENG-002",
        "2022-03-15",
    ),  # BE
    (
        "ENG-008",
        "Fatima",
        "Al-Hassan",
        "fatima.alhassan@company.com",
        "Engineering",
        "employee",
        "ENG-002",
        "2023-06-01",
    ),  # Junior BE
    (
        "ENG-009",
        "Ryan",
        "O'Brien",
        "ryan.obrien@company.com",
        "Engineering",
        "employee",
        "ENG-003",
        "2020-09-01",
    ),  # Senior FE
    (
        "ENG-010",
        "Yuki",
        "Tanaka",
        "yuki.tanaka@company.com",
        "Engineering",
        "employee",
        "ENG-003",
        "2021-05-15",
    ),  # FE
    (
        "ENG-011",
        "Sophie",
        "Mueller",
        "sophie.mueller@company.com",
        "Engineering",
        "employee",
        "ENG-003",
        "2022-01-10",
    ),  # FE
    (
        "ENG-012",
        "Omar",
        "Hassan",
        "omar.hassan@company.com",
        "Engineering",
        "employee",
        "ENG-003",
        "2023-09-01",
    ),  # Junior FE
    (
        "ENG-013",
        "Kevin",
        "Zhang",
        "kevin.zhang@company.com",
        "Engineering",
        "employee",
        "ENG-001",
        "2020-07-15",
    ),  # DevOps Lead
    (
        "ENG-014",
        "Nina",
        "Petrova",
        "nina.petrova@company.com",
        "Engineering",
        "employee",
        "ENG-013",
        "2022-02-01",
    ),  # DevOps
    (
        "ENG-015",
        "Tom",
        "Anderson",
        "tom.anderson@company.com",
        "Engineering",
        "employee",
        "ENG-001",
        "2021-03-01",
    ),  # QA Lead
    (
        "ENG-016",
        "Aisha",
        "Mohammed",
        "aisha.mohammed@company.com",
        "Engineering",
        "employee",
        "ENG-015",
        "2022-06-15",
    ),  # QA
    (
        "ENG-017",
        "Jake",
        "Rivera",
        "jake.rivera@company.com",
        "Engineering",
        "employee",
        "ENG-015",
        "2023-01-10",
    ),  # QA
    (
        "ENG-018",
        "Mei",
        "Lin",
        "mei.lin@company.com",
        "Engineering",
        "employee",
        "ENG-002",
        "2024-06-01",
    ),  # Intern
    # ────────────── PRODUCT (3) ──────────────
    (
        "PRD-001",
        "Rachel",
        "Green",
        "rachel.green@company.com",
        "Product",
        "manager",
        "EXEC-001",
        "2019-08-01",
    ),  # VP Product
    (
        "PRD-002",
        "Daniel",
        "Foster",
        "daniel.foster@company.com",
        "Product",
        "employee",
        "PRD-001",
        "2021-02-15",
    ),  # Senior PM
    (
        "PRD-003",
        "Lauren",
        "Mitchell",
        "lauren.mitchell@company.com",
        "Product",
        "employee",
        "PRD-001",
        "2022-07-01",
    ),  # PM
    # ────────────── SALES (11) ──────────────
    (
        "SLS-001",
        "Robert",
        "Thompson",
        "robert.thompson@company.com",
        "Sales",
        "manager",
        "EXEC-001",
        "2019-05-01",
    ),  # VP Sales
    (
        "SLS-002",
        "Jessica",
        "Martinez",
        "jessica.martinez@company.com",
        "Sales",
        "manager",
        "SLS-001",
        "2020-08-15",
    ),  # Sales Mgr - Enterprise
    (
        "SLS-003",
        "Brandon",
        "Lee",
        "brandon.lee@company.com",
        "Sales",
        "manager",
        "SLS-001",
        "2021-01-10",
    ),  # SDR Manager
    (
        "SLS-004",
        "Amanda",
        "Clark",
        "amanda.clark@company.com",
        "Sales",
        "employee",
        "SLS-002",
        "2021-04-01",
    ),  # Enterprise AE
    (
        "SLS-005",
        "Marcus",
        "Brown",
        "marcus.brown@company.com",
        "Sales",
        "employee",
        "SLS-002",
        "2021-09-15",
    ),  # Mid-Market AE
    (
        "SLS-006",
        "Tiffany",
        "Davis",
        "tiffany.davis@company.com",
        "Sales",
        "employee",
        "SLS-002",
        "2022-06-01",
    ),  # AE
    (
        "SLS-007",
        "Nathan",
        "Garcia",
        "nathan.garcia@company.com",
        "Sales",
        "employee",
        "SLS-003",
        "2022-01-15",
    ),  # SDR
    (
        "SLS-008",
        "Olivia",
        "Wright",
        "olivia.wright@company.com",
        "Sales",
        "employee",
        "SLS-003",
        "2022-08-01",
    ),  # SDR
    (
        "SLS-009",
        "Derek",
        "Johnson",
        "derek.johnson@company.com",
        "Sales",
        "employee",
        "SLS-003",
        "2023-03-15",
    ),  # SDR
    (
        "SLS-010",
        "Samantha",
        "Hall",
        "samantha.hall@company.com",
        "Sales",
        "employee",
        "SLS-001",
        "2021-11-01",
    ),  # RevOps
    (
        "SLS-011",
        "Tyler",
        "Young",
        "tyler.young@company.com",
        "Sales",
        "employee",
        "SLS-002",
        "2024-01-15",
    ),  # Junior AE
    # ────────────── MARKETING (4) ──────────────
    (
        "MKT-001",
        "Jennifer",
        "Adams",
        "jennifer.adams@company.com",
        "Marketing",
        "manager",
        "EXEC-001",
        "2020-02-01",
    ),  # Dir of Marketing
    (
        "MKT-002",
        "Brian",
        "Cooper",
        "brian.cooper@company.com",
        "Marketing",
        "employee",
        "MKT-001",
        "2021-06-15",
    ),  # Product Mktg Mgr
    (
        "MKT-003",
        "Ashley",
        "Turner",
        "ashley.turner@company.com",
        "Marketing",
        "employee",
        "MKT-001",
        "2022-03-01",
    ),  # Content/Demand Gen
    (
        "MKT-004",
        "Ethan",
        "Walker",
        "ethan.walker@company.com",
        "Marketing",
        "employee",
        "MKT-001",
        "2023-07-15",
    ),  # Growth Specialist
    # ────────────── CUSTOMER SUCCESS (7) ──────────────
    (
        "CS-001",
        "Michelle",
        "Robinson",
        "michelle.robinson@company.com",
        "Customer Success",
        "manager",
        "EXEC-001",
        "2020-05-01",
    ),  # Dir of CS
    (
        "CS-002",
        "Andrew",
        "Scott",
        "andrew.scott@company.com",
        "Customer Success",
        "employee",
        "CS-001",
        "2021-03-15",
    ),  # Senior CSM
    (
        "CS-003",
        "Diana",
        "Phillips",
        "diana.phillips@company.com",
        "Customer Success",
        "employee",
        "CS-001",
        "2021-10-01",
    ),  # CSM
    (
        "CS-004",
        "Jason",
        "Campbell",
        "jason.campbell@company.com",
        "Customer Success",
        "employee",
        "CS-001",
        "2022-04-15",
    ),  # CSM
    (
        "CS-005",
        "Laura",
        "Evans",
        "laura.evans@company.com",
        "Customer Success",
        "employee",
        "CS-001",
        "2022-11-01",
    ),  # Implementation
    (
        "CS-006",
        "Patrick",
        "Reed",
        "patrick.reed@company.com",
        "Customer Success",
        "employee",
        "CS-001",
        "2023-02-15",
    ),  # Support
    (
        "CS-007",
        "Monica",
        "Stewart",
        "monica.stewart@company.com",
        "Customer Success",
        "employee",
        "CS-001",
        "2023-08-01",
    ),  # Support
    # ────────────── HUMAN RESOURCES (3) ──────────────
    (
        "HR-001",
        "Emily",
        "Rodriguez",
        "emily.rodriguez@company.com",
        "Human Resources",
        "hr_admin",
        "EXEC-001",
        "2019-01-15",
    ),  # VP People
    (
        "HR-002",
        "Sandra",
        "Morales",
        "sandra.morales@company.com",
        "Human Resources",
        "hr_admin",
        "HR-001",
        "2021-07-01",
    ),  # HR Manager
    (
        "HR-003",
        "Kevin",
        "Patel",
        "kevin.patel@company.com",
        "Human Resources",
        "employee",
        "HR-001",
        "2022-09-15",
    ),  # HR Coordinator
    # ────────────── FINANCE & OPS (3) ──────────────
    (
        "FIN-001",
        "Richard",
        "Baker",
        "richard.baker@company.com",
        "Finance",
        "manager",
        "EXEC-002",
        "2019-11-01",
    ),  # CFO/Controller
    (
        "FIN-002",
        "Catherine",
        "Diaz",
        "catherine.diaz@company.com",
        "Finance",
        "employee",
        "FIN-001",
        "2021-09-15",
    ),  # Finance Manager
    (
        "FIN-003",
        "Victor",
        "Ruiz",
        "victor.ruiz@company.com",
        "Finance",
        "employee",
        "FIN-001",
        "2023-04-01",
    ),  # Finance Analyst
    # ────────────── ADDITIONAL EMPLOYEES (reaching ~70) ──────────────
    # John Smith is in the original seed — we keep him as a known employee
    (
        "EMP-001",
        "John",
        "Smith",
        "john.smith@company.com",
        "Engineering",
        "employee",
        "ENG-002",
        "2023-01-15",
    ),
]

# Total: 2 exec + 18 eng + 3 product + 11 sales + 4 mkt + 7 CS + 3 HR + 3 finance + 1 (John) = 52
# We add 15 more to reach ~67

EXTRA_EMPLOYEES = [
    (
        "ENG-019",
        "Lucas",
        "Fernandez",
        "lucas.fernandez@company.com",
        "Engineering",
        "employee",
        "ENG-003",
        "2024-01-15",
    ),
    (
        "ENG-020",
        "Hannah",
        "Brooks",
        "hannah.brooks@company.com",
        "Engineering",
        "employee",
        "ENG-002",
        "2024-02-01",
    ),
    (
        "SLS-012",
        "Jordan",
        "White",
        "jordan.white@company.com",
        "Sales",
        "employee",
        "SLS-003",
        "2024-03-01",
    ),
    (
        "SLS-013",
        "Megan",
        "Lewis",
        "megan.lewis@company.com",
        "Sales",
        "employee",
        "SLS-002",
        "2024-04-15",
    ),
    (
        "CS-008",
        "Connor",
        "Murphy",
        "connor.murphy@company.com",
        "Customer Success",
        "employee",
        "CS-001",
        "2024-02-15",
    ),
    (
        "CS-009",
        "Isabella",
        "Flores",
        "isabella.flores@company.com",
        "Customer Success",
        "employee",
        "CS-002",
        "2024-05-01",
    ),
    (
        "MKT-005",
        "Dylan",
        "Reed",
        "dylan.reed@company.com",
        "Marketing",
        "employee",
        "MKT-001",
        "2024-06-01",
    ),
    (
        "ENG-021",
        "Zara",
        "Khan",
        "zara.khan@company.com",
        "Engineering",
        "employee",
        "ENG-001",
        "2021-10-15",
    ),  # Staff Engineer
    (
        "PRD-004",
        "Steven",
        "Howard",
        "steven.howard@company.com",
        "Product",
        "employee",
        "PRD-001",
        "2024-01-10",
    ),  # Associate PM
    (
        "FIN-004",
        "Angela",
        "Torres",
        "angela.torres@company.com",
        "Finance",
        "employee",
        "FIN-001",
        "2024-03-15",
    ),  # Ops Coordinator
    (
        "ENG-022",
        "Raj",
        "Patel",
        "raj.patel@company.com",
        "Engineering",
        "employee",
        "ENG-003",
        "2023-11-01",
    ),
    (
        "CS-010",
        "Emma",
        "Watson",
        "emma.watson@company.com",
        "Customer Success",
        "employee",
        "CS-001",
        "2024-07-01",
    ),
    (
        "SLS-014",
        "Carlos",
        "Mendez",
        "carlos.mendez@company.com",
        "Sales",
        "employee",
        "SLS-003",
        "2024-08-01",
    ),
    (
        "ENG-023",
        "Lily",
        "Chen",
        "lily.chen@company.com",
        "Engineering",
        "employee",
        "ENG-002",
        "2024-09-01",
    ),
    (
        "HR-004",
        "Grace",
        "Kim",
        "grace.kim@company.com",
        "Human Resources",
        "employee",
        "HR-001",
        "2024-10-01",
    ),
]

ALL_EMPLOYEES = ORG_CHART + EXTRA_EMPLOYEES  # Total ≈ 67


def _leave_allowance(role_level: str, hire_date_str: str) -> tuple:
    """Return (vacation_total, sick_total, personal_total) based on role & tenure."""
    hire = datetime.strptime(hire_date_str, "%Y-%m-%d")
    tenure_years = (datetime(2026, 1, 1) - hire).days / 365.25

    if role_level == "hr_admin":
        base_v, s, p = 20, 12, 5
    elif role_level == "manager":
        base_v, s, p = 18, 10, 5
    else:
        base_v, s, p = 12, 10, 3

    # Tenure bonus: +1 vacation per 2 full years (cap at +5)
    bonus = min(int(tenure_years // 2), 5)
    return base_v + bonus, s, p


def seed_expanded_org() -> None:
    """Seed the database with the full 67-employee org chart.

    Handles manager_id resolution via two-pass:
      Pass 1: Create all Employee rows (manager_id=None).
      Pass 2: Link managers by looking up hris_id→id mapping.
    """
    import bcrypt
    from src.core.database import Employee, LeaveBalance, SessionLocal

    if SessionLocal is None:
        logger.warning("Cannot seed expanded org — DB not initialised")
        return

    session = SessionLocal()
    try:
        # Check if expanded seed already ran (look for a VP-level employee)
        marker = session.query(Employee).filter_by(hris_id="ENG-001").first()
        if marker:
            count = session.query(Employee).count()
            logger.info(f"Expanded org already seeded ({count} employees)")
            return

        password_hash = bcrypt.hashpw(b"demo123", bcrypt.gensalt()).decode("utf-8")

        # ── Pass 1: insert all employees with manager_id=None ──
        hris_to_obj: dict[str, Employee] = {}

        for hris_id, first, last, email, dept, role, mgr_hris, hire_str in ALL_EMPLOYEES:
            # If employee already exists (e.g. john.smith from old seed), update them
            existing = session.query(Employee).filter_by(email=email).first()
            if existing:
                existing.hris_id = hris_id
                existing.department = dept
                existing.role_level = role
                existing.hire_date = datetime.strptime(hire_str, "%Y-%m-%d")
                hris_to_obj[hris_id] = existing
                continue

            emp = Employee(
                hris_id=hris_id,
                hris_source="internal",
                first_name=first,
                last_name=last,
                email=email,
                department=dept,
                role_level=role,
                manager_id=None,
                hire_date=datetime.strptime(hire_str, "%Y-%m-%d"),
                status="active",
                password_hash=password_hash,
            )
            session.add(emp)
            hris_to_obj[hris_id] = emp

        session.flush()  # assign primary-key IDs

        # ── Pass 2: link managers ──
        for hris_id, _, _, _, _, _, mgr_hris, _ in ALL_EMPLOYEES:
            if mgr_hris and mgr_hris in hris_to_obj:
                hris_to_obj[hris_id].manager_id = hris_to_obj[mgr_hris].id

        session.flush()

        # ── Pass 3: create leave balances ──
        for hris_id, _, _, _, _, role, _, hire_str in ALL_EMPLOYEES:
            emp = hris_to_obj[hris_id]
            existing_bal = session.query(LeaveBalance).filter_by(employee_id=emp.id).first()
            if existing_bal:
                continue

            vt, st, pt = _leave_allowance(role, hire_str)
            # Randomise some usage for realism
            vu = random.randint(0, max(1, vt // 3))
            su = random.randint(0, max(1, st // 4))
            pu = random.randint(0, max(1, pt // 3))

            session.add(
                LeaveBalance(
                    employee_id=emp.id,
                    vacation_total=vt,
                    vacation_used=vu,
                    sick_total=st,
                    sick_used=su,
                    personal_total=pt,
                    personal_used=pu,
                )
            )

        session.commit()
        count = session.query(Employee).count()
        logger.info(f"✅ Expanded org seeded: {count} employees across 7 departments")

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to seed expanded org: {e}")
        raise
    finally:
        session.close()
