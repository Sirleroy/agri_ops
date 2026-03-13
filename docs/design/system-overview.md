# AgriOps — System Overview

**Version:** 2.0
**Date:** March 2026
**Status:** Phase 2 Complete

---

## 1. Product Summary

AgriOps is a secure, multi-tenant SaaS platform for agricultural SMEs and cooperatives. It provides real-time traceability across agricultural supply chains — from farm procurement through storage and inventory to market dispatch — with built-in EUDR compliance support.

**Primary market:** Agricultural cooperatives, SME processors, and agri-logistics companies in Sub-Saharan Africa and South Asia.

**Core value proposition:** Farm-to-market clarity without the enterprise price tag. Security-first architecture from day one.

---

## 2. Architecture Overview
```
┌─────────────────────────────────────────────────┐
│                  Client Layer                   │
│     Browser (Django Templates + Tailwind)       │
│     Mobile / External (REST API — JWT)          │
└────────────────────┬────────────────────────────┘
                     │ HTTPS
┌────────────────────▼────────────────────────────┐
│              Application Layer                  │
│                                                 │
│  Django 6.x                                     │
│  ├── Authentication (Session + JWT)             │
│  ├── RBAC Permission Layer                      │
│  ├── Multi-Tenant Queryset Filtering            │
│  ├── Business Logic (Views / Viewsets)          │
│  ├── Audit Logging                              │
│  └── Django REST Framework + SimpleJWT          │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│                 Data Layer                      │
│                                                 │
│  PostgreSQL 15                                  │
│  ├── All application data                       │
│  ├── JSONB for geolocation (PostGIS in Phase 4) │
│  ├── Audit log table                            │
│  └── Row-level security (Phase 4)              │
└─────────────────────────────────────────────────┘
```

---

## 3. Application Structure
```
agri_ops/
├── agri_ops_project/      # Django configuration
│   ├── settings.py        # Imports from config/settings/development.py
│   ├── urls.py            # Root URL configuration
│   ├── wsgi.py
│   └── asgi.py
├── config/
│   └── settings/
│       ├── base.py        # All shared settings — python-decouple
│       ├── development.py # DEBUG=True, local overrides
│       └── production.py  # HTTPS, HSTS, secure cookies, logging
├── apps/
│   ├── api/               # DRF viewsets, serializers, JWT endpoints
│   ├── audit/             # AuditLog model, write action logging
│   ├── companies/         # Tenant root — Company model
│   ├── users/             # CustomUser, RBAC mixins, permissions
│   ├── suppliers/         # Supplier + Farm + ComplianceDocument
│   ├── products/          # Product catalogue
│   ├── inventory/         # Stock management with low-stock alerts
│   ├── purchase_orders/   # Procurement records
│   ├── sales_orders/      # Customer order records
│   ├── dashboard/         # Aggregated stats + seed_data command
│   └── reports/           # Compliance reporting — Phase 3
├── templates/             # Django HTML templates
├── static/                # Static assets
├── docs/                  # This documentation
├── logs/                  # Application logs (not in git)
└── manage.py
```

---

## 4. Domain Model Summary

| Model | App | Purpose | Tenant Scoped |
|---|---|---|---|
| Company | companies | Tenant root | — |
| CustomUser | users | Platform users with RBAC | ✅ |
| Supplier | suppliers | Trading entities | ✅ |
| Farm | suppliers | Physical farm plots — EUDR unit | ✅ |
| ComplianceDocument | suppliers | Farm compliance file attachments | ✅ |
| Product | products | Commodity catalogue | ✅ |
| Inventory | inventory | Stock levels per product | ✅ |
| PurchaseOrder | purchase_orders | Procurement records | ✅ |
| PurchaseOrderItem | purchase_orders | Line items | ✅ |
| SalesOrder | sales_orders | Customer order records | ✅ |
| SalesOrderItem | sales_orders | Line items | ✅ |
| AuditLog | audit | Write action history | ✅ |

Full ERD: `/docs/diagrams/erd.dbml`
Full data model documentation: `/docs/design/data-model.md`

---

## 5. RBAC Permission Matrix

| Action | Viewer | Staff | Manager | OrgAdmin |
|---|---|---|---|---|
| View records | ✅ | ✅ | ✅ | ✅ |
| Create records | ❌ | ✅ | ✅ | ✅ |
| Edit records | ❌ | ✅ | ✅ | ✅ |
| Delete records | ❌ | ❌ | ✅ | ✅ |
| Manage users | ❌ | ❌ | ❌ | ✅ |
| Manage company settings | ❌ | ❌ | ❌ | ✅ |
| View compliance reports | ❌ | ✅ | ✅ | ✅ |
| Export compliance data | ❌ | ❌ | ✅ | ✅ |
| Change system_role | ❌ | ❌ | ❌ | ✅ |

All permission checks use `system_role` exclusively. See ADR 002.
Implementation detail: `/docs/design/rbac.md`

---

## 6. Tenant Isolation Model

Every record in the system belongs to exactly one Company. All querysets filter by `request.user.company`. No cross-tenant data access is permitted at any layer — enforced in both Django views (via `RoleRequiredMixin`) and DRF viewsets (via `TenantScopedViewSet`).

Full strategy: ADR 003.
Diagram: `/docs/diagrams/tenant-isolation.mermaid`

---

## 7. EUDR Compliance Module

AgriOps includes a dedicated compliance module supporting the EU Deforestation Regulation. The traceability chain runs:
```
Company → Supplier → Farm → Product → Inventory → PurchaseOrder → SalesOrder
```

Key compliance data stored per Farm:
- GeoJSON polygon (farm boundary)
- Deforestation risk classification
- Verification status and expiry
- Compliance documents
- Audit trail (mapped_by, verified_by)

Full specification: `/docs/design/compliance-module.md`

---

## 8. API Layer

The REST API is available at `/api/v1/`. All endpoints require JWT Bearer token authentication.

**Token endpoints:**
- `POST /api/v1/token/` — obtain access + refresh token pair
- `POST /api/v1/token/refresh/` — rotate access token

**Resource endpoints:** suppliers, farms, products, inventory, purchase-orders, sales-orders

**Custom actions:**
- `GET /api/v1/farms/eudr-pending/` — farms not yet EUDR verified
- `GET /api/v1/farms/high-risk/` — farms with high deforestation risk
- `GET /api/v1/inventory/low-stock/` — inventory items below threshold

All querysets are tenant-scoped. Deletes require Manager role or above.

Full contract: `/docs/design/api-contract.md`

---

## 9. Technology Stack

| Layer | Technology | Phase |
|---|---|---|
| Backend | Django 6.x | 1 |
| Database | PostgreSQL 15 | 1 |
| Frontend | Django Templates + Tailwind CSS + Alpine.js | 1 |
| Auth | Session auth (UI) + JWT simplejwt (API) | 2 |
| API | Django REST Framework 3.16 | 2 |
| RBAC | Custom permission mixins + DRF permission classes | 2 |
| Audit | Custom AuditLog model + view mixins | 2 |
| Secrets | python-decouple + .env | 2 |
| Geolocation | JSONField (GeoJSON) → PostGIS | 2 → 4 |
| Task Queue | Celery + Redis | 4 |
| CI/CD | GitHub Actions | 3 |
| Hosting | Railway / Render | 3 |
| Payments | Stripe + dj-stripe | 4 |
| Monitoring | Sentry + structured logging | 3 |
| Containers | Docker + docker-compose | 3 |

---

## 10. Security Architecture

| Control | Status |
|---|---|
| Multi-tenant data isolation | ✅ Phase 1 — enforced at view and API layer |
| Environment variables — no hardcoded secrets | ✅ Phase 2 — python-decouple + .env |
| Login UI + session management | ✅ Phase 2 — Django auth views, 8hr session |
| Role-based access control | ✅ Phase 2 — system_role, RoleRequiredMixin |
| Audit log | ✅ Phase 2 — AuditLog captures all writes |
| Security headers (XSS, CSRF, X-Frame) | ✅ Phase 2 — base.py + production.py |
| HSTS + secure cookies | ✅ Phase 2 — production.py (activates on deploy) |
| JWT API authentication | ✅ Phase 2 — simplejwt, 60min access token |
| Brute-force protection (django-axes) | 🔄 Phase 3 |
| CORS policy | 🔄 Phase 3 |
| HTTPS | 🔄 Phase 3 |
| Structured JSON logging (SIEM-compatible) | 🔄 Phase 3 |
| PostgreSQL row-level security | 🔄 Phase 4 |
| Internal penetration test | 🔄 Phase 5 |

---

## 11. Development Phases

| Phase | Focus | Status |
|---|---|---|
| 1 | Local prototype — models, CRUD UI, admin | ✅ Complete |
| 2 | Auth, RBAC, tenant isolation, audit log, EUDR schema, API, security headers | ✅ Complete |
| 3 | Cloud deployment, CI/CD, closed beta | Planned |
| 4 | Freemium launch, Stripe, PostGIS upgrade | Planned |
| 5 | Analytics, integrations, ML, pen test | Planned |
