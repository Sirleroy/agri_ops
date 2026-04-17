---
layout: default
title: Production Readiness Audit
---
# AgriOps — Production Readiness Audit

A full audit of the platform against common production failure modes.
Last reviewed: 2026-04-17. Status reflects the current `main` branch.

---

## Audit Results

| Area | Status | Detail |
|---|---|---|
| Input sanitisation | ✅ | Django ORM prevents SQL injection. All user input validated through forms at system boundaries. `\|escapejs` applied on Alpine.js attribute interpolation. |
| Error boundaries | ✅ | Custom branded 404, 403, and 500 pages. Self-contained HTML (no base.html dependency) — render correctly even if context processors or DB are unavailable. |
| Hardcoded secrets | ✅ | `python-decouple` throughout. No secrets in codebase. All credentials via environment variables. |
| Token storage | ✅ | Main app uses session auth — no localStorage tokens. DRF API uses SimpleJWT for external consumers only. |
| Session expiry | ✅ | `SESSION_COOKIE_AGE = 28800` (8 hours). Ops dashboard: 2 hours. |
| Password reset expiry | ✅ | `PASSWORD_RESET_TIMEOUT = 86400` (24 hours). Tightened from Django's 3-day default on 2026-04-17. |
| Email sending | ✅ | All email sends run in daemon threads — SMTP latency does not block the request cycle. See ADR 009. |
| CDN for assets | ✅ N/A | No user-uploaded images. WhiteNoise serves static assets with compression. Non-issue at current scale. |
| Env validation at startup | ✅ | `CompaniesConfig.ready()` checks `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS` on boot in production. Raises `ImproperlyConfigured` immediately rather than failing on first request. |
| Health check | ✅ | `/health/` returns `{"status": "ok"}`. Wired to Render's health check. |
| Rate limiting | ✅ | DRF throttle: 20 req/hr anon, 200 req/hr authenticated. `django-axes`: 5 failures → 1-hour lockout, keyed on username + IP. Public trace view: 60 req/hr per IP (manual cache counter). |
| Pagination | ✅ | `paginate_by = 50` on all list views (8+). Enforced at the ListView level. |
| DB indexing | ✅ | 12 compound indexes added 2026-04-17. See index inventory below. |
| CORS | ✅ | `CORS_ALLOWED_ORIGINS` explicitly set. `CORS_ALLOW_CREDENTIALS = True`. No wildcard. |
| DB connection pooling | ✅ | `conn_max_age=600` on production `DATABASE_URL` config — persistent connections, 10-minute pool. |
| Role checks | ✅ | `StaffRequiredMixin`, `ManagerRequiredMixin`, `OrgAdminRequiredMixin` on every view. Template permission guards sync'd to view mixins (audited 2026-03-22, re-checked 2026-04-16). |
| Logging | ✅ | Production: rotating file handler + console at WARNING level. `django.security` errors captured separately. `AuditLog` model records every create/update/delete with user, IP, and before/after field changes. |
| Backups | ✅ | Render managed PostgreSQL — daily automated backups included. See `docs/runbooks/backup-restore.md`. |
| Stripe webhook verification | ✅ N/A | Stripe not integrated. Parked until first paying tenant. |
| Brute force protection | ✅ | `django-axes` — see Rate limiting above. |
| Tenant isolation | ✅ | Every view filters by `company=request.user.company`. No middleware — enforced manually in `get_queryset()` and `get_object()` on every view. See ADR 003. |

---

## DB Index Inventory

Added 2026-04-17. All indexes are composite with `company` as the leading column to align with the multi-tenant query pattern (`WHERE company_id = X AND ...`).

| Model | Index name | Fields | Purpose |
|---|---|---|---|
| `SalesOrder` | `so_company_date_idx` | `company, -order_date` | Order list sorted by date |
| `SalesOrder` | `so_company_status_idx` | `company, status` | Status filter (pending/completed/etc) |
| `PurchaseOrder` | `po_company_date_idx` | `company, -order_date` | Order list sorted by date |
| `PurchaseOrder` | `po_company_status_idx` | `company, status` | Status filter |
| `Batch` | `batch_company_created_idx` | `company, -created_at` | Batch list sorted by date |
| `Batch` | `batch_company_commodity_idx` | `company, commodity` | EUDR report commodity filter |
| `Batch` | `batch_locked_idx` | `is_locked` | Lock/unlock status filter |
| `Inventory` | `inv_company_product_idx` | `company, product` | Stock lookup by product |
| `Farm` | `farm_company_eudr_idx` | `company, is_eudr_verified` | EUDR report verified farm count |
| `Farm` | `farm_company_commodity_idx` | `company, commodity` | Farm filter by commodity |
| `Farm` | `farm_company_risk_idx` | `company, deforestation_risk_status` | Risk classification filter |
| `Farm` | `farm_company_supplier_idx` | `company, supplier` | Farm filter by supplier |

Pre-existing indexes (not added here):
- All `ForeignKey` fields: Django creates a DB index automatically
- `unique=True` fields (`batch_number`, `public_token`, `order_number`): implicit unique index

Pre-existing indexes on `AuditLog`:
- `company, -timestamp` — audit trail list
- `model_name, object_id` — per-object history lookup

---

## Known Gaps

| Gap | Severity | Plan |
|---|---|---|
| ~~No custom 404/500 error pages~~ | ✅ Closed 2026-04-17 | |
| Sync Django password reset email (via `django.contrib.auth`) | Low | Built-in view — cannot wrap in thread without overriding. SMTP latency on password reset is acceptable. |
| No startup validation of email/SMTP vars | Info | Email fails silently (`fail_silently=True`) so a missing SMTP config won't crash the app — it just won't send. Acceptable until email is a critical user flow. |

---

## Review Schedule

Re-audit before each of:
- First paying tenant onboarding
- First external security review or compliance audit
- Any significant infrastructure change (CDN, new auth flow, Stripe integration)
