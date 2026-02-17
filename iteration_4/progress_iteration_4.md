# Iteration 4 — Progress Report

## Overview
**Iteration**: 4 — Switch to OpenAI + LangSmith Monitoring  
**Status**: ✅ Complete  
**Total Issues**: 10  
**Total Tests**: 671 passing (0 failures)  
**New Tests Added**: 29 (test_tracing.py)  
**Date**: February 2026  

---

## What Changed

### Primary LLM Provider: Google Gemini → OpenAI
- **Before**: All agents used `ChatGoogleGenerativeAI(model="gemini-2.0-flash")` from `langchain-google-genai`
- **After**: All agents use `ChatOpenAI(model="gpt-4o-mini")` from `langchain-openai`
- **Fallback**: Google Gemini kept as fallback via circuit breaker (if OpenAI fails 3 times, auto-switch to Gemini)

### LangSmith Observability Added
- **New module**: `src/core/tracing.py` — LangSmith global tracing + custom per-agent callbacks
- **Opt-in**: Disabled by default. Set `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` to enable
- **Auto-traces**: Every LangGraph node transition, LLM call, and tool execution
- **Custom callbacks**: Per-agent trace summaries with step counts, timing, and error tracking

---

## Wave Summary

### Wave 1 — Dependencies & Configuration (CFG-003 to CFG-006)
**Status**: ✅ Complete

| File | Change |
|------|--------|
| requirements.txt | Added `langchain-openai`, `openai`, `langsmith`. Kept `langchain-google-genai` for fallback |
| .env.example | Added `OPENAI_API_KEY` (primary), `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` |
| config/settings.py | Added `OPENAI_API_KEY`, `LLM_PREMIUM_MODEL`, `LLM_FALLBACK_MODEL`, LangSmith fields |
| config/settings_prod.py | Updated models to `gpt-4o-mini`, added LangSmith config |
| config/settings_dev.py | Same updates, dev project name |
| config/settings_test.py | Added `OPENAI_API_KEY`, mock models, tracing disabled |
| docker-compose.yml | Added `OPENAI_API_KEY` and LangSmith env vars |

### Wave 2 — LLM Provider Swap (LLM-001 to LLM-004)
**Status**: ✅ Complete

| File | Change |
|------|--------|
| src/services/llm_service.py | Primary flipped to OpenAI, Gemini becomes fallback, updated cost tracking |
| src/services/agent_service.py | `ChatGoogleGenerativeAI` → `ChatOpenAI`, added LangSmith init |
| src/core/llm_gateway.py | All DEFAULT_MODELS switched from `gemini-2.0-flash` → `gpt-4o-mini`, default call uses ChatOpenAI with Gemini fallback |
| src/agent/agent_brain.py | Import + instantiation switched to ChatOpenAI |
| src/agent/agent_config.py | Model string: `gemini-2.0-flash` → `gpt-4o-mini` |
| src/agent/tools/web_search_tool.py | ChatOpenAI with `OPENAI_API_KEY` |
| src/agent/tools/fact_checker.py | Same |
| src/agent/tools/planner.py | Same |
| src/agent/tools/comparator.py | Same |

**Key design decision**: BaseAgent and RouterAgent did NOT need changes — they use dependency injection (receive LLM as constructor param). `ChatOpenAI` has the same `.invoke()` interface as `ChatGoogleGenerativeAI`.

### Wave 3 — LangSmith Tracing (TRACE-001, TEST-001)
**Status**: ✅ Complete

| File | Change |
|------|--------|
| src/core/tracing.py | **NEW** — `LangSmithTracer` + `AgentTraceCallback` (~275 lines) |
| src/agents/base_agent.py | `run()` method now creates callback and passes to `graph.invoke(config={"callbacks": [...]})` |
| tests/unit/test_tracing.py | **NEW** — 29 tests covering callbacks, tracer setup, summary generation |
| tests/unit/test_llm_gateway.py | Updated all `gemini-2.0-flash` assertions → `gpt-4o-mini` |

---

## Files Modified

| File | Lines Changed |
|------|---------------|
| requirements.txt | +4 lines (openai, langchain-openai, langsmith) |
| .env.example | +12 lines (OPENAI_API_KEY, LangSmith section) |
| config/settings.py | +8 lines |
| config/settings_prod.py | +8 lines |
| config/settings_dev.py | +8 lines |
| config/settings_test.py | +8 lines |
| docker-compose.yml | +6 lines |
| src/services/llm_service.py | ~40 lines rewritten |
| src/services/agent_service.py | ~20 lines changed |
| src/core/llm_gateway.py | ~25 lines changed |
| src/agent/agent_brain.py | 4 lines changed |
| src/agent/agent_config.py | 1 line changed |
| src/agent/tools/web_search_tool.py | 4 lines changed |
| src/agent/tools/fact_checker.py | 4 lines changed |
| src/agent/tools/planner.py | 4 lines changed |
| src/agent/tools/comparator.py | 4 lines changed |
| src/agents/base_agent.py | ~20 lines added |
| tests/unit/test_llm_gateway.py | 8 lines changed |

## Files Created

| File | Lines |
|------|-------|
| src/core/tracing.py | ~275 |
| tests/unit/test_tracing.py | ~270 |
| iteration_4/plan.md | ~95 |

---

## Cumulative Project Stats

| Metric | Iter 1 | Iter 2 | Iter 3 | Iter 4 | Total |
|--------|--------|--------|--------|--------|-------|
| Issues | 20 | 15 | 14 | 10 | 59 |
| Modules | 16 | 14 | 39 | 3 | 72 |
| Tests | 163 | 504 | 642 | 671 | 671* |

*Cumulative total — each iteration includes prior tests.

---

## How to Use

### Start with OpenAI
```bash
# Set your OpenAI key
echo "OPENAI_API_KEY=sk-..." >> .env

# Run the app
python -m src.app_v2
```

### Enable LangSmith Tracing
```bash
# Add to .env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=hr-multi-agent

# Run the app — all LangGraph runs now appear in LangSmith dashboard
python -m src.app_v2
```

### View traces
Go to https://smith.langchain.com → select "hr-multi-agent" project → see every agent run with node-by-node execution trace.

---

## Gate 4 Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | POST /api/v2/query uses ChatOpenAI for reasoning | ✅ |
| 2 | Circuit breaker falls back to Gemini after 3 OpenAI failures | ✅ |
| 3 | All 671 tests pass with OpenAI mocks | ✅ |
| 4 | LangSmith traces appear when LANGCHAIN_TRACING_V2=true | ✅ |
| 5 | Tracing has zero overhead when disabled | ✅ |
