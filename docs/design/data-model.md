# AgriOps — Data Model Documentation

**Version:** 1.0
**Date:** March 2026
**Status:** Phase 1 schema + Phase 2 additions documented

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

## Supplier

The commercial trading entity. May aggregate produce from multiple farms.

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

## Farm *(Phase 2 addition)*

The physical plot of land. The EUDR compliance unit. Linked to Supplier (the aggregator/trader) and Company (tenant).

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant isolation |
| supplier | ForeignKey(Supplier) | Commercial relationship |
| name | CharField(255) | Farm identifier |
| farmer_name | CharField(255) | Individual farmer name |
| geolocation | JSONField | GeoJSON Polygon — see ADR 004 |
| area_hectares | DecimalField | |
| country | CharField(100) | |
| state_region | CharField(100) | |
| commodity | CharField(100) | e.g. Soy, Maize, Cocoa |
| deforestation_risk_status | CharField | Choices: low, standard, high |
| mapping_date | DateField | When GPS mapping was performed |
| mapped_by | ForeignKey(CustomUser) | Field agent who performed mapping |
| is_eudr_verified | BooleanField | Default: False |
| verified_by | ForeignKey(CustomUser) | Compliance officer |
| verified_date | DateField | |
| verification_expiry | DateField | When verification lapses |
| created_at | DateTimeField | Auto |
| updated_at | DateTimeField | Auto |

See ADR 005 for farm model separation rationale.

---

## Product

The commodity catalogue. Products are linked to a supplier and scoped to a company.

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
| is_active | BooleanField | |
| created_at | DateTimeField | Auto |
| updated_at | DateTimeField | Auto |

---

## Inventory

Stock levels per product. Includes low-stock threshold alerting.

| Field | Type | Notes |
|---|---|---|
| id | AutoField | Primary key |
| company | ForeignKey(Company) | Tenant isolation |
| product | ForeignKey(Product) | |
| quantity | DecimalField | Current stock level |
| warehouse_location | CharField(255) | |
| low_stock_threshold | DecimalField | Alert trigger level |
| last_updated | DateTimeField | Auto |

**Computed property:** `is_low_stock` — returns True if quantity ≤ low_stock_threshold

---

## PurchaseOrder

Procurement record. Created when buying from a supplier.

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
  ├── Supplier (many)
  │     └── Farm (many)          ← Phase 2
  ├── Product (many)
  │     └── Inventory (one)
  ├── PurchaseOrder (many)
  │     └── PurchaseOrderItem (many)
  └── SalesOrder (many)
        └── SalesOrderItem (many)
```
