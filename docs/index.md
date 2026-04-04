---
layout: default
title: AgriOps Documentation
---

# AgriOps Documentation

**Agricultural Supply Chain Intelligence**

AgriOps is a secure, multi-tenant SaaS platform for agricultural SMEs and cooperatives — built for EUDR compliance, farm-level GPS traceability, and supply chain intelligence.

**Live platform:** [app.agriops.io](https://app.agriops.io) · **API:** [api.agriops.io/api/v1/](https://api.agriops.io/api/v1/)

---

## User Guide

| Document | Description |
|---|---|
| [User Manual](user-manual.md) | Field officers, coordinators, managers — how to use AgriOps end-to-end |

---

## System Design

| Document | Description |
|---|---|
| [System Overview](design/system-overview.md) | Architecture, stack, RBAC matrix, security posture |
| [Data Model](design/data-model.md) | All models, fields, relationships, ERD |
| [API Contract](design/api-contract.md) | REST API endpoints, authentication, throttling |
| [EUDR Compliance Module](design/compliance-module.md) | Farm traceability and EU regulation |
| [RBAC Design](design/rbac.md) | Permission matrix and role hierarchy |
| [Tenant Model](design/tenant-model.md) | Multi-tenant isolation design |

---

## Architecture Decision Records

| ADR | Decision |
|---|---|
| [ADR 001](adr/001-django-postgres-stack.md) | Django + PostgreSQL stack selection |
| [ADR 002](adr/002-hybrid-role-architecture.md) | Hybrid role architecture — system_role + job_title |
| [ADR 003](adr/003-tenant-isolation-strategy.md) | Tenant isolation strategy |
| [ADR 004](adr/004-geolocation-jsonfield-over-postgis.md) | GeoJSON over PostGIS for farm geolocation |
| [ADR 005](adr/005-eudr-farm-model-separation.md) | Farm model separation from Supplier |

---

## Runbooks

| Runbook | Description |
|---|---|
| [Local Setup](runbooks/local-setup.md) | Getting started locally |
| [Deployment](runbooks/deployment.md) | Render deployment, CI/CD, DNS |
| [Seed Data](runbooks/seed-data.md) | Loading test data |
| [Incident Response](runbooks/incident-response.md) | How to respond to production incidents |
| [Backup and Restore](runbooks/backup-restore.md) | Database backup and restore procedures |

---

## Security

| Document | Description |
|---|---|
| [Threat Model](threat-model.md) | STRIDE threat analysis and mitigations |

---

## Project Roadmap

See [ROADMAP.md](ROADMAP.md) for the full phase-by-phase build plan.

---

## Platform URLs

| URL | Purpose |
|---|---|
| [app.agriops.io](https://app.agriops.io) | Main platform |
| [api.agriops.io/api/v1/](https://api.agriops.io/api/v1/) | REST API root |
| [docs.agriops.io](https://docs.agriops.io) | This documentation |

---

*Built by [Sirleroy](https://github.com/Sirleroy/agri_ops) · Phase 4.7 complete · April 2026*
