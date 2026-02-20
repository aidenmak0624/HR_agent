# Iteration 5 — Plan

## Focus: CI/CD, Messaging Integration & Conversation Memory

**Date:** February 2026
**Issues:** 8
**Priority:** Address critical PRD gaps — Slack/Teams (FR-014 P0), persistent memory (FR-009 P1), and testing infrastructure

---

## Issues

### Wave 1 — CI/CD & Testing Infrastructure

| Issue | Title | Description |
|-------|-------|-------------|
| CICD-001 | GitHub Actions CI Pipeline | Lint (flake8), test (pytest), build (Docker) on every push and PR. Matrix across Python 3.10/3.11. |
| TEST-002 | E2E Test Framework | Playwright-based test scaffolding with conftest, page objects, and 6 scenario definitions for frontend flows. |
| TEST-003 | Integration Test Templates | Database integration test patterns using testcontainers for PostgreSQL + Redis. |
| TEST-004 | LLM Smoke Test Framework | Rate-limited smoke tests that validate real OpenAI API responses when API key is available. |

### Wave 2 — Messaging Platform Integration

| Issue | Title | Description |
|-------|-------|-------------|
| MSG-001 | Slack Bot Integration | Slack Bolt SDK-based event handler. Handles messages, app mentions, slash commands (/hr-ask). Channel allowlist, user context mapping, formatted responses with confidence badges. |
| MSG-002 | Microsoft Teams Bot | Bot Framework-compatible activity handler. Handles messages, conversation updates, card invocations. Adaptive Card responses with confidence indicators. |

### Wave 3 — Conversation Memory

| Issue | Title | Description |
|-------|-------|-------------|
| MEM-001 | Persistent Conversation Memory | DB-backed session store with in-memory fallback. Session lifecycle (create/get/close/cleanup), context windowing with token budget, message history, session search. |
| MEM-002 | Conversation Summarization | LLM-powered summarization of long conversations. Extracts key facts, action items, topics. Merges summaries across sessions. Creates augmented context with summary + recent messages. |

---

## Gate 5 Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | GitHub Actions pipeline runs on push (lint + test + build) |
| 2 | E2E test framework collects and runs Playwright tests |
| 3 | Slack bot handles messages, mentions, and slash commands |
| 4 | Teams bot handles messages and conversation updates |
| 5 | Conversation memory persists sessions with token-windowed context |
| 6 | Conversation summarizer extracts key facts from message history |
| 7 | All new modules have comprehensive unit tests |
| 8 | All 1070+ unit tests pass with 0 failures |

---

## Dependencies

- `slack-bolt` (Slack SDK)
- `botbuilder-core` (Teams Bot Framework)
- `playwright` (E2E testing)
- `testcontainers` (integration testing)
- No new production dependencies added to requirements.txt yet (Slack/Teams are optional)

## Risk Notes

- Slack/Teams integrations require external API tokens for live testing — unit tests use mocks
- E2E tests require a running server — separate from unit test suite
- Conversation memory token counting is approximate (word-based estimate)
