# AgriOps
**Agricultural Supply Chain Intelligence — Built for the businesses that feed the world.**

A secure, multi-tenant SaaS platform giving agricultural SMEs and cooperatives end-to-end traceability across their supply chains — from farm procurement to market dispatch — with compliance verification for any buyer or regulatory framework.

![Status](https://img.shields.io/badge/status-active%20development-green)
![Phase](https://img.shields.io/badge/phase-4%20active-blue)
![Stack](https://img.shields.io/badge/stack-Django%20%2B%20PostgreSQL-blue)
![License](https://img.shields.io/badge/license-All%20Rights%20Reserved-red)

---

## The Problem

Smallholder farmers, cooperatives, and agricultural SMEs manage supply chains through WhatsApp groups, paper manifests, and spreadsheets. The result: post-harvest losses, compliance failures, and zero visibility across the chain.

The EU Deforestation Regulation (EUDR — Regulation (EU) 2023/1115) now mandates supply chain traceability for commodity imports — making digital farm-to-buyer records a legal requirement for export-market operators, not just a convenience.

Enterprise AgriTech exists but is priced for multinationals. The gap is everyone else.

**AgriOps is built for the gap.**

---

## What AgriOps Does

| Feature | Description | Status |
|---|---|---|
| Multi-Tenant Architecture | Complete data isolation between organisations | ✅ Live |
| Supplier Management | Centralised supplier profiles with category and contact tracking | ✅ Live |
| Farmer Registry | Farmer model with village, LGA, NIN, and FVF consent records | ✅ Live |
| Farm Mapping (EUDR) | GPS polygon draw/import per farm — SW Maps / NCAN Farm Mapper compatible | ✅ Live |
| GeoJSON Ingestion Pipeline | 27-test validation + normalisation (Z-strip, dedup, simplify, closure). Dry-run mode, multi-file upload, one-tap commit. SW Maps properties matched case-insensitively | ✅ Live |
| Product & Inventory Tracking | Stock levels, low-stock alerts, warehouse location management | ✅ Live |
| Purchase Orders | Full procurement workflow with line items and status tracking | ✅ Live |
| Sales Orders + Batches | Customer order management with batch traceability links to farms | ✅ Live |
| EUDR Compliance Reports | Full traceability chain PDF — Company → Supplier → Farm → Batch | ✅ Live |
| Role-Based Access Control | org_admin / manager / staff / viewer with template-level enforcement | ✅ Live |
| Audit Logging | Every write action recorded — who, what, when, from where | ✅ Live |
| REST API | DRF + SimpleJWT — versioned API at `/api/v1/` | ✅ Live |
| Notification System | In-app alerts for low stock, overdue POs, expiring farm verifications | ✅ Live |
| Ops Dashboard | TOTP-gated internal panel for platform superusers | ✅ Live |
| Public Traceability View | Token-based public trace page for buyer-facing chain visibility | ✅ Live |

---

## Architecture

AgriOps uses a modular Django app structure with PostgreSQL. The central design principle is **Company as tenant root** — every record belongs to exactly one organisation, enforced manually in every view's `get_queryset()`.

```
agri_ops/
├── agri_ops_project/          # Django config (settings, urls, wsgi)
├── apps/
│   ├── companies/             # Tenant root — Company model
│   ├── users/                 # CustomUser: system_role + job_title
│   ├── suppliers/             # Supplier + Farmer + Farm (EUDR)
│   ├── products/              # Product catalogue
│   ├── inventory/             # Stock levels with low-stock alerts
│   ├── purchase_orders/       # Procurement orders + line items
│   ├── sales_orders/          # Customer orders + line items + Batch
│   ├── reports/               # EUDR compliance PDF generation
│   ├── dashboard/             # Aggregated stats + notifications
│   ├── audit/                 # AuditLog model + mixins
│   └── api/                   # DRF API endpoints
├── ops_dashboard/             # Internal ops panel (TOTP-gated)
├── templates/                 # Django HTML templates (dark UI, Tailwind + Alpine.js)
├── static/                    # Static assets
└── manage.py
```

**Tenant isolation model:**
```
Company (Tenant Root)
    ├── CustomUser         (scoped to company, system_role drives RBAC)
    ├── Supplier
    │     ├── Farmer       (name, phone, village, LGA, NIN, FVF consent)
    │     └── Farm         (GPS polygon, EUDR verification, expiry)
    ├── Product
    ├── Inventory
    ├── PurchaseOrder
    │     └── PurchaseOrderItem
    └── SalesOrder
          ├── SalesOrderItem
          └── Batch        (traceability — links SO → Farms for EUDR chain)
```

---

## EUDR Compliance

AgriOps includes a dedicated compliance module for **Regulation (EU) 2023/1115**.

The regulation requires operators trading in specific commodities (soy, cattle, palm oil, wood, cocoa, coffee, rubber) to prove those commodities did not contribute to deforestation after 31 December 2020.

AgriOps manages the full chain:

- **Farm boundary polygons** — drawn directly on an interactive map or imported from SW Maps / NCAN Farm Mapper (GeoJSON)
- **27-test ingestion pipeline** — validation (structure, coordinate range, self-intersection, coordinate bomb) + normalisation (Z-strip, 6dp rounding, dedup, closure, simplification)
- **Deforestation risk classification** per farm — Low / Standard / High
- **Field Verification Form (FVF)** — land acquisition, land tenure, years farming, untouched forest, expansion intent, signed consent record
- **Verification status, dates, and expiry** with in-app expiry alerts
- **Full traceability chain** — Farm → Supplier → PurchaseOrder → Inventory → SalesOrderItem → Batch → EUDR compliance PDF

---

## Security Posture

| Control | Status |
|---|---|
| Multi-tenant data isolation (queryset + object level) | ✅ Live |
| Secrets in environment variables — never in code | ✅ Live |
| Login UI + session management (8-hour timeout) | ✅ Live |
| Brute-force login protection — django-axes (5 failures → 1hr lockout) | ✅ Live |
| Role-based access control — backend mixin + template guard | ✅ Live |
| Audit log — all write actions with IP, user, field-level diff | ✅ Live |
| CSRF protection on all forms including Alpine.js delete modal | ✅ Live |
| XSS protection — `\|escapejs` on all Alpine.js string interpolation | ✅ Live |
| DRF throttling — 20 req/hr anon, 200 req/hr authenticated | ✅ Live |
| Ops dashboard TOTP 2FA — separate session, 2-hour timeout | ✅ Live |
| HTTPS + HSTS — production settings configured | ✅ Configured |
| Sentry error monitoring — production only | ✅ Configured |
| PostgreSQL Row-Level Security | Planned — Phase 5 |
| Internal penetration test | Planned — Phase 5 |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 / Django 6.x |
| Database | PostgreSQL |
| Auth | Django session auth + django-axes + django-otp (ops) |
| API | Django REST Framework + SimpleJWT |
| Frontend | Django templates (SSR), Tailwind CSS (CDN), Alpine.js 3 (CDN) |
| Icons | Heroicons (inline SVG) |
| Fonts | Syne (sans), JetBrains Mono (mono) — Google Fonts CDN |
| Maps | Leaflet.js + Leaflet.draw (farm form + detail) |
| Config | python-decouple + split settings (base / development / production) |
| Static files | WhiteNoise |
| Monitoring | Sentry (production) |

No build step. No webpack. No npm. All JS/CSS is CDN or inline.

---

## Development Roadmap

```
Phase 1 ██████████  Local prototype — models, CRUD UI, multi-tenancy   [COMPLETE]
Phase 2 ██████████  Auth, RBAC, Farm/EUDR, audit log, API              [COMPLETE]
Phase 3 ██████████  Reports, ops dashboard, traceability chain          [COMPLETE]
Phase 4 ████░░░░░░  Product depth & revenue — first paying tenant       [ACTIVE]
Phase 5 ░░░░░░░░░░  Buyer portal — catalogue, trace viewer, orders      [Planned]
```

**Phase 4 active work:**
- Demo chain — end-to-end seed data for operator demos
- Billing / subscription management (trigger: first paying tenant)

**Phase 4.11 complete (14 April 2026):**
Field flow hardened end-to-end — dry run → one-tap commit (sticky bar, no re-upload), multi-file selection, farmer auto-creation on GeoJSON import, completeness badges, post-import nudge, case-insensitive SW Maps property lookup, float coercion hotfix.

**Phase 5 planned:**
- `buyers.agriops.io` — buyer-facing catalogue and traceability viewer
- Prerequisite: EUDR chain complete + at least one live tenant

---

## Getting Started (Local Development)

**Prerequisites**
- Python 3.12
- PostgreSQL
- pip / virtualenv

```bash
# Clone the repo
git clone https://github.com/Sirleroy/agri_ops.git
cd agri_ops

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your PostgreSQL credentials and secret key

# Run migrations
python manage.py migrate

# Load demo data (optional)
python manage.py seed_demo

# Start development server
python manage.py runserver 8001
```

| URL | Description |
|---|---|
| http://localhost:8001/ | Landing page |
| http://localhost:8001/dashboard/ | Main dashboard |
| http://localhost:8001/suppliers/ | Suppliers |
| http://localhost:8001/suppliers/farms/ | Farm registry (EUDR) |
| http://localhost:8001/products/ | Products |
| http://localhost:8001/inventory/ | Inventory |
| http://localhost:8001/purchase-orders/ | Purchase Orders |
| http://localhost:8001/sales-orders/ | Sales Orders |
| http://localhost:8001/reports/ | EUDR compliance reports |
| http://localhost:8001/users/ | Team management |
| http://localhost:8001/ops-access/9f3k/ | Ops dashboard login (TOTP) |
| http://localhost:8001/api/v1/ | REST API |

---

## Security Disclosure

If you discover a vulnerability:

- Do not open a public issue
- Contact the maintainer directly (see GitHub profile)
- Responsible disclosure is appreciated and will be acknowledged

---

## Licence

Copyright (c) 2026 Ezinna Ohah. All rights reserved. See `LICENSE`.

---

*Built by [@Sirleroy](https://github.com/Sirleroy) · Agricultural Supply Chain Intelligence*
