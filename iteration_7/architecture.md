# Architecture Update — Iteration 7

## Changes Introduced

### New Layer: Multi-Jurisdiction Compliance Engine

Iteration 7 adds a comprehensive compliance layer (CCPA + multi-jurisdiction), payroll data integration, document versioning, real-time WebSocket notifications, cross-agent handoff protocol, and performance optimization (connection pooling + query caching).

### Updated Request Flow

```
                         Incoming Request
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│              SECURITY MIDDLEWARE PIPELINE                │
│  CORS → Sanitizer → Rate Limiter → Security Headers     │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              AUTH + COMPLIANCE PIPELINE                   │
│                                                         │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────────┐ │
│  │   Auth   │→ │   RBAC    │→ │    PII Stripper      │ │
│  │  (JWT)   │  │ (4-tier)  │  │  (regex + rehydrate) │ │
│  └──────────┘  └───────────┘  └──────────────────────┘ │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │         COMPLIANCE CHECK (NEW)                     │ │
│  │  Multi-Jurisdiction Engine                         │ │
│  │  ├── Determine applicable jurisdictions            │ │
│  │  ├── GDPR checks (EU/UK employees)                │ │
│  │  ├── CCPA checks (California consumers)           │ │
│  │  └── Resolve conflicts (most restrictive)         │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              I18N + QUERY CACHE PIPELINE                 │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │  Language   │→ │  Cache      │→ │   Agent        │  │
│  │  Detector   │  │  Lookup     │  │   Processing   │  │
│  │  (5 langs)  │  │  (LRU/LFU) │  │   (if miss)    │  │
│  └─────────────┘  └─────────────┘  └───────┬────────┘  │
│                                             │           │
│  ┌─────────────┐  ┌─────────────┐           │           │
│  │  Cache      │← │  Translate  │←──────────┘           │
│  │  Store      │  │  Response   │                       │
│  └─────────────┘  └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

### Component Details

#### CCPA Compliance Service (`src/core/ccpa.py`)

```
CCPAComplianceService
  ├── Consumer Rights Management
  │     ├── ConsumerRight: KNOW, DELETE, OPT_OUT, NON_DISCRIMINATION, CORRECT, LIMIT
  │     └── CCPADataCategory: PERSONAL_INFO, FINANCIAL, BIOMETRIC, GEOLOCATION,
  │                            INTERNET_ACTIVITY, PROFESSIONAL, EDUCATION, INFERENCES
  │
  ├── Request Lifecycle
  │     submit_request(consumer_id, right_type, categories)
  │       → CCPARequest (status: PENDING, deadline: 45 days)
  │     verify_consumer(consumer_id, verification_data)
  │       → bool (identity verification)
  │     process_request(request_id)
  │       → dict (status + details)
  │     extend_deadline(request_id, reason)
  │       → CCPARequest (deadline + 45 days)
  │
  ├── Data Operations
  │     ├── get_data_inventory(consumer_id) → List[DataInventoryItem]
  │     ├── classify_data(data) → List[CCPADataCategory]
  │     ├── opt_out_of_sale(consumer_id) → dict
  │     └── generate_disclosure(consumer_id) → dict (12-month lookback)
  │
  └── Compliance Tracking
        ├── check_minor_consent(consumer_id, age) → dict
        ├── get_request_status(request_id) → dict
        └── get_annual_metrics() → dict
```

#### Multi-Jurisdiction Engine (`src/core/multi_jurisdiction.py`)

```
MultiJurisdictionEngine
  ├── Jurisdictions (9)
  │     US_FEDERAL, US_CALIFORNIA, US_NEW_YORK, US_ILLINOIS
  │     EU_GDPR, UK_GDPR, CANADA_PIPEDA, AUSTRALIA_APPS, BRAZIL_LGPD
  │
  ├── JurisdictionConfig (per jurisdiction)
  │     ├── data_residency_required: bool
  │     ├── breach_notification_hours: int (24-72)
  │     ├── consent_type: "opt-in" | "opt-out"
  │     ├── dpo_required: bool
  │     └── cross_border_transfer_mechanism: str
  │
  ├── determine_jurisdictions(employee_data) → List[Jurisdiction]
  │     Employee country/state → applicable jurisdictions
  │     US + California → [US_FEDERAL, US_CALIFORNIA]
  │     Germany → [EU_GDPR]
  │     UK → [UK_GDPR]
  │
  ├── check_compliance(data, jurisdictions) → List[ComplianceCheckResult]
  │     For each jurisdiction: check all requirements
  │     Result: COMPLIANT | NON_COMPLIANT | PARTIAL | NOT_APPLICABLE
  │
  ├── resolve_conflicts(results) → List[ComplianceCheckResult]
  │     Strategy: most_restrictive wins
  │     Shorter deadlines, stricter consent, more protections
  │
  └── Cross-Border Operations
        ├── get_breach_notification_deadline(jurisdictions) → shortest hours
        ├── check_cross_border_transfer(source, target, categories) → dict
        └── get_consent_requirements(jurisdictions) → most restrictive
```

#### Payroll Connector (`src/connectors/payroll_connector.py`)

```
PayrollConnector (read-only)
  ├── PayrollProvider: WORKDAY | ADP | PAYCHEX | GENERIC
  │
  ├── Authentication
  │     authenticate() → bool
  │     ├── OAuth2 token caching with automatic refresh
  │     └── API key fallback
  │
  ├── Data Retrieval
  │     ├── get_payroll_record(employee_id, pay_period) → PayrollRecord
  │     ├── get_payroll_history(employee_id, start, end) → List[PayrollRecord]
  │     ├── get_payroll_summary(employee_id, year) → PayrollSummary
  │     ├── get_deduction_breakdown(employee_id, period) → dict
  │     ├── get_tax_summary(employee_id, year) → dict
  │     └── search_records(filters) → List[PayrollRecord]
  │
  ├── Provider Field Mapping
  │     Workday: worker_id, period_start, gross_amount, ...
  │     ADP: associate_id, check_date, gross_earnings, ...
  │     Paychex: employee_number, pay_begin_date, gross, ...
  │
  └── Reliability
        ├── _make_request() with exponential backoff retry
        ├── Rate limiting awareness
        └── validate_connection() → health status
```

#### Document Versioning (`src/core/document_versioning.py`)

```
DocumentVersioningService
  ├── Document Lifecycle
  │     DRAFT → PENDING_REVIEW → APPROVED → PUBLISHED → ARCHIVED
  │                                                    → DEPRECATED
  │
  ├── Version Management
  │     create_document(title, content, author) → Document (v1.0)
  │     create_version(doc_id, content, author) → DocumentVersion (v1.1, v2.0)
  │     rollback_to_version(doc_id, version) → DocumentVersion
  │
  ├── Approval Workflow
  │     submit_for_review(doc_id, version) → status: PENDING_REVIEW
  │     approve_version(doc_id, version, approver) → status: APPROVED
  │     publish_version(doc_id, version) → status: PUBLISHED
  │
  ├── Operations
  │     compare_versions(doc_id, v_a, v_b) → unified diff
  │     search_documents(query, category, tags, status) → List[Document]
  │     get_document_history(doc_id) → List[DocumentVersion]
  │     cleanup_old_versions(doc_id) → int (removed count)
  │
  └── Audit Trail
        All operations logged with timestamps and actors
```

#### WebSocket Manager (`src/core/websocket_manager.py`)

```
WebSocketManager
  ├── Event Types
  │     NOTIFICATION | QUERY_UPDATE | AGENT_STATUS | SYSTEM_ALERT | WORKFLOW_UPDATE
  │
  ├── Connection Management
  │     connect(user_id, metadata) → ConnectionInfo
  │     disconnect(connection_id) → bool
  │     ├── Max 5 connections per user
  │     ├── Ping/pong health monitoring (30s interval)
  │     └── Stale connection cleanup
  │
  ├── Messaging
  │     send_message(connection_id, message) → bool
  │     broadcast(message, exclude_users) → int (count)
  │     send_to_user(user_id, message) → int (count)
  │     send_notification(user_id, title, body, priority) → bool
  │
  └── WebSocketMessage
        ├── event_type: WebSocketEvent
        ├── payload: dict
        ├── priority: "low" | "medium" | "high"
        ├── broadcast: bool
        └── target_user: Optional[str]
```

#### Cross-Agent Handoff Protocol (`src/agents/handoff_protocol.py`)

```
HandoffProtocol
  ├── Handoff Reasons
  │     EXPERTISE_REQUIRED | ESCALATION | WORKFLOW_CONTINUATION
  │     USER_REQUEST | CAPABILITY_MISMATCH | LOAD_BALANCING
  │
  ├── Handoff Lifecycle
  │     initiate_handoff(session, source, target, reason, context)
  │       → HandoffState (status: INITIATED)
  │     accept_handoff(handoff_id)
  │       → HandoffState (status: ACCEPTED)
  │     reject_handoff(handoff_id, reason)
  │       → HandoffState (status: REJECTED)
  │     complete_handoff(handoff_id, result)
  │       → HandoffState (status: COMPLETED)
  │
  ├── Shared State Management
  │     ┌─────────────────────────────────────┐
  │     │         SharedAgentState            │
  │     │  session_id                         │
  │     │  current_agent: "leave_agent"       │
  │     │  previous_agents: ["router","emp"]  │
  │     │  shared_context: {key: value}       │
  │     │  accumulated_facts: [...]           │
  │     │  pending_actions: [...]             │
  │     │  handoff_history: [...]             │
  │     └─────────────────────────────────────┘
  │
  │     update_shared_context(session, key, value) → SharedAgentState
  │     add_accumulated_fact(session, fact) → SharedAgentState
  │     add_pending_action(session, action) → SharedAgentState
  │
  └── Validation
        can_handoff(source, target) → bool
        Max 5 handoffs per session
        Configurable allowed_handoff_pairs
```

#### Connection Pool Manager (`src/core/connection_pool.py`)

```
ConnectionPoolManager
  ├── Pool Types: POSTGRESQL | REDIS | HTTP
  │
  ├── PoolConfig (per type)
  │     min_connections: 2    max_connections: 20
  │     max_overflow: 10      pool_timeout: 30s
  │     pool_recycle: 3600s   health_check_interval: 60s
  │
  ├── Pool Operations
  │     initialize_pool(pool_type) → bool
  │     get_connection(pool_type) → connection
  │     release_connection(pool_type, conn) → bool
  │     resize_pool(pool_type, new_max) → bool
  │     drain_pool(pool_type) → int (count)
  │     shutdown() → bool (graceful)
  │
  ├── Health Monitoring
  │     health_check(pool_type) → Dict[PoolType, ConnectionHealth]
  │     ├── PostgreSQL: SELECT 1
  │     ├── Redis: PING
  │     └── HTTP: Connection validation
  │
  └── Analytics
        get_pool_stats() → Dict[PoolType, PoolStats]
        get_optimal_pool_size() → recommendation (peak × 1.2)
        get_status() → overall health report
```

#### Query Cache Service (`src/core/query_cache.py`)

```
QueryCacheService
  ├── Strategies: LRU | TTL | LFU | WRITE_THROUGH | WRITE_BEHIND
  │
  ├── Dual Backend
  │     ┌─────────────────────────────────────┐
  │     │  Local Cache (Dict)                 │
  │     │  ├── Fast access                    │
  │     │  ├── Memory-limited                 │
  │     │  └── Strategy-based eviction        │
  │     └─────────────────┬───────────────────┘
  │                       │ sync
  │     ┌─────────────────▼───────────────────┐
  │     │  Redis Backend (Optional)           │
  │     │  ├── Distributed caching            │
  │     │  ├── JSON serialization             │
  │     │  └── Graceful fallback              │
  │     └─────────────────────────────────────┘
  │
  ├── Core Operations
  │     get(key) → value | None
  │     set(key, value, ttl, tags) → bool
  │     delete(key) → bool
  │     get_or_set(key, factory_fn, ttl) → value (cache-aside)
  │
  ├── Bulk Operations
  │     bulk_get(keys) → Dict[key, value]
  │     bulk_set(items, ttl) → int (count)
  │
  ├── Invalidation
  │     invalidate_by_tag(tag) → int (count)
  │     invalidate_by_pattern(regex) → int (count)
  │     clear(namespace) → int (count)
  │
  ├── Eviction (10% at a time)
  │     LRU: Sort by last_accessed, evict oldest
  │     LFU: Sort by access_count, evict least frequent
  │     TTL: Sort by expires_at, evict soonest expiring
  │
  └── Warmup
        warmup(queries) → int (pre-populated count)
```

---

## Full System Architecture (Post Iteration 7)

```
┌──────────────────────────────────────────────────────────────┐
│                      CLIENT CHANNELS                         │
│    Web Chat    │    Slack Bot    │    Teams Bot               │
│                │                 │                 WebSocket ◄├─── Real-time
└───────┬────────┴───────┬────────┴──────────┬─────────────────┘
        │                │                   │
        ▼                ▼                   ▼
┌──────────────────────────────────────────────────────────────┐
│  SECURITY PIPELINE: CORS → Sanitizer → Rate Limiter → Hdrs  │
├──────────────────────────────────────────────────────────────┤
│  AUTH PIPELINE:     JWT Auth → RBAC → PII Stripper           │
├──────────────────────────────────────────────────────────────┤
│  COMPLIANCE:        Multi-Jurisdiction Engine                │
│                     ├── GDPR (EU/UK)                         │
│                     ├── CCPA (California)                    │
│                     └── 7 additional jurisdictions           │
├──────────────────────────────────────────────────────────────┤
│  I18N PIPELINE:     Detect Language → Translate → Process    │
├──────────────────────────────────────────────────────────────┤
│  CACHE LAYER:       Query Cache (LRU/LFU/TTL)               │
│                     ├── Local cache (fast)                   │
│                     └── Redis backend (distributed)          │
├──────────────────────────────────────────────────────────────┤
│                    API GATEWAY v2 (Flask)                     │
├──────────────────────────────────────────────────────────────┤
│  AGENT SERVICE:     Memory → Summarizer → RouterAgent        │
│                     Handoff Protocol (cross-agent state)     │
├──────────────────────────────────────────────────────────────┤
│  SPECIALIST AGENTS: Employee │ Policy │ Leave │ Onboarding   │
│                     Benefits │ Performance │ Leave Request    │
├──────────────────────────────────────────────────────────────┤
│  CORE SERVICES:     LLM Gateway │ RAG Pipeline │ Quality     │
│                     Workflow Engine │ Doc Generator           │
│                     Document Versioning │ WebSocket Manager   │
├──────────────────────────────────────────────────────────────┤
│  CONNECTORS:        BambooHR │ Workday │ Custom DB           │
│                     Payroll Connector (read-only)            │
├──────────────────────────────────────────────────────────────┤
│  DATA LAYER:        Repository Pattern │ SQLAlchemy ORM      │
│                     Connection Pool Manager                  │
│                     PostgreSQL │ Redis Cache │ ChromaDB       │
├──────────────────────────────────────────────────────────────┤
│  COMPLIANCE:        GDPR │ CCPA │ Multi-Jurisdiction         │
│                     Bias Audit │ Audit Logging               │
├──────────────────────────────────────────────────────────────┤
│  OBSERVABILITY:     Prometheus Metrics │ Alerting Service     │
│                     LangSmith Tracing │ Structured Logging    │
├──────────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE:    Docker │ GitHub Actions CI/CD             │
│                     PostgreSQL 15 │ Redis 7 │ Grafana         │
└──────────────────────────────────────────────────────────────┘
```

---

## Module Count Summary

| Layer | Modules | New in Iter 7 |
|-------|---------|---------------|
| Client Channels | 4 (Web, Slack, Teams, WebSocket) | +1 |
| Security Middleware | 6 (Auth, PII, CORS, Sanitizer, Rate Limiter, Sec Headers) | — |
| Compliance | 6 (GDPR, CCPA, Multi-Jurisdiction, Bias Audit, Audit Log, +1) | +2 |
| i18n | 1 (Language Detection + Translation) | — |
| Cache Layer | 2 (Redis Cache, Query Cache) | +1 |
| API | 2 (API Gateway v2, Agent Routes) | — |
| Services | 6 (Agent, LLM, RAG, Memory, Summarizer, Doc Versioning) | +1 |
| Agents | 9 (Router + 7 specialists + Handoff Protocol) | +1 |
| Core | 14 (LLM GW, RAG, Quality, Workflow, DocGen, Metrics, Alerting, etc.) | +2 |
| Connectors | 5 (Interface, BambooHR, Custom DB, Workday, Payroll) | +1 |
| Repositories | 8 (Base + 7 domain repos) | — |
| Infrastructure | 3 (Docker, CI/CD, Connection Pool) | +1 |
| **Total** | **92 production modules** | **+8** |

---

## File Structure Changes

```
src/
├── core/
│   ├── ccpa.py                  (853 lines)  ← NEW
│   ├── multi_jurisdiction.py    (972 lines)  ← NEW
│   ├── document_versioning.py   (707 lines)  ← NEW
│   ├── websocket_manager.py     (461 lines)  ← NEW
│   ├── connection_pool.py       (660 lines)  ← NEW
│   └── query_cache.py           (740 lines)  ← NEW
├── connectors/
│   └── payroll_connector.py     (654 lines)  ← NEW
├── agents/
│   └── handoff_protocol.py      (501 lines)  ← NEW
tests/unit/
├── test_ccpa.py                 (55 tests)   ← NEW
├── test_multi_jurisdiction.py   (55 tests)   ← NEW
├── test_payroll_connector.py    (40 tests)   ← NEW
├── test_document_versioning.py  (48 tests)   ← NEW
├── test_websocket_manager.py    (47 tests)   ← NEW
├── test_handoff_protocol.py     (50 tests)   ← NEW
├── test_connection_pool.py      (50 tests)   ← NEW
└── test_query_cache.py          (61 tests)   ← NEW
```
