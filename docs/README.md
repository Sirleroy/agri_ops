---
layout: default
title: How to Navigate These Docs
---

# AgriOps — Documentation Conventions

**Status:** Living document
**Scope:** How this documentation set is organised, who each part is for, and what every doc must contain.

This page is the *meta* of `docs.agriops.io` — read it once and you'll know which corner of the docs to open for any future question. The [home page](index.md) is the table of contents; this page is the map legend.

---

## Reading Orders by Audience

**New to the codebase:**
1. [System Overview](design/system-overview.md) — architecture, stack, RBAC matrix
2. [Data Model](design/data-model.md) — all models, relationships, ERD
3. [Tenant Model](design/tenant-model.md) — the security boundary
4. [ADR 003 — Tenant Isolation Strategy](adr/003-tenant-isolation-strategy.md) and [ADR 011 — RLS Deferral](adr/011-postgres-row-level-security-deferral.md) — why the boundary is shaped this way
5. [Local Setup](runbooks/local-setup.md) — get the project running

**Implementing a new feature:**
1. [Tenant Model](design/tenant-model.md) — every feature respects tenant isolation
2. [ADR 003 — Tenant Isolation Strategy](adr/003-tenant-isolation-strategy.md) — non-negotiable rules
3. [Data Model](design/data-model.md) — understand the schema before adding to it
4. The relevant ADR if your feature touches an existing decision

**Conducting a security review:**
1. [Threat Model](threat-model.md) — full STRIDE landscape and control mapping
2. [Security Testing Log](security-testing.md) — red team exercises, findings, resolutions (RT-001, RT-002, RT-003)
3. [ADR 003 — Tenant Isolation Strategy](adr/003-tenant-isolation-strategy.md) and [ADR 011 — RLS Deferral](adr/011-postgres-row-level-security-deferral.md)
4. [Production Readiness Audit](production-readiness.md)

**Responding to an incident:**
1. [Incident Response Runbook](runbooks/incident-response.md) — start here, no detours

**Onboarding a tenant:**
1. [Tenant Onboarding Checklist](commercial/tenant-onboarding-checklist.md)
2. [Subscription Agreement Template](commercial/subscription-agreement-template.md)

---

## Folder Structure

```
docs/
  README.md                        ← You are here (conventions + reading orders)
  index.md                         ← Live homepage / table of contents
  ROADMAP.md                       ← Phase-by-phase build plan
  threat-model.md                  ← Full threat landscape and mitigations
  security-testing.md              ← Red-team exercises and findings
  production-readiness.md          ← Production-failure-mode audit
  user-manual.md                   ← End-user guide
  eudr-compliance-gaps.md          ← EUDR-specific feature deltas
  export-compliance-gaps.md        ← Export-readiness deltas
  ingestion-resilience-batch9.md   ← GeoJSON import resilience notes
  CNAME                            ← docs.agriops.io binding
  _config.yml                      ← Jekyll configuration

  adr/                             ← Architecture Decision Records (immutable)
    001-django-postgres-stack.md
    002-hybrid-role-architecture.md
    003-tenant-isolation-strategy.md
    004-geolocation-jsonfield-over-postgis.md
    005-eudr-farm-model-separation.md
    006-ops-event-log-separation.md
    007-totp-over-ip-restriction.md
    008-cloudflare-email-routing-interim.md
    009-production-hardening-indexes-async-email-env-validation.md
    010-billing-architecture.md
    011-postgres-row-level-security-deferral.md

  design/                          ← Living system-design documents
    system-overview.md
    data-model.md
    tenant-model.md
    api-contract.md
    compliance-module.md
    rbac.md

  runbooks/                        ← Operational procedures
    local-setup.md
    seed-data.md
    deployment.md
    incident-response.md
    backup-restore.md
    geometry_drift_test.md

  diagrams/                        ← Text-based visual diagrams
    erd.dbml                       (render at dbdiagram.io)
    auth-flow.mermaid              (render at mermaid.live)
    tenant-isolation.mermaid
    eudr-traceability-chain.mermaid

  commercial/                      ← Customer-facing legal and onboarding
    subscription-agreement-template.md
    tenant-onboarding-checklist.md

  assets/                          ← Images and static files
  _layouts/                        ← Jekyll templates (Cayman theme override)
```

---

## Document Types

### Architecture Decision Records (ADRs)
Each ADR captures a single architectural decision — the context, options considered, choice made, and consequences. ADRs are immutable records of intent. They are never deleted — if a decision is reversed or refined, a new ADR is written referencing the old one.

**ADR Status values:**
- `Accepted` — decision in effect
- `Deferred` — decision made *not* to implement now, with explicit triggers documented for when to revisit
- `Superseded by ADR-XXX` — replaced by a later decision
- `Deprecated` — no longer relevant but kept for history

### Design Documents
How the system actually works — what the implementation looks like today. Living documents updated as the system evolves. They cross-reference ADRs for the *why* behind each shape.

### Runbooks
Step-by-step operational procedures, written for a developer who may be under pressure (incident response) or unfamiliar with the system (new hire setup). Runbooks assume nothing — they are explicit, numbered, and complete.

### Diagrams
Stored as text-based formats for version control friendliness:
- `.mermaid` — render at [mermaid.live](https://mermaid.live) or any Mermaid-compatible viewer
- `.dbml` — render at [dbdiagram.io](https://dbdiagram.io)

### Commercial Documents
Customer-facing legal templates and onboarding checklists. Treated with the same change discipline as ADRs — versions visible in git history, no silent rewrites.

---

## Documentation Standards

**Every ADR must include:**
- Date, status, and author
- Context — why this decision needed to be made
- Options considered with honest pros/cons (or trigger criteria for Deferred ADRs)
- The decision clearly stated
- Consequences — what this decision means going forward
- Related decisions linked

**Every design document must include:**
- Status (which phase it reflects)
- Last meaningful update reference (in commit history if not in the doc)
- Cross-references to relevant ADRs

**Every runbook must include:**
- Prerequisites
- Step-by-step instructions (numbered, not bulleted)
- Expected output at each step
- Common failure modes and how to resolve them

---

## Contributing Documentation

When adding a new feature or making an architectural decision:

1. **New architectural decision** — write an ADR before writing code
2. **Data model change** — update `design/data-model.md` and `diagrams/erd.dbml`
3. **API change** — update `design/api-contract.md`
4. **New operational procedure** — write a runbook
5. **Threat surface change** — update `threat-model.md`
6. **New ADR** — also add the row to `index.md` and (for accepted ADRs) any back-references in older ADRs being superseded

**Documentation and code ship together.** A PR that adds a new model without updating the data model documentation is incomplete.

---

## Phase Status

| Phase | Status | Where to look |
|---|---|---|
| Phase 1 — Local Prototype | ✅ Complete | Stack and structure documented in [System Overview](design/system-overview.md) |
| Phase 2 — Auth, RBAC, API | ✅ Complete | [RBAC Design](design/rbac.md), [API Contract](design/api-contract.md) |
| Phase 3 — Cloud Deployment | ✅ Complete | [Deployment Runbook](runbooks/deployment.md) |
| Phase 4 — Inventory, Traceability, Compliance, Billing | 🔄 In progress | See [ROADMAP](ROADMAP.md) for current block status |
| Phase 5 — Buyer Portal, Market Intelligence | Planned | [ROADMAP](ROADMAP.md) |

For the live build status — what's done this week, what's open — see [ROADMAP.md](ROADMAP.md).

---

*AgriOps — Trust verification infrastructure for agricultural supply chains*
*github.com/Sirleroy · Built in public · Security-first SaaS*
