# 2026-05-06 — AgriOps Defense-in-Depth Posture

Tags: #AgriOps #Security #MVP #Compliance #GrantReadiness

## Core Position

AgriOps is MVP-ready from a security posture standpoint because it does not rely on a single claim of safety. It has layered controls across authentication, tenant isolation, role-based permissions, suspended-company enforcement, audit logging, certificate readiness, geometry integrity, production hardening, and regression tests.

The current tenant isolation model is application-enforced, not PostgreSQL row-level security. That is acceptable for MVP and early tenant onboarding because the enforcement is centralized, documented, and covered by tests. RLS remains a future defense-in-depth upgrade for enterprise, government, or institutional due diligence.

## Current Evidence

- Tenant-scoped views filter data by `request.user.company`.
- Detail/update/delete views use ownership guards so cross-tenant objects return 404.
- API endpoints use tenant-aware permissions and queryset scoping.
- Suspended companies are blocked at web, dashboard, admin panel, and API layers.
- Tenant users cannot create or delete tenant `Company` records; tenant lifecycle actions belong in the TOTP-gated ops dashboard.
- Audit logs capture tenant-scoped create/update/delete/import/download events.
- Certificate downloads are blocked until required compliance evidence is present and current.
- Farm geometry hashes make polygon drift detectable.
- The regression suite currently covers 36 security and compliance tests.

## How To Say It Externally

AgriOps uses a layered security model. Tenant data is separated at the application layer through company-scoped querysets, object ownership checks, API permissions, role-based access controls, and active-account enforcement. These controls are backed by regression tests that verify cross-tenant data is excluded from list views, blocked from detail views, and rejected through the API. Compliance outputs also use evidence gates: certificates cannot be downloaded until the batch passes farm, quantity, phytosanitary, and quality-test readiness checks.

For data integrity, farm polygons are fingerprinted with SHA-256 geometry hashes, and AgriOps can detect geometry drift before certificates are issued. PostgreSQL row-level security is planned as a future defense-in-depth layer when enterprise or institutional deployment requirements justify the added operational complexity.

## RLS Trigger Conditions

Implement PostgreSQL row-level security when one of these becomes true:

- a major tenant or grant evaluator explicitly requires database-enforced tenant isolation
- a government or institutional deployment moves into formal due diligence
- multiple engineers begin making tenant-scoped code changes regularly
- background workers and async processing become central to production operations
- ops dashboard roles become granular enough to require different platform-access levels

## Implementation Principle

RLS should not replace the current controls. It should sit underneath them. Application-level RBAC, object ownership checks, audit logging, certificate blockers, and secure UI gates remain required even after database-level policies are added.
