# AgriOps — RBAC Design

**Version:** 1.0
**Date:** March 2026
**Status:** Phase 2 Complete — fully implemented

---

## Overview

AgriOps uses a four-level role hierarchy enforced via `system_role` on `CustomUser`. All permission decisions in both the Django view layer and the DRF API layer trace to this single field.

See ADR 002 for the rationale behind the hybrid `system_role` + `job_title` architecture.

---

## Role Hierarchy
```
org_admin  (level 4)  — Full control within their tenant
manager    (level 3)  — Can delete records, cannot manage users or roles
staff      (level 2)  — Can create and edit records, cannot delete
viewer     (level 1)  — Read-only access
```

Roles are strictly hierarchical. A higher level includes all permissions of lower levels.

---

## Permission Matrix

| Action | Viewer | Staff | Manager | OrgAdmin |
|---|---|---|---|---|
| View records | ✅ | ✅ | ✅ | ✅ |
| Create records | ❌ | ✅ | ✅ | ✅ |
| Edit records | ❌ | ✅ | ✅ | ✅ |
| Delete records | ❌ | ❌ | ✅ | ✅ |
| Manage users | ❌ | ❌ | ❌ | ✅ |
| Change system_role | ❌ | ❌ | ❌ | ✅ |
| Manage company settings | ❌ | ❌ | ❌ | ✅ |
| View compliance reports | ❌ | ✅ | ✅ | ✅ |
| Export compliance data | ❌ | ❌ | ✅ | ✅ |

---

## Django View Layer — Permission Mixins

Location: `apps/users/permissions.py`
```
RoleRequiredMixin (base)
  ├── StaffRequiredMixin    — required_role = 'staff'   (level 2+)
  ├── ManagerRequiredMixin  — required_role = 'manager' (level 3+)
  └── OrgAdminRequiredMixin — required_role = 'org_admin' (level 4)
```

All mixins extend `LoginRequiredMixin` — unauthenticated users are redirected to `/login/`. Authenticated users who fail the role check receive `403 PermissionDenied`.

**Usage pattern:**
```python
class SupplierDeleteView(ManagerRequiredMixin, DeleteView):
    ...
```

Mixin order matters — permission mixin always comes before the Django generic view class.

---

## API Layer — DRF Permission Classes

Location: `apps/api/permissions.py`
```
IsTenantMember        — user is authenticated and belongs to a company
IsManagerOrAbove      — IsTenantMember + system_role level >= 3
IsOrgAdmin            — IsTenantMember + system_role == 'org_admin'
```

All API viewsets inherit from `TenantScopedViewSet` which uses `IsTenantMember` by default and enforces `IsManagerOrAbove` for delete operations.

---

## Tenant Isolation

RBAC and tenant isolation are enforced together. A user with `org_admin` role can only manage users and records within their own company — not across tenants.

All querysets in views and viewsets filter by `request.user.company`. Cross-tenant access raises `Http404` — not `403` — to avoid leaking the existence of records in other tenants.

---

## system_role Change Control

`system_role` can only be changed via the dedicated `UserSystemRoleUpdateView` at `/users/<pk>/role/`. This view is protected by `OrgAdminRequiredMixin`.

`system_role` is excluded from the general `UserUpdateView` fields list — it cannot be changed via the standard profile edit form under any circumstances.

Every `system_role` change is captured in the AuditLog.

---

## Related Documents

- ADR 002 — Hybrid Role Architecture
- ADR 003 — Tenant Isolation Strategy
- `/apps/users/permissions.py` — Django mixin implementation
- `/apps/api/permissions.py` — DRF permission class implementation
