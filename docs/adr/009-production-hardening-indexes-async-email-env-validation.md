---
layout: default
title: "ADR 009: Production Hardening — DB Indexes, Async Email, Env Validation"
---
# ADR 009 — Production Hardening: DB Indexes, Async Email, Env Validation

**Date:** 2026-04-17
**Status:** Accepted

---

## Context

A systematic audit of the platform against common production failure modes (the
"vibe-coded SaaS" failure checklist) identified three concrete gaps that warranted
immediate resolution before the first load test and tenant onboarding:

1. **No explicit DB indexes** on high-traffic filter columns.
2. **Synchronous email sending** — SMTP latency blocking request threads.
3. **Env vars not validated at startup** — missing config fails silently on first
   request rather than loudly on boot.

---

## Decisions

### 1. DB Indexes

**Decision:** Add 12 composite indexes across `SalesOrder`, `PurchaseOrder`, `Batch`,
`Inventory`, and `Farm`. All indexes lead with `company_id` to match the dominant
multi-tenant query pattern (`WHERE company_id = X AND ...`).

**Why composite with `company` first:** Every query in the platform is scoped to a
single tenant. An index on `commodity` alone would be broad and largely useless; an
index on `(company_id, commodity)` targets the exact query shape used by the EUDR
report, batch creation, and farm filtering.

**What was not indexed:** Fields already covered by `unique=True` (which creates an
implicit unique index — `batch_number`, `public_token`, `order_number`) and all
`ForeignKey` fields (Django creates a B-tree index automatically). `AuditLog` already
had compound indexes added in a prior pass.

### 2. Async Email

**Decision:** Wrap all `EmailMultiAlternatives.send()` calls in a daemon thread.

**Why a thread, not Celery:** Celery requires a broker (Redis/RabbitMQ), worker
processes, and deployment configuration. For the current scale (one tenant, low
email volume), this overhead is unjustified. A daemon thread achieves the primary
goal — request returns immediately, SMTP handshake happens out-of-band — with no
new infrastructure dependencies.

**Tradeoffs accepted:**
- No retry on failure. Emails that fail silently are lost. Acceptable until email
  becomes a critical user flow (e.g., order confirmations, compliance alerts).
  `fail_silently=True` ensures a failed send never crashes the app.
- No delivery tracking. Sufficient for current operational notifications.

**What was not changed:** Django's built-in password reset email
(`django.contrib.auth` views). Overriding this requires subclassing the auth views.
Password reset SMTP latency is a one-off user action, not a request-path bottleneck.
`PASSWORD_RESET_TIMEOUT` tightened to 86400s (24 hours) as a separate hardening step.

### 3. Env Validation at Startup

**Decision:** `CompaniesConfig.ready()` validates that `SECRET_KEY`, `DATABASE_URL`,
and `ALLOWED_HOSTS` are present in the OS environment when `DEBUG = False`.
Raises `ImproperlyConfigured` immediately, crashing the boot process with a clear
message before any request is served.

**Why `CompaniesConfig`:** It is the foundational tenant model app, loaded early in
`INSTALLED_APPS`. `ready()` is called once during startup after all apps are
registered — the correct hook for pre-flight checks.

**Why only these three vars:** They are the minimum required for the app to function
at all. Missing `SECRET_KEY` → all sessions and CSRF tokens are broken. Missing
`DATABASE_URL` → every request fails. Missing `ALLOWED_HOSTS` → Django rejects all
requests. Other vars (email, Stripe) fail gracefully or are not yet integrated.

---

## Consequences

- All list views and EUDR report queries are now index-backed for multi-tenant filter
  patterns. Performance impact will be measurable under the first real load test.
- A bad deployment (missing env var) now fails loudly at boot on Render rather than
  producing cryptic errors on user requests.
- Email sends are fire-and-forget. No delivery confirmation. Acceptable at current
  scale; revisit before email becomes a contractual obligation (e.g., compliance
  deadline alerts to operators).
