# AgriOps — Tenant Model

**Version:** 1.0
**Date:** March 2026
**Status:** Phase 1 architecture in place — Phase 2 enforcement layer being added

---

## Overview

AgriOps is a multi-tenant SaaS platform. Every organisation (Company) that uses the platform shares the same database and application instance, but each organisation's data is completely invisible to every other organisation. This document describes exactly how that isolation is implemented, enforced, and tested.

For the architectural decision rationale, see ADR 003.

---

## The Tenant Root

`Company` is the tenant root. It is the single model from which all data isolation flows.

Every model in the system has a direct `ForeignKey` to `Company`. There are no exceptions. A record without a `company` foreign key does not belong to the tenant model and must not contain customer data.

```python
# Every model follows this pattern
class Supplier(models.Model):
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='suppliers'
    )
    # ... other fields
```

---

## The Isolation Boundary

```
┌─────────────────────────────────────────┐
│           Company A (Tenant)            │
│  Users · Suppliers · Farms · Products   │
│  Inventory · PurchaseOrders · Sales     │
└─────────────────────────────────────────┘
                    ▲
         ISOLATION BOUNDARY
         No data crosses here
                    ▼
┌─────────────────────────────────────────┐
│           Company B (Tenant)            │
│  Users · Suppliers · Farms · Products   │
│  Inventory · PurchaseOrders · Sales     │
└─────────────────────────────────────────┘
```

A user authenticated as belonging to Company A can never read, write, or infer the existence of Company B's data, regardless of the URL they request, the API call they make, or the query parameters they supply.

---

## Enforcement Layer 1 — ListView Queryset Filtering

Every `ListView` and `ListAPIView` overrides `get_queryset()` to filter by the authenticated user's company.

**Django template views:**
```python
class SupplierListView(LoginRequiredMixin, ListView):
    model = Supplier
    template_name = 'suppliers/list.html'
    context_object_name = 'suppliers'

    def get_queryset(self):
        # TENANT ISOLATION: Only return records belonging to the current user's company
        return super().get_queryset().filter(company=self.request.user.company)
```

**DRF API viewsets (Phase 2):**
```python
class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        # TENANT ISOLATION: Scoped to authenticated user's company
        return Supplier.objects.filter(company=self.request.user.company)
```

**Rule:** Every `get_queryset()` method must include `.filter(company=self.request.user.company)`. This is reviewed at every PR. A missing filter is a security vulnerability, not a bug.

---

## Enforcement Layer 2 — DetailView Object Verification

Filtering the list is not sufficient. A user could bypass the list entirely by requesting a specific URL: `/suppliers/99/` where supplier 99 belongs to a different company.

Every `DetailView`, `UpdateView`, and `DeleteView` verifies company ownership after fetching the object:

```python
class SupplierDetailView(LoginRequiredMixin, DetailView):
    model = Supplier
    template_name = 'suppliers/detail.html'

    def get_object(self):
        obj = super().get_object()
        # TENANT ISOLATION: Verify this object belongs to the current user's company
        if obj.company != self.request.user.company:
            raise Http404  # 404 not 403 — see security note below
        return obj
```

**Why 404 and not 403?**

Returning HTTP 403 (Forbidden) confirms to an attacker that the record exists — they just can't access it. This is an information leak. Returning HTTP 404 (Not Found) reveals nothing. From the attacker's perspective, the record simply does not exist. This is the correct behaviour for a multi-tenant system.

---

## Enforcement Layer 3 — CreateView Company Assignment

When a user creates a new record, the `company` field must be assigned from the server side — never accepted from the client.

```python
class SupplierCreateView(LoginRequiredMixin, CreateView):
    model = Supplier
    fields = ['name', 'category', 'contact_person', 'phone', 'email', 'country', 'city', 'address', 'is_active']
    # Note: 'company' is NOT in fields — it is never accepted from POST data

    def form_valid(self, form):
        # TENANT ISOLATION: Assign company from authenticated user — never from form data
        form.instance.company = self.request.user.company
        return super().form_valid(form)
```

**Why is `company` excluded from `fields`?**

If `company` were in the form fields, a crafted POST request could assign a new record to a different company. By excluding it from `fields` and assigning it programmatically in `form_valid()`, the company assignment cannot be manipulated by the client under any circumstances.

---

## Enforcement Layer 4 — API Serializer Company Assignment (Phase 2)

At the DRF API layer, the same principle applies. `company` is a read-only field on all serializers — it is never writable from the API.

```python
class SupplierSerializer(serializers.ModelSerializer):
    company = serializers.HiddenField(
        default=serializers.CurrentUserDefault()
    )
    # company is hidden — never exposed in API input or output as a writable field

    class Meta:
        model = Supplier
        fields = ['id', 'name', 'category', 'contact_person', 'phone',
                  'email', 'country', 'city', 'is_active', 'company']
        read_only_fields = ['company']
```

---

## User — Company Relationship

A user belongs to exactly one company. This is enforced at the model level.

```python
class CustomUser(AbstractUser):
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        null=True,  # null only for superusers who span all companies
        blank=True
    )
```

**Superuser exception:** Django superusers (`is_superuser=True`) are platform administrators — they exist outside the tenant model. Superusers access data via the Django admin panel only, never through the regular application views. All superuser actions are logged.

**Unauthenticated users:** All views require authentication via `LoginRequiredMixin` (template views) or `IsAuthenticated` (API views). An unauthenticated request is redirected to the login page before any queryset is ever executed.

---

## Tenant Isolation in the Audit Log

Every audit log entry records the `company` it belongs to. This means:

- Compliance reports only surface audit events for the requesting user's company
- Cross-tenant audit log access is blocked by the same queryset filtering pattern
- Platform administrators can query audit logs across all companies via admin panel only

---

## Phase 4 — Second Layer: PostgreSQL Row-Level Security

In Phase 4, PostgreSQL Row-Level Security (RLS) will be added as a defence-in-depth layer. This operates independently of application code.

```sql
-- Example RLS policy (Phase 4)
ALTER TABLE suppliers_supplier ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON suppliers_supplier
    USING (company_id = current_setting('app.current_company_id')::int);
```

With RLS in place, even if a bug in application code produced an unfiltered queryset, the database itself would refuse to return records outside the current tenant context. Two independent isolation layers — application and database.

---

## Testing Requirements

The following tests are mandatory. They run as part of the CI/CD pipeline and are blocking — no deployment proceeds if they fail.

```python
class TenantIsolationTests(TestCase):

    def setUp(self):
        self.company_a = Company.objects.create(name="Company A")
        self.company_b = Company.objects.create(name="Company B")
        self.user_a = CustomUser.objects.create_user(
            username='user_a', company=self.company_a, system_role='staff'
        )
        self.user_b = CustomUser.objects.create_user(
            username='user_b', company=self.company_b, system_role='staff'
        )
        self.supplier_b = Supplier.objects.create(
            company=self.company_b, name="Supplier B"
        )

    def test_list_view_only_returns_own_company_records(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('suppliers:list'))
        self.assertEqual(response.status_code, 200)
        # Company A user sees zero suppliers — all belong to Company B
        self.assertEqual(len(response.context['suppliers']), 0)

    def test_detail_view_returns_404_for_other_company_record(self):
        self.client.force_login(self.user_a)
        response = self.client.get(
            reverse('suppliers:detail', args=[self.supplier_b.pk])
        )
        # Must return 404, not 200 or 403
        self.assertEqual(response.status_code, 404)

    def test_create_view_assigns_correct_company(self):
        self.client.force_login(self.user_a)
        self.client.post(reverse('suppliers:create'), {'name': 'New Supplier', ...})
        new_supplier = Supplier.objects.get(name='New Supplier')
        # Must be assigned to Company A regardless of POST data
        self.assertEqual(new_supplier.company, self.company_a)

    def test_create_view_cannot_assign_other_company_via_post(self):
        self.client.force_login(self.user_a)
        # Attempt to assign record to Company B via POST
        self.client.post(reverse('suppliers:create'), {
            'name': 'Malicious Supplier',
            'company': self.company_b.pk  # This should be ignored
        })
        supplier = Supplier.objects.get(name='Malicious Supplier')
        self.assertEqual(supplier.company, self.company_a)  # Still Company A
```

---

## Developer Checklist

Before submitting any PR that adds or modifies a view:

- [ ] `get_queryset()` filters by `company=self.request.user.company`
- [ ] `get_object()` raises `Http404` if `obj.company != self.request.user.company`
- [ ] `form_valid()` assigns `form.instance.company = self.request.user.company`
- [ ] `company` is NOT in the `fields` list of any CreateView or UpdateView
- [ ] `company` is a `read_only_field` in any DRF serializer
- [ ] Tenant isolation tests exist and pass for the new view

---

## Related Documents

- ADR 003 — Tenant Isolation Strategy (decision rationale)
- `/docs/diagrams/tenant-isolation.mermaid` — sequence diagram
- `/docs/threat-model.md` — cross-tenant access threat analysis
