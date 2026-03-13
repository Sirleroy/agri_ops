# AgriOps — API Contract

**Version:** Draft 1.0
**Date:** March 2026
**Status:** Design phase — implementation in Phase 2

---

## Overview

The AgriOps REST API provides programmatic access to all platform data. It is versioned, JWT-authenticated, and scoped to the authenticated user's organisation (tenant isolation enforced at every endpoint).

**Base URL:** `/api/v1/`
**Authentication:** JWT Bearer token
**Format:** JSON
**Schema:** OpenAPI 3.0 (auto-generated via drf-spectacular)

---

## Authentication

### POST /api/v1/auth/token/
Obtain JWT access and refresh tokens.

**Request:**
```json
{
  "username": "ezinna",
  "password": "securepassword"
}
```

**Response 200:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

**Response 401:**
```json
{
  "detail": "No active account found with the given credentials"
}
```

---

### POST /api/v1/auth/token/refresh/
Refresh an expired access token.

**Request:**
```json
{
  "refresh": "eyJ..."
}
```

**Response 200:**
```json
{
  "access": "eyJ..."
}
```

---

## Suppliers

### GET /api/v1/suppliers/
List all suppliers for the authenticated user's organisation.

**Auth:** Required
**Permission:** Viewer and above

**Response 200:**
```json
{
  "count": 12,
  "next": null,
  "previous": null,
  "results": [
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
      "farm_count": 12,
      "created_at": "2026-03-01T10:00:00Z"
    }
  ]
}
```

---

### POST /api/v1/suppliers/
Create a new supplier.

**Auth:** Required
**Permission:** Staff and above

**Request:**
```json
{
  "name": "Ake Collective",
  "category": "cooperative",
  "contact_person": "John Doe",
  "phone": "+234...",
  "email": "info@akecollective.com",
  "country": "Nigeria",
  "city": "Jos"
}
```

**Note:** `company` is automatically assigned from the authenticated user's organisation. It is never accepted from the request body.

---

### GET /api/v1/suppliers/{id}/
Retrieve a single supplier.

**Auth:** Required
**Permission:** Viewer and above
**Tenant check:** Returns 404 if supplier belongs to a different organisation.

---

### PATCH /api/v1/suppliers/{id}/
Partial update of a supplier.

**Auth:** Required
**Permission:** Staff and above

---

### DELETE /api/v1/suppliers/{id}/
Delete a supplier.

**Auth:** Required
**Permission:** Manager and above

---

## Farms

### GET /api/v1/farms/
List all farms for the authenticated user's organisation.

**Auth:** Required
**Permission:** Viewer and above

**Response 200:**
```json
{
  "count": 34,
  "results": [
    {
      "id": 1,
      "supplier": {"id": 1, "name": "Ake Collective"},
      "name": "Ake Farm 01",
      "farmer_name": "Musa Ibrahim",
      "geolocation": {
        "type": "Polygon",
        "coordinates": [[[8.85, 9.89], [8.86, 9.89], [8.86, 9.90], [8.85, 9.90], [8.85, 9.89]]],
        "properties": {
          "area_hectares": 12.4,
          "source_app": "SW Maps",
          "mapped_date": "2026-02-15"
        }
      },
      "area_hectares": "12.40",
      "commodity": "Soy",
      "deforestation_risk_status": "low",
      "is_eudr_verified": true,
      "verified_date": "2026-02-20",
      "verification_expiry": "2027-02-20"
    }
  ]
}
```

---

### POST /api/v1/farms/
Create a new farm record.

**Auth:** Required
**Permission:** Staff and above

---

### GET /api/v1/farms/{id}/compliance/
Retrieve full compliance detail for a single farm including documents.

**Auth:** Required
**Permission:** Staff and above

---

## Products

### GET /api/v1/products/
**Auth:** Required | **Permission:** Viewer and above

### POST /api/v1/products/
**Auth:** Required | **Permission:** Staff and above

### GET /api/v1/products/{id}/
**Auth:** Required | **Permission:** Viewer and above

### PATCH /api/v1/products/{id}/
**Auth:** Required | **Permission:** Staff and above

### DELETE /api/v1/products/{id}/
**Auth:** Required | **Permission:** Manager and above

---

## Inventory

### GET /api/v1/inventory/
**Auth:** Required | **Permission:** Viewer and above

**Query params:**
- `?low_stock=true` — return only items below threshold

### POST /api/v1/inventory/
**Auth:** Required | **Permission:** Staff and above

### PATCH /api/v1/inventory/{id}/
**Auth:** Required | **Permission:** Staff and above

---

## Purchase Orders

### GET /api/v1/purchase-orders/
**Auth:** Required | **Permission:** Viewer and above

**Query params:**
- `?status=received` — filter by status
- `?supplier=1` — filter by supplier

### POST /api/v1/purchase-orders/
**Auth:** Required | **Permission:** Staff and above

### GET /api/v1/purchase-orders/{id}/
Returns order with nested line items.

### PATCH /api/v1/purchase-orders/{id}/
**Auth:** Required | **Permission:** Staff and above

### DELETE /api/v1/purchase-orders/{id}/
**Auth:** Required | **Permission:** Manager and above

---

## Sales Orders

### GET /api/v1/sales-orders/
**Auth:** Required | **Permission:** Viewer and above

### POST /api/v1/sales-orders/
**Auth:** Required | **Permission:** Staff and above

### GET /api/v1/sales-orders/{id}/
Returns order with nested line items.

### PATCH /api/v1/sales-orders/{id}/
**Auth:** Required | **Permission:** Staff and above

### DELETE /api/v1/sales-orders/{id}/
**Auth:** Required | **Permission:** Manager and above

---

## Compliance Reports

### GET /api/v1/reports/compliance/
Generate compliance report for the organisation.

**Auth:** Required
**Permission:** Manager and above

**Query params:**
- `?format=pdf` — return PDF
- `?format=csv` — return CSV
- `?from=2026-01-01&to=2026-03-31` — date range

---

## Error Responses

All errors follow a consistent format:

```json
{
  "detail": "Human-readable error message"
}
```

| Code | Meaning |
|---|---|
| 400 | Bad request — validation error |
| 401 | Unauthenticated — no or invalid token |
| 403 | Forbidden — insufficient permissions |
| 404 | Not found — record does not exist or belongs to another tenant |
| 429 | Rate limited |
| 500 | Server error |

**Note:** Cross-tenant access attempts return 404, not 403. Returning 403 would confirm the record exists to an attacker. 404 reveals nothing.

---

## Versioning

The API is versioned via the URL path (`/api/v1/`). Breaking changes increment the version. Non-breaking additions (new fields, new endpoints) do not require a version bump. Deprecated versions are supported for a minimum of 6 months after a new version is released.

---

## Rate Limiting

Authentication endpoints: 5 requests/minute per IP
All other endpoints: 100 requests/minute per authenticated user

Exceeded limits return HTTP 429 with a `Retry-After` header.

---

## Implementation Notes

- All endpoints enforce tenant isolation — `company` is never accepted from request body
- `company` is always assigned from `request.user.company` at the serializer/view level
- Full OpenAPI schema auto-generated via `drf-spectacular` at `/api/schema/`
- Interactive Swagger UI at `/api/schema/swagger-ui/`
- Postman collection published alongside repo at `/docs/agriops.postman_collection.json`
