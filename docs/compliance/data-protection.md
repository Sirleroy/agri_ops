---
layout: default
title: Data Protection — AgriOps
---

# Data Protection

AgriOps is designed as compliance infrastructure for agricultural supply chains. This page documents our data protection posture under the **Nigeria Data Protection Act 2023 (NDPA)** and our obligations as a data controller processing personal data on behalf of tenant organisations.

---

## Legal Framework

| Instrument | Status |
|---|---|
| Nigeria Data Protection Act 2023 (Act No. 37) | Primary framework — AgriOps is fully subject |
| EU General Data Protection Regulation (GDPR) | Applicable to cross-border transfers to EU buyers and processors |
| EUDR (EU Deforestation Regulation) | Drives the core farm traceability data requirement |

AgriOps is incorporated as **AgriOps Technologies Ltd** (CAC registration in progress). The data controller for all platform processing is AgriOps Technologies Ltd.

---

## What Personal Data We Process

The platform processes personal data of smallholder farmers on behalf of tenant organisations:

| Category | Examples | Lawful Basis |
|---|---|---|
| Identity | Full name, phone number, NIN | Consent |
| Location | GPS farm polygon, village, LGA | Legitimate interest (EUDR/supply chain compliance) |
| Compliance records | Verification status, certification dates | Legitimate interest + legal obligation |
| Audit trail | User actions, timestamps | Legal obligation |

GPS farm polygons constitute location data under NDPA s.65 and are treated with corresponding care. NIN is treated as sensitive-adjacent due to its link to biometric enrollment.

Tenant organisations access only their own farmers' data. Cross-tenant data access is prevented at the application layer and enforced by all API endpoints.

---

## Lawful Basis for Processing

Processing is grounded in:

- **Consent** (NDPA s.25(1)(a)) — obtained from farmers at the point of field data collection via a documented field officer consent protocol
- **Legitimate interest** (NDPA s.25(1)(b)(v)) — supply chain traceability and EUDR compliance represent a proportionate business and regulatory necessity; a formal balancing test has been conducted and documented in our DPIA
- **Legal obligation** (NDPA s.25(1)(b)(ii)) — audit logging and compliance records required under contract and regulation

---

## Data Privacy Impact Assessment

A Data Privacy Impact Assessment (DPIA) has been conducted in accordance with NDPA s.28, covering:

- Systematic description of farm data processing and purposes
- Necessity and proportionality assessment
- Risk register (9 identified risks including unconsented collection, GPS misuse, cross-border exposure)
- Mitigation measures and residual risk rating
- Data subject rights procedures

**Overall residual risk: Medium — acceptable for operations.** No residual high risk requiring NDPC consultation under s.28(2).

The DPIA is an internal document available to the NDPC on request. It is reviewed annually and on any material change to processing scope.

---

## Data Security

AgriOps implements layered security controls:

- Role-based access control — four-tier permission hierarchy (viewer → staff → manager → org_admin)
- Session management — 8-hour timeout, CSRF protection on all forms
- Brute-force protection — account lockout after 5 failed login attempts (django-axes)
- Audit logging — every create, update, and delete action is logged with user, timestamp, and field-level diff
- Geometry integrity hashing — farm GPS polygons carry SHA-256 fingerprints; out-of-band mutations are detectable
- HTTPS enforced in production
- Data processor agreement with Render (cloud hosting) — standard contractual clauses for cross-border transfer

---

## Cross-Border Data Transfers

Farmer personal data is hosted on Render's infrastructure (US). This constitutes a cross-border transfer under NDPA s.41. Basis: **standard contractual clauses** (Render Data Processing Agreement).

When EUDR compliance documentation is shared with EU-based buyers or regulatory portals, the transfer basis is **contract performance** under NDPA s.43(1)(b) — the transfer is necessary for the performance of the supply chain compliance contract to which the farmer's cooperative is a party.

---

## Data Retention

| Data | Retention |
|---|---|
| Farmer personal data | Duration of active farmer relationship |
| Farm GPS polygon | Minimum 7 years from last associated transaction (EUDR audit requirement) |
| Audit logs | Indefinite (compliance evidence) |
| Failed import records | 12 months, then purged |

---

## Data Subject Rights

Farmers whose data is held on the platform have the following rights under NDPA Part VI:

| Right | How to Exercise | Response Time |
|---|---|---|
| Access — receive a copy of your data | Email privacy@agriops.io | 14 days |
| Rectification — correct inaccurate data | Email privacy@agriops.io | 7 days |
| Erasure — request deletion | Email privacy@agriops.io | 14 days |
| Restriction — pause processing pending a query | Email privacy@agriops.io | 7 days |
| Objection — object to processing | Email privacy@agriops.io | 14 days |
| Complaint to NDPC | [ndpc.gov.ng](https://ndpc.gov.ng) | — |

---

## Data Protection Officer

An external Data Protection Officer engagement is budgeted and will be formalised post-initial funding. In the interim, data protection queries are handled directly by the founder.

**Contact:** privacy@agriops.io

---

## NDPC Registration

AgriOps will register with the Nigeria Data Protection Commission as a data controller of major importance (NDPA s.44) when the platform reaches **2,000 data subjects** — the statutory threshold for mandatory registration. Registration will be completed within the 6-month window required by the Act.

---

*Last reviewed: 2026-05-13 · AgriOps Technologies Ltd*
