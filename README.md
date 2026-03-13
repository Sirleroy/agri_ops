# AgriOps 🌾
**Agricultural Supply Chain Intelligence — Built for the businesses that feed the world.**

A secure, multi-tenant SaaS platform giving agricultural SMEs and cooperatives real-time traceability across their supply chains — from farm procurement to market dispatch — with built-in EUDR compliance support.

![Status](https://img.shields.io/badge/status-active%20development-green)
![Phase](https://img.shields.io/badge/phase-2%20starting-yellow)
![Stack](https://img.shields.io/badge/stack-Django%20%2B%20PostgreSQL-blue)
![License](https://img.shields.io/badge/license-MIT-brightgreen)

---

## The Problem

Smallholder farmers, cooperatives and agricultural SMEs manage supply chains through WhatsApp groups, paper manifests and Excel sheets. The result: post-harvest losses, compliance failures and zero visibility across the chain.

The EU Deforestation Regulation (EUDR, 2024) now mandates supply chain traceability for agricultural commodity imports — making digital record-keeping a legal requirement for export-market operators, not just a convenience.

Enterprise AgriTech exists — but it's priced for multinationals. The gap is everyone else.

**AgriOps is built for the gap.**

---

## What AgriOps Does

| Feature | Description | Status |
|---|---|---|
| 🏢 Multi-Tenant Architecture | Complete data isolation between organisations | ✅ Phase 1 |
| 🤝 Supplier Management | Centralised supplier profiles with category and contact tracking | ✅ Phase 1 |
| 🌿 Product & Inventory Tracking | Stock levels, low-stock alerts, warehouse location management | ✅ Phase 1 |
| 📦 Purchase Orders | Full procurement workflow with line items and status tracking | ✅ Phase 1 |
| 💰 Sales Orders | Customer order management with line items and dispatch status | ✅ Phase 1 |
| 👥 Role-Based User Management | System roles + custom job titles per organisation | ✅ Phase 1 |
| 🗺️ Farm Mapping (EUDR) | GPS polygon mapping per farm — SW Maps / NCAN Farm Mapper compatible | 🔄 Phase 2 |
| 🔐 Auth & RBAC | Login UI, JWT, role-based access control, brute-force protection | 🔄 Phase 2 |
| 📋 Audit Logging | Every write action recorded — who, what, when, from where | 🔄 Phase 2 |
| 📄 EUDR Compliance Reports | Traceability chain export — PDF and CSV | 🔄 Phase 3 |
| 📡 REST API | Versioned API with OpenAPI documentation | 🔄 Phase 2 |

---

## Architecture

AgriOps uses a modular Django app structure with PostgreSQL as the primary database. The central design principle is **Company as tenant root** — every record belongs to exactly one organisation, enforced at both the application and (Phase 4) database layer.

```
agri_ops/
├── agri_ops_project/          # Django config (settings, urls, wsgi, asgi)
├── apps/
│   ├── companies/             # Tenant root — Company model
│   ├── users/                 # CustomUser: system_role + job_title
│   ├── suppliers/             # Supplier profiles + Farm model (Phase 2)
│   ├── products/              # Product catalogue
│   ├── inventory/             # Stock levels with low-stock alerts
│   ├── purchase_orders/       # Procurement orders + line items
│   ├── sales_orders/          # Customer orders + line items
│   ├── dashboard/             # Aggregated stats view
│   └── reports/               # Compliance reporting — Phase 2/3
├── templates/                 # Django HTML templates (dark UI, Tailwind CSS)
├── static/                    # Static assets
├── docs/                      # Full technical documentation
│   ├── adr/                   # Architecture Decision Records
│   ├── design/                # System design documents
│   ├── diagrams/              # ERD, sequence diagrams, flow diagrams
│   └── runbooks/              # Operational procedures
└── manage.py
```

**Tenant isolation model:**
```
Company (Tenant Root)
    ├── Users              (scoped to company)
    ├── Suppliers
    │     └── Farms        (EUDR compliance unit — Phase 2)
    ├── Products
    ├── Inventory
    ├── Purchase Orders
    └── Sales Orders
```

---

## EUDR Compliance

AgriOps includes a dedicated compliance module supporting the **EU Deforestation Regulation (EUDR) — Regulation (EU) 2023/1115**.

The regulation requires operators trading in specific commodities (soy, cattle, palm oil, wood, cocoa, coffee, rubber) to prove those commodities did not contribute to deforestation after December 31, 2020.

AgriOps stores and manages:
- Farm boundary polygons (GeoJSON — compatible with SW Maps and NCAN Farm Mapper exports)
- Deforestation risk classification per farm (Low / Standard / High)
- Verification status, dates, and expiry
- Compliance documents (farm maps, satellite imagery, land registry, certifications)
- Full traceability chain: Company → Supplier → Farm → Product → Purchase Order → Sales Order

Full specification: [`/docs/design/compliance-module.md`](docs/design/compliance-module.md)

---

## Security Posture

Security is a core feature, not a roadmap item. AgriOps is built by someone in active cybersecurity training — every control is implemented deliberately and documented.

| Control | Status |
|---|---|
| Multi-tenant data isolation (queryset + object level) | ✅ Phase 1 |
| Secrets in environment variables — never in code | ✅ Phase 1 |
| Login UI + session management | 🔄 Phase 2 |
| Brute-force login protection (django-axes) | 🔄 Phase 2 |
| Role-based access control (RBAC) | 🔄 Phase 2 |
| Audit log — all write actions | 🔄 Phase 2 |
| CORS + CSP + security headers | 🔄 Phase 2 |
| HTTPS + HSTS | 🔄 Phase 3 |
| Structured JSON logging (SIEM-compatible) | 🔄 Phase 3 |
| PostgreSQL Row-Level Security | 🔄 Phase 4 |
| Internal penetration test | 🔄 Phase 5 |

Full threat model: [`/docs/threat-model.md`](docs/threat-model.md)

---

## Documentation

AgriOps maintains production-grade technical documentation from day one.

| Document | Description |
|---|---|
| [`/docs/README.md`](docs/README.md) | Documentation index and navigation guide |
| [`/docs/threat-model.md`](docs/threat-model.md) | Full STRIDE threat model and security posture |
| [`/docs/adr/`](docs/adr/) | Architecture Decision Records — why every major decision was made |
| [`/docs/design/system-overview.md`](docs/design/system-overview.md) | Full system architecture, RBAC matrix, tech stack |
| [`/docs/design/data-model.md`](docs/design/data-model.md) | All models, fields, and relationships |
| [`/docs/design/tenant-model.md`](docs/design/tenant-model.md) | Tenant isolation implementation detail |
| [`/docs/design/compliance-module.md`](docs/design/compliance-module.md) | EUDR compliance module specification |
| [`/docs/design/api-contract.md`](docs/design/api-contract.md) | REST API endpoints and contracts |
| [`/docs/diagrams/erd.dbml`](docs/diagrams/erd.dbml) | Entity relationship diagram (render at dbdiagram.io) |
| [`/docs/runbooks/local-setup.md`](docs/runbooks/local-setup.md) | Local development setup |
| [`/docs/runbooks/incident-response.md`](docs/runbooks/incident-response.md) | Security incident procedures |
| [`/docs/runbooks/backup-restore.md`](docs/runbooks/backup-restore.md) | Database backup and restore |

---

## Tech Stack

| Layer | Technology | Phase |
|---|---|---|
| Backend | Python 3.x / Django 6.x | 1 |
| Database | PostgreSQL 15 | 1 |
| Frontend | Django Templates + Tailwind CSS + Alpine.js | 1 |
| Auth | Django auth → JWT via simplejwt | 2 |
| API | Django REST Framework | 2 |
| Geolocation | JSONField/GeoJSON → PostGIS | 2 → 4 |
| Task Queue | Celery + Redis | 4 |
| CI/CD | GitHub Actions | 3 |
| Hosting | Railway / Render | 3 |
| Payments | Stripe + dj-stripe | 4 |
| Monitoring | Sentry + structured logging | 3 |
| Containers | Docker + docker-compose | 3 |

---

## Development Roadmap

```
Phase 1 ██████████  Local prototype — models, CRUD UI, admin       [COMPLETE]
Phase 2 ░░░░░░░░░░  Auth, RBAC, Farm model, audit log, API         [STARTING]
Phase 3 ░░░░░░░░░░  Cloud deployment, CI/CD, closed beta           [Planned]
Phase 4 ░░░░░░░░░░  Freemium launch, Stripe, PostGIS               [Planned]
Phase 5 ░░░░░░░░░░  Analytics, integrations, pen test              [Planned]
```

Full roadmap: [`/docs/design/system-overview.md`](docs/design/system-overview.md)

---

## Getting Started (Local Development)

**Prerequisites**
- Python 3.x
- PostgreSQL 15+
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

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver 8001
```

Full setup guide: [`/docs/runbooks/local-setup.md`](docs/runbooks/local-setup.md)

| URL | Description |
|---|---|
| http://localhost:8001/ | Dashboard |
| http://localhost:8001/admin/ | Django admin panel |
| http://localhost:8001/suppliers/ | Suppliers |
| http://localhost:8001/products/ | Products |
| http://localhost:8001/inventory/ | Inventory |
| http://localhost:8001/purchase-orders/ | Purchase Orders |
| http://localhost:8001/sales-orders/ | Sales Orders |
| http://localhost:8001/companies/ | Companies |
| http://localhost:8001/users/ | Users |

---

## Phase 1 — What's Built

Phase 1 is complete. The following is fully operational locally:

- 9-app modular Django project structure
- PostgreSQL database — all migrations applied and verified
- Full CRUD UI for all 7 modules (Companies, Suppliers, Products, Inventory, Purchase Orders, Sales Orders, Users)
- Dark-themed dashboard UI — Tailwind CSS + Alpine.js, no build step
- Sidebar navigation grouped by module (Operations, Procurement, Sales, Admin)
- Django admin with all models registered — list display, search, filters, inline items
- Hybrid role architecture — `system_role` drives RBAC, `job_title` is display-only free text
- Multi-tenant data model — every record scoped to a Company
- Production-grade documentation set — ADRs, design docs, threat model, runbooks

---

## Contributing

AgriOps is built in public and open to collaboration. If you work in agricultural technology, food security, cybersecurity, or want to build something real — reach out.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit with clear messages (`git commit -m "feat: add farm mapping view"`)
4. Open a pull request with a description of what and why

Please read `CONTRIBUTING.md` before submitting. Every PR that changes the data model must update `/docs/design/data-model.md`. Every architectural decision must have an ADR.

---

## Security

This project takes security seriously. If you discover a vulnerability:

- Do not open a public issue
- Email the maintainer directly (see GitHub profile)
- Responsible disclosure is appreciated and will be acknowledged

See `SECURITY.md` for the full disclosure policy.
See [`/docs/threat-model.md`](docs/threat-model.md) for the full threat landscape.

---

## Background

AgriOps is dual-tracked as a real product and a portfolio project built during a structured cybersecurity career transition. The founding team has direct operational experience with EUDR compliance — the platform digitises a supply chain traceability process the founder manages professionally.

Every architectural decision is documented in `/docs/adr/`. Every security control is mapped in `/docs/threat-model.md`. The codebase is built to be handed to a development team — not reverse-engineered by one.

---

## Licence

MIT — see `LICENSE`

---

*Built by [@Sirleroy](https://github.com/Sirleroy) · Agricultural Supply Chain Intelligence · Security-First SaaS*
