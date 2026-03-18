# AgriOps Documentation

**Agricultural Supply Chain Intelligence**

Welcome to the AgriOps technical documentation. AgriOps is a secure, multi-tenant SaaS platform for agricultural SMEs and cooperatives — built for EUDR compliance, farm-level traceability, and supply chain intelligence.

---

## Quick Links

- **[System Overview](design/system-overview.md)** — Architecture, stack, RBAC matrix
- **[Data Model](design/data-model.md)** — All models, fields, relationships
- **[EUDR Compliance Module](design/compliance-module.md)** — Farm traceability and EU regulation
- **[API Contract](design/api-contract.md)** — REST API endpoints
- **[RBAC Design](design/rbac.md)** — Permission matrix and role hierarchy
- **[Tenant Model](design/tenant-model.md)** — Multi-tenant isolation design

---

## Architecture Decisions

- [ADR 001 — Django + PostgreSQL Stack](adr/001-django-postgres-stack.md)
- [ADR 002 — Hybrid Role Architecture](adr/002-hybrid-role-architecture.md)
- [ADR 003 — Tenant Isolation Strategy](adr/003-tenant-isolation-strategy.md)
- [ADR 004 — GeoJSON over PostGIS](adr/004-geolocation-jsonfield-over-postgis.md)
- [ADR 005 — Farm Model Separation](adr/005-eudr-farm-model-separation.md)

---

## Runbooks

- [Local Setup](runbooks/local-setup.md)
- [Seed Data](runbooks/seed-data.md)
- [Deployment](runbooks/deployment.md)
- [Incident Response](runbooks/incident-response.md)
- [Backup and Restore](runbooks/backup-restore.md)

---

## Live Platform

| URL | Purpose |
|---|---|
| [app.agriops.io](https://app.agriops.io) | Platform |
| [api.agriops.io/api/v1/](https://api.agriops.io/api/v1/) | REST API |
| [docs.agriops.io](https://docs.agriops.io) | This documentation |

---

*Built with security-first architecture · GitHub: [Sirleroy/agri_ops](https://github.com/Sirleroy/agri_ops)*
