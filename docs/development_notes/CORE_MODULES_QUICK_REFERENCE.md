# Core Modules - Quick Reference Guide

## Files Created

```
✓ /sessions/beautiful-amazing-lamport/mnt/HR_agent/src/core/llm_gateway.py (CORE-002)
✓ /sessions/beautiful-amazing-lamport/mnt/HR_agent/src/core/quality.py (CORE-005)
✓ /sessions/beautiful-amazing-lamport/mnt/HR_agent/src/middleware/pii_stripper.py (CORE-004)
```

---

## 1. LLM Gateway - Usage Examples

### Import
```python
from core.llm_gateway import LLMGateway, TaskType, ModelConfig, LLMResponse
```

### Basic Usage
```python
gateway = LLMGateway()

# Send a classification task
response = gateway.send_prompt(
    TaskType.CLASSIFICATION,
    "Classify this employee request: ..."
)

print(response.text)           # Response content
print(response.model_used)     # "gemini-2.0-flash"
print(response.latency_ms)     # ~500
print(response.cached)         # True if from cache
```

### With Custom Handler (Testing)
```python
def mock_llm(model_config, prompt, **kwargs):
    return "Mock response"

gateway = LLMGateway(llm_call_handler=mock_llm)
```

### With Redis Cache
```python
import redis

cache = redis.Redis(host='localhost', port=6379)
gateway = LLMGateway(cache_backend=cache, enable_caching=True)
```

### Get Statistics
```python
stats = gateway.get_stats()
# {
#   'gemini-2.0-flash': {
#     'call_count': 42,
#     'success_count': 40,
#     'failure_count': 2,
#     'success_rate': 0.952,
#     'total_tokens_in': 5200,
#     'total_tokens_out': 3400,
#     'average_latency_ms': 450.5,
#     'cache_hits': 8,
#     'circuit_breaker_state': 'closed'
#   }
# }
```

### Custom Model Configuration
```python
custom_config = ModelConfig(
    model_name="custom-llm",
    temperature=0.2,
    max_tokens=1024,
    timeout_seconds=25
)

# Can be used with DEFAULT_MODELS override if needed
```

### Task Types and Default Configs
```python
TaskType.CLASSIFICATION    # Fast, deterministic (0.1 temp)
TaskType.SYNTHESIS         # Longer, creative (0.3 temp)
TaskType.EMBEDDING         # Local transformer model
TaskType.COMPLIANCE        # Strict, deterministic (0.0 temp)
TaskType.REFLECTION        # Thoughtful analysis (0.1 temp)
```

---

## 2. PII Stripper - Usage Examples

### Import
```python
from middleware.pii_stripper import PIIStripper, PIIResult, PIIMiddleware
```

### Basic Usage
```python
stripper = PIIStripper()

# Detect and redact PII
result = stripper.strip(
    "Employee EMP-123 (SSN: 123-45-6789) email: john@example.com",
    employee_context=["John Smith", "Jane Doe"]
)

print(result.sanitized_text)    # "Employee [EMPLOYEE_ID_REDACTED] (SSN: [SSN_REDACTED]) email: [EMAIL_REDACTED_1]"
print(result.pii_count)         # 3
print(result.pii_types_found)   # ['EMPLOYEE_ID', 'SSN', 'EMAIL']
print(result.mapping)           # {'EMP-123': '[EMPLOYEE_ID_REDACTED]', ...}
```

### Rehydrate Original Values
```python
sanitized = result.sanitized_text
original = stripper.rehydrate(sanitized, result.mapping)
# Restores all original PII values
```

### Check PII Safety
```python
is_safe = stripper.is_pii_safe("Hello, this is a safe message")
# True (no PII patterns found)

is_safe = stripper.is_pii_safe("SSN: 123-45-6789")
# False (SSN detected)
```

### Flask Integration
```python
from flask import Flask
from middleware.pii_stripper import PIIMiddleware

app = Flask(__name__)

# Initialize middleware
middleware = PIIMiddleware(app)

# Automatically:
# - Strips PII from request bodies
# - Rehydrates PII in response bodies
# - Stores mapping in flask.g per-request
```

### PII Patterns Detected
```
SSN:          123-45-6789              → [SSN_REDACTED]
Email:        john@example.com         → [EMAIL_REDACTED_1]
Phone:        (555) 123-4567           → [PHONE_REDACTED]
Employee ID:  EMP-12345                → [EMPLOYEE_ID_REDACTED]
Salary:       $75,000.00               → [SALARY_REDACTED]
Names:        John Smith (from context) → [PERSON_1]
```

---

## 3. Quality Assessor - Usage Examples

### Import
```python
from core.quality import QualityAssessor, QualityScore, QualityLevel
```

### Assess Response Quality
```python
assessor = QualityAssessor()

score = assessor.assess(
    query="What is the employee's current role?",
    response="John is a Senior Manager in the HR department.",
    sources=[
        {
            'source_type': 'rag',
            'relevance_score': 0.92,
            'content': '...'
        }
    ],
    tool_results={
        'confidence_score': 0.85,
        'successful_calls': 2,
        'total_calls': 2
    }
)

print(score.relevance)         # 0.85
print(score.completeness)      # 0.9
print(score.confidence)        # 0.85
print(score.source_quality)    # 0.9
print(score.overall)           # 0.877
```

### Get Quality Level
```python
level = assessor.get_level(score)
# QualityLevel.SUFFICIENT

if level == QualityLevel.SUFFICIENT:
    # Proceed with response
    pass
elif level == QualityLevel.MARGINAL:
    # Consider alternative sources
    pass
else:  # INSUFFICIENT
    # Escalate or retry
    pass
```

### Get Fallback Suggestion
```python
fallback = assessor.suggest_fallback(score)

if fallback == "web_search":
    # Try web search for more sources
    pass
elif fallback == "human_escalation":
    # Route to human agent
    pass
# else: None (no fallback needed)
```

### Validate Response for Issues
```python
issues = assessor.validate_response(response_text)

for issue in issues:
    print(f"Issue found: {issue}")
    # Example issues:
    # - "excessive_hedging (5 phrases)"
    # - "unsupported_claims_detected"
    # - "potential_contradiction_detected"
    # - "error_in_response"
    # - "unresolved_placeholders: ['[TODO]']"
    # - "response_too_short"
    # - "high_non_ascii_content"
```

### Quality Score Components
```python
# Relevance: Based on keyword overlap
# Example: Query has 8 keywords, response contains 6
# Score: 6/8 = 0.75

# Completeness: Addresses all query parts
# Example: Query has 3 questions, response answers all 3
# Score: 3/3 = 1.0

# Confidence: From agent or computed
# Example: Agent provides confidence_score = 0.85
# Score: 0.85

# Source Quality: Based on source type
# RAG documents: 0.9
# Web results: 0.7
# No sources: 0.5

# Overall: Weighted average
# 0.75*0.3 + 1.0*0.3 + 0.85*0.2 + 0.9*0.2 = 0.86
```

---

## Integration Pattern

```python
from core.llm_gateway import LLMGateway, TaskType
from core.quality import QualityAssessor, QualityLevel
from middleware.pii_stripper import PIIStripper

# Initialize components
gateway = LLMGateway()
stripper = PIIStripper()
assessor = QualityAssessor()

def process_user_query(user_input, employee_context=None):
    # 1. Strip PII from input
    pii_result = stripper.strip(user_input, employee_context)
    
    # 2. Get LLM response
    llm_response = gateway.send_prompt(
        TaskType.SYNTHESIS,
        pii_result.sanitized_text
    )
    
    # 3. Assess quality
    quality = assessor.assess(
        query=pii_result.sanitized_text,
        response=llm_response.text
    )
    
    # 4. Check quality and decide next action
    level = assessor.get_level(quality)
    if level == QualityLevel.INSUFFICIENT:
        fallback = assessor.suggest_fallback(quality)
        # Trigger fallback (web search, escalation, etc.)
    
    # 5. Validate response
    issues = assessor.validate_response(llm_response.text)
    if issues:
        print(f"Warning: {issues}")
    
    # 6. Rehydrate PII in response
    final_response = stripper.rehydrate(
        llm_response.text,
        pii_result.mapping
    )
    
    return {
        'response': final_response,
        'quality': quality,
        'metrics': gateway.get_stats()
    }
```

---

## Configuration Examples

### Strict Compliance Mode
```python
from core.llm_gateway import LLMGateway, TaskType, ModelConfig

# Override for COMPLIANCE task
strict_config = ModelConfig(
    model_name="gemini-2.0-flash",
    temperature=0.0,      # No randomness
    max_tokens=512,       # Limit output
    timeout_seconds=15
)

gateway = LLMGateway()
gateway.DEFAULT_MODELS[TaskType.COMPLIANCE] = strict_config
```

### Verbose PII Detection
```python
from middleware.pii_stripper import PIIStripper

stripper = PIIStripper(enable_name_detection=True)

# With comprehensive employee list
employees = [
    "John Smith",
    "Jane Doe", 
    "Robert Johnson",
    "Maria Garcia"
]

result = stripper.strip(text, employee_context=employees)
print(f"Found {result.pii_count} PII items: {result.pii_types_found}")
```

### High-Bar Quality Assessment
```python
from core.quality import QualityAssessor

assessor = QualityAssessor()

score = assessor.assess(query, response, sources)

# Custom threshold
if score.overall < 0.8:  # High bar
    print("Response quality below acceptable threshold")
```

---

## Error Handling

### LLM Gateway Failures
```python
from core.llm_gateway import LLMGateway, TaskType

gateway = LLMGateway()

try:
    response = gateway.send_prompt(TaskType.SYNTHESIS, prompt)
except RuntimeError as e:
    print(f"LLM failed after retries: {e}")
    # Circuit breaker may be open if repeated failures
    # Check gateway.get_stats() for circuit_breaker_state
```

### PII Processing
```python
from middleware.pii_stripper import PIIStripper

stripper = PIIStripper()
result = stripper.strip(text)

if result.pii_count > 0:
    print(f"Sanitized {result.pii_count} PII items")
    print(f"Types: {result.pii_types_found}")
```

### Quality Assessment
```python
from core.quality import QualityAssessor, QualityLevel

assessor = QualityAssessor()
score = assessor.assess(query, response)

if assessor.get_level(score) == QualityLevel.INSUFFICIENT:
    issues = assessor.validate_response(response)
    print(f"Quality issues: {issues}")
```

---

## Performance Tips

1. **Caching**: Enable Redis caching for frequently repeated queries
2. **Task Type Selection**: Use lower temp (CLASSIFICATION, COMPLIANCE) for deterministic tasks
3. **PII Detection**: Pre-filter text if employee list is very large
4. **Quality Assessment**: Cache scores for identical query-response pairs
5. **Metrics**: Periodically review stats to identify failing models

---

## Testing Checklist

- [ ] LLMGateway sends correct task type to model
- [ ] Retry logic works with exponential backoff
- [ ] Circuit breaker opens after 5 failures
- [ ] Response caching works correctly
- [ ] PII patterns detect all 6 types
- [ ] Rehydration restores original values
- [ ] QualityAssessor scores in 0-1 range
- [ ] Fallback suggestions are appropriate
- [ ] Validation catches hallucination indicators

