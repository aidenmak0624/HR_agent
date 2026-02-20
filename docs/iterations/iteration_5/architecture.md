# Architecture Update — Iteration 5

## Changes Introduced

### New Layer: Messaging Integrations

Iteration 5 introduces the **Integrations Layer** (`src/integrations/`) for external messaging platform connectivity. This is the first implementation of the PRD's FR-014 (Slack and Microsoft Teams Integration).

```
┌─────────────────────────────────────────────────────────┐
│                    Client Channels                       │
│                                                         │
│   ┌──────────┐   ┌──────────┐   ┌───────────────────┐  │
│   │ Web Chat │   │  Slack   │   │ Microsoft Teams   │  │
│   │  (HTML)  │   │  (Bolt)  │   │ (Bot Framework)   │  │
│   └────┬─────┘   └────┬─────┘   └────────┬──────────┘  │
│        │              │                   │             │
└────────┼──────────────┼───────────────────┼─────────────┘
         │              │                   │
         ▼              ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                 API Gateway v2 (Flask)                   │
│   POST /api/v2/query  │  POST /api/v2/slack/events     │
│   GET  /api/v2/health │  POST /api/v2/teams/messages   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Agent Service                         │
│         (Singleton Orchestrator)                        │
│                                                         │
│   ┌─────────────────────────────────────────────────┐   │
│   │          Conversation Memory Store              │   │
│   │  create_session → add_message → get_context     │   │
│   │  close_session → cleanup_expired → search       │   │
│   └─────────────────────────────────────────────────┘   │
│                                                         │
│   ┌─────────────────────────────────────────────────┐   │
│   │         Conversation Summarizer                 │   │
│   │  should_summarize → summarize → merge           │   │
│   │  create_context_with_summary                    │   │
│   └─────────────────────────────────────────────────┘   │
│                         │                               │
└─────────────────────────┼───────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Router Agent                          │
│           Intent Classification + Dispatch              │
│                         │                               │
│    ┌────────┬───────────┼──────────┬──────────┐        │
│    ▼        ▼           ▼          ▼          ▼        │
│ Employee  Policy    Leave     Onboarding  Benefits     │
│  Info     Agent     Agent      Agent       Agent       │
│  Agent              Request                             │
│                     Agent    Performance                │
│                               Agent                    │
└─────────────────────────────────────────────────────────┘
```

### Component Details

#### Slack Integration (`src/integrations/slack_bot.py`)

```
SlackBotService
  └── SlackEventHandler
        ├── handle_message(event)      → AgentService.process_query()
        ├── handle_app_mention(event)  → AgentService.process_query()
        ├── handle_slash_command(cmd)   → AgentService.process_query()
        ├── _format_slack_response()   → Slack Block Kit format
        └── _get_user_context()        → Maps Slack user → RBAC context
```

**Message flow:** Slack Event → Event Handler → Strip mention/parse → AgentService → RouterAgent → Specialist Agent → Format response → Slack API

#### Teams Integration (`src/integrations/teams_bot.py`)

```
TeamsBotService
  └── TeamsActivityHandler
        ├── handle_message(activity)          → AgentService.process_query()
        ├── handle_conversation_update(act)   → Welcome/goodbye messages
        ├── handle_invoke(activity)           → Adaptive Card actions
        ├── _format_teams_response()          → Adaptive Card format
        └── _get_user_context()               → Maps Teams user → RBAC context
```

**Message flow:** Teams Activity → Activity Handler → Parse text → AgentService → RouterAgent → Specialist Agent → Format Adaptive Card → Bot Framework

#### Conversation Memory (`src/core/conversation_memory.py`)

```
ConversationMemoryStore (in-memory, DB-ready interface)
  ├── Sessions Dict[session_id → ConversationSession]
  │     ├── messages: List[ConversationMessage]
  │     ├── total_tokens: int
  │     └── is_active: bool
  │
  ├── create_session(user_id, agent_type) → session_id
  ├── add_message(session_id, role, content) → ConversationMessage
  ├── get_context_window(session_id, max_tokens) → List[ConversationMessage]
  ├── close_session(session_id) → bool
  ├── cleanup_expired() → int (count removed)
  └── search_sessions(user_id, keyword) → List[ConversationSession]
```

**Token budget strategy:** Returns most recent messages that fit within `max_tokens` parameter. Default window: 4000 tokens. Token counting is word-based approximation (words × 1.3).

#### Conversation Summarizer (`src/core/conversation_summarizer.py`)

```
ConversationSummarizer
  ├── should_summarize(messages) → bool (threshold check)
  ├── summarize(messages, user_context) → ConversationSummary
  │     ├── summary_text: str
  │     ├── key_facts: List[str]
  │     ├── action_items: List[str]
  │     └── topics: List[str]
  ├── merge_summaries(summaries) → ConversationSummary
  └── create_context_with_summary(summary, recent_msgs) → List[Message]
```

**Usage pattern:** When message count exceeds threshold (default 10), summarize older messages and use summary + recent messages as agent context. Reduces token usage while preserving important context.

### CI/CD Pipeline (`.github/workflows/ci.yml`)

```
Push/PR → Lint (flake8) → Unit Tests (pytest) → Build (Docker)
                            │
                            ├── Python 3.10
                            └── Python 3.11
                                 │
                                 ├── PostgreSQL 15 (service)
                                 └── Redis 7 (service)
```

---

## File Structure Changes

```
src/
├── integrations/          ← NEW PACKAGE
│   ├── __init__.py
│   ├── slack_bot.py       (495 lines)
│   └── teams_bot.py       (593 lines)
├── core/
│   ├── conversation_memory.py      (477 lines)  ← NEW
│   └── conversation_summarizer.py  (508 lines)  ← NEW
│   └── ... (existing modules unchanged)
.github/
└── workflows/
    └── ci.yml             (137 lines)  ← NEW
tests/
├── e2e/
│   └── __init__.py        ← NEW PACKAGE
├── unit/
│   ├── test_slack_bot.py            (36 tests)  ← NEW
│   ├── test_teams_bot.py            (34 tests)  ← NEW
│   ├── test_conversation_memory.py  (50 tests)  ← NEW
│   └── test_conversation_summarizer.py (31 tests) ← NEW
```
