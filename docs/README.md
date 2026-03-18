# AgriOps — Documentation

**Version:** 2.0 | **Last Updated:** March 2026

Welcome to the AgriOps technical documentation. This folder contains the complete architectural, design, security and operational record of the platform — from the first decision made to the current state of the build.

---

## How to Use This Documentation

If you are **new to the codebase**, read in this order:
1. `/design/system-overview.md` — understand the big picture
2. `/design/data-model.md` — understand the data structure
3. `/design/tenant-model.md` — understand the security boundary
4. `/adr/` — understand why key decisions were made
5. `/runbooks/local-setup.md` — get the project running locally

If you are **implementing a new feature**, read:
1. `/design/tenant-model.md` — every feature must respect tenant isolation
2. `/adr/003-tenant-isolation-strategy.md` — the rules are non-negotiable
3. `/design/data-model.md` — understand the existing schema before adding to it
4. The relevant ADR if your feature touches an existing decision

If you are **conducting a security review**, read:
1. `/threat-model.md` — the full threat landscape and control mapping
2. `/adr/003-tenant-isolation-strategy.md` — cross-tenant isolation design
3. `/diagrams/tenant-isolation.mermaid` — isolation sequence diagram
4. `/diagrams/auth-flow.mermaid` — authentication flow

If you are **responding to an incident**, go directly to:
1. `/runbooks/incident-response.md`

---

## Folder Structure
```
/docs
  README.md                        ← You are here
  threat-model.md                  ← Full threat model and security posture

  /adr                             ← Architecture Decision Records
    001-django-postgres-stack.md
    002-hybrid-role-architecture.md
    003-tenant-isolation-strategy.md
    004-geolocation-jsonfield-over-postgis.md
    005-eudr-farm-model-separation.md

  /design                          ← System design documents
    system-overview.md             ← Architecture, stack, RBAC matrix
    data-model.md                  ← All models, fields, relationships
    tenant-model.md                ← Tenant isolation implementation detail
    api-contract.md                ← REST API endpoints and contracts
    compliance-module.md           ← EUDR compliance module specification
    rbac.md                        ← Permission matrix, mixin hierarchy

  /diagrams                        ← Visual architecture diagrams
    erd.dbml                       ← Entity relationship diagram (dbdiagram.io)
    auth-flow.mermaid              ← Authentication sequence diagram
    tenant-isolation.mermaid       ← Tenant isolation sequence diagram
    eudr-traceability-chain.mermaid← EUDR supply chain traceability flow

  /runbooks                        ← Operational procedures
    local-setup.md                 ← Local development environment setup
    seed-data.md                   ← Test data generation
    deployment.md                  ← Cloud deployment (Phase 3)
    incident-response.md           ← Security incident procedures
    backup-restore.md              ← Database backup and restore
```

---

## Document Types Explained

### Architecture Decision Records (ADRs)
Each ADR captures a single architectural decision — the context, the options considered, the choice made and the consequences. ADRs are immutable records of intent. They are never deleted — if a decision is reversed, a new ADR is written referencing the old one.

**ADR Status values:**
- `Accepted` — decision in effect
- `Superseded by ADR-XXX` — replaced by a later decision
- `Deprecated` — no longer relevant but kept for history

### Design Documents
Design documents describe how the system works — not why decisions were made (that's ADRs) but what the implementation looks like. They are living documents updated as the system evolves.

### Diagrams
Diagrams are stored as text-based formats for version control friendliness:
- `.mermaid` files — render at [mermaid.live](https://mermaid.live) or in any Mermaid-compatible viewer
- `.dbml` files — render at [dbdiagram.io](https://dbdiagram.io)

### Runbooks
Step-by-step operational procedures. Written for a developer who may be under pressure (incident response) or unfamiliar with the system (new hire setup). Runbooks assume nothing — they are explicit and complete.

---

## Documentation Standards

All documentation in this folder follows these standards:

**Every ADR must include:**
- Date, status, and author
- Context — why this decision needed to be made
- Options considered with honest pros/cons
- The decision clearly stated
- Consequences — what this decision means going forward
- Related decisions linked

**Every design document must include:**
- Version and last updated date
- Current status (which phase it reflects)
- Cross-references to relevant ADRs

**Every runbook must include:**
- Prerequisites
- Step-by-step instructions (numbered, not bulleted)
- Expected output at each step
- Common failure modes and how to resolve them

---

## Contributing Documentation

When adding a new feature or making an architectural decision:

1. **If it's a new architectural decision** — write an ADR before writing code
2. **If it changes the data model** — update `data-model.md` and `erd.dbml`
3. **If it changes the API** — update `api-contract.md`
4. **If it introduces a new operational procedure** — write a runbook
5. **If it changes the threat surface** — update `threat-model.md`

Documentation and code ship together. A PR that adds a new model without updating the data model documentation will not be merged.

---

## Project Status

| Phase | Status | Documentation |
|---|---|---|
| Phase 1 — Local Prototype | ✅ Complete | Fully documented |
| Phase 2 — Auth, RBAC, API | ✅ Complete | Fully documented |
| Phase 3 — Cloud Deployment | ✅ Complete | Fully documented |
| Phase 4 — Inventory, Traceability, Stripe | Planned | — |
| Phase 5 — Buyer Portal, Market Intelligence | Planned | — |

---

*AgriOps — Agricultural Supply Chain Intelligence*
*github.com/Sirleroy · Built in public · Security-first SaaS*
