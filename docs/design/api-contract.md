# AgriOps — API Contract

**Version:** Snapshot 1.1  
**Date:** April 2026  
**Status:** Current implementation snapshot

---

## Overview

The AgriOps REST API exposes a JWT-authenticated `/api/v1/` surface for core tenant data.
This document describes the endpoints and behaviours currently implemented in the codebase.
It is intentionally conservative: where hardening work is still in progress, this document does not claim the stronger target state.

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
  "username": "ezinna",
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

- All API endpoints require authentication unless stated otherwise.
- Current write permissions are based on authenticated tenant membership for most viewsets.
- Delete operations are restricted to manager-or-above in the API layer.
- Stricter method-level role enforcement for create/update is a hardening task and should not be assumed from this snapshot.

---

## Tenant Scoping

- Top-level list and detail querysets are filtered by `request.user.company`.
- `company` is assigned server-side on create and update paths and is never accepted from the request body.
- Foreign-key inputs such as `supplier` and `product` must still be validated against the tenant boundary; this contract does not assume that queryset scoping alone is sufficient.

---

## Endpoints

### Suppliers

`GET /api/v1/suppliers/`  
List suppliers for the authenticated tenant.

`POST /api/v1/suppliers/`  
Create a supplier for the authenticated tenant.

`GET /api/v1/suppliers/{id}/`  
Retrieve a supplier in the authenticated tenant.

`PATCH /api/v1/suppliers/{id}/`  
Update a supplier in the authenticated tenant.

`DELETE /api/v1/suppliers/{id}/`  
Delete a supplier. Manager-or-above required.

**Example response**
```json
{
  "id": 1,
  "name": "Ake Collective",
  "category": "cooperative",
  "contact_person": "John Doe",
  "phone": "+234...",
  "email": "info@akecollective.com",
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
Create a farm for the authenticated tenant.

`GET /api/v1/farms/{id}/`  
Retrieve a farm in the authenticated tenant.

`PATCH /api/v1/farms/{id}/`  
Update a farm in the authenticated tenant.

`DELETE /api/v1/farms/{id}/`  
Delete a farm. Manager-or-above required.

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
  "name": "Ake Farm 01",
  "farmer_name": "Musa Ibrahim",
  "country": "Nigeria",
  "state_region": "Plateau",
  "commodity": "soy",
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
`POST /api/v1/products/`  
`GET /api/v1/products/{id}/`  
`PATCH /api/v1/products/{id}/`  
`DELETE /api/v1/products/{id}/` — manager-or-above required

### Inventory

`GET /api/v1/inventory/`  
`POST /api/v1/inventory/`  
`GET /api/v1/inventory/{id}/`  
`PATCH /api/v1/inventory/{id}/`  
`DELETE /api/v1/inventory/{id}/` — manager-or-above required

`GET /api/v1/inventory/low-stock/`  
List inventory items at or below threshold.

### Purchase Orders

`GET /api/v1/purchase-orders/`  
`POST /api/v1/purchase-orders/`  
`GET /api/v1/purchase-orders/{id}/`  
`PATCH /api/v1/purchase-orders/{id}/`  
`DELETE /api/v1/purchase-orders/{id}/` — manager-or-above required

### Sales Orders

`GET /api/v1/sales-orders/`  
`POST /api/v1/sales-orders/`  
`GET /api/v1/sales-orders/{id}/`  
`PATCH /api/v1/sales-orders/{id}/`  
`DELETE /api/v1/sales-orders/{id}/` — manager-or-above required

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
| 400 | Bad request / validation error |
| 401 | Unauthenticated |
| 403 | Forbidden |
| 404 | Not found |
| 429 | Rate limited |
| 500 | Server error |

Cross-tenant access to top-level detail routes should return `404`, not `403`.

---

## Rate Limiting

Default DRF throttle rates in the current settings:

- Anonymous: `20/hour`
- Authenticated user: `200/hour`

---

## Notes

- This file is a code-aligned snapshot, not a roadmap.
- If the API permission model or serializer validation changes, this file should be updated in the same change set.
