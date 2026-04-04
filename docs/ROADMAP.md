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

## Phase 4.5 — Compliance Infrastructure ✅ Complete
Two gap analyses completed against EU and Nigerian export regulations. All gaps closed.

### EUDR Gaps — closed March 2026
- Farm: `deforestation_reference_date` (default 2020-12-31) + `land_cleared_after_cutoff` flag ✅
- Farm: `harvest_year` — production period proxy per Article 9(1)(d) ✅
- Product: `hs_code` for due diligence statement ✅
- Batch: `quantity_kg` (net mass in kg, operator-confirmed) ✅
- EUDR commodity scope — `EUDR_COMMODITIES` lookup set, `is_eudr_commodity` + `is_disqualified` properties on Farm ✅
- Certificate PDF: supplier chain section, harvest year + reference date columns ✅
- Batch: `is_locked` flag + delete guard (5-year retention) ✅
- Nigeria risk classification — MONITORING

### Export Compliance Gaps — closed March 2026
- `PhytosanitaryCertificate` model linked to Batch ✅
- `BatchQualityTest` model linked to Batch ✅
- Company: `nepc_registration_number` + `nepc_registration_expiry` ✅
- SalesOrder: `nxp_reference` + `certificate_of_origin_ref` ✅
- Product: `nafdac_registration_number` ✅
- `FarmCertification` model linked to Farm ✅
- Product: `eu_novel_food_status` + `eu_novel_food_ref` ✅

---

## Phase 4.6 — UX Simplification & Farmer Registry ✅ Complete
Shipped March 2026. Driven by live contract execution (soy export, Ake Collective) — all features confirmed against real operational need, not hypothetical users.

- **Farmer model** — proper farmer registry (name, phone, village, LGA, NIN). Replaces free-text `farmer_name` on Farm with a FK to a structured Farmer record ✅
- **Farm form** — `farmer` dropdown scoped to tenant, `farmer_name` field retired from UI ✅
- **PO auto-receipt** — "Mark as Received" button on PO detail automatically stocks inventory for each line item. No separate inventory trip required ✅
- **Batch embedded in SO flow** — farm linking moved to Sales Order detail page. User selects farms, Batch is created transparently. Batches removed from sidebar nav ✅
- **EUDR certificate on SO** — download button appears on Sales Order detail once farms are linked ✅
- **Farmer & Farm registry exports** — CSV and PDF export on both list pages. Branded PDF with AgriOps header, colour-coded EUDR status, page numbers ✅
- **PDF header fix** — resolved jumbled header rendering across all PDF generators (EUDR report, registry exports) ✅

**Discipline note:** From Phase 4.6 forward, no feature is built until confirmed by field use or direct user feedback. The live soy export contract is the primary signal source.

---

## Phase 4.7 — Field Operations Hardening ✅ Complete

Shipped April 2026. Focused on making bulk farm data ingestion reliable and auditable for field officers — the people who do the uploads are typically the least technical in the organisation and the data they capture is the foundation of the EUDR compliance chain.

- **GeoJSON import validation hardening** — Nigeria bounding box check catches wrong CRS and swapped lat/lon; completeness warnings (non-blocking) flag missing farmer name, LGA, or commodity per row; area upper bound flags declared areas > 200 ha as suspicious ✅
- **Dry-run mode** — full validation pipeline runs without writing to the database. Field officers validate before committing. UI shows "would create" count and all warnings/errors ✅
- **Upload history** — `FarmImportLog` model records every import attempt (dry-run and real): who uploaded, when, which supplier, filename, all counts, and full error/blocked/warning detail in JSON. Visible on the import page (last 5) and at `/farms/import/history/` (full log, expandable rows) ✅
- **Mobile upload UX** — import result summary appears above the form so field officers on phones see outcomes without scrolling; stats grids collapse to 2-column on small screens; download bars stack vertically; detail tables scroll horizontally ✅
- **HS code in compliance PDF** — batch DDS section now includes HS code derived from sales order line item products ✅
- **Security patch** — `requests` bumped to 2.33.0 ✅

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

*Last updated: 5 April 2026*
