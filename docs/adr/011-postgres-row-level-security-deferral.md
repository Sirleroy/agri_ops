---
layout: default
title: "ADR 011 — PostgreSQL Row-Level Security: Deferral Criteria and Implementation Shape"
---

# ADR 011 — PostgreSQL Row-Level Security: Deferral Criteria and Implementation Shape

**Date:** May 2026
**Status:** Deferred — triggers and implementation shape defined
**Author:** Ezinna (Founder)

---

## Context

ADR 003 chose application-enforced tenant isolation (queryset filtering, mixins, suspended-company checks) and noted that PostgreSQL Row-Level Security (RLS) would be added as a Phase 5 defence-in-depth layer. That note was directional but did not specify *when* the implementation tax becomes worth paying, *what* the trigger criteria are, or *how* the implementation should be shaped.

This ADR fills those gaps. It supersedes the brief Phase 5 note in ADR 003.

The current application-enforced isolation is defensible:

- Every list view filters by `company=request.user.company`
- `CompanyOwnedMixin` returns 404 on cross-tenant detail access
- `CompanySetMixin` stamps the company on creation
- DRF API permission classes apply equivalent rules on the JWT path
- Suspended-company enforcement runs at web, dashboard, admin panel, and API layers
- 36 regression tests run via `verify.sh` before every deploy
- Tenant lifecycle (create / delete) is locked out of tenant users entirely (ADR 003 hardening, May 2026)

RLS would add a database-layer enforcement on top of all of the above. The question is when — not whether.

---

## What RLS Actually Is

PostgreSQL RLS evaluates a policy expression on every row touched by SELECT / INSERT / UPDATE / DELETE. The policy typically reads a session-set variable and applies it as an invisible WHERE clause:

```sql
ALTER TABLE suppliers_farm ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON suppliers_farm
  USING (company_id = current_setting('app.tenant_id')::int);
```

After this, any query against `suppliers_farm` — ORM, raw SQL, BI tool, future library — only returns rows where `company_id` matches the session variable. If the variable is unset, the policy returns false and no rows are visible. RLS is a database-level lock, independent of application code.

---

## Trigger Criteria (any one fires)

Implement RLS when any of the following becomes true:

1. **First paying enterprise tenant with a security questionnaire** asking "is tenant isolation enforced at the database layer?" This is the most likely real trigger and the answer matters to commercial procurement.
2. **Phase 5 buyer portal goes live.** External multi-tenant read consumers — the largest data-exposure blast radius the platform will ever have. RLS should be in place *before* this ships, not bolted on after.
3. **Second active ORM-query author on the codebase.** The discipline of `.filter(company=request.user.company)` is conventionally enforced by review. With more than ~3 reviewers, drift is statistically inevitable. RLS becomes the backstop.
4. **Government procurement, grant due diligence, NDPR audit, or SOC 2 / ISO 27001 process** that explicitly probes data-layer enforcement.
5. **Third-party DB-adjacent access** — read replicas given to partners, BI tools given direct connections, customer-facing JDBC. RLS lets you grant DB access without granting cross-tenant access.

If none of the above applies, RLS is premature: the implementation tax outweighs the benefit at the current threat model.

---

## Pros (when triggered)

- **Defence in depth.** Two locks instead of one. A forgotten `.filter(company=...)` does not leak data.
- **Audit story.** "Tenant isolation is enforced at the database layer" reads stronger to auditors than "we filter in querysets and have tests." It is harder to disable and easier to verify.
- **Catches arbitrary query paths.** Raw SQL, custom managers, future libraries, BI tools, ad-hoc shell sessions — all enforced.
- **Better fix-latency on isolation bugs.** With application-only enforcement, a leaky view in production means data is leaking until the deploy lands. With RLS, the database holds the line while the fix ships.
- **Trusted-but-scoped DB access becomes safe.** A tenant-scoped read replica connection can be exposed without exposing the platform.
- **Reduced cognitive load on new code.** New queries inherit isolation by default — though best practice keeps explicit `.filter()` calls for clarity, performance, and N+1 prevention.

## Cons (when triggered)

- **Implementation tax.** Every tenant-scoped table needs `ENABLE ROW LEVEL SECURITY`, one or more `CREATE POLICY` statements, migrations, and a documented bypass role.
- **Tenant-context propagation everywhere.** Web middleware, JWT middleware, management commands, migrations, Celery tasks, tests, Django shell, database backups — all need to set `app.tenant_id` or use the bypass role.
- **The bypass role is a new attack surface.** Whoever holds the bypass credential sees all data across all tenants. That credential becomes high-value: it needs a separate connection pool, audit logging on use, and a rotation procedure.
- **Cross-tenant features get harder.** The ops dashboard, `OpsEventLog`, `AccessRequest`, management commands, and the Phase 5 buyer portal all legitimately query across tenants. Each needs explicit bypass + audit.
- **Performance gotchas.** Simple equality (`company_id = X`) uses indexes and is fine. Complex policies with subqueries, joins, or function calls can degrade. The PostgreSQL planner does not always push down RLS as efficiently as a developer-written WHERE clause.
- **Migration complexity.** Schema changes need to maintain policies. Adding RLS to an existing populated table requires staged rollout: enable → verify → `FORCE`.
- **Debugging gets harder.** "Why no rows?" gains a new answer: "you didn't set tenant context." Non-obvious to new developers.
- **Connection pooling interactions.** `SET LOCAL app.tenant_id` is transaction-scoped and safe. Plain `SET` persists across connection reuse and is dangerous with pgbouncer transaction-pooling. Middleware must use `SET LOCAL` inside an explicit transaction.
- **Test setup overhead.** Every test sets tenant context. Platform-scope tests (ops dashboard, auth, AccessRequest) coexist with tenant-scoped tests. Fixtures get more complex.
- **Application-layer enforcement still required.** RLS does not validate FK *targets* — you can still write a row pointing at another tenant's product unless the form/serializer validates. RLS does not know about roles. RLS does not enforce UI permission gates. Mixins, audit logs, certificate blockers, and UI guards remain load-bearing.

---

## AgriOps-Specific Considerations

Things in this codebase that bend the standard RLS playbook:

1. **Intentional cross-tenant flows already exist:**
   - Ops dashboard (suspend/reactivate, `OpsEventLog`)
   - `AccessRequest` (platform-scope, no tenant FK)
   - Management commands (`seed_demo`, `backfill_*`, `check_geometry_integrity`)
   - Phase 5 buyer portal — external multi-tenant *read* path with separate auth model

   Each needs explicit bypass logic. The bypass paths are the actual new attack surface RLS introduces.

2. **JWT API path is separate from session middleware.** Tenant context for JWT requests comes from the decoded token's user, not the session. RLS context-setting middleware must handle both transports.

3. **Indirect tenant scoping.** `PurchaseOrderItem` and `SalesOrderItem` have no direct `company` FK — they are scoped through their parent's company. RLS policies for these tables need either a subquery (`WHERE order_id IN (SELECT id FROM purchase_orders_purchaseorder WHERE company_id = ...)`) or a denormalised `company_id` column. The latter is faster but adds a write-path invariant to maintain.

4. **GeoJSON in JSONField.** RLS protects the *row* containing the geometry, not the geometry bytes. A platform-wide deforestation analytics query running under bypass exposes everything in a single statement. Plan for it.

5. **Geometry hash is application-layer integrity.** RLS does not protect against tampering by anyone with bypass — only against cross-tenant access by anyone *without* bypass. The SHA-256 hash and `check_geometry_integrity` command remain load-bearing for write-side integrity.

6. **`check_geometry_integrity` queries cross-tenant by design.** It scans every farm in the database. It needs to run under bypass.

7. **Half-RLS is worse than no-RLS.** Some tables enabled, others not, no audited bypass — the platform sounds protected but has gaps. If RLS is implemented, it must be implemented end-to-end on every tenant-scoped table at once.

---

## Implementation Shape (when triggered)

The work is approximately one to two weeks of focused effort given how many cross-tenant flows already exist. Sequencing:

1. **Audit every query path** — web views, DRF API, ops dashboard, management commands, migrations, Celery (when added), tests, Django shell. Catalogue which are tenant-scoped and which are platform-scope.
2. **Build per-request tenant-context middleware** for both session and JWT transports. Use `SET LOCAL app.tenant_id = %s` inside an explicit transaction, never plain `SET`.
3. **Create a `bypass_rls` PostgreSQL role** with `BYPASSRLS` privilege. Issue separate connection DSN for ops dashboard, migrations, and management commands. Audit every use.
4. **Denormalise indirect FKs** — add `company_id` columns to `PurchaseOrderItem` and `SalesOrderItem` with a write-path invariant matching their parent. Backfill before policy creation.
5. **Add RLS policies to every tenant-scoped table** in a single coordinated migration. Enable `ROW LEVEL SECURITY`, create the policy, do not yet `FORCE`.
6. **Update intentional cross-tenant flows** to connect with the bypass DSN explicitly. Add audit log entries for each bypass use.
7. **Update test infrastructure** to set tenant context per test. Add a new test class that proves DB-level blocking persists even when application-layer filtering is removed — the "would RLS catch a regression?" sanity check.
8. **Document the bypass model and credential management** in this repo and in the runbooks folder.
9. **Roll out enabled-but-not-FORCED first.** Monitor for breakage in staging and a quiet period of production. Then `ALTER TABLE ... FORCE ROW LEVEL SECURITY` to also block superusers from accidental bypass.

CI must run the existing 36-test application-layer suite *and* the new DB-level blocking suite. Both must pass for deploy.

---

## Cost of Deferral

While RLS is deferred:

- A tenant-isolation bug in a new view immediately leaks data — there is no database-layer backstop.
- The application-layer enforcement is the only line; its discipline must be maintained on every new view, every new serialiser, every new management command.
- Multi-engineer drift risk grows the longer the codebase lives without RLS.
- Grant proposals and security questionnaires that ask about DB-level enforcement get a "planned, not implemented" answer rather than a "yes, see ADR 011 and policy migrations."

These costs are acceptable today. They are not acceptable past any of the trigger criteria above.

---

## Decision

Defer PostgreSQL Row-Level Security. Implement to the shape described above when any single trigger criterion fires.

Half-RLS is forbidden — when the build is triggered, all tenant-scoped tables are migrated together, with audited bypass and end-to-end test coverage. No tables are RLS-enabled in isolation as a "trial."

This ADR supersedes the Phase 5 RLS note in ADR 003.

---

## Related Decisions

- [ADR 003 — Tenant Isolation Strategy](003-tenant-isolation-strategy.md) — the application-layer foundation that RLS sits on top of
- [ADR 006 — OpsEventLog Separation](006-ops-event-log-separation.md) — example of a platform-scope table that will need bypass
- [ADR 010 — Billing Architecture](010-billing-architecture.md) — billing tables will be tenant-scoped and inherit the same RLS policy treatment when triggered
