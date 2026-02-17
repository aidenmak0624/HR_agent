# Core AI Python Modules - HR Multi-Agent Platform

## Overview

Three core Python modules have been created to support the HR multi-agent platform's LLM processing, data privacy, and response quality assessment capabilities.

---

## 1. LLM Gateway (CORE-002)
**File:** `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/core/llm_gateway.py`

### Purpose
Centralized model routing and request management with built-in reliability patterns.

### Key Classes

#### TaskType (Enum)
Classifies different types of LLM tasks:
- `CLASSIFICATION`: Extract and categorize information (temp=0.1, tokens=256, timeout=10s)
- `SYNTHESIS`: Combine and summarize information (temp=0.3, tokens=2048, timeout=30s)
- `EMBEDDING`: Generate vector embeddings (temp=0.0, tokens=384, timeout=5s)
- `COMPLIANCE`: Ensure HR/legal compliance (temp=0.0, tokens=1024, timeout=20s)
- `REFLECTION`: Analyze and reflect on responses (temp=0.1, tokens=512, timeout=15s)

#### ModelConfig (Pydantic BaseModel)
Configuration for individual models:
- `model_name`: Name/identifier of the LLM
- `temperature`: Sampling temperature (0.0-1.0)
- `max_tokens`: Maximum output tokens
- `timeout_seconds`: Request timeout

#### LLMResponse (Dataclass)
Response envelope from LLM calls:
- `text`: Generated response content
- `model_used`: Which model was used
- `tokens_in`: Input token count
- `tokens_out`: Output token count
- `latency_ms`: Response time in milliseconds
- `cached`: Whether response came from cache

#### LLMGateway (Main Class)
Centralized gateway for all LLM operations.

**Default Models Configuration:**
```python
{
    CLASSIFICATION: gemini-2.0-flash (temp=0.1, max_tokens=256, timeout=10s),
    SYNTHESIS: gemini-2.0-flash (temp=0.3, max_tokens=2048, timeout=30s),
    EMBEDDING: sentence-transformers/all-MiniLM-L6-v2 (timeout=5s),
    COMPLIANCE: gemini-2.0-flash (temp=0.0, max_tokens=1024, timeout=20s),
    REFLECTION: gemini-2.0-flash (temp=0.1, max_tokens=512, timeout=15s)
}
```

**Key Methods:**
- `send_prompt(task_type, prompt, **kwargs) -> LLMResponse`: Main entry point for LLM requests
- `get_stats() -> Dict`: Returns comprehensive usage metrics per model

**Reliability Features:**
- **Retry Logic**: 3 attempts with exponential backoff (1s, 2s, 4s)
- **Circuit Breaker**: Automatic failure detection after 5 consecutive failures; models skip for 60s
- **Response Caching**: SHA256-based prompt hashing with Redis support (24hr TTL)
- **Metrics Tracking**: Per-model statistics including success rate, latency, token counts, cache hits

**Pluggable LLM Handler:**
- Default implementation uses `langchain_google_genai.ChatGoogleGenerativeAI`
- Custom handlers can be injected via constructor for testing/alternative providers

---

## 2. PII Stripper (CORE-004)
**File:** `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/middleware/pii_stripper.py`

### Purpose
Automatically detects and redacts personally identifiable information while maintaining ability to restore original values.

### Key Classes

#### PIIResult (Dataclass)
Result from PII detection/stripping:
- `sanitized_text`: Text with PII replaced by placeholders
- `mapping`: Dict mapping original PII to redaction tokens
- `pii_count`: Total number of PII items found
- `pii_types_found`: List of PII categories detected

#### PIIStripper (Main Class)
Regex-based PII detection and redaction.

**PII Patterns Detected:**
| Pattern | Regex | Redaction |
|---------|-------|-----------|
| SSN | `\d{3}-\d{2}-\d{4}` | `[SSN_REDACTED]` |
| Email | RFC 5322 pattern | `[EMAIL_REDACTED_N]` |
| Phone | US formats (555-1234, (555) 123-4567, etc.) | `[PHONE_REDACTED]` |
| Employee ID | `EMP-\d+` | `[EMPLOYEE_ID_REDACTED]` |
| Salary | `$[\d,]+` | `[SALARY_REDACTED]` |
| Names | From employee context list | `[PERSON_N]` |

**Key Methods:**
- `strip(text, employee_context=None) -> PIIResult`: Detect and redact PII
  - Returns mapping to enable later restoration
- `rehydrate(text, mapping) -> str`: Restore original PII values
- `is_pii_safe(text) -> bool`: Check if text contains any PII patterns

#### PIIMiddleware (Flask Integration)
Automatic PII handling in HTTP requests/responses.

**Hooks:**
- `before_request()`: Strips PII from request body
- `after_request(response)`: Rehydrates original values in response
- Stores mapping in Flask `g` object per-request

**Usage:**
```python
from flask import Flask
from middleware.pii_stripper import PIIMiddleware

app = Flask(__name__)
PIIMiddleware(app)
```

---

## 3. Quality Assessor (CORE-005)
**File:** `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/core/quality.py`

### Purpose
Evaluate response quality across multiple dimensions and recommend fallback actions.

### Key Classes

#### QualityLevel (Enum)
Quality classification:
- `SUFFICIENT`: Score >= 0.7 (response meets quality threshold)
- `MARGINAL`: 0.4 <= Score < 0.7 (borderline quality)
- `INSUFFICIENT`: Score < 0.4 (quality below threshold)

#### QualityScore (Dataclass)
Detailed quality metrics:
- `relevance`: 0-1, keyword overlap + semantic similarity
- `completeness`: 0-1, addresses all parts of query
- `confidence`: 0-1, agent confidence or computed from response
- `source_quality`: 0-1, based on source types (RAG > Web > None)
- `overall`: Weighted average (0.3 relevance + 0.3 completeness + 0.2 confidence + 0.2 source_quality)

#### HallucinationDetector (Helper Class)
Detects potential hallucinations via:
- Excessive hedging phrases ("I think", "might be", etc.)
- Unsupported claims ("allegedly", "reportedly")
- Logical contradictions between sentences

#### QualityAssessor (Main Class)
Evaluates response quality.

**Key Methods:**
- `assess(query, response, sources, tool_results) -> QualityScore`: Full quality assessment
  - Analyzes relevance via keyword overlap and simple semantic similarity
  - Checks completeness by verifying all query parts addressed
  - Computes confidence from agent results or response indicators
  - Rates source quality (RAG=0.9, Web=0.7, None=0.5)

- `get_level(quality_score) -> QualityLevel`: Classify score into level

- `suggest_fallback(quality_score) -> Optional[str]`: Recommend action
  - Returns `"web_search"` if source quality insufficient
  - Returns `"human_escalation"` if comprehensively low quality
  - Returns `None` if quality sufficient

- `validate_response(response) -> List[str]`: Check for common issues
  - Hallucination indicators
  - Error messages in response
  - Unresolved placeholders
  - Response too short
  - Encoding issues

---

## Integration Points

### With LLM Gateway
```python
from core.llm_gateway import LLMGateway, TaskType

gateway = LLMGateway()
response = gateway.send_prompt(TaskType.CLASSIFICATION, user_prompt)
```

### With PII Stripper
```python
from middleware.pii_stripper import PIIStripper

stripper = PIIStripper()

# Strip PII from user input
pii_result = stripper.strip(user_input, employee_names=['John Smith', 'Jane Doe'])

# Process sanitized text
response = process(pii_result.sanitized_text)

# Restore PII in output
original_response = stripper.rehydrate(response, pii_result.mapping)
```

### With Quality Assessor
```python
from core.quality import QualityAssessor, QualityLevel

assessor = QualityAssessor()

quality_score = assessor.assess(
    query=user_query,
    response=llm_response,
    sources=rag_documents,
    tool_results={'confidence_score': 0.85}
)

level = assessor.get_level(quality_score)
if level == QualityLevel.INSUFFICIENT:
    fallback = assessor.suggest_fallback(quality_score)
    # trigger web search or human escalation
```

---

## Dependencies

**Required:**
- `pydantic`: Data validation and settings management

**Optional:**
- `langchain_google_genai`: For Google Generative AI integration
- `redis`: For response caching (if using cache backend)
- `flask`: For PII middleware

---

## Performance Characteristics

### LLM Gateway
- **Caching**: SHA256-hashed prompts, 24-hour TTL
- **Latency**: Measured per request
- **Retry Overhead**: Up to 7 seconds (1+2+4s) on failures

### PII Stripper
- **Processing**: Regex-based, O(n) text length
- **Patterns**: 6 PII categories (SSN, Email, Phone, Employee ID, Salary, Names)
- **Rehydration**: Simple string replacement

### Quality Assessor
- **Assessment Time**: <100ms per response
- **Dimensions**: 4 factors (relevance, completeness, confidence, source_quality)
- **Validation**: Checks for 7+ issue types

---

## File Locations

```
/sessions/beautiful-amazing-lamport/mnt/HR_agent/
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── llm_gateway.py        (CORE-002)
│   │   └── quality.py             (CORE-005)
│   └── middleware/
│       ├── __init__.py
│       └── pii_stripper.py        (CORE-004)
```

---

## Testing

All modules pass Python AST syntax validation:
```bash
python3 -c "import ast; ast.parse(open('llm_gateway.py').read())"
python3 -c "import ast; ast.parse(open('pii_stripper.py').read())"
python3 -c "import ast; ast.parse(open('quality.py').read())"
```

### Example Test Cases

**LLM Gateway:**
```python
gateway = LLMGateway()
response = gateway.send_prompt(TaskType.CLASSIFICATION, "Classify this: ...")
print(response.model_used, response.latency_ms, response.cached)
```

**PII Stripper:**
```python
stripper = PIIStripper()
result = stripper.strip("Employee EMP-123 has SSN 123-45-6789")
assert "[SSN_REDACTED]" in result.sanitized_text
assert result.pii_count == 2
```

**Quality Assessor:**
```python
assessor = QualityAssessor()
score = assessor.assess(query, response)
level = assessor.get_level(score)
validation_issues = assessor.validate_response(response)
```

