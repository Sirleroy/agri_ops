# ADR 003 — Tenant Isolation Strategy: Company as Tenant Root

**Date:** March 2026
**Status:** Accepted
**Author:** Ezinna (Founder)

---

## Context

AgriOps is a multi-tenant SaaS platform. Multiple organisations (companies) share the same database and application instance. The most critical security requirement of the entire platform is that Organisation A can never access, view, modify, or infer the existence of Organisation B's data under any circumstances.

This decision was made at schema design time — before any models were written — because retrofitting tenant isolation onto an existing schema with live customer data is one of the most expensive and risky operations in SaaS engineering.

---

## Decision Drivers

- Data confidentiality between tenants is a hard security requirement
- EUDR compliance data is commercially sensitive — supply chain intelligence must not leak between organisations
- The platform must support future row-level security at the PostgreSQL level (Phase 4)
- Implementation must be simple enough that every developer on the team applies it consistently
- Must not require a separate database per tenant (operationally unscalable at seed stage)

---

## Multi-Tenancy Approaches Considered

### Approach 1 — Separate database per tenant
Each organisation gets its own PostgreSQL database.

**Pros:** Complete isolation by infrastructure. Zero risk of cross-tenant data leakage.

**Cons:** Operationally unscalable — 100 tenants means 100 databases to manage, back up, and migrate. Not viable at any stage of this project.

### Approach 2 — Separate schema per tenant (PostgreSQL schemas)
Each organisation gets its own PostgreSQL schema within a single database.

**Pros:** Strong isolation, single database to manage.

**Cons:** Django ORM does not natively support schema-per-tenant without third-party packages (django-tenant-schemas, django-tenants). Adds significant complexity. Migration management becomes painful. Overkill for current scale.

### Approach 3 — Shared schema with ForeignKey isolation ✅ Chosen
All tenants share the same tables. Every model has a `ForeignKey` to `Company` (the tenant root). All querysets are filtered by the current user's company at the view layer.

**Pros:**
- Simple, consistent, Django-native
- Easy to implement, easy to audit, easy to explain to new developers
- Scales well to thousands of tenants without operational overhead
- Clear path to PostgreSQL row-level security in Phase 4
- Every developer can understand and apply the pattern without specialist knowledge

**Cons:**
- Isolation is enforced at application layer — a bug in a queryset could theoretically expose cross-tenant data
- Requires discipline: every ListView and DetailView must filter by company
- Mitigation: comprehensive test suite (Phase 2) that explicitly tests cross-tenant access attempts

---

## Decision

**Shared schema with Company as tenant root.** Every core model has a `ForeignKey(Company, on_delete=models.CASCADE)`. All querysets in views are filtered by `request.user.company`. No exceptions.

---

## Architecture

```
Company (Tenant Root)
    ├── CustomUser      ForeignKey(Company)
    ├── Farmer          ForeignKey(Company)  ← Phase 4.6
    ├── Supplier        ForeignKey(Company)
    │     └── Farm      ForeignKey(Company)  ← Phase 2
    ├── Product         ForeignKey(Company)
    ├── Inventory       ForeignKey(Company)
    ├── PurchaseOrder   ForeignKey(Company)
    ├── SalesOrder      ForeignKey(Company)
    ├── Batch           ForeignKey(Company)  ← Phase 4
    └── AuditLog        ForeignKey(Company)  ← Phase 2
```

### TenantManager *(Phase 4.9 addition)*

All core models now carry `objects = TenantManager()` — a custom Django manager that adds a `for_company(company)` shortcut:

```python
# apps/companies/managers.py
class TenantManager(models.Manager):
    def for_company(self, company):
        return self.get_queryset().filter(company=company)
```

Usage:
```python
Farm.objects.for_company(request.user.company)
Farmer.objects.for_company(company).select_related('company')
```

This is an **additive convention layer** — it does not replace view-layer filtering (Rules 1–4 above remain mandatory). It provides:
- A named, documented pattern future developers can follow at the model layer
- A path to centralising any future pre-filtering logic (e.g. `is_active=True`) in one place
- Defence-in-depth against view-layer filtering being accidentally omitted

---

## Enforcement Rules

These rules are mandatory for every developer working on the codebase:

**Rule 1 — Every ListView filters by company:**
```python
def get_queryset(self):
    return super().get_queryset().filter(company=self.request.user.company)
```

**Rule 2 — Every DetailView verifies company ownership:**
```python
def get_object(self):
    obj = super().get_object()
    if obj.company != self.request.user.company:
        raise PermissionDenied
    return obj
```

**Rule 3 — No queryset may return records across companies:**
Any queryset that does not filter by company is a bug and must be treated as a security vulnerability.

**Rule 4 — CreateView automatically assigns company:**
```python
def form_valid(self, form):
    form.instance.company = self.request.user.company
    return super().form_valid(form)
```

---

## Testing Requirements (Phase 2)

The following tests are mandatory before Phase 2 exit:

- User from Company A cannot access Company B records via direct URL (`/suppliers/99/`)
- User from Company A receives 403 or 404 on any Company B object — never 200
- All ListViews return zero records from other companies regardless of database state
- CreateView assigns the correct company automatically — never accepts company from POST data

---

## Phase 5 Upgrade Path

In Phase 5, PostgreSQL Row-Level Security (RLS) will be added as a third layer of isolation — enforced at the database level independently of application code. This provides defence-in-depth: even if application-layer filtering is bypassed, the database itself refuses to return cross-tenant records.

The shared schema approach chosen here is fully compatible with RLS — no schema changes required for the upgrade.

---

## Consequences

- Every model migration must include the `company` ForeignKey — reviewed at PR time
- The tenant isolation test suite is a blocking gate for every Phase release
- URL enumeration attacks (incrementing PKs) are explicitly mitigated by Rule 2
- Audit log records the `company` on every entry for forensic traceability

---

## Related Decisions

- ADR 001 — Django + PostgreSQL stack
- ADR 002 — Hybrid Role Architecture
- Diagram: `/docs/diagrams/tenant-isolation.mermaid`
