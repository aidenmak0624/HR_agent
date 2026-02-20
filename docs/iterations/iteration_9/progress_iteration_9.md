# Iteration 9 — Progress Report (Post-Iteration 8 Expansion)

## Overview
**Iteration**: 9 — Expanded Org, Role-Based Case Studies, Auth Upgrade & File Reorganization
**Status**: ✅ Complete
**Date**: February 8, 2026
**Key Metrics**: 67 employees | 8 departments | 50/50 case study tests | 100% pass rate

---

## Summary of Changes

This iteration expanded the platform from 3 demo users to a realistic 67-employee organization, upgraded the authentication system to resolve real users from tokens, ran 6 multi-role case studies across departments, and reorganized the project file structure.

---

## Phase 1: Expanded Organization Database

### What Changed
**New file**: `src/core/seed_org.py`
- 67 employees across 8 departments with proper management hierarchy
- Based on research of mid-size tech company structures (Stripe, HubSpot, Shopify)
- Two-pass seeding: creates all employees first, then links manager_id relationships
- Leave balances vary by seniority (C-Suite: 20 vacation, Intern: 10 vacation)
- Tenure bonus: +1 vacation day per 2 years of service

### Department Breakdown

| Department | Count | Key Roles | Hierarchy Depth |
|------------|-------|-----------|-----------------|
| Engineering | 24 | VP, 2 EMs, DevOps Lead, QA Lead, 19 ICs | 4 layers |
| Sales | 14 | VP, Sales Mgr, SDR Mgr, 11 ICs | 3 layers |
| Customer Success | 10 | Director, Sr CSM, 8 ICs | 3 layers |
| Marketing | 5 | Director, 4 ICs | 2 layers |
| Product | 4 | VP, 3 PMs | 2 layers |
| Human Resources | 4 | VP People, HR Mgr, 2 ICs | 3 layers |
| Finance | 4 | CFO, Mgr, 2 ICs | 3 layers |
| Executive | 2 | CEO, COO | Top level |

### Management Chain Examples
```
CEO (Michael Chang)
├── VP Engineering (Sarah Chen)
│   ├── EM Backend (David Kim) → 6 engineers + 1 intern
│   ├── EM Frontend (Maria Santos) → 5 engineers
│   ├── DevOps Lead (Kevin Zhang) → 1 DevOps
│   └── QA Lead (Tom Anderson) → 2 QA
├── VP Sales (Robert Thompson)
│   ├── Sales Mgr Enterprise (Jessica Martinez) → 4 AEs
│   └── SDR Manager (Brandon Lee) → 4 SDRs
├── VP People (Emily Rodriguez)
│   ├── HR Manager (Sandra Morales)
│   └── HR Coordinator (Kevin Patel)
└── CFO (Richard Baker)
    ├── Finance Manager (Catherine Diaz)
    └── Finance Analyst (Victor Ruiz)
```

### Leave Policy by Seniority

| Role Level | Vacation | Sick | Personal | Tenure Bonus |
|------------|----------|------|----------|--------------|
| C-Suite/VP | 20 | 12 | 5 | +1 per 2 years |
| Director/Manager | 18 | 10 | 5 | +1 per 2 years |
| Senior IC | 15 | 10 | 5 | +1 per 2 years |
| IC | 12 | 10 | 3 | +1 per 2 years |
| Junior/Intern | 10 | 8 | 3 | +1 per 2 years |

---

## Phase 2: Authentication System Upgrade

### What Changed

**File**: `src/app_v2.py` — `before_request()` middleware
- **Before**: Hardcoded 3 user profiles mapped to role strings ("employee" → John, "manager" → Sarah, "hr_admin" → Emily)
- **After**: Extracts employee ID from Bearer token (`token_{id}_{timestamp}` format), looks up the actual Employee record from the database, and populates `g.user_context` with real user data including `employee_id`, `email`, `name`, `role`, `department`

```python
# NEW: Extract employee ID from Bearer token
if auth_header.startswith('Bearer '):
    token = auth_header[7:].strip()
    parts = token.split('_')
    emp_id = int(parts[1])
    emp = db.query(Employee).filter_by(id=emp_id).first()
    g.user_context = {
        "user_id": str(emp.id),
        "role": emp.role_level,
        "department": emp.department,
        "employee_id": emp.id,
        "email": emp.email,
        "name": f"{emp.first_name} {emp.last_name}",
    }
```

**File**: `src/platform/api_gateway.py` — `_get_current_employee()`
- **Before**: Hardcoded email lookup based on role name
- **After**: 3-tier resolution: (1) employee_id from token → (2) email from context → (3) fallback to demo accounts for backward compatibility

```python
# Primary: look up by employee_id from token
emp_id = user_context.get("employee_id")
if emp_id:
    employee = session.query(Employee).filter_by(id=emp_id).first()
    if employee:
        return employee, role
# Secondary: email from context
# Fallback: role→demo email mapping
```

**File**: `src/app_v2.py` — Startup
- Added `from src.core.seed_org import seed_expanded_org` call after `seed_demo_data()`
- Expanded org seeds on first startup, skips if already seeded

---

## Phase 3: Chatbot Keyword Expansion

### What Changed

**File**: `src/platform/api_gateway.py` — `_static_query_fallback()`
- Added `"holiday"` keyword → policy_agent with 2026 company holiday schedule
- Added `"calendar"` keyword → policy_agent with company calendar/important dates
- These were discovered as gaps during Case Study 3 when HR Admin Emily queried for "company holiday schedule"

---

## Phase 4: Role-Based Case Studies

### Test Results: 50/50 (100%)

| # | Case Study | Roles Involved | Steps | Result |
|---|-----------|---------------|-------|--------|
| 1 | Engineering Sick Leave | Fatima (Eng IC) → David Kim (EM) | 9 | ✅ 9/9 |
| 2 | Sales Vacation Request | Nathan (SDR) → Brandon Lee (SDR Mgr) | 9 | ✅ 9/9 |
| 3 | Cross-Dept Marketing + HR Audit | Ashley (Mktg) → Jennifer (Dir Mktg) → Emily (HR VP) | 10 | ✅ 10/10 |
| 4 | Finance Leave + HR Compliance | Victor (Fin Analyst) → Richard (CFO) → Sandra (HR Mgr) | 9 | ✅ 9/9 |
| 5 | New Hire Onboarding + First Leave | Mei Lin (Intern) → David Kim (EM) | 8 | ✅ 8/8 |
| 6 | RBAC Security Boundary Test | Omar (employee blocked) → Maria (manager allowed) | 5 | ✅ 5/5 |

### Workflow Coverage
Each case study tests the full lifecycle:
1. **Employee login** → JWT token with real employee ID
2. **Chatbot queries** → Policy, benefits, payroll, onboarding questions
3. **Leave balance check** → Real DB balance for logged-in user
4. **Leave request submission** → Persisted to SQLite with correct employee_id
5. **Manager login** → Different user, correct role resolved from token
6. **Pending queue review** → Manager sees pending requests
7. **Approval** → Status updated, approved_by set, balance deducted
8. **DB verification** → Direct SQLite query confirms persistence

### Approval Chains Validated

| Department | Employee | Leave Type | Approver |
|------------|----------|-----------|----------|
| Engineering | Fatima Al-Hassan (Junior BE) | Sick 2d | David Kim (EM Backend) |
| Sales | Nathan Garcia (SDR) | Vacation 5d | Brandon Lee (SDR Mgr) |
| Marketing | Ashley Turner (Content) | Personal 1d | Jennifer Adams (Dir) |
| Finance | Victor Ruiz (Analyst) | Personal 2d | Richard Baker (CFO) |
| Engineering | Mei Lin (Intern) | Sick 1d | David Kim (EM Backend) |

### RBAC Enforcement Verified
- Employee Omar Hassan → 403 on `/workflows/pending` and `/workflows/approve`
- Manager Maria Santos → 200 on the same endpoints

---

## Phase 5: File Reorganization

### New Folder Structure
```
reports/
├── business/                     ← Stakeholder & management reports
│   ├── AI_HR_Productivity_Report.docx
│   ├── Case_Study_Report.docx
│   ├── Multi_Agent_HR_Platform_Documentation.docx
│   ├── PRD_Multi_Agent_HR_Platform.docx
│   ├── PRD_Multi_Agent_HR_Platform_v2.docx
│   ├── PRD_Gap_Analysis.docx
│   └── Roadmap_SystemDesign_CodingGuide.docx
│
├── engineering/                   ← Technical & development reports
│   ├── CHATBOT_ANALYSIS.md
│   ├── CHATBOT_TEST_REPORT.md
│   ├── HR_Agent_Multi_Agent_Analysis.docx
│   ├── HR_Platform_Architecture_Diagrams.html
│   ├── TEST_EXECUTION_SUMMARY.md
│   ├── Test_Execution_Report.docx
│   └── research.md
│
└── README.md                      ← Index with summaries and audience guide

tests/e2e/results/                 ← Test result data
├── chatbot_test_results.json
└── chatbot_test_results.csv

iteration_9/                       ← This iteration's docs
├── progress_iteration_9.md        (this file)
└── plan.md
```

### Classification Logic
| Folder | Content Type | Audience |
|--------|-------------|----------|
| `reports/business/` | PRDs, productivity reports, case studies, roadmaps | Executives, product managers, HR leadership |
| `reports/engineering/` | Architecture, test analysis, chatbot metrics, research | Developers, QA, engineering managers |
| `tests/e2e/results/` | Raw test output data (JSON, CSV) | CI/CD, automated tooling |
| `docs/development_notes/` | Dev reference docs (unchanged) | Individual developers |
| `docs/prd/` | Original PRD files (kept as-is, copies in reports/) | Product team |
| `iteration_N/` | Per-iteration progress, plans, test summaries | Project tracking |

---

## Files Modified

| File | Change | Lines Changed |
|------|--------|---------------|
| `src/core/seed_org.py` | **NEW** — 67-employee org chart with hierarchy | ~220 |
| `src/app_v2.py` | Auth middleware: real user resolution from token | ~30 |
| `src/app_v2.py` | Startup: call `seed_expanded_org()` | ~3 |
| `src/platform/api_gateway.py` | `_get_current_employee()`: 3-tier lookup | ~25 |
| `src/platform/api_gateway.py` | Added `holiday` and `calendar` keywords | ~25 |
| `reports/README.md` | **NEW** — Reports folder index | ~60 |

## Files Created

| File | Purpose |
|------|---------|
| `src/core/seed_org.py` | Expanded org seed data (67 employees, 8 depts) |
| `reports/business/Case_Study_Report.docx` | 6 case studies, 50/50 pass, org structure analysis |
| `reports/README.md` | Reports classification index |
| `iteration_9/progress_iteration_9.md` | This progress document |

---

## Database Changes

### Before (Iteration 8)
- 3 employees (John, Sarah, Emily)
- 3 leave balances
- Hardcoded role→user mapping

### After (Iteration 9)
- 67 employees across 8 departments
- 67 leave balances (seniority-adjusted)
- Real user resolution from JWT tokens
- Manager_id foreign keys creating proper org tree
- Leave requests linked to actual employee IDs from auth

### Schema (Unchanged)
No schema changes — all existing tables (`employees`, `leave_requests`, `leave_balances`, `generated_documents`, `auth_sessions`, `audit_logs`, `conversations`, `conversation_messages`) remain the same. Only data volume expanded.

---

## How to Test

```bash
# Start server (auto-seeds 67 employees on first run)
cd HR_agent && python3 run.py

# Run case studies
python3 case_studies.py

# Login as any employee
curl -X POST http://localhost:5050/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"fatima.alhassan@company.com","password":"demo123"}'

# All 67 employees use password: demo123
```

### Key Test Accounts by Department
| Email | Name | Role | Department |
|-------|------|------|------------|
| michael.chang@company.com | Michael Chang | hr_admin (CEO) | Executive |
| sarah.chen@company.com | Sarah Chen | manager (VP Eng) | Engineering |
| david.kim@company.com | David Kim | manager (EM Backend) | Engineering |
| fatima.alhassan@company.com | Fatima Al-Hassan | employee (Junior BE) | Engineering |
| robert.thompson@company.com | Robert Thompson | manager (VP Sales) | Sales |
| brandon.lee@company.com | Brandon Lee | manager (SDR Mgr) | Sales |
| nathan.garcia@company.com | Nathan Garcia | employee (SDR) | Sales |
| jennifer.adams@company.com | Jennifer Adams | manager (Dir Mktg) | Marketing |
| emily.rodriguez@company.com | Emily Rodriguez | hr_admin (VP People) | Human Resources |
| sandra.morales@company.com | Sandra Morales | hr_admin (HR Mgr) | Human Resources |
| richard.baker@company.com | Richard Baker | manager (CFO) | Finance |
| mei.lin@company.com | Mei Lin | employee (Intern) | Engineering |
