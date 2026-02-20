# Iteration 6 — Plan

## Focus: Security Hardening, Monitoring & Internationalization

**Date:** February 2026
**Issues:** 9
**Priority:** Production-readiness — security middleware, Prometheus metrics, alerting, multi-language support

---

## Issues

### Wave 1 — Security Middleware

| Issue | Title | Description |
|-------|-------|-------------|
| SEC-001 | CORS & CSP Middleware | Configurable CORS policy with origin allowlist, method/header control. Content Security Policy headers with nonce support, frame ancestors, form-action directives. |
| SEC-002 | Input Sanitization | XSS prevention (HTML tag stripping, script removal), SQL injection detection (UNION, DROP, etc.), path traversal blocking, null byte removal. Configurable strictness levels. |
| SEC-003 | Rate Limiter | Redis-backed token bucket algorithm with in-memory fallback. Per-user and per-IP limiting, configurable burst capacity, sliding window, penalty system for violations. |
| SEC-004 | Security Headers | Strict-Transport-Security, X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy. Configurable per header. |

### Wave 2 — Monitoring & Alerting

| Issue | Title | Description |
|-------|-------|-------------|
| MON-001 | Prometheus Metrics | Counter, Gauge, Histogram metric types. MetricsRegistry for registration and export. Prometheus text format export endpoint. Pre-built HTTP request, agent, and LLM metrics. |
| MON-002 | Alerting Service | Multi-channel alerting (log, Slack webhook, PagerDuty, email). Rule-based evaluation with cooldown periods. Alert severity levels (info, warning, critical). Consecutive failure thresholds. |
| MON-003 | Grafana Dashboard Config | JSON dashboard definition for Grafana with panels for request latency, agent throughput, error rates, LLM token usage, and system health. |

### Wave 3 — Internationalization

| Issue | Title | Description |
|-------|-------|-------------|
| I18N-001 | Language Detection | Character set analysis + keyword detection for 5 languages (English, Spanish, French, German, Chinese). Confidence scoring with configurable thresholds. |
| I18N-002 | Translation Service | LLM-powered translation with caching. Translation memory for repeated phrases. Middleware integration for auto-detect → translate → respond → translate-back flow. |

---

## Gate 6 Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | CORS middleware validates origins and sets correct headers |
| 2 | Input sanitizer detects and blocks XSS, SQL injection, path traversal |
| 3 | Rate limiter enforces per-user token bucket with Redis backend |
| 4 | Security headers applied to all responses |
| 5 | Prometheus metrics exported in text format |
| 6 | Alerting service evaluates rules and dispatches to configured channels |
| 7 | Language detector identifies 5 supported languages |
| 8 | Translation service translates and caches responses |
| 9 | All 1070+ unit tests pass with 0 failures, 0 Pydantic deprecation warnings |

---

## Dependencies

- No new pip packages required (all implemented with stdlib + existing deps)
- Grafana dashboard is a JSON config file (no runtime dependency)
- Alerting uses HTTP requests to Slack/PagerDuty webhooks (optional external services)

## Risk Notes

- Rate limiter Redis dependency — falls back to in-memory if Redis unavailable
- Language detection is heuristic-based (no ML model) — accuracy ~85-90% for supported languages
- Translation caching uses in-memory store — consider Redis cache for production scale
