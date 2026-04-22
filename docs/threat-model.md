# AgriOps — Threat Model

**Version:** 1.2
**Date:** April 2026
**Status:** Living document — updated as attack surface changes per phase
**Framework:** STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)

---

## 1. Overview

This document defines the threat model for AgriOps — a multi-tenant SaaS platform handling commercially sensitive agricultural supply chain data including EUDR compliance records, farm geolocation polygons, supplier contracts, and procurement and sales data.

The threat model identifies what we are protecting, who might attempt to compromise it, the attack vectors available to them, and the controls in place or planned to mitigate each threat.

---

## 2. Assets — What We Are Protecting

| Asset | Sensitivity | Why It Matters |
|---|---|---|
| Farm geolocation polygons | High | Commercially sensitive. Reveals exact farm boundaries and locations of supply chain partners. EUDR compliance data. |
| Supplier records | High | Commercial relationships, contact data, pricing. Competitive intelligence if leaked. |
| Purchase and sales order data | High | Volumes, prices, buyer identities. Directly reveals commercial position. |
| EUDR compliance documents | High | Legal documents. Tampering could constitute fraud. |
| User credentials | Critical | Compromise enables full account takeover |
| Multi-tenant isolation | Critical | Breach allows one tenant to read another's data — catastrophic trust failure |
| Audit log integrity | High | Tampering destroys chain of custody — forensic and legal implications |
| Application secret key | Critical | Django SECRET_KEY compromise allows session forgery and CSRF bypass |
| Database credentials | Critical | Direct database access bypasses all application controls |

---

## 3. Trust Boundaries

```
┌─────────────────────────────────────────────────────┐
│                  INTERNET (Untrusted)                │
│   Anonymous users, bots, attackers, API consumers   │
└──────────────────────┬──────────────────────────────┘
                       │ HTTPS only
              Authentication boundary
                       │
┌──────────────────────▼──────────────────────────────┐
│              AUTHENTICATED USERS (Partial trust)     │
│   Legitimate users — but scoped to own org only      │
│   Cannot be trusted with cross-tenant access         │
└──────────────────────┬──────────────────────────────┘
                       │ Tenant isolation boundary
                       │
┌──────────────────────▼──────────────────────────────┐
│              OWN ORGANISATION DATA (Trusted)         │
│   User may read/write within their company scope     │
│   Subject to RBAC role restrictions                  │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              DATABASE (Highly trusted)               │
│   Accessible only by application — never directly    │
│   from internet. Credentials in env vars only.       │
└─────────────────────────────────────────────────────┘
```

---

## 4. Threat Actors

| Actor | Motivation | Capability |
|---|---|---|
| Competing agri-business | Steal supplier/pricing data | Low-medium — targeted, patient |
| Disgruntled user | Damage, data leak, sabotage | Medium — authenticated access |
| Opportunistic attacker | Credential stuffing, data resale | Medium — automated tooling |
| EU buyer auditor | Verify compliance data integrity | Low threat — legitimate access |
| Malicious insider (future employee) | Data exfiltration, fraud | High — privileged access |
| Automated bots | Credential stuffing, scraping | High volume — low sophistication |

---

## 5. STRIDE Threat Analysis

### 5.1 Spoofing — Impersonating a legitimate user or system

| Threat | Attack Vector | Likelihood | Impact | Control | Status |
|---|---|---|---|---|---|
| Credential theft | Phishing, password reuse, data breach | High | Critical | Strong password policy, brute-force lockout (django-axes), TOTP MFA on ops dashboard | ✅ Active |
| Session hijacking | Cookie theft via XSS or network sniffing | Medium | High | HTTPS enforced, HttpOnly + Secure cookie flags, session timeout | ✅ Active |
| JWT token theft | Token intercepted or leaked in logs | Medium | High | Short token expiry, HTTPS only, tokens never logged | ✅ Active |
| Credential stuffing | Automated login attempts with leaked passwords | High | High | django-axes rate limiting, IP lockout after 5 failures, 1hr lockout | ✅ Active |

---

### 5.2 Tampering — Modifying data without authorisation

| Threat | Attack Vector | Likelihood | Impact | Control | Status |
|---|---|---|---|---|---|
| EUDR compliance data tampering | Authenticated user modifies farm verification records | Medium | Critical | Audit log on all writes, OrgAdmin-only verification fields, immutable audit trail | ✅ Active |
| Cross-tenant data modification | Crafted PUT/PATCH request to another org's record URL or cross-tenant foreign-key reference | Medium | Critical | Top-level object lookup is tenant-scoped; related-object tenant validation is part of ongoing hardening work | 🔄 Hardening |
| CSRF attack | Forged form submission from malicious site | Medium | High | Django CSRF middleware enabled by default | ✅ Active |
| Mass assignment | Extra POST fields used to overwrite sensitive model fields | Medium | High | Explicit `fields` lists on all forms and serializers | ✅ Active |
| Audit log tampering | User attempts to delete or modify audit entries | Low | Critical | Audit log is append-only, no delete/update views exposed, admin-only access | ✅ Active |

---

### 5.3 Repudiation — Denying an action was performed

| Threat | Attack Vector | Likelihood | Impact | Control | Status |
|---|---|---|---|---|---|
| User denies creating/modifying a record | No audit trail | Medium | High | Audit log: every create/update/delete records user, timestamp, IP, changes | ✅ Active |
| Disputed EUDR compliance verification | No record of who verified a farm | High | Critical | `verified_by`, `verified_date` fields on Farm model. Audit log entry on verification. | ✅ Active |
| Disputed document upload | No record of who uploaded compliance document | Medium | High | `uploaded_by`, `uploaded_at` on ComplianceDocument. | ✅ Active |

---

### 5.4 Information Disclosure — Exposing data to unauthorised parties

| Threat | Attack Vector | Likelihood | Impact | Control | Status |
|---|---|---|---|---|---|
| Cross-tenant data read | URL enumeration — requesting `/suppliers/99/` belonging to another org | High | Critical | DetailView raises Http404 if `obj.company != request.user.company` | ✅ Active |
| Cross-tenant list exposure | Unfiltered queryset returns all records | High | Critical | All ListViews filter by `company=request.user.company` | ✅ Active |
| Secrets in version control | `settings.py` committed with DB password or SECRET_KEY | High | Critical | `settings.py` in `.gitignore`. `.env` pattern enforced. Repository is private. | ✅ Active |
| Sensitive data in logs | Passwords, tokens, PII logged in plaintext | Medium | High | Structured logging — sensitive fields explicitly excluded. Passwords never logged. | ✅ Active |
| Database exposed to internet | PostgreSQL port open on hosting server | Medium | Critical | DB accessible only from application server. Port 5432 not publicly exposed. | ✅ Active |
| API over HTTP | Data intercepted in transit | High | High | HTTPS enforced. HTTP requests redirected. HSTS header. | ✅ Active |
| Farm geolocation in error messages | Stack trace reveals GeoJSON data | Low | Medium | DEBUG=False in production. Custom error pages. Sentry configured with PII scrubbing. | ✅ Active |

---

### 5.5 Denial of Service — Making the system unavailable

| Threat | Attack Vector | Likelihood | Impact | Control | Status |
|---|---|---|---|---|---|
| Login endpoint flooding | Automated POST requests to `/login/` | High | Medium | django-axes lockout. Rate limiting on auth endpoints. | ✅ Active |
| API endpoint flooding | High-volume API requests | Medium | Medium | DRF throttling — 200 req/hr per user, 20 req/hr anonymous | ✅ Active |
| Large file upload abuse | Uploading massive or unexpected compliance documents | Low | Medium | Compliance document upload validation is being hardened; until then, rely on authenticated access and operational monitoring | 🔄 Hardening |
| Expensive database queries | Crafted filter parameters causing full table scans | Low | Medium | Query optimisation audit and DB query timeouts | 🔄 Phase 5 |

---

### 5.6 Elevation of Privilege — Gaining higher access than authorised

| Threat | Attack Vector | Likelihood | Impact | Control | Status |
|---|---|---|---|---|---|
| Role field manipulation | User edits own `system_role` via profile form | Medium | Critical | `system_role` not in any user-facing form `fields` list. OrgAdmin-only via dedicated view. | ✅ Active |
| Horizontal privilege escalation | Low-privilege tenant user reaches write-capable endpoints intended for staff or manager roles | Medium | High | Server-rendered views use RBAC mixins; API method-level role enforcement is being aligned with the same policy | 🔄 Hardening |
| IDOR — access another user's profile | Authenticated user requests `/users/99/` for another org's user | Medium | High | UserDetailView filters by company. 404 on cross-tenant. | ✅ Active |
| Django admin exposure | Admin panel accessible to non-superusers | Low | Critical | Admin at non-default URL. Superuser-only access enforced. | ✅ Active |
| JWT algorithm confusion | Attacker crafts token using `alg: none` | Low | Critical | djangorestframework-simplejwt enforces HS256. Algorithm explicitly configured. | ✅ Active |
| Self-service tenant provisioning | Public onboarding path creates company and admin account without manual approval | Medium | High | Pre-commercial rollout requires gating or replacing public auto-provisioning before live tenant onboarding | 🔄 Hardening |

---

## 6. EUDR-Specific Threats

The compliance module introduces additional threats specific to regulatory data:

| Threat | Description | Control |
|---|---|---|
| False verification | User marks unverified farm as EUDR verified | `verified_by` and `verified_date` required. Audit logged. Manager+ permission only. |
| Geolocation spoofing | Farm polygon submitted does not match actual farm location | Satellite imagery cross-check (manual, Phase 5). SW Maps GPS accuracy field stored. |
| Corrupt geospatial data at import | Self-intersecting polygon, coordinate bomb, swapped lat/lon, or degenerate ring enters the database and silently corrupts area calculations and risk status downstream | 15-point GeoJSON validation suite runs in CI on every deployment. Validator catches all known failure modes before data reaches the database. ✅ Phase 4.8 |
| Document forgery | Fraudulent compliance documents uploaded | Document hash stored on upload. Out-of-scope for platform to validate content — operator responsibility. |
| Verification expiry ignored | Expired farm verification used in active orders | Compliance dashboard alerts on expiring verifications. Future: block order creation for expired farms. |
| Supply chain data sold to competitors | Internal user exfiltrates supplier + farm data | Audit log. DLP not in scope at current phase. Access reviews by OrgAdmin. |

---

## 7. Controls Summary

### Phases 1–3 ✅ Complete
- Multi-tenant queryset filtering — top-level ListViews
- Cross-tenant DetailView 404 — top-level DetailViews
- Company auto-assignment on primary create paths — never from client body
- Explicit `fields` lists — no mass assignment
- Django CSRF middleware
- Secrets excluded from version control (`.gitignore`). Repository private.
- Login UI with brute-force protection (django-axes) — 5 failures, 1hr lockout
- RBAC permission mixins on server-rendered sensitive views
- Role field removed from user-facing forms
- Audit log — all create/update/delete actions
- JWT authentication for API
- Rate limiting — 200 req/hr authenticated, 20 req/hr anonymous
- Environment variables for all secrets
- Security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
- CORS configuration
- HTTPS enforced, HTTP redirected, HSTS header
- DEBUG=False enforced in production
- Database not publicly exposed
- Django admin at non-default URL
- Sentry error tracking (PII scrubbing configured)

### Phase 4 ✅ Complete
- TOTP 2FA — ops dashboard (platform superusers)
- GeoJSON 15-point validation suite — CI enforced on every deployment

### Current Hardening Work 🔄 In Progress
- Related-object tenant validation on serializer and form foreign keys
- API method-level role enforcement aligned with UI RBAC
- Public onboarding path gated before live tenant rollout
- Compliance document upload validation

### Phase 5 🔄 Planned
- Internal penetration test — documented findings and remediations
- Dependency vulnerability scanning (Safety / pip-audit — GitHub Advanced Security not active on private repo)
- Tenant OrgAdmin MFA — TOTP for tenant-level accounts
- NDPA compliance review
- GDPR readiness assessment
- Query timeout configuration

---

## 8. Residual Risks

| Risk | Reason Accepted | Mitigation Plan |
|---|---|---|
| No tenant-level MFA | Ops dashboard TOTP live; tenant OrgAdmin MFA deferred pre-revenue | Phase 5 with TOTP for OrgAdmin accounts |
| Single-layer DB isolation | RLS adds complexity — manual filtering sufficient at current scale | Phase 5 if multi-tenant load increases |
| No dependency scanning | Private repo — GitHub Advanced Security not active. Manual review currently sufficient. | Safety / pip-audit in Phase 5 CI |
| No penetration test | Product has a public marketing surface and pre-commercial onboarding flow, but no formal external test yet | Phase 5 with documented report |
| Expensive query DoS | No query timeout configured | Phase 5 query optimisation audit |

---

## 9. Threat Model Maintenance

This document is reviewed and updated:
- At the start of each new phase
- When a new model or API endpoint is added
- When a security incident occurs
- When a new threat actor or attack vector is identified

**Owner:** Ezinna (Founder)
**Next review:** Phase 5 — Buyer Portal (new public-facing attack surface)

---

## Related Documents

- ADR 003 — Tenant Isolation Strategy
- `/docs/design/tenant-model.md` — isolation implementation detail
- `/docs/security-testing.md` — red team exercises and findings log
- `/docs/diagrams/tenant-isolation.mermaid` — isolation sequence diagram
- `/docs/diagrams/auth-flow.mermaid` — authentication flow
- `/docs/runbooks/incident-response.md` — what to do when a threat is realised
