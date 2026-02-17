# HR Multi-Agent Platform — Comprehensive Test Plan

**Version:** 1.0
**Date:** 2026-02-07
**Aligned to:** Product Requirements Document (PRD) v2

---

## Overview

This test plan validates all PRD features across the HR Multi-Agent Platform, covering the multi-agent query system, all 7 UI pages, API endpoints, and end-to-end workflows.

---

## A. Multi-Agent Query System (Core)

| ID | Test Case | Steps | Expected Result | Type |
|----|-----------|-------|-----------------|------|
| A1 | Route policy query to policy agent | POST `/api/v2/query` with `{"query": "What is the leave policy?"}` | Response contains `agent: "policy"` with confidence >= 0.7 | API |
| A2 | Route leave query to leave agent | POST `/api/v2/query` with `{"query": "I want to request vacation time"}` | Response routes to leave agent | API |
| A3 | Route benefits query to benefits agent | POST `/api/v2/query` with `{"query": "What health insurance options do we have?"}` | Response routes to benefits agent | API |
| A4 | Route employee info query | POST `/api/v2/query` with `{"query": "Who is the head of engineering?"}` | Response routes to employee_info agent | API |
| A5 | RBAC: employee role restrictions | POST query with employee role requesting performance data | Access denied or routed to appropriate fallback | API |
| A6 | Static fallback when LLM unavailable | Kill LLM service, then POST query | Returns curated static response (not error) | API |
| A7 | Confidence score returned | POST any valid query | Response includes `confidence` field >= 0.0 and <= 1.0 | API |
| A8 | Conversation history support | POST query with `conversation_history` array | Agent uses context from history | API |

---

## B. Chat Interface

| ID | Test Case | Steps | Expected Result | Type |
|----|-----------|-------|-----------------|------|
| B1 | Send message and receive response | Type message in chat input, press Enter or click send | Message appears in chat, agent response rendered below | UI |
| B2 | Suggested questions trigger queries | Click "What is my leave balance?" button | Query sent, response displayed | UI |
| B3 | New chat button resets conversation | Click "+" new chat button | Message container cleared, welcome message restored | UI |
| B4 | Typing indicator during API call | Send a message | Typing indicator appears while waiting for response | UI |
| B5 | Enter key sends message | Type message, press Enter | Message sent (same as clicking send button) | UI |
| B6 | Shift+Enter does not send | Type message, press Shift+Enter | No message sent, newline added (if applicable) | UI |
| B7 | Empty message not sent | Click send with empty input | Nothing happens, no API call made | UI |
| B8 | Agent response shows confidence | Send any query | Response includes confidence badge/indicator | UI |
| B9 | Conversation sidebar shows history | Send multiple messages | Conversation appears in sidebar list | UI |

---

## C. Leave Management

| ID | Test Case | Steps | Expected Result | Type |
|----|-----------|-------|-----------------|------|
| C1 | Leave balance cards display data | Navigate to /leave | Three leave cards show vacation, sick, personal balances | UI |
| C2 | Balance values from API | Page load triggers GET `/api/v2/leave/balance` | Cards show: Vacation 15 avail/5 used, Sick 10/2, Personal 5/1 | API+UI |
| C3 | Submit leave request — success | Fill form (type, start, end, reason), submit | Toast "Leave request submitted successfully", form resets | UI |
| C4 | Submit leave request — API call | Submit form | POST `/api/v2/leave/request` with correct payload, returns 201 | API |
| C5 | Validation: start before end | Set start date after end date, submit | Toast "Start date must be before end date" | UI |
| C6 | Validation: required fields | Submit with empty leave type | Toast "Please fill in all required fields" | UI |
| C7 | Leave history table populates | Page load | GET `/api/v2/leave/history` returns data, table shows rows | API+UI |
| C8 | History refreshes after submit | Submit leave request | `loadLeaveHistory()` called again, table updates | UI |

---

## D. Workflows & Approvals

| ID | Test Case | Steps | Expected Result | Type |
|----|-----------|-------|-----------------|------|
| D1 | Approve button — API call | Click "Approve" on first card | POST `/api/v2/workflows/approve` with `{request_id: "leave-001"}` | API |
| D2 | Approve — card removed | Click "Approve" | Card fades out and is removed from DOM | UI |
| D3 | Approve — toast shown | Click "Approve" | Toast "Request approved successfully" (green) | UI |
| D4 | Reject button — confirmation prompt | Click "Reject" on any card | Browser prompt asks for rejection reason | UI |
| D5 | Reject — cancel prompt | Click "Reject", then cancel the prompt | No API call, card remains | UI |
| D6 | Reject — API call | Click "Reject", enter reason, confirm | POST `/api/v2/workflows/reject` with request_id and reason | API |
| D7 | Reject — card removed | Complete rejection | Card fades out and is removed from DOM | UI |
| D8 | Reject — toast shown | Complete rejection | Toast "Request rejected" (blue info) | UI |
| D9 | Buttons disabled during API call | Click Approve/Reject | Both buttons on that card become disabled | UI |
| D10 | Buttons re-enabled on error | Simulate API failure | Buttons become enabled again | UI |
| D11 | Active workflows display | Navigate to /workflows | Onboarding, Leave Approval, Document Gen workflows visible | UI |
| D12 | Workflow timeline steps render | Check workflow cards | Steps show correct icons (checkmark, hourglass, circle) | UI |

---

## E. Document Management

| ID | Test Case | Steps | Expected Result | Type |
|----|-----------|-------|-----------------|------|
| E1 | Click template — form appears | Click "Employment Certificate" card | Generate form section becomes visible | UI |
| E2 | Form has correct template ID | Click any template card | Hidden input `selected-template` has correct value | UI |
| E3 | Cancel hides form | Click Cancel button | Form section hidden, form fields reset | UI |
| E4 | Generate — API call | Select template, employee, submit form | POST `/api/v2/documents/generate` with template_id, employee_id | API |
| E5 | Generate — new row in table | Submit generate form | New row appears at top of Recent Documents table | UI |
| E6 | Generate — toast shown | Submit generate form | Toast "Document generated successfully" (green) | UI |
| E7 | Generate — form resets | Submit generate form | Form hidden, fields reset after successful generation | UI |
| E8 | Generate — button disabled during call | Submit form | "Generate Document" button shows "Generating..." and is disabled | UI |
| E9 | Download button — toast | Click download on any document | Toast "Download started for document..." | UI |
| E10 | Validation — missing fields | Submit with no employee selected | Toast "Please select a template and employee" | UI |
| E11 | Six template cards displayed | Navigate to /documents | All 6 template cards visible (Employment Cert, Offer, Promotion, Separation, Experience, Salary) | UI |

---

## F. Analytics & Reporting

| ID | Test Case | Steps | Expected Result | Type |
|----|-----------|-------|-----------------|------|
| F1 | Charts render on page load | Navigate to /analytics | 4 charts render: Headcount (bar), Turnover (line), Leave (doughnut), Agent (bar) | UI |
| F2 | Default date range set | Page load | Date-from = 1 year ago, date-to = today | UI |
| F3 | Filter by date range | Change date-from or date-to | `loadAnalytics()` called, charts update | UI |
| F4 | Filter by department | Select "Engineering" from dropdown | `loadAnalytics()` called, charts update | UI |
| F5 | Export CSV — file downloads | Click "Export CSV" button | Browser initiates CSV download from `/api/v2/metrics/export` | UI |
| F6 | Export CSV — endpoint response | GET `/api/v2/metrics/export` | Returns CSV with headers, Content-Disposition attachment | API |
| F7 | Charts use API data when available | GET `/api/v2/metrics` returns data | Charts use real data instead of fallback | API+UI |
| F8 | Charts use fallback on empty data | API returns empty metrics | Charts render with default placeholder data | UI |
| F9 | Summary stat cards displayed | Navigate to /analytics | 4 stat cards: Total Headcount, Turnover Rate, Avg Leave Days, Resolution Rate | UI |

---

## G. Dashboard

| ID | Test Case | Steps | Expected Result | Type |
|----|-----------|-------|-----------------|------|
| G1 | KPI cards show metrics | Navigate to /dashboard | 4 KPI cards render with values (not "--") | UI |
| G2 | KPI data from API | Page load triggers GET `/api/v2/metrics` | KPI values populated from response data | API+UI |
| G3 | Department headcount chart | Page load | Bar chart renders with department data | UI |
| G4 | Monthly query trend chart | Page load | Line chart renders with query trend data | UI |
| G5 | Quick action: Leave Request | Click "New Leave Request" | Navigates to /leave | UI |
| G6 | Quick action: Ask Agent | Click "Ask Agent" | Navigates to /chat | UI |
| G7 | Quick action: Generate Document | Click "Generate Document" | Navigates to /documents | UI |
| G8 | Activity feed displays | Page load | 5 activity items visible with icons, titles, details, times | UI |
| G9 | Auto-refresh every 60s | Wait 60 seconds | `fetchMetrics()` called again automatically | UI |

---

## H. Navigation & General UI

| ID | Test Case | Steps | Expected Result | Type |
|----|-----------|-------|-----------------|------|
| H1 | Sidebar: Dashboard link | Click Dashboard in sidebar | Navigates to /dashboard | UI |
| H2 | Sidebar: Chat link | Click Chat in sidebar | Navigates to /chat | UI |
| H3 | Sidebar: Leave link | Click Leave in sidebar | Navigates to /leave | UI |
| H4 | Sidebar: Workflows link | Click Workflows in sidebar | Navigates to /workflows | UI |
| H5 | Sidebar: Documents link | Click Documents in sidebar | Navigates to /documents | UI |
| H6 | Sidebar: Analytics link | Click Analytics in sidebar | Navigates to /analytics | UI |
| H7 | Sidebar: Settings link | Click Settings in sidebar | Navigates to /settings | UI |
| H8 | Active page highlighted | Navigate to any page | Corresponding sidebar item has "active" class | UI |
| H9 | Notification bell toggles panel | Click bell icon | Notification panel appears/disappears | UI |
| H10 | Click outside closes notifications | Open panel, click outside | Panel closes | UI |
| H11 | Toast notifications appear | Trigger any action that shows toast | Toast appears at bottom-right with correct color | UI |
| H12 | Toast auto-dismisses | Trigger toast | Toast disappears after 3 seconds | UI |

---

## I. API Endpoints

| ID | Endpoint | Method | Expected Status | Expected Shape |
|----|----------|--------|-----------------|----------------|
| I1 | `/api/v2/health` | GET | 200 | `{success: true, data: {status: "healthy"}}` |
| I2 | `/api/v2/query` | POST | 200 | `{success: true, data: {answer, agent, confidence}}` |
| I3 | `/api/v2/metrics` | GET | 200 | `{success: true, data: {...metrics}}` |
| I4 | `/api/v2/leave/balance` | GET | 200 | `{success: true, data: {vacation, sick, personal}}` |
| I5 | `/api/v2/leave/request` | POST | 201 | `{success: true, data: {request_id, status: "submitted"}}` |
| I6 | `/api/v2/leave/history` | GET | 200 | `{success: true, data: {history: [...]}}` |
| I7 | `/api/v2/documents/templates` | GET | 200 | `{success: true, data: {templates: [...]}}` |
| I8 | `/api/v2/documents/generate` | POST | 201 | `{success: true, data: {document_id, status: "finalized"}}` |
| I9 | `/api/v2/workflows/pending` | GET | 200 | `{success: true, data: {pending: [...], count}}` |
| I10 | `/api/v2/workflows/approve` | POST | 200 | `{success: true, data: {request_id, status: "approved"}}` |
| I11 | `/api/v2/workflows/reject` | POST | 200 | `{success: true, data: {request_id, status: "rejected"}}` |
| I12 | `/api/v2/metrics/export` | GET | 200 | CSV file download |
| I13 | `/api/v2/agents` | GET | 200 | `{success: true, data: {agents: [...], count}}` |
| I14 | `/api/v2/auth/token` | POST | 200 | `{success: true, data: {access_token, refresh_token}}` |
| I15 | `/api/v2/leave/request` (missing fields) | POST | 400 | `{success: false, error: "Missing required fields"}` |
| I16 | `/api/v2/query` (empty query) | POST | 400 | `{success: false, error: "Query is required"}` |

---

## J. Error Handling & Edge Cases

| ID | Test Case | Steps | Expected Result | Type |
|----|-----------|-------|-----------------|------|
| J1 | API 401 redirects to login | Return 401 from any endpoint | `removeAuthToken()` called, redirect to /login | UI |
| J2 | API error — toast shown | Simulate 500 error | Toast with error message | UI |
| J3 | Rate limiting | Send 61+ requests in 1 minute | 429 status returned with retry_after | API |
| J4 | Network failure graceful | Disconnect network, try action | Error toast, no crash | UI |
| J5 | Double-click prevention | Rapidly click Approve twice | Only one API call sent (buttons disabled) | UI |

---

## Test Execution Commands

### Unit Tests (existing — 1909 tests)
```bash
cd /path/to/HR_agent
python -m pytest tests/ -x -q
```

### API Endpoint Smoke Tests
```bash
# Health check
curl -s http://localhost:5050/api/v2/health | python3 -m json.tool

# Query routing
curl -s -X POST http://localhost:5050/api/v2/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the leave policy?"}' | python3 -m json.tool

# Leave balance
curl -s http://localhost:5050/api/v2/leave/balance | python3 -m json.tool

# Leave history
curl -s http://localhost:5050/api/v2/leave/history | python3 -m json.tool

# Submit leave request
curl -s -X POST http://localhost:5050/api/v2/leave/request \
  -H "Content-Type: application/json" \
  -d '{"leave_type":"vacation","start_date":"2024-04-01","end_date":"2024-04-05","reason":"Family trip"}' | python3 -m json.tool

# Pending approvals
curl -s http://localhost:5050/api/v2/workflows/pending | python3 -m json.tool

# Approve request
curl -s -X POST http://localhost:5050/api/v2/workflows/approve \
  -H "Content-Type: application/json" \
  -d '{"request_id":"leave-001"}' | python3 -m json.tool

# Reject request
curl -s -X POST http://localhost:5050/api/v2/workflows/reject \
  -H "Content-Type: application/json" \
  -d '{"request_id":"expense-001","reason":"Over budget"}' | python3 -m json.tool

# Document generation
curl -s -X POST http://localhost:5050/api/v2/documents/generate \
  -H "Content-Type: application/json" \
  -d '{"template_id":"employment-cert","employee_id":"john-smith"}' | python3 -m json.tool

# Metrics
curl -s http://localhost:5050/api/v2/metrics | python3 -m json.tool

# CSV Export
curl -s -o analytics_export.csv http://localhost:5050/api/v2/metrics/export
```

### Page Load Tests
```bash
for page in dashboard chat leave workflows documents analytics settings; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/$page)
  echo "$page: $STATUS"
done
```

---

## Traceability Matrix

| PRD Requirement | Test IDs |
|----------------|----------|
| Multi-agent query routing | A1-A8 |
| Chat interface | B1-B9 |
| Leave management | C1-C8 |
| Workflow approvals | D1-D12 |
| Document generation | E1-E11 |
| Analytics & reporting | F1-F9 |
| Dashboard overview | G1-G9 |
| Navigation & UI | H1-H12 |
| API contract validation | I1-I16 |
| Error handling | J1-J5 |
