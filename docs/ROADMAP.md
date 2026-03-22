---
layout: default
title: AgriOps Roadmap
---
# AgriOps — Project Roadmap

---

## Phase 1 — Core Data Models ✅ Complete
Django project setup, PostgreSQL, multi-tenant architecture, CustomUser, Company, Supplier, Farm, Product, Inventory, PurchaseOrder, SalesOrder models. Full CRUD for all modules.

---

## Phase 2 — Auth, RBAC, API ✅ Complete
Session authentication, JWT API, role-based access control (system_role + job_title), RoleRequiredMixin, AuditLog on all writes, security headers, HSTS, secure cookies.

---

## Phase 3 — Cloud Deployment ✅ Complete
- Render deployment (web + PostgreSQL)
- GitHub Actions CI/CD — 12 tests, auto-deploy on pass
- Custom domains — app.agriops.io, api.agriops.io, docs.agriops.io
- Brute force protection — django-axes, 5 attempts, 1hr lockout
- CORS policy — django-cors-headers
- Dashboard live stats — suppliers, farms, EUDR panel, activity feed
- Compliance PDF — full traceability report on demand
- Landing page — agriops.io with request access form

---

## Phase 4 — Product Depth ✅ Complete
- Inventory commodity fields — lot number, moisture, quality grade, harvest date, origin
- Supplier reliability score
- Bulk GeoJSON farm importer — SW Maps FeatureCollection support
- Traceability certificates — Batch model, QR codes, public trace URL
- Leaflet farm boundary maps on farm detail page
- Compliance report filtering — per sales order, per date range
- Request access form backend — auto-approve, creates Company + OrgAdmin user, welcome email, founder notification
- UX polish layer — toasts, search bars, empty states, overdue badges, EUDR expiry badges across all templates
- Dashboard intelligence cards Layer 1 — 6 rotating insight slides
- Ops dashboard — TOTP 2FA, OpsEventLog, 5 monitoring panels, live at app.agriops.io/ops-access/9f3k/
- Sentry error monitoring — live on production
- Posthog analytics — autocapture, pageview tracking, authenticated user identification
- SendGrid transactional email — domain authenticated, sender verified (no-reply@agriops.io)
- Cloudflare Email Routing — founder@agriops.io forwarding
- Landing page messaging overhaul — intelligence framing, two journeys (EUDR + supply chain intelligence)

---

## Phase 4.5 — EUDR Compliance Gaps 🔄 In Progress
Required before Phase 5. Gaps identified against Article 9 of EU Regulation 2023/1115:

- Farm: deforestation_reference_date (default 2020-12-31) + land_cleared_after_cutoff flag — HIGH
- Product: hs_code field for due diligence statement — MEDIUM
- Batch: quantity_kg field (net mass in kg, operator-confirmed) — MEDIUM
- Farm: harvest_year (production period proxy per Article 9(1)(d)) — MEDIUM
- EUDR commodity scope flag — lookup list distinguishing regulated vs non-regulated commodities — MEDIUM
- Supplier: verify/add postal address + email, surface on certificate — LOW-MEDIUM
- Batch: is_locked flag on dispatched batches (5-year retention) — LOW
- Nigeria risk classification — check EU country list, surface status in EUDR report header — MONITORING

---

## Phase 5 — Buyer Portal 🔄 Planned
- buyers.agriops.io — separate authenticated surface for EU buyers
- Available inventory catalogue per operator
- Traceability certificate viewer per batch
- Sample requests — triggers operator notification
- Order placement — connects to SalesOrder model
- Buyer registration and authentication

---

## Phase 6 — Market Intelligence 🔄 Planned
- Commodity price trends — AFEX API + World Bank
- Harvest forecasting — Open-Meteo weather API + historical yield data
- Warehouse stock analytics — turnover rates, low-stock frequency
- Regional supply heatmaps — Leaflet choropleth by state/region

---

## Phase 7 — AI Intelligence 🔄 Planned
- Anthropic API integration
- Customer onboarding assistant — guided setup for new tenants
- Document parsing — extract fields from PDFs, pre-fill forms
- Supplier reliability scoring — anomaly detection from purchase history
- EUDR risk assessment — location-based deforestation risk suggestions
- Compliance report narrative — natural language due diligence statements

---

## Tier System — Starter → Growth → Enterprise 🔄 Planned
Seat-based pricing with feature gating. Trigger: first paying tenant.

---

## Revenue Model

| Stream | Detail | Phase |
|---|---|---|
| SaaS subscriptions | Starter / Growth / Enterprise tiers | Phase 4 (Stripe pending) |
| Transaction fees | 1–2% on buyer portal orders | Phase 5 |
| Data intelligence | Supply trend subscriptions | Phase 6 |

---

## EU Buyer Target Markets
France (gum arabic), Germany (organic ingredients), Netherlands (Rotterdam import hub), UK (superfoods).
Key targets: Nexira, Alland & Robert, IMCD, Caldic, Kerry Group, Aduna, Tradin Organic.
Trade shows: Biofach, SIAL Paris, Fi Europe.

---

*Last updated: March 2026*
