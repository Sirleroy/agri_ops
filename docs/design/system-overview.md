# AgriOps — System Overview

**Version:** 1.0
**Date:** March 2026
**Status:** Phase 1 Complete / Phase 2 Starting

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
│     Mobile / External (REST API — Phase 2)      │
└────────────────────┬────────────────────────────┘
                     │ HTTPS
┌────────────────────▼────────────────────────────┐
│              Application Layer                  │
│                                                 │
│  Django 6.x                                     │
│  ├── Authentication (Phase 2: JWT)              │
│  ├── RBAC Permission Layer (Phase 2)            │
│  ├── Multi-Tenant Queryset Filtering            │
│  ├── Business Logic (Views / Viewsets)          │
│  ├── Audit Logging (Phase 2)                    │
│  └── Django REST Framework (Phase 2)            │
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

AgriOps uses a modular Django app structure. Each domain is an independent app under the `apps/` directory.

```
agri_ops/
├── agri_ops_project/      # Django configuration
│   ├── settings.py        # → split to base/dev/prod in Phase 2
│   ├── urls.py            # Root URL configuration
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── companies/         # Tenant root — Company model
│   ├── users/             # CustomUser with system_role + job_title
│   ├── suppliers/         # Supplier profiles
│   ├── products/          # Product catalogue
│   ├── inventory/         # Stock management with low-stock alerts
│   ├── purchase_orders/   # Procurement with line items
│   ├── sales_orders/      # Customer orders with line items
│   ├── dashboard/         # Aggregated stats
│   └── reports/           # Compliance reporting — Phase 2/3
├── templates/             # Django HTML templates
├── static/                # Static assets
├── docs/                  # This documentation
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
| Product | products | Commodity catalogue | ✅ |
| Inventory | inventory | Stock levels per product | ✅ |
| PurchaseOrder | purchase_orders | Procurement records | ✅ |
| PurchaseOrderItem | purchase_orders | Line items | ✅ |
| SalesOrder | sales_orders | Customer order records | ✅ |
| SalesOrderItem | sales_orders | Line items | ✅ |
| AuditLog | — | Write action history | ✅ |

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

---

## 6. Tenant Isolation Model

Every record in the system belongs to exactly one Company. All querysets filter by `request.user.company`. No cross-tenant data access is permitted at any layer.

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

## 8. Technology Stack

| Layer | Technology | Phase |
|---|---|---|
| Backend | Django 6.x | 1 |
| Database | PostgreSQL 15 | 1 |
| Frontend | Django Templates + Tailwind CSS + Alpine.js | 1 |
| Auth | Django auth → JWT (simplejwt) | 2 |
| API | Django REST Framework | 2 |
| Geolocation | JSONField (GeoJSON) → PostGIS | 2 → 4 |
| Task Queue | Celery + Redis | 4 |
| CI/CD | GitHub Actions | 3 |
| Hosting | Railway / Render | 3 |
| Payments | Stripe + dj-stripe | 4 |
| Monitoring | Sentry + structured logging | 3 |
| Containers | Docker + docker-compose | 3 |

---

## 9. Security Architecture

| Control | Status |
|---|---|
| Multi-tenant data isolation | ✅ Phase 1 — architecture in place |
| Environment variables — no hardcoded secrets | 🔄 Phase 2 |
| Login UI + session management | 🔄 Phase 2 |
| Role-based access control | 🔄 Phase 2 |
| Brute-force protection (django-axes) | 🔄 Phase 2 |
| Audit log | 🔄 Phase 2 |
| CORS + CSP + security headers | 🔄 Phase 2 |
| HTTPS | 🔄 Phase 3 |
| Structured JSON logging (SIEM-compatible) | 🔄 Phase 3 |
| PostgreSQL row-level security | 🔄 Phase 4 |
| Internal penetration test | 🔄 Phase 5 |

---

## 10. Development Phases

| Phase | Focus | Status |
|---|---|---|
| 1 | Local prototype — models, CRUD UI, admin | ✅ Complete |
| 2 | Auth, RBAC, tenant isolation, audit log, API | 🔄 Starting |
| 3 | Cloud deployment, CI/CD, closed beta | Planned |
| 4 | Freemium launch, Stripe, PostGIS upgrade | Planned |
| 5 | Analytics, integrations, ML, pen test | Planned |
