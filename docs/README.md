# Documentation - HR Multi-Agent Intelligence Platform

Welcome to the complete documentation suite for the HR Multi-Agent Intelligence Platform. This directory contains comprehensive guides for different audiences.

---

## Documentation Files

### 1. **API_REFERENCE.md** (20 KB, 1,051 lines)
**For:** Backend developers, API consumers, integrations

Complete REST API documentation including:
- Authentication (JWT login, register, refresh flows)
- All 11 module groups with endpoints:
  - Auth, Profile, Dashboard, Leave, Workflows, Documents
  - Employees, Analytics, Notifications, Chat/AI, Agents, Health
- Request/response examples with actual JSON payloads
- Authentication headers and JWT token details
- Rate limiting (60 requests/minute per IP)
- Standard error format and HTTP status codes
- Error codes and meanings
- Pagination, date formats, CORS policy
- Changelog and support information

**Key Endpoints Documented:**
- POST /api/v2/auth/login, /register, /refresh
- GET/PUT /api/v2/profile
- GET /api/v2/metrics, /metrics/export
- GET /api/v2/leave/balance, /history; POST /leave/request
- GET /api/v2/workflows/pending; POST /approve, /reject
- GET /api/v2/documents/templates; POST /generate
- GET /api/v2/employees, PUT /employees/:id
- GET /api/v2/notifications, /notifications/stream (SSE)
- POST /api/v2/query (AI queries)
- GET /api/v2/agents, /health

---

### 2. **ARCHITECTURE.md** (22 KB, 719 lines)
**For:** System architects, senior engineers, technical leads

Complete system architecture with:
- High-level architecture diagram (Mermaid graph)
  - Clients → Load Balancer → Nginx → Flask → Services
- Component architecture breakdown
  - Frontend layer (React.js SPA)
  - API layer with 11 route groups
  - Middleware stack (5 layers)
- Agent architecture with Mermaid diagram
  - Router Agent (orchestrator)
  - 5 Specialist agents: Leave, Policy, Onboarding, Analytics, Compliance
- Database schema (Mermaid ER diagram)
  - 9 key tables with relationships
  - Employee, AuthSession, LeaveRequest, Workflow, Conversation, etc.
- RAG pipeline explanation
  - Document embedding, ChromaDB vector search
  - Semantic retrieval and LLM generation with sources
- Server-Sent Events (SSE) flow diagram
  - Real-time notification architecture
- Complete directory structure tree (80+ files mapped)
- Deployment architecture (Docker Compose, Kubernetes)
- Security architecture (JWT, RBAC, encryption, compliance)
- Performance optimization strategies
- Monitoring & observability (metrics, logging, tracing)
- Disaster recovery procedures (RTO/RPO)

---

### 3. **DEVELOPER_GUIDE.md** (20 KB, 901 lines)
**For:** Developers, DevOps engineers, QA engineers

Complete setup and development guide including:
- Prerequisites (Python 3.10+, Node 20+, PostgreSQL, Docker)
- Quick start (7 steps: clone, venv, pip install, npm install, .env, migrate, run)
- Environment variables reference (50+ variables documented)
  - Flask, Database, Auth, OpenAI, ChromaDB, Redis, Email, Slack, Teams
  - HRIS, Logging, Rate limiting, Features
- Docker setup (docker-compose.yml with 5 services)
- Running tests (unit, integration, E2E with Playwright)
- Database migrations (Alembic commands and best practices)
- Adding new endpoints (4-step template with example code)
- Adding new agents (3-step template with base class extension)
- Database model changes (SQLAlchemy, migrations, testing)
- Deployment checklist (pre, staging, production, post)
- Development tools (code quality, debugging, API testing, DB inspection)
- Common development tasks (features, debugging agents, RAG inspection)
- Performance optimization (query optimization, caching, response optimization, async)
- Troubleshooting (8 common issues with solutions)
- IDE setup (VS Code extensions and PyCharm configuration)
- Resources and documentation links

---

### 4. **USER_GUIDE.md** (19 KB, 719 lines)
**For:** End users (employees, managers, HR admins)

Comprehensive user guide organized by role:

**Employee Section:**
- Dashboard overview
- Leave management (checking balance, requesting, history)
- Profile management (viewing, updating)
- AI chat assistant (asking questions, conversation features)
- Documents (downloading certificates, managing)
- Notifications (viewing, types, real-time updates)
- Settings (password, 2FA, preferences, data export)

**Manager Section (includes all employee + ...):**
- Team dashboard
- Workflow approvals (leave requests, documents, training, etc.)
- Employee directory (team view)
- Team-level analytics and reports

**HR Administrator Section (includes all manager + ...):**
- Full employee directory (company-wide)
- Document management (templates, generation, versioning)
- Company-wide analytics and dashboards
- Compliance and audit (audit trails, privacy requests)

**Additional Sections:**
- Common tasks by role (daily, weekly, monthly)
- Mobile usage (responsive design, features, limitations)
- Troubleshooting (8 common issues with steps)
- Tips & best practices (for each role)
- Support options (in-app help, HR, IT, status page)
- Data privacy & security (encryption, 2FA, incident reporting)
- Glossary (15 key terms)
- FAQ (12 frequently asked questions)

---

## Quick Navigation

### By Role

**👨‍💼 Employee?**
→ Start with [USER_GUIDE.md - Employee Features](USER_GUIDE.md#employee-features)

**👔 Manager?**
→ Start with [USER_GUIDE.md - Manager Features](USER_GUIDE.md#manager-features)

**👩‍💼 HR Administrator?**
→ Start with [USER_GUIDE.md - HR Administrator Features](USER_GUIDE.md#hr-administrator-features)

### By Task

**🔌 Integrate with the API?**
→ [API_REFERENCE.md](API_REFERENCE.md)

**🏗️ Understanding the system?**
→ [ARCHITECTURE.md](ARCHITECTURE.md)

**👨‍💻 Setting up development?**
→ [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)

**📱 Using the platform?**
→ [USER_GUIDE.md](USER_GUIDE.md)

---

## Documentation Summary

| Document | Purpose | Audience | Size | Topics |
|----------|---------|----------|------|--------|
| API_REFERENCE.md | API documentation | Developers | 20 KB | Auth, endpoints, examples, errors |
| ARCHITECTURE.md | System design | Architects | 22 KB | Components, agents, DB, security |
| DEVELOPER_GUIDE.md | Development setup | Developers | 20 KB | Setup, tests, deployment, debugging |
| USER_GUIDE.md | User instructions | End users | 19 KB | Features, tasks, troubleshooting |

**Total Documentation:** ~82 KB, 4,043 lines

---

## Key Features Documented

### Authentication & Security
- JWT token flow
- Role-based access control (RBAC)
- Two-factor authentication
- Data encryption
- GDPR & CCPA compliance

### API Endpoints (50+)
- Authentication (3 endpoints)
- Profile (2 endpoints)
- Leave (3 endpoints)
- Workflows (3 endpoints)
- Documents (2 endpoints)
- Employees (2 endpoints)
- Analytics (2 endpoints)
- Notifications (2 endpoints)
- Chat/AI (1 endpoint)
- Agents (1 endpoint)
- Health (1 endpoint)
- Plus admin and export endpoints

### Multi-Agent System
- Router Agent (orchestrator)
- Leave Agent
- Policy Agent
- Onboarding Agent
- Analytics Agent
- Compliance Agent

### Database
- 9 core tables
- Relationships and constraints documented
- Migration procedures
- Backup/recovery strategies

### Deployment
- Docker Compose (development)
- Kubernetes (production)
- CI/CD integration points
- Monitoring setup

---

## How to Keep Documentation Updated

### When Adding New Features
1. Update API_REFERENCE.md with new endpoints
2. Update ARCHITECTURE.md if changing system design
3. Update USER_GUIDE.md if affecting end users
4. Update DEVELOPER_GUIDE.md if adding setup/deployment steps

### When Changing API
1. Update endpoint details in API_REFERENCE.md
2. Update request/response examples
3. Update error codes if applicable
4. Update authentication flow if changed

### When Updating Code
1. Update DEVELOPER_GUIDE.md with setup changes
2. Update deployment checklist
3. Update troubleshooting if known issues resolved

---

## Maintenance Schedule

- **Weekly:** Review recent changes and update docs
- **Monthly:** Full documentation review and validation
- **Quarterly:** Comprehensive update and reorganization
- **Annually:** Major documentation revision

---

## Contributing to Documentation

### Guidelines
1. Use clear, concise language
2. Include practical examples
3. Add code snippets where helpful
4. Use Mermaid diagrams for visual concepts
5. Keep formatting consistent
6. Use markdown best practices

### Format Standards
- Headers: H1 for main sections, H2 for subsections
- Code: Use triple backticks with language specification
- Links: Use relative paths for internal links
- Tables: Use markdown table format
- Examples: Show both request and response

---

## Support & Questions

- **Documentation Issues:** Create GitHub issue with "docs" label
- **API Questions:** Refer to API_REFERENCE.md and error responses
- **Architecture Questions:** Refer to ARCHITECTURE.md and DEVELOPER_GUIDE.md
- **User Questions:** Refer to USER_GUIDE.md and FAQ
- **General Questions:** Contact support@company.com

---

## Related Documents

- IMPLEMENTATION_SUMMARY.md - Project implementation overview
- QUICK_REFERENCE.md - Quick lookup tables and shortcuts
- VERIFICATION_REPORT.md - System verification and testing

---

**Last Updated:** February 15, 2025
**Documentation Version:** 2.0
**Platform Version:** 2.0

