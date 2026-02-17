# HR Multi-Agent Platform - API v2 Endpoints Documentation

## Base URL
```
http://localhost:5050/api/v2
```

---

## Health & Status

### GET /health
Check system health status.

**Response:**
```json
{
  "success": true,
  "status": "healthy",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "llm": "ok"
  }
}
```

**Status Codes:**
- `200 OK` - System healthy
- `503 Service Unavailable` - System degraded

---

## Core Query Processing

### POST /query
Process user query through multi-agent system.

**Request:**
```json
{
  "query": "What's our remote work policy?",
  "conversation_history": [
    {
      "role": "user",
      "content": "Hi, I have a question about policies"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "query": "What's our remote work policy?",
    "answer": "Our remote work policy allows employees with 6+ months tenure...",
    "sources": ["remote_work_policy.txt"],
    "confidence": 0.92,
    "agent_type": "router",
    "intents": [["policy", 0.95]],
    "agents_used": ["PolicyAgent"],
    "execution_time_ms": 2847,
    "request_id": "abc-def-123",
    "timestamp": "2025-02-06T12:34:56.789Z"
  },
  "metadata": {
    "execution_time_ms": 2847,
    "request_id": "abc-def-123"
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Query is required",
  "request_id": "abc-def-123"
}
```

**Status Codes:**
- `200 OK` - Query processed successfully
- `400 Bad Request` - Invalid query
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Processing failed

---

## Agent Information

### GET /agents
List all available specialist agents.

**Response:**
```json
{
  "success": true,
  "data": {
    "agents": [
      {
        "type": "employee_info",
        "name": "Employee Info Agent",
        "description": "Retrieves employee profiles, contact info, compensation"
      },
      {
        "type": "policy",
        "name": "Policy Agent",
        "description": "Answers HR policies, compliance, procedures"
      },
      {
        "type": "leave",
        "name": "Leave Agent",
        "description": "Manages PTO, sick leave, vacation requests"
      },
      {
        "type": "onboarding",
        "name": "Onboarding Agent",
        "description": "Handles new hire processes, orientation, documentation"
      },
      {
        "type": "benefits",
        "name": "Benefits Agent",
        "description": "Explains health insurance, retirement, perks"
      },
      {
        "type": "performance",
        "name": "Performance Agent",
        "description": "Manages reviews, goals, feedback"
      },
      {
        "type": "analytics",
        "name": "Analytics Agent",
        "description": "Generates reports, statistics, trends"
      },
      {
        "type": "router",
        "name": "Router Agent",
        "description": "Classifies intent, checks permissions, dispatches queries"
      }
    ],
    "count": 8
  }
}
```

**Status Codes:**
- `200 OK` - Agents listed successfully
- `500 Internal Server Error` - Listing failed

---

## Metrics & Statistics

### GET /metrics
Get agent usage statistics and performance metrics.

**Response:**
```json
{
  "success": true,
  "data": {
    "total_queries": 247,
    "avg_confidence": 0.87,
    "min_confidence": 0.45,
    "max_confidence": 0.98,
    "conversation_count": 42,
    "agent_breakdown": {
      "policy": 89,
      "leave": 56,
      "employee_info": 45,
      "benefits": 32,
      "onboarding": 15,
      "performance": 10
    },
    "popular_agents": [
      {"agent": "policy", "count": 89},
      {"agent": "leave", "count": 56},
      {"agent": "employee_info", "count": 45},
      {"agent": "benefits", "count": 32},
      {"agent": "onboarding", "count": 15}
    ],
    "llm_stats": {
      "gemini-2.0-flash": {
        "call_count": 247,
        "success_count": 245,
        "failure_count": 2,
        "success_rate": 0.9919,
        "average_latency_ms": 1245.3,
        "cache_hits": 12
      }
    }
  }
}
```

**Status Codes:**
- `200 OK` - Metrics retrieved successfully
- `500 Internal Server Error` - Retrieval failed

---

## RAG (Retrieval-Augmented Generation)

### GET /rag/stats
Get RAG collection statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "collections": {
      "hr_policies": {
        "doc_count": 24,
        "chunk_count": 156,
        "backend": "chromadb"
      },
      "employee_handbook": {
        "doc_count": 8,
        "chunk_count": 64,
        "backend": "chromadb"
      },
      "compliance_docs": {
        "doc_count": 12,
        "chunk_count": 89,
        "backend": "chromadb"
      },
      "benefits_guides": {
        "doc_count": 6,
        "chunk_count": 48,
        "backend": "chromadb"
      }
    },
    "total_collections": 4
  }
}
```

**Status Codes:**
- `200 OK` - Statistics retrieved successfully
- `500 Internal Server Error` - Retrieval failed

### POST /rag/ingest
Ingest documents into RAG system.

**Request:**
```json
{
  "filepath": "/path/to/document.txt",
  "collection": "hr_policies",
  "doc_type": "policy"
}
```

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "success": true,
    "filepath": "/path/to/document.txt",
    "collection": "hr_policies",
    "chunk_count": 12
  }
}
```

**Response (Failure):**
```json
{
  "success": false,
  "data": {
    "success": false,
    "error": "File not found: /path/to/document.txt"
  },
  "error": "File not found: /path/to/document.txt"
}
```

**Status Codes:**
- `200 OK` - Ingestion completed (check success field)
- `400 Bad Request` - Missing filepath
- `500 Internal Server Error` - Ingestion failed

---

## Authentication (Legacy Support)

### POST /auth/token
Generate authentication token.

**Request:**
```json
{
  "user_id": "emp123",
  "password": "password123"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "token_emp123_1707225296",
    "refresh_token": "refresh_emp123_1707225296",
    "expires_in": 3600,
    "token_type": "Bearer"
  }
}
```

**Status Codes:**
- `200 OK` - Token generated
- `400 Bad Request` - Missing credentials
- `500 Internal Server Error` - Generation failed

### POST /auth/refresh
Refresh authentication token.

**Request:**
```json
{
  "refresh_token": "refresh_emp123_1707225296"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "token_emp123_1707225297",
    "expires_in": 3600,
    "token_type": "Bearer"
  }
}
```

**Status Codes:**
- `200 OK` - Token refreshed
- `400 Bad Request` - Invalid token
- `500 Internal Server Error` - Refresh failed

---

## Leave Management

### GET /leave/balance
Get employee leave balance.

**Query Parameters:**
- `employee_id` (optional) - Employee ID

**Response:**
```json
{
  "success": true,
  "data": {
    "employee_id": "emp123",
    "vacation": {
      "available": 15,
      "used": 5,
      "pending": 2
    },
    "sick": {
      "available": 10,
      "used": 2,
      "pending": 0
    },
    "personal": {
      "available": 5,
      "used": 1,
      "pending": 0
    }
  }
}
```

**Status Codes:**
- `200 OK` - Balance retrieved successfully
- `500 Internal Server Error` - Retrieval failed

### POST /leave/request
Submit leave request.

**Request:**
```json
{
  "employee_id": "emp123",
  "start_date": "2025-02-17",
  "end_date": "2025-02-21",
  "leave_type": "vacation"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "request_id": "req_1707225296",
    "status": "submitted",
    "employee_id": "emp123",
    "leave_type": "vacation",
    "start_date": "2025-02-17",
    "end_date": "2025-02-21"
  }
}
```

**Status Codes:**
- `201 Created` - Request submitted successfully
- `400 Bad Request` - Missing required fields
- `500 Internal Server Error` - Submission failed

---

## Document Management

### GET /documents/templates
List available document templates.

**Response:**
```json
{
  "success": true,
  "data": {
    "templates": [
      {
        "template_id": "t1",
        "name": "Offer Letter",
        "type": "offer_letter"
      },
      {
        "template_id": "t2",
        "name": "Contract",
        "type": "employment_contract"
      },
      {
        "template_id": "t3",
        "name": "Termination",
        "type": "termination_letter"
      }
    ]
  }
}
```

**Status Codes:**
- `200 OK` - Templates listed successfully
- `500 Internal Server Error` - Listing failed

### POST /documents/generate
Generate document from template.

**Request:**
```json
{
  "template_id": "t1",
  "data": {
    "candidate_name": "John Doe",
    "position": "Software Engineer",
    "start_date": "2025-03-01",
    "salary": "150000"
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "document_id": "doc_1707225296",
    "template_id": "t1",
    "status": "finalized",
    "created_at": "2025-02-06T12:34:56.789Z"
  }
}
```

**Status Codes:**
- `201 Created` - Document generated successfully
- `400 Bad Request` - Missing template_id
- `500 Internal Server Error` - Generation failed

---

## Rate Limiting

All endpoints (except `/health` and auth endpoints) are rate-limited.

**Default:** 60 requests per minute per user

**Response Headers:**
```
X-RateLimit-Remaining: 59
X-Request-ID: abc-def-123
```

**Rate Limit Exceeded Response:**
```json
{
  "success": false,
  "error": "Rate limit exceeded",
  "metadata": {
    "retry_after": 60
  }
}
```

**Status Code:** `429 Too Many Requests`

---

## Error Handling

### Standard Error Response
```json
{
  "success": false,
  "error": "Error message describing what went wrong",
  "request_id": "unique-request-id"
}
```

### Common Error Codes

| Code | Reason |
|------|--------|
| 400 | Bad Request (missing/invalid parameters) |
| 404 | Endpoint not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 503 | Service unavailable (health check failed) |

---

## Request ID Tracking

Every request receives a unique `request_id` in:
1. Response JSON (`data.request_id` or `request_id`)
2. Response headers (`X-Request-ID`)

Use this for debugging and tracing.

---

## Example Usage

### Using curl

**Query the multi-agent system:**
```bash
curl -X POST http://localhost:5050/api/v2/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the eligibility requirements for remote work?",
    "conversation_history": []
  }'
```

**Get agent statistics:**
```bash
curl http://localhost:5050/api/v2/metrics
```

**List available agents:**
```bash
curl http://localhost:5050/api/v2/agents
```

**Ingest a document:**
```bash
curl -X POST http://localhost:5050/api/v2/rag/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "filepath": "/data/policies/new_policy.txt",
    "collection": "hr_policies",
    "doc_type": "policy"
  }'
```

### Using Python

```python
import requests

BASE_URL = "http://localhost:5050/api/v2"

# Query the multi-agent system
response = requests.post(
    f"{BASE_URL}/query",
    json={
        "query": "What's our PTO policy?",
        "conversation_history": []
    }
)
print(response.json())

# Get metrics
metrics = requests.get(f"{BASE_URL}/metrics").json()
print(f"Total queries: {metrics['data']['total_queries']}")
print(f"Avg confidence: {metrics['data']['avg_confidence']:.2f}")
```

---

## Response Format

All endpoints return consistent JSON structure:

```json
{
  "success": true|false,
  "data": {...} | null,
  "error": "error message" | null,
  "metadata": {...},
  "timestamp": "2025-02-06T12:34:56.789Z"
}
```

---

## Next Steps

- Implement JWT authentication for all endpoints
- Add user context extraction from Bearer tokens
- Implement database persistence for conversations
- Add webhook support for async processing
- Create WebSocket support for real-time streaming

---

**Last Updated:** February 6, 2025
**API Version:** 2.0.0
**Status:** Production-Ready
