---
layout: default
title: "ADR 012 — Enterprise Tenant API Integration: Deferral and Build Sequence"
---

# ADR 012 — Enterprise Tenant API Integration: Deferral and Build Sequence

**Date:** May 2026
**Status:** Deferred — triggers and P0 build sequence defined
**Author:** Ezinna (Founder)

---

## Context

AgriOps already exposes a REST API at `/api/v1/` built on DRF + SimpleJWT. Six tenant-scoped viewsets (suppliers, farms, products, inventory, purchase-orders, sales-orders), three special endpoints (`farms/eudr-pending`, `farms/high-risk`, `inventory/low-stock`), one bulk-import endpoint (`farms/import/`), and JWT token issuance/refresh. Tenant scoping is enforced through `TenantScopedViewSet`, audit logging fires on writes, pagination defaults to 20/page, throttling is `20/hr` anonymous and `200/hr` per user.

This is sufficient for human users and minimal first-party integrations. It is **not** sufficient for an enterprise tenant integration — a paying customer (e.g. a cocoa exporter or institutional buyer) connecting their own backend systems to AgriOps for compliance reporting, traceability ingestion, or certificate retrieval.

The gap between "API exists" and "API ready for serious enterprise integration" is real, sized, and worth naming explicitly so it is built deliberately rather than reactively.

---

## What an enterprise tenant integration requires

A sophisticated integrator expects:

1. **Tenant-scoped service-account credentials** — long-lived API keys, separate from human user logins, rotatable, scoped (read vs. read-write), revocable.
2. **Versioned and documented endpoints** — OpenAPI / Swagger specification, code samples, errors catalogue, deprecation policy.
3. **Hard-enforced tenant scoping** — cross-tenant access returns 404 (no information leakage), enforced by both application layer and database layer (RLS — see [ADR 011](011-postgres-row-level-security-deferral.md)).
4. **Idempotency on writes** — `Idempotency-Key` header so retries don't double-create.
5. **Webhooks for events** — push notifications when batch state, farm verification, or certificate generation changes; signed payloads, retry queue, dead-letter handling.
6. **Per-tenant rate limits driven by `plan_tier`** — Enterprise quotas, not user-blind throttling.
7. **Sandbox environment** — a dummy-data tenant they integrate against before flipping to production.
8. **Read-action audit logs** on sensitive endpoints — who downloaded what, when (their auditors will ask).
9. **Customer-facing status page + SLA** — incident communication, uptime guarantees, support escalation.
10. **Tenant-facing credential management UI** — `org_admin` issues, rotates, revokes API keys from the admin panel.

Today, items 3 (partial — application-layer only), 5 (event sources exist), and parts of 8 (write actions) exist. Items 1, 2, 4, 6, 7, 9, 10 are unbuilt.

---

## Triggers

Implement to the P0 sequence below when **any one** of the following becomes true:

1. **First paying enterprise tenant signs a contract that includes API integration as a deliverable.** This is the most likely real trigger.
2. **First paying enterprise tenant requires data export/integration in their own systems** even if not formally specified in contract.
3. **Buyer portal (Phase 5) goes live.** External multi-tenant API consumers shift the threat model the same way; the build sequence overlaps significantly with the buyer portal's API requirements.
4. **A grant or partnership requires programmatic data access** (e.g. a research partner wanting batch traceability dumps via API).

If none of the above applies, this work is premature: the platform's current API is sufficient for human users and first-party tooling.

---

## P0 Build Sequence (when triggered)

These four items must ship before any enterprise tenant integration is flipped to production. Building one without the others ships an incomplete posture.

### 1. API tests
Close the gap from [`project_api_test_gap.md`](https://github.com/Sirleroy/agri_ops). The currently-empty `apps/api/tests.py` becomes a real suite:

- Tenant A token cannot read Tenant B resources (404, not 403)
- Suspended tenant token returns 403 on every protected endpoint
- Role-sensitive permissions (viewer / staff / manager / org_admin) behave correctly per HTTP method
- JWT tampered token returns 401, not 500
- Idempotency-key duplicate request returns the original response

Add to `verify.sh` so they run pre-deploy alongside the existing suite.

### 2. API key / service account model
A new `TenantAPICredential` model: tenant-scoped, name, prefix, hashed key, scopes (read / write), expiry, last-used-at, revocation. Org admins manage from the admin panel. JWT remains for human users.

This is also where API access metering connects to billing — see ADR 010. Design the model with that in mind; do not bolt billing on later.

### 3. Per-tenant rate limits driven by `plan_tier`
Custom DRF throttle class reads the credential's tenant `plan_tier` and applies tier-based limits (e.g. `Starter: 200/hr · Growth: 1000/hr · Enterprise: 10000/hr`) with documented burst tolerance. The current user-based throttle becomes a fallback floor.

### 4. Idempotency on writes
POST endpoints accept `Idempotency-Key`. Same key plus same body within 24h returns the original response without re-executing. Stripe-shape pattern. Stored in a small `APIIdempotencyRecord` model with TTL.

---

## P1 Build Sequence (within first month of integration)

Required for a polished customer experience but not strictly blocking go-live:

### 5. OpenAPI / Swagger specification
Enable DRF's built-in schema generation. Host at `/api/docs/` or publish to `docs.agriops.io`. Customer reads this; AI coding tools generate clients from it.

### 6. Webhooks
`WebhookSubscription` model + signed payload (HMAC-SHA256) + retry queue with exponential backoff + dead-letter after 7 days. Event catalogue starts with: `batch.compliance_status_changed`, `farm.verified`, `certificate.issued`, `farm.imported`. **Requires a task queue (Celery + Redis or Django-Q2)** — see [`project_async_queue.md`](https://github.com/Sirleroy/agri_ops). That async queue is also a prerequisite for the deforestation engine; building it once benefits both tracks.

### 7. Read-action audit logging on sensitive endpoints
Every farm download, every certificate fetch — logged with user, IP, timestamp, endpoint, and the tenant's perspective. Volume is the concern; sample non-sensitive reads, log all sensitive ones. Their auditors will ask.

### 8. API health endpoint and customer-facing status page
`/api/v1/health` returning version, build time, DB latency. Status page (statuspage.io or self-hosted at `status.agriops.io`).

---

## P2 (defer until customer asks)

- **Sandbox environment** — Render preview env + `seed_demo` snapshot + `sandbox.api.agriops.io` subdomain. Hosting cost is non-zero; defer until a customer specifically requests one.
- **Code samples** — Python, Node, Java client examples. OpenAPI generators handle this once the spec is published.
- **SLA / uptime monitoring** — UptimeRobot or similar. Cheap, addable any time.
- **Stable error code catalogue** — `{"error": {"code": "FARM_NOT_FOUND", ...}}` shape standardised across endpoints. Useful but not blocking.

---

## Hidden Dependencies

Three things look small but bite when triggered:

- **The API key model couples to billing.** ADR 010 (billing architecture) does not yet account for API metering. If Enterprise plan includes 10k req/hr, you must count and bill overage. That decision must be made *before* the API key model ships, otherwise refactoring billing later is costly.
- **Webhook delivery is fragile from a synchronous Django process.** A task queue is genuinely required, not optional. The deferred [`project_async_queue.md`](https://github.com/Sirleroy/agri_ops) memory becomes load-bearing the moment webhooks are scheduled.
- **OpenAPI schema generation surfaces serialiser inconsistencies.** First time enabled, expect 2–3 days of cleanup. Better before a customer reads the spec than after.

---

## RLS Connection

The "first paying enterprise tenant" trigger here overlaps directly with [ADR 011](011-postgres-row-level-security-deferral.md) trigger 1 ("first paying enterprise tenant with a security questionnaire") and trigger 5 ("third-party DB-adjacent access"). When this work is triggered, RLS is also triggered. Sequence them together: build API keys, RLS bypass, and the test suite for both as one coherent migration. Two security questionnaires, one set of work.

---

## Decision

Defer the enterprise API integration build. Implement the P0 sequence in full when any single trigger criterion fires. Do not flip an enterprise integration to production with any P0 item missing. Sign contracts only after either:

(a) the P0 list is shipped, or
(b) the contract explicitly includes a 30-day pre-go-live integration delivery window during which AgriOps builds the missing primitives.

Half-API-readiness is forbidden — the gap between "tests pass on dev" and "we can credibly serve a paying integrator" is wider than it looks.

---

## Related Decisions

- [ADR 003 — Tenant Isolation Strategy](003-tenant-isolation-strategy.md) — the application-layer foundation that API tenant scoping rides on
- [ADR 010 — Billing Architecture](010-billing-architecture.md) — API metering connects here; design the API key model with billing in mind
- [ADR 011 — PostgreSQL Row-Level Security Deferral](011-postgres-row-level-security-deferral.md) — same "first enterprise tenant" trigger fires both this and RLS
- `project_api_test_gap.md` — the test suite gap closes as part of P0 step 1
- `project_async_queue.md` — task queue is a hard prerequisite for webhooks (P1 step 6)
- `project_pricing_model.md` — Enterprise plan API quotas must be defined before P0 step 3 ships
- `project_buyer_portal.md` — buyer portal API surface overlaps significantly; build sequence pays forward to Phase 5
