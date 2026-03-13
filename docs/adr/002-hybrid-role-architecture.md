# ADR 002 — Hybrid Role Architecture: System Roles + Job Titles

**Date:** March 2026
**Status:** Accepted
**Author:** Ezinna (Founder)

---

## Context

AgriOps is a multi-tenant SaaS platform serving agricultural SMEs and cooperatives across diverse markets. During Phase 1 development, a critical design question arose around user roles: how do we implement role-based access control (RBAC) in a way that is both secure and flexible enough to accommodate the diversity of job titles across different client organisations?

A cooperative in Northern Nigeria may use "Field Coordinator" where an agri-processor in Plateau State uses "Zone Supervisor" — both functionally equivalent roles with identical access requirements but entirely different titles. A fixed choices-only approach would either be too restrictive or require constant maintenance as new client organisations onboard with their own internal terminology.

---

## Decision Drivers

- RBAC must be consistent and predictable — permission logic cannot depend on free-text values
- Client organisations have diverse internal job title conventions
- The platform must feel native to each organisation's own language and structure
- Security: misconfigured or manipulated role values must not be able to escalate or reduce privileges
- Flexibility: onboarding a new organisation should not require platform code changes to accommodate their titles
- Auditability: every access control decision must be traceable to a defined system role

---

## Options Considered

### Option 1 — Fixed choices only
A single `role` field with predefined choices: `admin`, `manager`, `staff`, `viewer`.

**Pros:** Simple, consistent, easy to enforce in permission logic.

**Cons:** Forces clients to use platform terminology rather than their own. A "Head of Procurement" becomes "Manager" — creates friction and adoption resistance. Does not scale across diverse markets.

### Option 2 — Free text only
A single `role` CharField where users type whatever they want.

**Pros:** Maximum flexibility, feels natural to each organisation.

**Cons:** Catastrophic for security. Permission logic cannot reliably gate access based on free-text values. A typo, a case difference, or a deliberate manipulation could grant or deny access incorrectly. Completely unworkable for RBAC.

### Option 3 — Hybrid: system_role + job_title ✅ Chosen
Two separate fields on `CustomUser`:
- `system_role` — fixed choices, drives all permission logic, invisible to end users as a raw value
- `job_title` — free text CharField, purely cosmetic, displays on profile and UI

**Pros:**
- Permission logic is consistent and predictable — always based on `system_role`
- Each organisation can use its own job title conventions
- Security boundary is clear — `job_title` has zero influence on access control
- Scalable — new organisations onboard without any code changes
- Auditable — every permission decision traces to a defined `system_role` value

**Cons:**
- Slightly more complex model — two fields instead of one
- OrgAdmin must assign both when creating users — minor UX overhead

---

## Decision

**Implement hybrid role architecture** with `system_role` (fixed choices) and `job_title` (free text) as two separate fields on `CustomUser`.

`system_role` is the single source of truth for all permission and access control logic throughout the platform. `job_title` is a display field only and must never be referenced in permission checks, querysets, or access control logic anywhere in the codebase.

---

## Implementation

```python
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('org_admin', 'Organisation Admin'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
        ('viewer', 'Viewer'),
    ]
    system_role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default='staff'
    )
    job_title = models.CharField(
        max_length=100,
        blank=True,
        help_text="Display title within the organisation. Does not affect permissions."
    )
```

---

## Consequences

- All permission mixins and DRF permission classes check `system_role` exclusively
- `job_title` is shown on user profile, user list, and any exported reports
- OrgAdmin role is the only role permitted to change another user's `system_role`
- Future roles (e.g. `auditor`, `api_client`) are added to `ROLE_CHOICES` — never to free text
- RBAC permission matrix documented in `/docs/design/system-overview.md`

---

## Security Note

This decision directly mitigates privilege escalation via role field manipulation. Because `job_title` has no bearing on permissions, a user who edits their own profile cannot affect their access level regardless of what they enter. `system_role` changes are restricted to OrgAdmin and logged in the audit trail.

---

## Related Decisions

- ADR 003 — Tenant Isolation Strategy
- Design doc: `/docs/design/system-overview.md` (RBAC permission matrix)
