# ADR 010 — Billing Architecture: Dual Processor, Isolated App, Plan-Gated Access

**Date:** April 2026
**Status:** Accepted — build triggered on first paying tenant
**Author:** Ezinna (Founder)

---

## Context

AgriOps is a multi-tenant SaaS platform moving toward its first paying tenant. The platform serves two distinct customer profiles with different payment realities:

- **Nigerian cooperatives and SMEs** — pay in NGN, use local payment infrastructure (Paystack, bank transfer)
- **International exporters and agri-businesses** — pay in USD, use international card infrastructure (Stripe)

A three-tier subscription model (Starter / Growth / Enterprise) has been designed with feature gates that map to real upgrade triggers: farm scale for Starter→Growth, and US/non-EU buyer market access (neutral traceability certificates) for Growth→Enterprise.

The architecture must stay consistent with existing codebase patterns — particularly the RBAC mixin + template guard discipline — and must not allow billing logic to leak into core domain apps.

---

## Decision Drivers

- Two payment processors required from day one — NGN and USD are not interchangeable
- Feature gating must be enforceable at the view layer and the template layer (same dual-gate discipline as RBAC)
- Billing logic must be isolatable — a payment processor SDK change must not require touching farm, order, or report code
- Ops dashboard superusers need manual override capability for pilots, deals, and grace periods
- Webhooks from both processors must be idempotent — both Stripe and Paystack retry on failure
- Build is deferred to first paying tenant — architecture must be decided now so implementation is a straight path when triggered

---

## Options Considered

### Option 1 — Single processor (Stripe only), NGN via manual invoicing
**Pros:**
- One integration, simpler codebase
- Stripe handles multi-currency internally

**Cons:**
- Stripe has limited penetration in Nigeria — local customers prefer Paystack or bank transfer
- Manual NGN invoicing does not scale and creates collection risk
- Locks out the cooperative/SME segment that is the Starter tier target

### Option 2 — Dual processor: Paystack (NGN) + Stripe (USD) behind a shared service layer ✅ Chosen
**Pros:**
- Each processor serves its natural market — no friction for either customer profile
- BillingService abstraction means views and models are processor-agnostic
- Adding a third processor in the future requires only a new processor class, not changes to views
- NGN prices set independently of USD — not FX-pegged — reflecting local purchasing power

**Cons:**
- Two webhook endpoints to maintain
- Two sets of credentials to manage in environment variables
- Slightly more surface area for billing bugs

### Option 3 — Usage-based billing (per farm, per report)
**Pros:**
- Revenue scales directly with customer activity

**Cons:**
- Disincentivises heavy farm mapping — the activity that creates lock-in and data depth
- Variable revenue is harder for customers to budget
- Farm count pricing breaks for commercial exporters who have few large farms but high commercial value

---

## Decision

### 1. Isolated billing app

All billing code lives in `apps/billing/`. No other app imports from it. Billing reads `Company` — that is the only dependency direction.

```
apps/billing/
├── models.py       # Subscription, Invoice
├── mixins.py       # PlanRequiredMixin
├── services.py     # BillingService — abstracts Stripe + Paystack
├── webhooks.py     # Idempotent webhook handlers for both processors
├── templatetags/   # {% plan_gate 'enterprise' %} template tag
└── urls.py         # /billing/ + /webhooks/stripe/ + /webhooks/paystack/
```

### 2. Plan tier on Company model

Four fields added to `Company`:

```python
plan_tier = CharField(choices=['starter', 'growth', 'enterprise'], default='starter')
subscription_status = CharField(choices=['trial', 'active', 'suspended', 'cancelled'])
billing_currency = CharField(choices=['ngn', 'usd'])
subscription_expires_at = DateTimeField(null=True)
```

`billing_currency` is set at company creation from registration country and never changed by the tenant. Nigerian-registered companies = NGN/Paystack. All others = USD/Stripe.

### 3. Feature gating follows existing RBAC discipline

`PlanRequiredMixin` mirrors `ManagerRequiredMixin`. Backend gate and template guard must always be in sync — the same permission sync checklist applies.

```python
class PlanRequiredMixin:
    required_plan = 'growth'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.company.meets_plan(self.required_plan):
            return redirect('billing:upgrade')
        return super().dispatch(request, *args, **kwargs)
```

`Company.meets_plan(tier)` evaluates tier hierarchy: enterprise ≥ growth ≥ starter.

Template guard:
```django
{% if request.user.company.meets_plan 'enterprise' %}
  ...feature...
{% else %}
  ...upgrade nudge...
{% endif %}
```

### 4. BillingService abstracts processor selection

```python
class BillingService:
    @staticmethod
    def get_processor(company):
        if company.billing_currency == 'ngn':
            return PaystackProcessor()
        return StripeProcessor()
```

Views and models call `BillingService` only. Stripe and Paystack SDKs are never imported outside `apps/billing/`.

### 5. Webhooks are idempotent

Both processors retry failed webhooks. Event IDs are stored on first receipt; duplicate events are discarded without side effects.

### 6. Ops dashboard integration

The ops dashboard gains a subscription management panel per tenant:

- View current plan tier, status, expiry, and billing currency
- Manual plan tier override — for pilots, negotiated deals, and grace periods
- Billing suspension connects to the existing `Company.is_active` flag — billing failure is another trigger for the same suspend/reactivate flow already built

---

## Consequences

- `Company` model gains four new fields — migration required at build time
- `PlanRequiredMixin` must be added to every view that gates a plan-restricted feature — same checklist discipline as RBAC
- Every plan-restricted template element requires a matching `{% if company.meets_plan %}` guard
- NGN prices are maintained independently — not derived from USD via FX rate
- Paystack and Stripe credentials stored in environment variables, never in code
- Webhook endpoints must be excluded from CSRF protection (use `@csrf_exempt` with signature verification instead)
- Build is deferred until first paying tenant — but no architectural rework will be required at that point

---

## Related Decisions

- ADR 003 — Tenant Isolation Strategy (Company as tenant root)
- ADR 006 — Ops Event Log Separation (ops dashboard architecture)
