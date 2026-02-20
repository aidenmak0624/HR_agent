# Architecture Update — Iteration 6

## Changes Introduced

### New Layer: Security Middleware Pipeline

Iteration 6 adds a 4-stage security middleware pipeline, a metrics/alerting observability stack, and internationalization (i18n) support. These are critical for production readiness.

### Updated Request Flow

```
                         Incoming Request
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│              SECURITY MIDDLEWARE PIPELINE                │
│                                                         │
│  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌──────┐ │
│  │   CORS    │→ │ Sanitizer │→ │  Rate    │→ │ Sec  │ │
│  │ Middleware │  │ (XSS/SQL) │  │ Limiter  │  │ Hdrs │ │
│  └───────────┘  └───────────┘  └──────────┘  └──────┘ │
│                                                         │
│  Origin check    Strip HTML     Token bucket   HSTS     │
│  CSP headers     SQL injection  Redis-backed   X-Frame  │
│  Preflight       Path traversal Per-user       nosniff  │
│  Credentials     Null bytes     Penalty sys    CSP      │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              EXISTING MIDDLEWARE PIPELINE                │
│                                                         │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────────┐ │
│  │   Auth   │→ │   RBAC    │→ │    PII Stripper      │ │
│  │  (JWT)   │  │ (4-tier)  │  │  (regex + rehydrate) │ │
│  └──────────┘  └───────────┘  └──────────────────────┘ │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  I18N MIDDLEWARE                         │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │  Language   │→ │  Translate  │→ │   Agent        │  │
│  │  Detector   │  │  to English │  │   Processing   │  │
│  │  (5 langs)  │  │  (if needed)│  │                │  │
│  └─────────────┘  └─────────────┘  └───────┬────────┘  │
│                                             │           │
│  ┌─────────────┐  ┌─────────────┐           │           │
│  │  Translate  │← │  English    │←──────────┘           │
│  │  Response   │  │  Response   │                       │
│  └─────────────┘  └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 OBSERVABILITY STACK                      │
│                                                         │
│  ┌────────────────────┐  ┌────────────────────────────┐ │
│  │  Prometheus Metrics │  │     Alerting Service       │ │
│  │                     │  │                            │ │
│  │  Counter (requests) │  │  Rules → Evaluate → Alert  │ │
│  │  Gauge (active)     │  │                            │ │
│  │  Histogram (latency)│  │  Channels:                 │ │
│  │                     │  │  • Log (always)            │ │
│  │  /metrics endpoint  │  │  • Slack webhook           │ │
│  │  (Prometheus fmt)   │  │  • PagerDuty               │ │
│  │                     │  │  • Email                   │ │
│  └────────────────────┘  └────────────────────────────┘ │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │              LangSmith Tracing (Iter 4)            │ │
│  │         Agent-level LLM call traces                │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Component Details

#### CORS Middleware (`src/middleware/cors_middleware.py`)

```
CORSMiddleware
  ├── CORSConfig
  │     ├── allowed_origins: ["https://hr.company.com"]
  │     ├── allowed_methods: ["GET", "POST", "PUT", "DELETE"]
  │     ├── allowed_headers: ["Content-Type", "Authorization"]
  │     ├── allow_credentials: True
  │     └── max_age: 86400
  ├── CSPConfig
  │     ├── default_src: ["'self'"]
  │     ├── script_src: ["'self'"]
  │     ├── style_src: ["'self'", "'unsafe-inline'"]
  │     ├── connect_src: ["'self'", "https://api.openai.com"]
  │     └── frame_ancestors: ["'none'"]
  │
  ├── validate_origin(origin) → bool
  ├── handle_preflight(origin) → dict (headers)
  ├── apply_headers(response, origin) → response
  └── get_csp_header() → str
```

#### Input Sanitizer (`src/middleware/sanitizer.py`)

```
InputSanitizer
  ├── SanitizationConfig
  │     ├── strip_html_tags: True
  │     ├── check_sql_injection: True
  │     ├── check_xss: True
  │     ├── check_path_traversal: True
  │     └── max_input_length: 10000
  │
  ├── sanitize(text) → SanitizationResult
  │     ├── sanitized_text: str
  │     ├── is_safe: bool
  │     └── threats_detected: List[str]
  │
  ├── _strip_html_tags(text) → str
  ├── _check_sql_injection(text) → List[str]
  ├── _check_xss(text) → List[str]
  ├── _check_path_traversal(text) → List[str]
  └── batch_sanitize(texts) → List[SanitizationResult]
```

**Detection patterns:**
- SQL: `UNION\s+SELECT`, `DROP\s+TABLE`, `OR\s+1\s*=\s*1`, `--`, `;\s*DELETE`
- XSS: `<script`, `onerror=`, `onload=`, `javascript:`, `data:text/html`
- Path: `../`, `..\\`, `%2e%2e`, `\x00`

#### Rate Limiter (`src/middleware/rate_limiter.py`)

```
RateLimiter
  ├── TokenBucket (per client)
  │     ├── capacity: 60 (tokens)
  │     ├── tokens: float (current)
  │     ├── refill_rate: 1.0 (tokens/sec)
  │     └── consume() → (allowed, remaining)
  │
  ├── check_rate_limit(client_id) → RateLimitResult
  │     ├── allowed: bool
  │     ├── remaining: int
  │     ├── retry_after: float (seconds)
  │     └── penalty_active: bool
  │
  ├── Penalty system:
  │     violations >= threshold → retry_after × penalty_multiplier
  │
  └── Redis backend (optional):
        ├── Token state stored in Redis hash
        ├── Falls back to in-memory if Redis unavailable
        └── Stale client cleanup based on last_seen
```

#### Prometheus Metrics (`src/core/metrics.py`)

```
MetricsRegistry (Singleton)
  ├── Metric Types:
  │     ├── Counter  — inc(), inc_by(n), value, labels
  │     ├── Gauge    — set(v), inc(), dec(), value, labels
  │     └── Histogram — observe(v), count, sum, buckets, percentile(p)
  │
  ├── register(name, type, description, labels, buckets)
  ├── get(name) → Metric
  ├── counter(name) / gauge(name) / histogram(name) → typed access
  │
  ├── export_prometheus() → str (Prometheus text format)
  │     # HELP http_requests_total Total HTTP requests
  │     # TYPE http_requests_total counter
  │     http_requests_total{method="GET",status="200"} 42
  │
  └── export_json() → dict (API-friendly format)
```

#### Alerting Service (`src/core/alerting.py`)

```
AlertingService
  ├── AlertRule
  │     ├── name: "high_error_rate"
  │     ├── metric_name: "http_errors_total"
  │     ├── threshold: 100
  │     ├── comparison: "gt"
  │     ├── severity: CRITICAL
  │     ├── channels: [LOG, SLACK, PAGERDUTY]
  │     ├── cooldown_seconds: 300
  │     └── consecutive_failures: 3
  │
  ├── evaluate_rules(metrics_registry) → List[Alert]
  │     for rule in rules:
  │       metric_value = registry.get(rule.metric_name)
  │       if compare(metric_value, rule.threshold):
  │         if consecutive_count >= rule.consecutive_failures:
  │           if not in_cooldown(rule):
  │             send_alert(rule)
  │
  ├── send_alert(alert)
  │     ├── LOG → logger.warning/critical
  │     ├── SLACK → POST webhook_url with JSON payload
  │     ├── PAGERDUTY → POST events API with routing key
  │     └── EMAIL → SMTP send (configurable)
  │
  └── acknowledge(alert_id) / resolve(alert_id)
```

#### i18n Service (`src/core/i18n.py`)

```
I18nMiddleware
  ├── LanguageDetector
  │     ├── detect(text) → LanguageDetectionResult
  │     │     ├── language: SupportedLanguage (EN/ES/FR/DE/ZH)
  │     │     ├── confidence: float (0.0-1.0)
  │     │     └── method: str ("charset"/"keyword"/"default")
  │     │
  │     ├── _detect_by_charset(text) → (lang, confidence)
  │     │     CJK chars → ZH, Latin diacritics → ES/FR/DE
  │     └── _detect_by_keywords(text) → (lang, confidence)
  │           Language-specific word lists with frequency scoring
  │
  ├── TranslationService
  │     ├── translate(text, source, target) → TranslationResult
  │     ├── Translation cache (LRU with TTL)
  │     │     key: f"{source}:{target}:{hash(text)}"
  │     │     hit rate tracking for optimization
  │     └── LLM-powered: ChatOpenAI with translation prompt
  │
  └── process_request(text) → (english_text, detected_language)
      process_response(text, target_language) → translated_text
```

**Supported languages:** English (EN), Spanish (ES), French (FR), German (DE), Chinese (ZH)

---

## Full System Architecture (Post Iteration 6)

```
┌──────────────────────────────────────────────────────────────┐
│                      CLIENT CHANNELS                         │
│    Web Chat    │    Slack Bot    │    Teams Bot               │
└───────┬────────┴───────┬────────┴──────────┬─────────────────┘
        │                │                   │
        ▼                ▼                   ▼
┌──────────────────────────────────────────────────────────────┐
│  SECURITY PIPELINE: CORS → Sanitizer → Rate Limiter → Hdrs  │
├──────────────────────────────────────────────────────────────┤
│  AUTH PIPELINE:     JWT Auth → RBAC → PII Stripper           │
├──────────────────────────────────────────────────────────────┤
│  I18N PIPELINE:     Detect Language → Translate → Process    │
├──────────────────────────────────────────────────────────────┤
│                    API GATEWAY v2 (Flask)                     │
├──────────────────────────────────────────────────────────────┤
│  AGENT SERVICE:     Memory → Summarizer → RouterAgent        │
├──────────────────────────────────────────────────────────────┤
│  SPECIALIST AGENTS: Employee │ Policy │ Leave │ Onboarding   │
│                     Benefits │ Performance │ Leave Request    │
├──────────────────────────────────────────────────────────────┤
│  CORE SERVICES:     LLM Gateway │ RAG Pipeline │ Quality     │
│                     Workflow Engine │ Doc Generator           │
├──────────────────────────────────────────────────────────────┤
│  DATA LAYER:        Repository Pattern │ SQLAlchemy ORM      │
│                     PostgreSQL │ Redis Cache │ ChromaDB       │
├──────────────────────────────────────────────────────────────┤
│  COMPLIANCE:        GDPR │ Bias Audit │ Audit Logging        │
├──────────────────────────────────────────────────────────────┤
│  OBSERVABILITY:     Prometheus Metrics │ Alerting Service     │
│                     LangSmith Tracing │ Structured Logging    │
├──────────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE:    Docker │ GitHub Actions CI/CD             │
│                     PostgreSQL 15 │ Redis 7 │ Grafana         │
└──────────────────────────────────────────────────────────────┘
```

---

## Module Count Summary

| Layer | Modules | New in Iter 6 |
|-------|---------|---------------|
| Client Channels | 3 (Web, Slack, Teams) | — |
| Security Middleware | 6 (Auth, PII, CORS, Sanitizer, Rate Limiter, Sec Headers) | +4 |
| i18n | 1 (Language Detection + Translation) | +1 |
| API | 2 (API Gateway v2, Agent Routes) | — |
| Services | 5 (Agent, LLM, RAG, Memory, Summarizer) | — |
| Agents | 8 (Router + 7 specialists) | — |
| Core | 12 (LLM GW, RAG, Quality, Workflow, DocGen, Metrics, Alerting, etc.) | +2 |
| Connectors | 4 (Interface, BambooHR, Custom DB, Workday) | — |
| Repositories | 8 (Base + 7 domain repos) | — |
| Compliance | 3 (GDPR, Bias Audit, Audit Log) | — |
| **Total** | **84 production modules** | **+7** |

---

## File Structure Changes

```
src/
├── middleware/
│   ├── cors_middleware.py     (294 lines)  ← NEW
│   ├── sanitizer.py           (349 lines)  ← NEW
│   ├── rate_limiter.py        (357 lines)  ← NEW
│   └── security_headers.py    (224 lines)  ← NEW
├── core/
│   ├── metrics.py             (475 lines)  ← NEW
│   ├── alerting.py            (510 lines)  ← NEW
│   └── i18n.py                (597 lines)  ← NEW
grafana/
└── dashboards/                              ← NEW
tests/unit/
├── test_cors_middleware.py    (32 tests)    ← NEW
├── test_sanitizer.py          (39 tests)    ← NEW
├── test_rate_limiter.py       (35 tests)    ← NEW
├── test_security_headers.py   (23 tests)    ← NEW
├── test_metrics.py            (40 tests)    ← NEW
├── test_alerting.py           (38 tests)    ← NEW
└── test_i18n.py               (41 tests)    ← NEW
```
