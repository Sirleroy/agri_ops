# AgriOps — EUDR Compliance Module

**Version:** 3.0
**Date:** April 2026
**Status:** Phase 4.7 Complete — full import pipeline, upload history, compliance PDF with HS code

---

## Overview

The AgriOps EUDR Compliance Module supports operators in meeting the requirements of the **EU Deforestation Regulation (EUDR)** — Regulation (EU) 2023/1115 — which mandates that specific commodities (including soy, cattle, palm oil, wood, cocoa, coffee, rubber) placed on the EU market must not have contributed to deforestation or forest degradation after December 31, 2020.

This module was designed based on direct operational experience. The founding company holds a soy supply contract with an EU buyer that explicitly requires EUDR compliance, including farm-level geolocation mapping using SW Maps and NCAN Farm Mapper.

---

## Regulatory Requirements Summary

The EUDR requires operators to:

1. **Collect geolocation data** — the precise location (GPS coordinates / polygon) of all plots of land where the commodity was produced
2. **Conduct due diligence** — assess the deforestation risk of each plot
3. **Maintain documentation** — keep records of the due diligence process, including satellite imagery, land registries, and third-party certifications
4. **File a Due Diligence Statement (DDS)** — submit to the EU Information System before placing goods on the EU market
5. **Maintain traceability** — be able to trace commodities back to the specific plot of land

---

## AgriOps Compliance Data Model

### The Traceability Chain
```
Company (Operator/Exporter)
  └── Supplier (Aggregator/Cooperative)
        └── Farm (Physical plot — EUDR unit of compliance)
              └── Product (Commodity: Soy, Maize, etc.)
                    └── Inventory (Stock batch)
                          └── PurchaseOrder (Procurement record)
                                └── SalesOrder (Dispatch to EU buyer)
```

### Farm — The Core Compliance Record

Each `Farm` record stores:

**Identity:**
- Farm name and farmer name
- Country, state/region
- Commodity produced

**Geolocation (EUDR Article 3):**
- GeoJSON Polygon — farm boundary measured by field agents
- Area in hectares
- Mapping date and mapped_by (field agent)
- Source application (SW Maps / NCAN Farm Mapper)

**Risk Classification:**
- `deforestation_risk_status` — Low / Standard / High
- Based on country risk profile and third-party assessment

**Verification:**
- `is_eudr_verified` — boolean
- `verified_by` — compliance officer
- `verified_date` — when verification was performed
- `verification_expiry` — when re-verification is due

**Computed properties:**
- `is_verification_current` — False if expired
- `compliance_status` — returns: `compliant`, `pending`, `expired`, or `high_risk`

**Compliance Documents:**
- Farm maps, satellite imagery, land registry documents
- Stored as file attachments per `ComplianceDocument` model

---

## ComplianceDocument Model ✅ Phase 2 Complete

Farm compliance documentation with version history.
```python
class ComplianceDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ('farm_map', 'Farm Map'),
        ('satellite_image', 'Satellite Image'),
        ('land_registry', 'Land Registry'),
        ('certification', 'Third-Party Certification'),
        ('declaration', 'Farmer Declaration'),
        ('other', 'Other'),
    ]
    company     = models.ForeignKey(Company, on_delete=models.CASCADE)
    farm        = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='documents')
    doc_type    = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    file        = models.FileField(upload_to='compliance_docs/%Y/%m/')
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_current  = models.BooleanField(default=True)

    class Meta:
        ordering = ['-uploaded_at']
```

**Key design decision:** `is_current` flag preserves document history. When a certification is renewed, the old document is marked `is_current=False` — not deleted. The EUDR requires you to demonstrate what documentation you held at the time of a transaction.

---

## Compliance Dashboard Widget *(Phase 3)*

The main dashboard will surface a compliance summary panel showing:
```
EUDR COMPLIANCE STATUS
━━━━━━━━━━━━━━━━━━━━━
✅ Verified          24 farms
⚠️  Pending           8 farms
🔴 High Risk          2 farms
📅 Expiring (30d)     3 farms
```

Clicking any figure navigates to a filtered farm list.

---

## API Compliance Endpoints ✅ Phase 2 Complete

The REST API exposes two EUDR-specific custom actions:

- `GET /api/v1/farms/eudr-pending/` — all farms with `is_eudr_verified=False`
- `GET /api/v1/farms/high-risk/` — all farms with `deforestation_risk_status=high`

Both endpoints are tenant-scoped and JWT-authenticated.

---

## Compliance Report *(Phase 3)*

A dedicated compliance report view pulling the full traceability chain per shipment or per period.

**Report includes:**
- Company (operator) details
- Supplier details
- Farm list with geolocation coordinates
- Risk classification per farm
- Verification status and dates
- Product (commodity) details
- Purchase order volumes and dates
- Sales order destination and buyer

**Export formats:**
- PDF — for submission to EU buyer or auditor
- CSV — for internal record-keeping and SIEM ingestion

---

## Due Diligence Statement Generator *(Phase 3)*

The EUDR requires a formal DDS to be filed with the EU Information System before goods enter the EU market. AgriOps will generate a pre-filled DDS draft from supply chain data.

**DDS fields sourced from AgriOps:**

| DDS Field | AgriOps Source |
|---|---|
| Operator name & address | Company model |
| Commodity & HS code | Product model |
| Country of production | Farm.country |
| Geolocation of plots | Farm.geolocation (GeoJSON) |
| Volume | PurchaseOrder / SalesOrder |
| Due diligence assessment | Farm.deforestation_risk_status |
| Reference documents | ComplianceDocument |

---

## Field Data Collection Workflow

Based on the operational process used by the founding company:

1. **Field agent** travels to farm with a field mapping app installed (e.g. SW Maps, Avenza Maps)
2. **Perimeter mapping** — agent walks the farm boundary; the app records the GPS track as a polygon
3. **Export** — app exports GeoJSON FeatureCollection (or ZIP containing GeoJSON)
4. **Dry-run upload** — GeoJSON uploaded to AgriOps import page with "Validate only" checked. System runs full validation pipeline and reports what would be created, any errors (bad geometry, wrong coordinates, non-Nigeria bounds), and completeness warnings (missing LGA, farmer name, commodity) — without writing anything
5. **Review** — field officer or coordinator reviews the dry-run report, fixes issues if needed, re-runs
6. **Commit upload** — same file uploaded without "Validate only" to write farms to the registry
7. **History check** — upload appears in `/farms/import/history/` with all counts and per-row detail. Dry-run and commit pair is visible side by side
8. **Compliance officer review** — reviews polygon on Leaflet map, confirms area, sets `deforestation_risk_status`
9. **Documentation** — satellite imagery and farmer declaration uploaded as ComplianceDocuments
10. **Verification** — `is_eudr_verified` set to True, `verified_date` and `verification_expiry` recorded

---

## Phase Implementation Plan

| Feature | Phase | Status |
|---|---|---|
| Farm model + EUDR fields | 2 | ✅ Complete |
| ComplianceDocument model | 2 | ✅ Complete |
| Farm CRUD UI | 2 | ✅ Complete |
| EUDR API endpoints | 2 | ✅ Complete |
| Compliance dashboard widget | 3 | ✅ Complete |
| GeoJSON / ZIP import from field mapping apps | 4 | ✅ Complete |
| Compliance Report (PDF) | 4 | ✅ Complete |
| Farm map visualisation (Leaflet.js) | 4 | ✅ Complete |
| Batch model + quantity_kg + is_locked | 4.5 | ✅ Complete |
| HS code in compliance PDF | 4.7 | ✅ Complete |
| GeoJSON import validation pipeline | 4.7 | ✅ Complete |
| Dry-run upload mode | 4.7 | ✅ Complete |
| Upload history (FarmImportLog) | 4.7 | ✅ Complete |
| Expiry alerting (email) | — | Planned |
| DDS submission to EU IS | — | Planned — trigger: active EU export volume |
| PostGIS polygon migration | — | Planned — trigger: farm count > 10,000 |

---

## Related Documents

- ADR 004 — Geolocation: JSONField over PostGIS
- ADR 005 — EUDR Farm Model Separation
- Diagram: `/docs/diagrams/eudr-traceability-chain.mermaid`
- Data model: `/docs/design/data-model.md`
