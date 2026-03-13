# ADR 001 — Django + PostgreSQL as Core Stack

**Date:** March 2026
**Status:** Accepted
**Author:** Ezinna (Founder)

---

## Context

AgriOps requires a backend framework and database capable of supporting a multi-tenant SaaS platform with security-first architecture, complex relational data models, and a clear path to a REST API layer. The platform targets agricultural SMEs and cooperatives in Sub-Saharan Africa and South Asia, with compliance requirements (EUDR) driving the need for robust audit trails and structured data storage.

The decision was made at project inception before any code was written.

---

## Decision Drivers

- Need for rapid development without sacrificing architectural integrity
- Strong ORM support for complex relational models (multi-tenant, FK chains)
- Built-in security defaults (CSRF, XSS, SQL injection protection)
- Clear path to REST API via Django REST Framework
- PostgreSQL-specific features needed: JSONB, row-level security readiness, full-text search
- Open source — zero licensing cost at seed stage
- Large ecosystem of production-tested packages
- Developer familiarity and transferable knowledge for future hires

---

## Options Considered

### Option 1 — Django + PostgreSQL ✅ Chosen
**Pros:**
- Batteries-included framework — admin, ORM, auth, migrations, forms out of the box
- PostgreSQL is the most capable open-source relational database — JSONB, GIS extensions, row-level security
- Django REST Framework is the industry standard for Django APIs
- Extensive security hardening built into the framework by default
- Large talent pool — hiring Django/PostgreSQL developers is straightforward
- Direct path to PostGIS for geolocation features in Phase 4

**Cons:**
- Monolithic by default — requires deliberate architecture to avoid becoming unmaintainable
- Slower than async-native frameworks for high-concurrency workloads (mitigated by Celery in Phase 4)

### Option 2 — FastAPI + PostgreSQL
**Pros:**
- Async-native, high performance
- Automatic OpenAPI documentation generation

**Cons:**
- No built-in admin panel — significant overhead to build
- No built-in auth system — everything must be assembled from scratch
- Smaller ecosystem of production-tested packages
- Less appropriate for a data-heavy, admin-driven application at seed stage

### Option 3 — Node.js (Express/NestJS) + PostgreSQL
**Pros:**
- JavaScript full-stack if frontend moves to React
- Large ecosystem

**Cons:**
- No equivalent of Django admin for rapid internal tooling
- ORM options (Prisma, TypeORM) less mature than Django ORM for complex relational models
- Founder's strongest stack is Python — context switching cost not justified

---

## Decision

**Django 6.x + PostgreSQL 15** is the core stack for AgriOps.

Django's batteries-included approach, security defaults, and mature ecosystem make it the correct choice for a solo founder building a security-first SaaS platform. PostgreSQL's advanced features — JSONB for geolocation data, readiness for PostGIS, row-level security — make it the only viable database choice given the EUDR compliance and multi-tenant requirements.

---

## Consequences

- All models use Django ORM — no raw SQL except for performance-critical queries
- Migrations managed via Django migrations — tracked in version control
- Admin panel used for internal operations and superuser management throughout all phases
- PostgreSQL password managed via environment variables — never hardcoded (Phase 2)
- Path to PostGIS confirmed for Phase 4 geolocation upgrade — JSONField used as interim storage
- Django REST Framework confirmed for Phase 2 API layer
- Future hires should have Django/PostgreSQL experience as a baseline requirement

---

## Related Decisions

- ADR 004 — Geolocation: JSONField over PostGIS (interim strategy)
- ADR 003 — Tenant Isolation Strategy
