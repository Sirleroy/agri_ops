# AgriOps — API Contract

**Version:** Snapshot 1.2
**Date:** April 2026
**Status:** Current implementation snapshot

---

## Overview

The AgriOps REST API exposes a JWT-authenticated `/api/v1/` surface for core tenant data.
This document describes the endpoints and behaviours currently implemented in the codebase.
It is intentionally conservative: this file is a code-aligned snapshot, not a roadmap.

**Base URL:** `/api/v1/`
**Authentication:** JWT Bearer token
**Format:** JSON
**Schema:** No public OpenAPI schema is currently published

---

## Authentication

### POST /api/v1/token/
Obtain JWT access and refresh tokens.

**Request**
```json
{
  "username": "example_user",
  "password": "securepassword"
}
```

**Response 200**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

### POST /api/v1/token/refresh/
Refresh an expired access token.

**Request**
```json
{
  "refresh": "eyJ..."
}
```

---

## Auth Model

All API endpoints require authentication unless stated otherwise.

Method-level role enforcement mirrors the server-rendered application:

| HTTP method | Minimum role required |
|---|---|
| GET, HEAD, OPTIONS | Any authenticated tenant member |
| POST, PUT, PATCH | Staff or above |
| DELETE | Manager or above |

This is enforced via `get_permissions()` on `TenantScopedViewSet`. Unauthenticated requests receive `401`. Authenticated requests below the required role receive `403`.

---

## Tenant Scoping

- Top-level list and detail querysets are filtered by `request.user.company`.
- `company` is assigned server-side on create and update paths and is never accepted from the request body.
- Foreign-key fields (`supplier`, `product`) are validated against the authenticated tenant's company boundary in each serializer via `validate_<field>()`. A cross-tenant FK reference returns `400`.

---

## Endpoints

### Suppliers

`GET /api/v1/suppliers/`
List suppliers for the authenticated tenant.

`POST /api/v1/suppliers/`
Create a supplier. Staff or above required.

`GET /api/v1/suppliers/{id}/`
Retrieve a supplier in the authenticated tenant.

`PATCH /api/v1/suppliers/{id}/`
Update a supplier. Staff or above required.

`DELETE /api/v1/suppliers/{id}/`
Delete a supplier. Manager or above required.

**Example response**
```json
{
  "id": 1,
  "name": "Plateau Shea Cooperative",
  "category": "cooperative",
  "contact_person": "Amina Yusuf",
  "phone": "+234...",
  "email": "info@example-supplier.com",
  "country": "Nigeria",
  "city": "Jos",
  "is_active": true,
  "reliability_score": "82.50",
  "created_at": "2026-03-01T10:00:00Z"
}
```

### Farms

`GET /api/v1/farms/`
List farms for the authenticated tenant.

`POST /api/v1/farms/`
Create a farm. Staff or above required.

`GET /api/v1/farms/{id}/`
Retrieve a farm in the authenticated tenant.

`PATCH /api/v1/farms/{id}/`
Update a farm. Staff or above required.

`DELETE /api/v1/farms/{id}/`
Delete a farm. Manager or above required.

`GET /api/v1/farms/eudr-pending/`
List farms where `is_eudr_verified=false`.

`GET /api/v1/farms/high-risk/`
List farms where `deforestation_risk_status=high`.

`POST /api/v1/farms/import/`
Run the farm GeoJSON bulk import pipeline for a tenant supplier.

**Example response**
```json
{
  "id": 1,
  "supplier": 1,
  "name": "Plot 01 — Barkin Ladi",
  "farmer_name": "Musa Ibrahim",
  "country": "Nigeria",
  "state_region": "Plateau",
  "commodity": "shea",
  "area_hectares": "12.40",
  "deforestation_risk_status": "low",
  "is_eudr_verified": true,
  "verified_date": "2026-02-20",
  "verification_expiry": "2027-02-20",
  "compliance_status": "verified",
  "created_at": "2026-03-01T10:00:00Z"
}
```

### Products

`GET /api/v1/products/`
`POST /api/v1/products/` — staff or above required
`GET /api/v1/products/{id}/`
`PATCH /api/v1/products/{id}/` — staff or above required
`DELETE /api/v1/products/{id}/` — manager or above required

### Inventory

`GET /api/v1/inventory/`
`POST /api/v1/inventory/` — staff or above required
`GET /api/v1/inventory/{id}/`
`PATCH /api/v1/inventory/{id}/` — staff or above required
`DELETE /api/v1/inventory/{id}/` — manager or above required

`GET /api/v1/inventory/low-stock/`
List inventory items at or below their low-stock threshold.

### Purchase Orders

`GET /api/v1/purchase-orders/`
`POST /api/v1/purchase-orders/` — staff or above required
`GET /api/v1/purchase-orders/{id}/`
`PATCH /api/v1/purchase-orders/{id}/` — staff or above required
`DELETE /api/v1/purchase-orders/{id}/` — manager or above required

Order numbers are unique per tenant (`unique_together: company + order_number`), not globally unique.

### Sales Orders

`GET /api/v1/sales-orders/`
`POST /api/v1/sales-orders/` — staff or above required
`GET /api/v1/sales-orders/{id}/`
`PATCH /api/v1/sales-orders/{id}/` — staff or above required
`DELETE /api/v1/sales-orders/{id}/` — manager or above required

Order numbers are unique per tenant (`unique_together: company + order_number`), not globally unique.

---

## Error Responses

Typical error shape:

```json
{
  "detail": "Human-readable error message"
}
```

| Code | Meaning |
|---|---|
| 400 | Bad request / validation error (includes cross-tenant FK rejection) |
| 401 | Unauthenticated |
| 403 | Authenticated but below required role |
| 404 | Not found (also returned for cross-tenant detail access) |
| 429 | Rate limited |
| 500 | Server error |

Cross-tenant access to top-level detail routes returns `404`, not `403`.

---

## Rate Limiting

Default DRF throttle rates:

- Anonymous: `20/hour`
- Authenticated user: `200/hour`

---

## Notes

- This file is a code-aligned snapshot. If the permission model, serializer validation, or endpoint surface changes, this file must be updated in the same change set.
- The API is JWT-authenticated. Session authentication used by the server-rendered application does not apply here.
