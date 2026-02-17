# Iteration 3, Wave 2: APP INTEGRATION - Quick Start Guide

## What's New in Wave 2

This wave implements **APP INTEGRATION** for the HR multi-agent platform, connecting the multi-agent system into a Flask application with full LLM and RAG integration.

## Quick Start

### 1. Install Dependencies
```bash
pip install flask flask-cors langchain-google-genai langchain-core python-dotenv
```

### 2. Configure Environment
Create `.env` file:
```env
GOOGLE_API_KEY=your-gemini-api-key-here
DEBUG=false
PORT=5050
```

### 3. Start the Server
```bash
python src/app_v2.py
```

Expected output:
```
╔═══════════════════════════════════════════════════════════════╗
║         HR Multi-Agent Platform v2 - Wave 2                   ║
║              APP INTEGRATION (Iteration 3)                     ║
╚═══════════════════════════════════════════════════════════════╝

Server starting on http://localhost:5050
```

### 4. Test the API
```bash
# Check health
curl http://localhost:5050/api/v2/health

# Query the multi-agent system
curl -X POST http://localhost:5050/api/v2/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our remote work policy?"}'

# List available agents
curl http://localhost:5050/api/v2/agents

# Get statistics
curl http://localhost:5050/api/v2/metrics
```

## File Structure

```
src/
├── app_v2.py                          # Main Flask app (NEW)
├── services/                          # Service layer (NEW)
│   ├── __init__.py
│   ├── agent_service.py              # Agent orchestrator
│   ├── llm_service.py                # LLM integration
│   └── rag_service.py                # RAG wrapper
├── platform/
│   └── api_gateway.py                # API endpoints (UPDATED)
├── agents/
│   ├── router_agent.py               # Intent routing
│   └── base_agent.py                 # Agent base class
├── core/
│   ├── llm_gateway.py                # LLM model routing
│   └── rag_pipeline.py               # Document retrieval
└── ... (other components)

Documentation/
├── ITERATION3_WAVE2_SUMMARY.md       # Detailed implementation guide
├── API_V2_ENDPOINTS.md               # Complete API reference
├── WAVE2_COMPLETION_CHECKLIST.md     # Verification checklist
└── README_WAVE2.md                   # This file
```

## Key Services

### 1. AgentService (Singleton)
Orchestrates multi-agent system.

```python
from src.services.agent_service import AgentService

service = AgentService()  # Singleton
result = service.process_query(
    query="What's our PTO policy?",
    user_context={"user_id": "emp123", "role": "employee"}
)
print(result["answer"])
```

### 2. LLMService
Integrates Google Gemini with OpenAI fallback.

```python
from src.services.llm_service import LLMService

llm = LLMService()
response = llm.generate("Write a brief summary of remote work benefits")
print(response)
```

### 3. RAGService
Document search and ingestion.

```python
from src.services.rag_service import RAGService

rag = RAGService()
results = rag.search("remote work eligibility")
print(results[0]["content"])
```

## API Endpoints

### Core Endpoints

**POST /api/v2/query** - Multi-agent query processing
```bash
curl -X POST http://localhost:5050/api/v2/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the benefits of remote work?",
    "conversation_history": []
  }'
```

**GET /api/v2/metrics** - Agent statistics
```bash
curl http://localhost:5050/api/v2/metrics
```

**GET /api/v2/agents** - List available agents
```bash
curl http://localhost:5050/api/v2/agents
```

### RAG Endpoints

**GET /api/v2/rag/stats** - Collection statistics
```bash
curl http://localhost:5050/api/v2/rag/stats
```

**POST /api/v2/rag/ingest** - Ingest documents
```bash
curl -X POST http://localhost:5050/api/v2/rag/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "filepath": "/path/to/document.txt",
    "collection": "hr_policies"
  }'
```

**GET /api/v2/health** - System health
```bash
curl http://localhost:5050/api/v2/health
```

## Available Agents

1. **Employee Info Agent** - Employee profiles, contact, compensation
2. **Policy Agent** - HR policies and procedures
3. **Leave Agent** - PTO and time-off management
4. **Onboarding Agent** - New hire processes
5. **Benefits Agent** - Health insurance and retirement
6. **Performance Agent** - Reviews and feedback
7. **Analytics Agent** - Reports and statistics
8. **Router Agent** - Intent classification and dispatch

## Architecture Overview

```
User Request
     ↓
APIGateway (rate limiting)
     ↓
AgentService (orchestration)
     ↓
RouterAgent (intent classification)
     ↓
Specialist Agents (execution)
     ├→ RAGService (document search)
     └→ LLMService (text generation)
     ↓
Response (with sources, confidence, etc.)
```

## Features

✅ **Multi-agent routing** - Intelligent intent classification  
✅ **LLM integration** - Google Gemini with OpenAI fallback  
✅ **Circuit breaker** - Fault tolerance for failed requests  
✅ **RAG pipeline** - Semantic document search  
✅ **Request tracing** - Unique ID per request  
✅ **Conversation logging** - All interactions recorded  
✅ **Health checks** - Monitor all services  
✅ **Rate limiting** - Prevent abuse  
✅ **Error handling** - Graceful degradation  

## Example Usage (Python)

```python
import requests

BASE_URL = "http://localhost:5050/api/v2"

# Query the multi-agent system
response = requests.post(
    f"{BASE_URL}/query",
    json={
        "query": "How much PTO do I have?",
        "conversation_history": []
    }
)

result = response.json()
print(f"Answer: {result['data']['answer']}")
print(f"Confidence: {result['data']['confidence']:.2f}")
print(f"Sources: {result['data']['sources']}")
print(f"Agent used: {result['data']['agent_type']}")
print(f"Time: {result['data']['execution_time_ms']:.0f}ms")
```

## Configuration

### Environment Variables

```env
# Required
GOOGLE_API_KEY=sk-...

# Optional
OPENAI_ENABLED=false
LLM_API_KEY=sk-...

# Server
PORT=5050
DEBUG=false
HOST=0.0.0.0

# Database
DATABASE_URL=sqlite:///hr_platform.db
REDIS_URL=redis://localhost:6379/0

# Security
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256

# Features
PII_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
CONFIDENCE_THRESHOLD=0.7
MAX_ITERATIONS=5
```

## Logging

The application logs to console with timestamps and levels:

```
2025-02-06 12:34:56 - src.services.agent_service - INFO - ROUTER: Processing query: What's the policy on...
2025-02-06 12:34:57 - src.services.llm_service - INFO - Provider google: 1245ms, tokens_out=156
2025-02-06 12:34:58 - src.services.rag_service - INFO - Search returned 3 results
2025-02-06 12:34:59 - src.app_v2 - INFO - REQUEST abc-123: 3245ms 200
```

## Troubleshooting

### Service won't start
- Check GOOGLE_API_KEY is set
- Verify Python 3.9+ installed
- Ensure all dependencies installed: `pip install -r requirements.txt`

### Query returns error
- Check service health: `curl http://localhost:5050/api/v2/health`
- Review app logs for error details
- Verify GOOGLE_API_KEY is valid

### Slow responses
- Check `execution_time_ms` in response
- Monitor LLM provider latency
- Check available document count in RAG

### Rate limiting issues
- Default limit: 60 requests/minute per user
- Check `X-RateLimit-Remaining` header
- Configure with `RATE_LIMIT_PER_MINUTE` env var

## Next Steps

### For Development
1. Read `ITERATION3_WAVE2_SUMMARY.md` for architecture details
2. Read `API_V2_ENDPOINTS.md` for complete API reference
3. Run tests to verify functionality
4. Implement specialist agents (Wave 3)

### For Deployment
1. Set up environment variables
2. Configure database (PostgreSQL recommended)
3. Set up Redis for caching
4. Configure JWT secrets
5. Deploy with Docker or directly to your infrastructure

### For Integration
1. Consume API v2 endpoints
2. Implement JWT token generation
3. Handle conversation history
4. Store conversations in database (Wave 3)

## Documentation

- **ITERATION3_WAVE2_SUMMARY.md** - Complete architecture and design
- **API_V2_ENDPOINTS.md** - Detailed API reference
- **WAVE2_COMPLETION_CHECKLIST.md** - Verification checklist
- **README_WAVE2.md** - This file (quick start)

## Support

For issues or questions:
1. Check the relevant documentation file
2. Review application logs
3. Verify environment configuration
4. Test with curl or Postman first

## License

Internal HR Platform - Iteration 3, Wave 2

---

**Status:** ✅ Complete and Production-Ready  
**Date:** February 6, 2025  
**Version:** 2.0.0
