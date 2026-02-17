# Iteration 4 — Switch to OpenAI + LangSmith Monitoring

## Overview
**Primary LLM**: OpenAI `gpt-4o-mini` (via `langchain-openai`)
**Fallback LLM**: Google Gemini `gemini-2.0-flash` (kept as fallback)
**Monitoring**: LangSmith (official LangChain observability, opt-in via env var)
**Issues**: 10
**Waves**: 3

---

## Wave 1 — Dependencies & Configuration (4 issues)

### CFG-003: Update requirements.txt
Add `langchain-openai`, `openai`, `langsmith`. Keep `langchain-google-genai` and `google-generativeai` for fallback.

### CFG-004: Update .env.example
- Add `OPENAI_API_KEY` as primary key
- Keep `GOOGLE_API_KEY` marked as fallback
- Add LangSmith vars: `LANGCHAIN_TRACING_V2=false`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT=hr-multi-agent`

### CFG-005: Update config/settings.py + settings_prod/dev/test.py
- Add `OPENAI_API_KEY` field
- Change default models from `gemini-2.0-flash` → `gpt-4o-mini`
- Add `LLM_PREMIUM_MODEL = "gpt-4o"`
- Add LangSmith config fields (tracing off by default)

### CFG-006: Update docker-compose.yml
- Add `OPENAI_API_KEY` env var
- Add optional LangSmith env vars

---

## Wave 2 — LLM Provider Swap (4 issues)

### LLM-001: Update src/services/llm_service.py
- Primary → `ChatOpenAI(model="gpt-4o-mini")`
- Fallback → `ChatGoogleGenerativeAI(model="gemini-2.0-flash")`
- Update circuit breaker: on OpenAI failure, switch to Gemini
- Update cost tracking for OpenAI pricing

### LLM-002: Update src/services/agent_service.py
- Import `ChatOpenAI` from `langchain_openai`
- Create LLM with `ChatOpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY)`
- Pass to RouterAgent (dependency injection — RouterAgent unchanged)

### LLM-003: Update src/core/llm_gateway.py
- Change DEFAULT_MODELS dict: all `gemini-2.0-flash` → `gpt-4o-mini`
- Replace `ChatGoogleGenerativeAI` instantiation with `ChatOpenAI`
- Keep Gemini as fallback option in provider enum

### LLM-004: Update legacy agent files (4 tool files + agent_brain.py + agent_config.py)
- `src/agent/agent_brain.py` — Replace primary LLM with ChatOpenAI
- `src/agent/agent_config.py` — Change model string
- `src/agent/tools/web_search_tool.py` — Replace ChatGoogleGenerativeAI → ChatOpenAI
- `src/agent/tools/fact_checker.py` — Same swap
- `src/agent/tools/planner.py` — Same swap
- `src/agent/tools/comparator.py` — Same swap

**Note**: BaseAgent and RouterAgent use dependency injection (receive LLM as constructor param). They do NOT need changes — ChatOpenAI has the same `.invoke()` interface.

---

## Wave 3 — LangSmith Tracing + Tests (2 issues)

### TRACE-001: Create src/core/tracing.py + integrate
- New file: `src/core/tracing.py`
  - `LangSmithTracer.setup_tracing()` — sets env vars for global LangGraph tracing
  - `AgentTraceCallback(BaseCallbackHandler)` — custom callback logging LLM calls, tool usage, node transitions
- Update `src/services/agent_service.py` — call `setup_tracing()` on startup
- Update `src/agents/base_agent.py` — pass callbacks to `graph.invoke(state, {"callbacks": [...]})`
- Tracing is opt-in: disabled by default, enabled when `LANGCHAIN_TRACING_V2=true`

### TEST-001: Update tests + write new tracing tests
- Update test mocks referencing Gemini → OpenAI
- Update model name assertions in test_services.py, test_config.py
- New `tests/unit/test_tracing.py` (~30 tests): setup, callbacks, enable/disable

---

## Files Changed Summary

| File | Change Type |
|------|-------------|
| requirements.txt | MODIFY — add openai, langchain-openai, langsmith |
| .env.example | MODIFY — add OPENAI_API_KEY, LangSmith vars |
| config/settings.py | MODIFY — add fields, change defaults |
| config/settings_prod.py | MODIFY — update model names |
| config/settings_dev.py | MODIFY — update model names |
| config/settings_test.py | MODIFY — update model names |
| docker-compose.yml | MODIFY — add env vars |
| src/services/llm_service.py | MODIFY — flip primary/fallback |
| src/services/agent_service.py | MODIFY — ChatOpenAI + tracing init |
| src/core/llm_gateway.py | MODIFY — default models + provider |
| src/agent/agent_brain.py | MODIFY — ChatOpenAI import |
| src/agent/agent_config.py | MODIFY — model string |
| src/agent/tools/web_search_tool.py | MODIFY — ChatOpenAI |
| src/agent/tools/fact_checker.py | MODIFY — ChatOpenAI |
| src/agent/tools/planner.py | MODIFY — ChatOpenAI |
| src/agent/tools/comparator.py | MODIFY — ChatOpenAI |
| src/core/tracing.py | **NEW** — LangSmith integration |
| src/agents/base_agent.py | MODIFY — callback support |
| tests/unit/test_tracing.py | **NEW** — tracing tests |
| tests/unit/test_services.py | MODIFY — update assertions |
| tests/unit/test_config.py | MODIFY — update assertions |

---

## How It Works After Implementation

```
User sets OPENAI_API_KEY in .env → app starts with ChatOpenAI as primary LLM
If OpenAI fails 3 times → circuit breaker switches to Gemini fallback
User optionally sets LANGCHAIN_TRACING_V2=true + LANGCHAIN_API_KEY → all LangGraph runs traced in LangSmith dashboard
```

## Gate 4 Criteria
1. POST /api/v2/query uses ChatOpenAI for reasoning
2. Circuit breaker falls back to Gemini after 3 OpenAI failures
3. All 642+ tests pass with OpenAI mocks
4. LangSmith traces appear when LANGCHAIN_TRACING_V2=true
5. Tracing has zero overhead when disabled
