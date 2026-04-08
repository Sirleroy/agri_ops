# AgriOps — Data Model Documentation

**Version:** 2.2
**Date:** 8 April 2026
**Status:** Current — updated through Phase 4.9

---

## Overview

AgriOps uses a relational data model built on PostgreSQL. The central design principle is **Company as tenant root** — every record in the system belongs to exactly one Company, enforcing data isolation between organisations.

Full ERD: `/docs/diagrams/erd.dbml`

---

## Company

The tenant root. Every other model has a ForeignKey to Company.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| name | CharField(255) | Organisation name |
| country | CharField(100) | |
| city | CharField(100) | |
| address | TextField | |
| phone | CharField(20) | |
| email | EmailField | |
| plan_tier | CharField | Choices: free, growth, pro, enterprise |
| is_active | BooleanField | Default: True |
| created_at | DateTimeField | Auto |
| updated_at | DateTimeField | Auto |

---

## CustomUser

Extends Django's AbstractUser. System role drives all permission logic. Job title is display only.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| username | CharField | Inherited |
| email | EmailField | Inherited |
| first_name | CharField | Inherited |
| last_name | CharField | Inherited |
| company | ForeignKey(Company) | Tenant assignment |
| system_role | CharField | Choices: org_admin, manager, staff, viewer |
| job_title | CharField(100) | Free text — display only, no permission bearing |
| phone | CharField(20) | |
| is_active | BooleanField | |
| date_joined | DateTimeField | Inherited |
| last_login | DateTimeField | Inherited |

See ADR 002 for role architecture rationale.

---

## Farmer *(Phase 4.6 addition)*

The individual who owns or manages a farm plot. Replaces the free-text `farmer_name` field that previously lived on Farm. One farmer can be linked to multiple farms.

**Manager:** `objects = TenantManager()` — use `Farmer.objects.for_company(company)` for tenant-scoped queries.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant isolation |
| first_name | CharField(150) | |
| last_name | CharField(150) | blank |
| gender | CharField | Choices: M, F — blank |
| phone | CharField(20) | blank |
| village | CharField(100) | Village of residence — blank |
| lga | CharField(100) | Local Government Area — blank |
| nin | CharField(20) | National Identification Number — blank, non-binding |
| crops | CharField(255) | Comma-separated crop/livestock list |
| consent_given | BooleanField | Default: False |
| consent_date | DateField | nullable |
| bank_name | CharField(150) | blank — parked, no UI until tenant request |
| account_number | CharField(50) | blank — parked |
| created_at | DateTimeField | Auto |
| updated_at | DateTimeField | Auto |

**Computed property:** `full_name` — concatenates first_name + last_name

**Relationship:** One Farmer → Many Farms

---

## Supplier

The commercial trading entity. May aggregate produce from multiple farms.

**Manager:** `objects = TenantManager()` — use `Supplier.objects.for_company(company)` for tenant-scoped queries.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant isolation |
| name | CharField(255) | |
| category | CharField | Choices: farmer, cooperative, processor, distributor, exporter |
| contact_person | CharField(255) | |
| phone | CharField(20) | |
| email | EmailField | |
| country | CharField(100) | |
| city | CharField(100) | |
| address | TextField | |
| is_active | BooleanField | |
| created_at | DateTimeField | Auto |
| updated_at | DateTimeField | Auto |

**Relationship:** One Supplier → Many Farms

---

## Farm *(Phase 2 addition — extended Phase 4.5 + 4.6 + 4.9)*

The physical plot of land. The EUDR compliance unit. Linked to Supplier (the aggregator/trader), Farmer (the individual), and Company (tenant).

**Manager:** `objects = TenantManager()` — use `Farm.objects.for_company(company)` for tenant-scoped queries.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant isolation |
| supplier | ForeignKey(Supplier) | Commercial relationship |
| farmer | ForeignKey(Farmer) | nullable — individual farmer owner/operator. Replaces retired `farmer_name` CharField |
| name | CharField(255) | Farm / Plot Name |
| geolocation | JSONField | GeoJSON Polygon — see ADR 004 |
| area_hectares | DecimalField | |
| country | CharField(100) | |
| state_region | CharField(100) | |
| commodity | CharField(100) | e.g. Soy, Maize, Cocoa |
| deforestation_risk_status | CharField | Choices: low, standard, high |
| deforestation_reference_date | DateField | Default: 2020-12-31. Evidence baseline per EUDR Article 2(28) |
| land_cleared_after_cutoff | BooleanField | nullable. True = disqualified from EUDR |
| harvest_year | PositiveSmallIntegerField | nullable. Production period proxy per Article 9(1)(d) |
| mapping_date | DateField | When GPS mapping was performed |
| mapped_by | ForeignKey(CustomUser) | Field agent who performed mapping |
| is_eudr_verified | BooleanField | Default: False |
| verified_by | ForeignKey(CustomUser) | Compliance officer |
| verified_date | DateField | |
| verification_expiry | DateField | When verification lapses |
| created_at | DateTimeField | Auto |
| updated_at | DateTimeField | Auto |

**Field Verification Form (FVF) fields** *(Phase 4.9 addition — digitalises the paper consent + land-use form collected during GPS mapping exercise)*

| Field | Type | Notes |
|---|---|---|
| fvf_land_acquisition | CharField | Choices: inherited, bought, granted — blank |
| fvf_land_tenure | CharField | Choices: title_deed, village_consent — blank |
| fvf_years_farming | PositiveSmallIntegerField | nullable |
| fvf_untouched_forest | BooleanField | nullable. True = primary forest present on farm |
| fvf_expansion_intent | BooleanField | nullable. True = forward risk flag (shown in red on detail page) |
| fvf_consent_given | BooleanField | Default: False. Farmer consented to GPS mapping and data collection |
| fvf_consent_date | DateField | nullable |

> The paper FVF (farmer + village head signatures) is the legal record. AgriOps holds the searchable digital copy.

**Computed properties:** `is_eudr_commodity`, `is_disqualified`, `is_verification_current`, `compliance_status`

See ADR 005 for farm model separation rationale.

---

## Product

The commodity catalogue. Products are linked to a supplier and scoped to a company.

**Manager:** `objects = TenantManager()` — use `Product.objects.for_company(company)`.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant isolation |
| supplier | ForeignKey(Supplier) | nullable |
| name | CharField(255) | |
| description | TextField | |
| category | CharField | Choices defined per commodity types |
| unit | CharField | Choices: kg, tonne, bag, litre, unit |
| unit_price | DecimalField | |
| hs_code | CharField(20) | EU Combined Nomenclature code — required for EUDR DDS |
| nafdac_registration_number | CharField(50) | NAFDAC reg number for regulated products — blank |
| eu_novel_food_status | BooleanField | Default: False |
| eu_novel_food_ref | CharField(100) | EU Novel Food Catalogue reference — blank |
| is_active | BooleanField | |
| created_at | DateTimeField | Auto |
| updated_at | DateTimeField | Auto |

---

## FarmImportLog *(Phase 4.7 addition)*

Audit record of every farm GeoJSON import attempt — dry-run and real. Written by both the web import view and the API endpoint. Gives field officers and managers a traceable history of what was uploaded, by whom, and what the outcome was.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant isolation |
| uploaded_by | ForeignKey(CustomUser) | nullable — SET_NULL on user delete |
| supplier | ForeignKey(Supplier) | nullable — SET_NULL on supplier delete |
| filename | CharField(255) | Original filename from the upload |
| dry_run | BooleanField | True if "Validate only" was checked |
| total | PositiveIntegerField | Features in the uploaded file |
| created | PositiveIntegerField | Farms actually written (0 on dry-run) |
| would_create | PositiveIntegerField | Farms that passed validation (populated on dry-run) |
| duplicates | PositiveIntegerField | Skipped — name+supplier match |
| blocked | PositiveIntegerField | Skipped — polygon overlaps existing farm |
| errors | PositiveIntegerField | Failed geometry or coordinate validation |
| warning_count | PositiveIntegerField | Rows with completeness issues (non-blocking) |
| error_detail | JSONField | Per-row: row, name, reason |
| blocked_detail | JSONField | Per-row: row, name, reason |
| warning_detail | JSONField | Per-row: row, name, issues[] |
| created_at | DateTimeField | Auto |

**UI surfaces:**
- Import page — last 5 entries shown as "Recent Uploads" table
- `/suppliers/farms/import/history/` — full paginated log with expandable detail rows

---

## Inventory *(extended Phase 4)*

Stock levels per product. Includes low-stock threshold alerting. Auto-updated when a PO is marked as Received.

**Manager:** `objects = TenantManager()`.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant isolation |
| product | ForeignKey(Product) | |
| quantity | DecimalField | Current stock level — auto-incremented on PO receipt |
| warehouse_location | CharField(255) | |
| low_stock_threshold | DecimalField | Alert trigger level |
| lot_number | CharField(50) | Auto-generated if blank |
| moisture_content | DecimalField | nullable. % at time of intake |
| quality_grade | CharField | Choices: A, B, C, off |
| harvest_date | DateField | nullable |
| origin_state | CharField(100) | State/region of origin |
| last_updated | DateTimeField | Auto |
| created_at | DateTimeField | Auto |

**Computed property:** `is_low_stock` — returns True if quantity ≤ low_stock_threshold

**Unique constraint:** `(company, product, warehouse_location)`

---

## PurchaseOrder

Procurement record. Created when buying from a supplier.

**Manager:** `objects = TenantManager()`.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant isolation |
| supplier | ForeignKey(Supplier) | nullable |
| order_number | CharField | Unique identifier |
| status | CharField | Choices: draft, approved, ordered, received, cancelled |
| order_date | DateField | Auto |
| expected_delivery | DateField | nullable |
| notes | TextField | |

---

## PurchaseOrderItem

Line items for a Purchase Order.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| purchase_order | ForeignKey(PurchaseOrder) | |
| product | ForeignKey(Product) | |
| quantity | DecimalField | |
| unit_price | DecimalField | |

**Computed property:** `total_price` — quantity × unit_price

---

## SalesOrder

Customer order record. Created when selling to a buyer.

**Manager:** `objects = TenantManager()`.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant isolation |
| order_number | CharField | Unique identifier |
| customer_name | CharField(255) | |
| customer_email | EmailField | nullable |
| customer_phone | CharField(20) | nullable |
| status | CharField | Choices: draft, confirmed, dispatched, completed, cancelled |
| order_date | DateField | Auto |
| notes | TextField | |

---

## SalesOrderItem

Line items for a Sales Order.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| sales_order | ForeignKey(SalesOrder) | |
| product | ForeignKey(Product) | |
| quantity | DecimalField | |
| unit_price | DecimalField | |

**Computed property:** `total_price` — quantity × unit_price

---

## Batch *(Phase 4 addition)*

Links a SalesOrder to a set of Farms for EUDR traceability.

**Manager:** `objects = TenantManager()`. Auto-generates a unique batch number. The core of the compliance chain.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant isolation |
| sales_order | ForeignKey(SalesOrder) | nullable |
| farms | ManyToManyField(Farm) | Farms that supplied this batch |
| batch_number | CharField(50) | Auto-generated: e.g. `SOY-AK-2026-0001` |
| commodity | CharField(100) | Derived from SO line item on creation |
| quantity_kg | DecimalField | Net mass in kg — required for EUDR Article 9 DDS |
| is_locked | BooleanField | Default: False. Locked batches cannot be deleted (5-year retention) |
| public_token | UUIDField | UUID for public QR trace URL |
| notes | TextField | |
| created_at | DateTimeField | Auto |
| updated_at | DateTimeField | Auto |

**Batch number format:** `{COMMODITY[:3]}-{COMPANY_INITIALS}-{YEAR}-{SEQUENCE:04d}`

**Access pattern:** Created transparently when farms are linked to a Sales Order. Not directly accessible from the sidebar — surfaced on the SO detail page only.

---

## AuditLog *(Phase 2 addition)*

Records every create, update, and delete action across the platform.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant scoped |
| user | ForeignKey(CustomUser) | Who performed the action |
| action | CharField | Choices: create, update, delete |
| model_name | CharField | Which model was affected |
| object_id | IntegerField | PK of the affected record |
| object_repr | CharField | String representation at time of action |
| changes | JSONField | Before/after field values for updates |
| ip_address | GenericIPAddressField | Request IP |
| timestamp | DateTimeField | Auto |

---

## Relationship Summary

```
Company
  ├── CustomUser (many)
  ├── Farmer (many)                        ← Phase 4.6
  ├── Supplier (many)
  │     └── Farm (many)                    ← Phase 2
  │           └── farmer FK → Farmer       ← Phase 4.6
  │           └── FarmCertification (many) ← Phase 4.5
  │           └── ComplianceDocument (many)
  ├── Product (many)
  │     └── Inventory (one per warehouse)
  ├── PurchaseOrder (many)
  │     └── PurchaseOrderItem (many)
  └── SalesOrder (many)
        ├── SalesOrderItem (many)
        └── Batch (many)                   ← Phase 4
              ├── farms M2M → Farm
              ├── PhytosanitaryCertificate  ← Phase 4.5
              └── BatchQualityTest          ← Phase 4.5
```

**EUDR traceability chain:**
`Farmer → Farm → Supplier → PurchaseOrder → Inventory → SalesOrderItem → SalesOrder → Batch → EUDR Certificate PDF`
