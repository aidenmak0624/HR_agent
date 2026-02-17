# API Reference - HR Multi-Agent Intelligence Platform

## Overview

The HR Multi-Agent Intelligence Platform provides a comprehensive REST API for HR operations, employee management, workflow automation, and AI-powered intelligence. All endpoints are versioned under `/api/v2/`.

**Base URL:** `https://api.hr-platform.local/api/v2`

**Current Version:** 2.0

---

## Authentication

### JWT Authentication Flow

The platform uses JWT (JSON Web Token) for stateless authentication. All protected endpoints require a valid JWT token in the `Authorization` header.

#### Token Format
```
Authorization: Bearer <jwt_token>
```

### Endpoints

#### POST /api/v2/auth/login
Login with email and password to obtain a JWT token.

**Request:**
```json
{
  "email": "john.doe@company.com",
  "password": "securepassword123"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "email": "john.doe@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "role_level": "employee",
    "department": "Engineering"
  }
}
```

**Error Response (401 Unauthorized):**
```json
{
  "success": false,
  "error": "Invalid email or password"
}
```

---

#### POST /api/v2/auth/register
Register a new employee account (typically admin-only, may require registration token).

**Request:**
```json
{
  "email": "jane.smith@company.com",
  "password": "securepassword456",
  "first_name": "Jane",
  "last_name": "Smith",
  "department": "Marketing",
  "registration_token": "admin_token_xyz"
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Account created successfully",
  "user": {
    "id": 2,
    "email": "jane.smith@company.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "role_level": "employee"
  }
}
```

**Error Response (400 Bad Request):**
```json
{
  "success": false,
  "error": "Email already exists"
}
```

---

#### POST /api/v2/auth/refresh
Refresh an expired or expiring JWT token.

**Request:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600
}
```

---

## Profile Management

### GET /api/v2/profile
Retrieve the current authenticated user's profile information.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response (200 OK):**
```json
{
  "success": true,
  "profile": {
    "id": 1,
    "email": "john.doe@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "department": "Engineering",
    "role_level": "employee",
    "manager_id": 5,
    "manager_name": "Alice Johnson",
    "hire_date": "2021-03-15",
    "status": "active",
    "phone": "+1-555-0123",
    "office_location": "San Francisco, CA",
    "avatar_url": "https://api.hr-platform.local/avatars/1.jpg"
  }
}
```

---

### PUT /api/v2/profile
Update the current user's profile information.

**Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request:**
```json
{
  "phone": "+1-555-0124",
  "office_location": "Remote",
  "avatar_url": "https://api.hr-platform.local/avatars/1-new.jpg"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Profile updated successfully",
  "profile": {
    "id": 1,
    "email": "john.doe@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+1-555-0124",
    "office_location": "Remote"
  }
}
```

---

## Dashboard & Metrics

### GET /api/v2/metrics
Retrieve dashboard metrics and KPIs.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Query Parameters:**
- `start_date`: (optional) YYYY-MM-DD format
- `end_date`: (optional) YYYY-MM-DD format
- `department`: (optional) Filter by department

**Response (200 OK):**
```json
{
  "success": true,
  "metrics": {
    "total_employees": 150,
    "active_employees": 145,
    "pending_leave_requests": 8,
    "pending_workflows": 12,
    "average_leave_balance": 15.5,
    "turnover_rate": 0.08,
    "headcount_by_department": {
      "Engineering": 45,
      "Sales": 38,
      "Marketing": 22,
      "HR": 8,
      "Finance": 37
    }
  }
}
```

---

## Leave Management

### GET /api/v2/leave/balance
Get the current user's leave balance by type.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response (200 OK):**
```json
{
  "success": true,
  "balances": {
    "annual_leave": {
      "available": 12,
      "used": 8,
      "pending": 2,
      "total": 20
    },
    "sick_leave": {
      "available": 8,
      "used": 2,
      "pending": 0,
      "total": 10
    },
    "personal_leave": {
      "available": 5,
      "used": 1,
      "pending": 0,
      "total": 5
    }
  }
}
```

---

### GET /api/v2/leave/history
Get the current user's leave request history.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Query Parameters:**
- `status`: (optional) approved, pending, rejected
- `year`: (optional) 2024, 2025, etc.

**Response (200 OK):**
```json
{
  "success": true,
  "requests": [
    {
      "id": 42,
      "type": "annual_leave",
      "start_date": "2025-03-10",
      "end_date": "2025-03-14",
      "days": 5,
      "status": "approved",
      "reason": "Vacation",
      "approver_name": "Alice Johnson",
      "created_at": "2025-02-01T10:30:00Z",
      "approved_at": "2025-02-02T14:20:00Z"
    },
    {
      "id": 43,
      "type": "sick_leave",
      "start_date": "2025-02-20",
      "end_date": "2025-02-20",
      "days": 1,
      "status": "pending",
      "reason": "Medical appointment",
      "created_at": "2025-02-19T09:15:00Z"
    }
  ]
}
```

---

### POST /api/v2/leave/request
Submit a new leave request.

**Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request:**
```json
{
  "type": "annual_leave",
  "start_date": "2025-04-01",
  "end_date": "2025-04-05",
  "reason": "Spring vacation",
  "contact_info": "+1-555-0123"
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Leave request submitted successfully",
  "request": {
    "id": 44,
    "type": "annual_leave",
    "start_date": "2025-04-01",
    "end_date": "2025-04-05",
    "days": 5,
    "status": "pending",
    "reason": "Spring vacation",
    "created_at": "2025-02-15T11:45:00Z"
  }
}
```

---

## Workflows & Approvals

### GET /api/v2/workflows/pending
Get pending workflow tasks for the current user (managers/admins).

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Query Parameters:**
- `type`: (optional) leave_approval, document_approval, hiring
- `priority`: (optional) high, medium, low

**Response (200 OK):**
```json
{
  "success": true,
  "workflows": [
    {
      "id": 1,
      "type": "leave_approval",
      "requester_name": "Jane Smith",
      "requester_id": 2,
      "details": {
        "leave_type": "annual_leave",
        "start_date": "2025-03-01",
        "end_date": "2025-03-05",
        "days": 5,
        "reason": "Vacation"
      },
      "priority": "normal",
      "created_at": "2025-02-14T09:30:00Z",
      "due_date": "2025-02-16T17:00:00Z"
    },
    {
      "id": 2,
      "type": "document_approval",
      "requester_name": "John Doe",
      "requester_id": 1,
      "details": {
        "document_type": "certification_letter",
        "department": "Engineering"
      },
      "priority": "high",
      "created_at": "2025-02-13T14:00:00Z",
      "due_date": "2025-02-15T17:00:00Z"
    }
  ]
}
```

---

### POST /api/v2/workflows/approve
Approve a pending workflow task.

**Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request:**
```json
{
  "workflow_id": 1,
  "comment": "Approved. Have a great vacation!"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Workflow approved successfully",
  "workflow": {
    "id": 1,
    "status": "approved",
    "approved_by": "Alice Johnson",
    "approved_at": "2025-02-15T10:20:00Z"
  }
}
```

---

### POST /api/v2/workflows/reject
Reject a pending workflow task.

**Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request:**
```json
{
  "workflow_id": 1,
  "reason": "Overlaps with project deadline"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Workflow rejected successfully",
  "workflow": {
    "id": 1,
    "status": "rejected",
    "rejected_by": "Alice Johnson",
    "rejection_reason": "Overlaps with project deadline",
    "rejected_at": "2025-02-15T10:20:00Z"
  }
}
```

---

## Documents

### GET /api/v2/documents/templates
List available document templates (HR admin only).

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Query Parameters:**
- `category`: (optional) offer_letter, employment_cert, nda, handbook

**Response (200 OK):**
```json
{
  "success": true,
  "templates": [
    {
      "id": 1,
      "name": "Offer Letter",
      "category": "offer_letter",
      "description": "Standard offer letter template",
      "required_fields": ["employee_name", "position", "salary", "start_date"],
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2025-02-01T10:00:00Z"
    },
    {
      "id": 2,
      "name": "Employment Certificate",
      "category": "employment_cert",
      "description": "Certificate of employment",
      "required_fields": ["employee_name", "hire_date", "position"],
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

### POST /api/v2/documents/generate
Generate a document from a template.

**Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request:**
```json
{
  "template_id": 1,
  "employee_id": 2,
  "data": {
    "position": "Senior Software Engineer",
    "salary": 150000,
    "start_date": "2025-03-01",
    "benefits": "Standard benefits package"
  },
  "format": "pdf"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "document": {
    "id": 101,
    "template_id": 1,
    "employee_id": 2,
    "filename": "offer_letter_jane_smith.pdf",
    "url": "https://api.hr-platform.local/documents/101/download",
    "created_at": "2025-02-15T11:30:00Z",
    "expires_at": "2025-03-17T11:30:00Z"
  }
}
```

---

## Employee Directory

### GET /api/v2/employees
List all employees (requires manager or admin role).

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Query Parameters:**
- `department`: (optional) Filter by department
- `status`: (optional) active, inactive, terminated
- `role_level`: (optional) employee, manager, hr_admin
- `search`: (optional) Search by name/email
- `page`: (optional, default: 1) Pagination
- `per_page`: (optional, default: 50) Items per page

**Response (200 OK):**
```json
{
  "success": true,
  "employees": [
    {
      "id": 1,
      "email": "john.doe@company.com",
      "first_name": "John",
      "last_name": "Doe",
      "department": "Engineering",
      "role_level": "employee",
      "manager_id": 5,
      "hire_date": "2021-03-15",
      "status": "active",
      "phone": "+1-555-0123"
    },
    {
      "id": 2,
      "email": "jane.smith@company.com",
      "first_name": "Jane",
      "last_name": "Smith",
      "department": "Marketing",
      "role_level": "manager",
      "manager_id": null,
      "hire_date": "2020-06-01",
      "status": "active",
      "phone": "+1-555-0124"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 150,
    "total_pages": 3
  }
}
```

---

### PUT /api/v2/employees/:id
Update employee information (HR admin only).

**Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request:**
```json
{
  "department": "Engineering Management",
  "role_level": "manager",
  "manager_id": 8,
  "status": "active"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Employee updated successfully",
  "employee": {
    "id": 1,
    "email": "john.doe@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "department": "Engineering Management",
    "role_level": "manager",
    "manager_id": 8
  }
}
```

---

## Analytics & Reporting

### GET /api/v2/metrics
Get comprehensive analytics and KPI data (see Dashboard & Metrics section above).

---

### GET /api/v2/metrics/export
Export metrics data in CSV format.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Query Parameters:**
- `format`: csv (required)
- `start_date`: YYYY-MM-DD
- `end_date`: YYYY-MM-DD
- `metrics`: Comma-separated list (employees, leave, workflows, turnover)

**Response (200 OK):**
```
Content-Type: text/csv
Content-Disposition: attachment; filename="metrics_2025_02_15.csv"

Date,Metric,Value,Department
2025-02-15,Total Employees,150,All
2025-02-15,Active Employees,145,All
2025-02-15,Pending Leave Requests,8,All
...
```

---

## Notifications

### GET /api/v2/notifications
Get user's notifications.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Query Parameters:**
- `status`: (optional) unread, read, all (default: unread)
- `limit`: (optional) Number of notifications to retrieve (default: 20)

**Response (200 OK):**
```json
{
  "success": true,
  "notifications": [
    {
      "id": 1,
      "type": "workflow_pending",
      "title": "Leave request from Jane Smith",
      "message": "Jane Smith has submitted a leave request for approval",
      "actor_id": 2,
      "actor_name": "Jane Smith",
      "related_id": 44,
      "status": "unread",
      "created_at": "2025-02-15T11:45:00Z",
      "read_at": null,
      "action_url": "/workflows/44"
    },
    {
      "id": 2,
      "type": "document_ready",
      "title": "Your certificate is ready",
      "message": "Your employment certificate has been generated",
      "status": "read",
      "created_at": "2025-02-14T14:30:00Z",
      "read_at": "2025-02-14T15:00:00Z",
      "action_url": "/documents/101"
    }
  ]
}
```

---

### GET /api/v2/notifications/stream
Server-Sent Events (SSE) stream for real-time notifications.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response (200 OK - Stream):**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

data: {"id": 3, "type": "workflow_approved", "title": "Your leave request was approved", "created_at": "2025-02-15T12:00:00Z"}

data: {"id": 4, "type": "team_update", "title": "New team member joined", "message": "Sarah Connor has joined Engineering team", "created_at": "2025-02-15T12:15:00Z"}
```

**Client Usage (JavaScript):**
```javascript
const eventSource = new EventSource('/api/v2/notifications/stream', {
  headers: { 'Authorization': 'Bearer ' + token }
});

eventSource.addEventListener('message', (event) => {
  const notification = JSON.parse(event.data);
  console.log('New notification:', notification);
});

eventSource.addEventListener('error', () => {
  eventSource.close();
});
```

---

## AI Query & Chat

### POST /api/v2/query
Submit a question to the multi-agent AI system for HR-related queries.

**Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request:**
```json
{
  "query": "How much annual leave do I have remaining?",
  "context": "leave_balance",
  "conversation_id": "conv_123abc"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "response": {
    "text": "You have 12 days of annual leave remaining out of your 20-day annual allocation. You've used 8 days so far this year.",
    "agent": "leave_agent",
    "confidence": 0.95,
    "sources": [
      {
        "type": "database",
        "reference": "leave_balances:user_id=1"
      }
    ],
    "follow_up_suggestions": [
      "Request leave",
      "View leave history",
      "Policy details"
    ]
  },
  "conversation_id": "conv_123abc"
}
```

---

## Agents

### GET /api/v2/agents
Get information about available agents (admin/debug endpoint).

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response (200 OK):**
```json
{
  "success": true,
  "agents": [
    {
      "name": "router_agent",
      "description": "Routes queries to appropriate specialist agents",
      "status": "active"
    },
    {
      "name": "leave_agent",
      "description": "Handles leave requests and balance inquiries",
      "status": "active"
    },
    {
      "name": "policy_agent",
      "description": "Provides HR policy information",
      "status": "active"
    },
    {
      "name": "onboarding_agent",
      "description": "Manages employee onboarding workflows",
      "status": "active"
    },
    {
      "name": "analytics_agent",
      "description": "Generates HR analytics and reports",
      "status": "active"
    }
  ]
}
```

---

## Health Check

### GET /api/v2/health
Health check endpoint for monitoring system status.

**Response (200 OK):**
```json
{
  "success": true,
  "status": "healthy",
  "timestamp": "2025-02-15T12:30:00Z",
  "version": "2.0.0",
  "services": {
    "database": "healthy",
    "cache": "healthy",
    "message_queue": "healthy",
    "vector_db": "healthy"
  }
}
```

---

## Rate Limiting

All API endpoints are subject to rate limiting to ensure fair usage and system stability.

**Headers Included in Responses:**
- `X-RateLimit-Limit`: Maximum requests per minute (typically 60)
- `X-RateLimit-Remaining`: Number of requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

**Example Response Headers:**
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1645007400
```

**Rate Limit Exceeded Response (429 Too Many Requests):**
```json
{
  "success": false,
  "error": "Rate limit exceeded. Please try again in 60 seconds.",
  "retry_after": 60
}
```

---

## Error Handling

### Standard Error Format

All error responses follow this format:

```json
{
  "success": false,
  "error": "Human-readable error message",
  "error_code": "SPECIFIC_ERROR_CODE",
  "details": {
    "field": "Optional field-specific errors"
  }
}
```

### Common HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid input parameters |
| 401 | Unauthorized | Missing or invalid token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

### Common Error Codes

- `INVALID_CREDENTIALS`: Login failed with wrong credentials
- `TOKEN_EXPIRED`: JWT token has expired
- `INSUFFICIENT_PERMISSIONS`: User lacks required role/permissions
- `RESOURCE_NOT_FOUND`: Requested resource doesn't exist
- `VALIDATION_ERROR`: Input validation failed
- `INTERNAL_ERROR`: Unexpected server error
- `RATE_LIMIT_EXCEEDED`: Too many requests

---

## Authentication Headers

All protected endpoints require:

```
Authorization: Bearer <jwt_token>
```

### Token Claims (JWT Payload Example)

```json
{
  "user_id": 1,
  "email": "john.doe@company.com",
  "role_level": "employee",
  "iat": 1645000000,
  "exp": 1645003600,
  "iss": "hr-platform"
}
```

---

## Pagination

List endpoints support pagination with these parameters:

- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 50, max: 500)

Response includes pagination metadata:

```json
{
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 150,
    "total_pages": 3
  }
}
```

---

## Data Format

### Date/Time Format
All timestamps use ISO 8601 format:
```
2025-02-15T12:30:00Z
```

### Date Format
All dates use ISO 8601 format:
```
2025-02-15
```

---

## CORS Policy

The API allows cross-origin requests for `/api/v2/*` endpoints from any origin with the following methods and headers:

**Allowed Methods:** GET, POST, PUT, DELETE, OPTIONS
**Allowed Headers:** Content-Type, Authorization

---

## Changelog

### Version 2.0 (Current)
- Initial release of v2 API
- JWT-based authentication
- Real-time notifications via SSE
- Multi-agent AI query support
- Comprehensive employee management
- Leave and workflow management
- Analytics and reporting

---

## Support

For API support and issues:
- Email: api-support@company.com
- Documentation: https://docs.hr-platform.local
- Status Page: https://status.hr-platform.local
