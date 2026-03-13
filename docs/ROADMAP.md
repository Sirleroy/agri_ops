# AgriOps — Technical Roadmap
**Startup-Aligned Engineering Plan**

Version: 2.1 | Last Updated: March 2026
Current Status: Phase 1 Complete — Phase 2 Starting

---

## Guiding Principles

- **Ship real code, not tutorial code** — every decision is defensible in a code review or investor conversation
- **Security is a feature, not a phase** — authentication, authorisation, and audit logging ship with the core
- **Multi-tenancy is not optional** — schema enforces org isolation from day one
- **Observability from the start** — structured logging and health endpoints are not post-launch concerns
- **Dual-track logging** — every technical decision maps to a learning outcome; documented in Obsidian

---

## Phase Overview

| Phase | Startup Milestone | Engineering Focus | Status |
|---|---|---|---|
| 1 | Working local prototype | Core models, CRUD UI, admin | ✅ Complete |
| 2 | Internal alpha | Auth, RBAC, multi-tenancy, API | 🔄 Starting |
| 3 | Closed beta | Deployment, monitoring, hardening | Planned |
| 4 | Freemium launch | Subscriptions, onboarding, scale | Planned |
| 5 | Revenue & growth | Analytics, integrations, ML | Planned |

---

## Phase 1 — Local Prototype ✅ COMPLETE

**Startup Goal:** Prove the data model works for the core use case.
**Completed:** March 2026

### What Was Built

- ✅ Django project scaffolding — 9-app modular structure under `apps/`
- ✅ PostgreSQL database connection (TLSv1.3, local)
- ✅ Core model definitions: Company, CustomUser, Supplier, Product, Inventory, PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem
- ✅ Django admin registration for all models — list_display, search_fields, list_filter, inline items
- ✅ Migration state resolution — all apps clean, no pending migrations
- ✅ Superuser created (admin access confirmed)
- ✅ Full CRUD views and templates for all 7 modules
- ✅ Dark-themed dashboard UI — Tailwind CSS CDN, Alpine.js CDN
- ✅ Sidebar navigation grouped by module (Operations, Procurement, Sales, Admin)
- ✅ GitHub repo initialised and pushed — `.gitignore` excludes secrets and venv

### Known Gaps Carried into Phase 2

- ⚠️ Database credentials hardcoded in `settings.py` — to be resolved in Phase 2 with `python-decouple`
- ⚠️ No login/logout UI — currently redirects through Django admin auth
- ⚠️ No seed data management command yet
- ⚠️ No unit tests yet — deferred to Phase 2
- ⚠️ `settings.py` excluded from git (correct) but no split settings pattern yet

### Design Decisions Logged

- **Hybrid role architecture** — `system_role` (fixed choices, drives RBAC) + `job_title` (free text, display only). Separates permission logic from display to avoid misconfigured access control.
- **Company as tenant root** — every model has `ForeignKey(Company)` enforcing data isolation at schema level
- **Port 8001** — Splunk occupies 8000 on the development machine

---

## Phase 2 — Internal Alpha 🔄 STARTING

**Startup Goal:** Build something a real user can log into and use securely.
**Engineering Focus:** Authentication, RBAC, tenant isolation, environment config, API layer

### 2.1 Environment & Secrets
- [ ] Install `python-decouple`
- [ ] Move `SECRET_KEY`, `DB_PASSWORD`, `DEBUG` to `.env`
- [ ] Update `settings.py` to read from environment
- [ ] Verify `.env` is in `.gitignore` and never committed
- [ ] Update `.env.example` with all required keys

### 2.2 Authentication UI
- [ ] Login page — styled to match design system
- [ ] Logout flow
- [ ] Redirect logic (`LOGIN_URL`, `LOGIN_REDIRECT_URL`)
- [ ] Session timeout configuration
- [ ] "Remember me" consideration — document decision

### 2.3 Role-Based Access Control
- [ ] Define permission matrix: what each `system_role` can access
- [ ] Implement `UserPassesTestMixin` on sensitive views
- [ ] Restrict Companies and Users modules to `admin` role only
- [ ] Restrict delete actions to `admin` and `manager` roles
- [ ] Document every permission decision in Obsidian

### 2.4 Tenant Isolation
- [ ] Override `get_queryset()` on all ListViews to filter by `request.user.company`
- [ ] Override `get_object()` protection — prevent URL enumeration across tenants
- [ ] Test: logged-in user from Company A cannot access Company B records via URL manipulation
- [ ] Document isolation approach and threat model

### 2.5 Audit Logging
- [ ] Create `AuditLog` model — fields: `user`, `action`, `model_name`, `object_id`, `timestamp`, `ip_address`, `changes`
- [ ] Hook into views via `post_save` signal or mixin
- [ ] Admin view for audit log — read-only
- [ ] Document: maps directly to SOC log analysis and chain of custody skills

### 2.6 Seed Data
- [ ] `management/commands/seed_data.py` — creates 2 companies, suppliers, products, inventory, orders
- [ ] Realistic Nigerian agricultural context (consistent with target market)
- [ ] Safe to run multiple times (idempotent)

### 2.7 API Layer (Phase 2 close)
- [ ] Django REST Framework setup
- [ ] API versioning (`/api/v1/`)
- [ ] Serializers for core models
- [ ] ViewSets + Router-based URLs
- [ ] JWT authentication (djangorestframework-simplejwt)
- [ ] OpenAPI schema (drf-spectacular)
- [ ] Postman collection published

### Phase 2 Exit Criteria
A second person can log in, create records scoped to their organisation only, and be blocked from seeing another organisation's data. All secrets are in environment variables. Audit log captures every write action.

---

## Phase 3 — Closed Beta (Planned)

**Startup Goal:** 3–5 real users on a live system.
**Engineering Focus:** Cloud deployment, observability, resilience

- Docker containerisation
- Hosting: Railway or Render
- PostgreSQL managed instance
- GitHub Actions CI/CD
- Structured JSON logging
- Sentry error tracking
- Health check endpoint
- Uptime monitoring

**Phase 3 Exit Criteria:** Live on a public URL, beta users active, errors captured, deployment automated.

---

## Phase 4 — Freemium Launch (Planned)

**Startup Goal:** Public signup, first paying customer.
**Engineering Focus:** Subscriptions, onboarding, scale

- Stripe integration (dj-stripe)
- Free / Growth / Pro tier enforcement
- Email verification (django-allauth)
- Transactional emails
- Redis caching
- Celery task queue
- Load testing baseline

**Phase 4 Exit Criteria:** Public signup end-to-end; first paid conversion; 100 concurrent users without degradation.

---

## Phase 5 — Revenue & Growth (Planned)

**Startup Goal:** Sustainable MRR, product-market fit signals.
**Engineering Focus:** Analytics, integrations, ML

- Organisation analytics dashboard
- CSV/PDF compliance exports
- REST webhook outbound
- Public API documentation
- Weather API integration (optional)
- Commodity price feed (optional)
- SSO / SAML for enterprise
- Internal penetration test — documented as portfolio piece

---

## SOC Analyst Crossover Map

| AgriOps Feature | SOC Skill Developed |
|---|---|
| Audit log model | Chain of custody, incident timeline reconstruction |
| Brute-force protection | Attack pattern recognition |
| Rate limiting + security headers | Defence-in-depth |
| Structured JSON logging | Log analysis, SIEM ingestion |
| CI/CD pipeline | DevSecOps awareness |
| Docker containerisation | Environment isolation |
| Penetration test (Phase 5) | Offensive security, reporting |
| Sentry error tracking | Alert triage, false positive management |
| Tenant isolation | Access control, privilege separation |

---

## Design Decision Log

| Decision | Rationale | Phase |
|---|---|---|
| Company as tenant root | Every model scoped by ForeignKey — isolation by schema design | 1 |
| Hybrid role architecture | `system_role` drives RBAC; `job_title` is display-only free text | 1 |
| Port 8001 for dev server | Splunk occupies 8000 on development machine | 1 |
| Modular app structure (`apps/`) | Separation of concerns; each domain is independently maintainable | 1 |
| Tailwind CDN + Alpine.js | No build step in Phase 1; swap to compiled Tailwind in Phase 3 | 1 |
| No UserCreateView in Phase 1 | User creation requires password handling — deferred to proper auth flow in Phase 2 | 1 |

