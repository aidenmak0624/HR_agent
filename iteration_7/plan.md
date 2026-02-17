# Iteration 7 — Plan

## Overview
**Iteration**: 7 — Compliance Extension, Advanced Features & Performance Optimization
**Priority**: P0/P1 (Production Readiness)
**Estimated Issues**: 8
**Planned Tests**: ~400+

---

## Objectives

1. Extend compliance beyond GDPR to CCPA and multi-jurisdiction support
2. Add payroll data integration (read-only) for HR analytics
3. Implement policy document versioning and lifecycle management
4. Build real-time notification infrastructure via WebSocket
5. Enable cross-agent handoff with shared state for complex queries
6. Optimize database and cache performance for production scale

---

## Wave 1 — Compliance Extension (COMP-002, COMP-003)

### COMP-002: CCPA Compliance Module
**File**: `src/core/ccpa.py`
**Priority**: P0

Implement California Consumer Privacy Act compliance following the existing GDPR module pattern:
- Consumer rights management (Right to Know, Delete, Opt-Out, Correct, Limit, Non-Discrimination)
- Data category classification (Personal Info, Financial, Biometric, Geolocation, Internet Activity, Professional, Education, Inferences)
- Consumer request lifecycle (submit → verify → process → complete)
- 45-day response deadline with extension support
- Minor consent handling (13+ and 16+ age tiers)
- 12-month disclosure report generation
- Opt-out of sale tracking
- Annual compliance metrics

### COMP-003: Multi-Jurisdiction Compliance Engine
**File**: `src/core/multi_jurisdiction.py`
**Priority**: P0

Create a unified compliance engine supporting 9 global jurisdictions:
- US Federal, California (CCPA), New York, Illinois
- EU GDPR, UK GDPR
- Canada PIPEDA, Australia APPs, Brazil LGPD
- Automatic jurisdiction determination from employee location
- Most-restrictive conflict resolution strategy
- Cross-border data transfer validation
- Breach notification deadline calculation (shortest across jurisdictions)
- Consent requirement aggregation
- Custom requirement registration per jurisdiction

---

## Wave 2 — Advanced Features (PAY-001, DOC-002, WS-001, AGENT-007)

### PAY-001: Payroll Data Connector
**File**: `src/connectors/payroll_connector.py`
**Priority**: P1

Read-only payroll data connector supporting multiple providers:
- Workday, ADP, Paychex, and Generic HTTP APIs
- OAuth2 authentication with token caching
- Payroll record retrieval (individual and history)
- Payroll summaries with deduction/tax breakdowns
- Provider-specific field mapping
- Retry logic with exponential backoff
- Rate limiting awareness

### DOC-002: Document Versioning Service
**File**: `src/core/document_versioning.py`
**Priority**: P1

Policy document versioning and lifecycle management:
- Semantic version numbering (1.0, 1.1, 2.0)
- Document lifecycle: Draft → Pending Review → Approved → Published → Archived
- Approval workflow with approver tracking
- Version comparison with unified diff
- Rollback to previous versions
- Search by query, category, tags, status
- Automatic version retention cleanup

### WS-001: WebSocket Manager
**File**: `src/core/websocket_manager.py`
**Priority**: P1

Real-time notification layer for the platform:
- 5 event types: Notification, Query Update, Agent Status, System Alert, Workflow Update
- Per-user connection management with limits
- Targeted, broadcast, and user-specific messaging
- Priority levels (low, medium, high)
- Connection health monitoring with ping/pong
- Stale connection cleanup
- Message size validation

### AGENT-007: Cross-Agent Handoff Protocol
**File**: `src/agents/handoff_protocol.py`
**Priority**: P1

Seamless agent-to-agent handoff with shared state:
- 6 handoff reasons: Expertise Required, Escalation, Workflow Continuation, User Request, Capability Mismatch, Load Balancing
- Handoff lifecycle: Initiated → Accepted/Rejected → Completed/Failed
- Shared agent state with accumulated facts and pending actions
- Configurable allowed handoff pairs
- Maximum handoffs per session limit
- Full audit trail of handoff history

---

## Wave 3 — Performance Optimization (PERF-001, PERF-002)

### PERF-001: Connection Pool Manager
**File**: `src/core/connection_pool.py`
**Priority**: P1

Database and service connection pooling:
- PostgreSQL, Redis, and HTTP pool types
- Configurable min/max connections, overflow, timeout, recycle
- Health checking with latency measurement
- Dynamic pool resizing
- Pool drain and graceful shutdown
- Optimal pool size recommendations based on usage
- Connection validation and recycling

### PERF-002: Query Cache Service
**File**: `src/core/query_cache.py`
**Priority**: P1

Multi-strategy query result caching:
- 5 strategies: LRU, TTL, LFU, Write-Through, Write-Behind
- Local cache with optional Redis backend
- Tag-based and pattern-based invalidation
- Cache-aside pattern (get_or_set)
- Bulk operations (bulk_get, bulk_set)
- Cache warmup for critical queries
- Memory-aware eviction
- Hit rate and performance statistics

---

## Gate 7 Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | CCPA module handles all 6 consumer rights with request lifecycle |
| 2 | Multi-jurisdiction engine resolves conflicts across 9 jurisdictions |
| 3 | Payroll connector retrieves records from multiple providers (read-only) |
| 4 | Document versioning supports full lifecycle with approval workflow |
| 5 | WebSocket manager handles connections, messaging, and notifications |
| 6 | Handoff protocol enables cross-agent transitions with shared state |
| 7 | Connection pool manages PostgreSQL, Redis, and HTTP pools with health checks |
| 8 | Query cache supports multiple eviction strategies with Redis backend |
| 9 | All unit tests pass with 0 failures, 0 deprecation warnings |

---

## Dependencies

- Iteration 6 complete (security middleware, metrics, i18n) ✅
- GDPR module for multi-jurisdiction integration ✅
- Workday connector pattern for payroll connector ✅
- Base agent pattern for handoff protocol ✅
- Redis cache pattern for query caching ✅
