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
- Email notifications — low stock, EUDR expiry, user invitation
- Landing page — agriops.io with request access form

---

## Phase 4 — Product Depth ✅ Complete

- Inventory commodity fields — lot number, moisture, quality grade, harvest date, origin
- Supplier reliability score
- Bulk GeoJSON farm importer — SW Maps FeatureCollection support
- Traceability certificates — Batch model, QR codes, public trace URL
- Leaflet farm boundary maps on farm detail page
- Compliance report filtering — per sales order, per date range
- Request access form backend — auto-approve, creates company + user

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

## Revenue Model

| Stream | Detail | Phase |
|---|---|---|
| SaaS subscriptions | $50–$200/month per tenant | Phase 4 (Stripe pending) |
| Transaction fees | 1–2% on buyer portal orders | Phase 5 |
| Data intelligence | Supply trend subscriptions | Phase 6 |

---

## EU Buyer Target Markets

France (gum arabic), Germany (organic ingredients), Netherlands (Rotterdam import hub), UK (superfoods).

Key targets: Nexira, Alland & Robert, IMCD, Caldic, Kerry Group, Aduna, Tradin Organic.

Trade shows: Biofach, SIAL Paris, Fi Europe.

---

*Last updated: March 2026*
