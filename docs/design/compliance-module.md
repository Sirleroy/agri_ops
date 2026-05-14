# AgriOps — EUDR Compliance Module

**Version:** 4.0
**Date:** May 2026
**Status:** Deforestation engine live · evidence-gated Compliance Readiness sign-off

---

## Overview

The AgriOps EUDR Compliance Module supports operators in meeting the requirements of the **EU Deforestation Regulation (EUDR)** — Regulation (EU) 2023/1115 as amended by Regulation (EU) 2025/2650 — which mandates that specific commodities (including soy, cattle, palm oil, wood, cocoa, coffee, rubber) placed on the EU market must not have contributed to deforestation or forest degradation after December 31, 2020.

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
- GeoJSON Polygon (or MultiPolygon if auto-repaired) — farm boundary measured by field agents
- Area in hectares
- Mapping date and mapped_by (field agent)
- Source application (any field mapping app — SW Maps, Avenza Maps, QGIS, etc.)

**Risk Classification:**
- `deforestation_risk_status` — Low / Standard / High
- Set by the **deforestation engine** (`run_check`), not by an operator — derived
  from satellite tree-cover-loss data, with a `DeforestationCheck` evidence record
  behind every value. See "Deforestation Engine" below.

**Disqualification:**
- `land_cleared_after_cutoff` — manager disqualification override (nullable)
- `null` defers to the engine (a flagged check disqualifies the farm); `True`/`False`
  lets a manager override the engine result. An override requires a documented
  reason (`land_cleared_after_cutoff_reason`), is manager-only, and is audit-logged.

**Compliance Readiness verification:**
- `is_eudr_verified` / `verified_by` / `verified_date` / `verification_expiry`
- Set **only** by the evidence-gated Compliance Readiness sign-off — a manager-only,
  server-side-re-checked, audited action on the farm detail page. It is not a free
  checkbox, is not on the edit form, and is read-only over the API. See ADR 013.

**Computed properties:**
- `is_verification_current` — False if the sign-off has lapsed
- `is_disqualified` — manager override wins; otherwise a flagged latest check disqualifies
- `readiness_blockers` / `readiness_state` — the evidence gate, surfaced as a
  lifecycle: `not_ready` → `awaiting_signoff` → `ready` (plus `disqualified` / `expired`)
- `compliance_status` — `compliant`, `pending`, `expired`, `high_risk`, or
  `disqualified`. **Evidence-backed**: a sign-off only counts as `compliant` when a
  clear, current, non-stale `DeforestationCheck` sits behind it

**Compliance Documents:**
- Farm maps, land registry, farmer declarations — `ComplianceDocument` model
- See the ComplianceDocument note below: the model and a read-only display exist;
  the tenant-facing upload path is not yet built

---

## ComplianceDocument Model ⚠️ Partially Built

> **Status — partially built.** The model, Django-admin registration, and a
> read-only display on the farm detail page exist. The tenant-facing upload
> path (view, URL, form, "Add Document" button) is **not** built — today a
> document can only be added via Django admin. The feature is paused pending a
> deliberate scoping decision: anchor it on the signed FVF plus an on-demand
> "other paper document", rather than the broad six-type taxonomy below, to
> avoid redundancy with the GPS polygon, the deforestation engine, and
> `FarmCertification`.

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

## Deforestation Engine ✅ Live

Deforestation risk is **not** an operator judgement — it is produced by an
in-platform engine that intersects each farm polygon against satellite
tree-cover-loss data and retains the evidence.

**How it runs:** `apps/suppliers/deforestation_engine.run_check(farm, user=None)`
loads the farm polygon, finds the Hansen GFC `lossyear` raster tile(s) it
intersects, masks loss pixels to the polygon boundary, and writes a
`DeforestationCheck` evidence record. It is callable from the farm detail page
("Run Check"), the per-supplier preview view, and the
`run_deforestation_checks` management command.

**`DeforestationCheck`** — one row per run: dataset name + version, pixel
counts, post-cut-off loss area and loss years, `risk_status`
(`clear` / `flagged` / `inconclusive` / `error`), `engine_status`, an
`evidence_summary`, who ran it, and `geometry_hash_at_assessment` (the farm's
geometry hash at check time, used for staleness detection). It is the auditable
evidence behind `Farm.deforestation_risk_status`. See `/docs/design/data-model.md`.

**What the engine drives:**
- `Farm.deforestation_risk_status` — `clear → low`, `flagged → high`,
  `inconclusive → standard` (`error` leaves it untouched).
- **Disqualification** — a `flagged` latest check disqualifies the farm unless a
  manager has set the `land_cleared_after_cutoff` override.
- **Sign-off auto-invalidation** — a non-clear re-check withdraws an existing
  Compliance Readiness sign-off (and that withdrawal is audit-logged). Editing
  the polygon also withdraws the sign-off, via `Farm.save()`.

---

## Compliance Readiness Sign-off ✅ Live

EUDR verification is an **evidence-gated, manager-only, audited sign-off** — not
a checkbox. See **ADR 013** for the decision rationale.

- **The gate** — `readiness_blockers` must be empty (GPS polygon on file; a
  latest `DeforestationCheck` that is `clear`, not `inconclusive`/`error`, and
  not stale) and the farm must not be disqualified.
- **The action** — `ConfirmComplianceReadinessView` (manager-or-above, POST-only)
  re-checks the gate server-side, then sets `is_eudr_verified`, `verified_by`,
  `verified_date`, and a 12-month `verification_expiry`. `WithdrawComplianceReadinessView`
  reverses it. Both are audit-logged.
- **Lifecycle** — `readiness_state`: `not_ready` (evidence incomplete) →
  `awaiting_signoff` (evidence complete, manager hasn't signed) → `ready`
  (signed off) — plus `disqualified` and `expired`.
- **Auto-invalidation** — a sign-off is withdrawn automatically when the polygon
  changes or a re-check is no longer clear, so `is_eudr_verified=True` always
  reflects current evidence.

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

## API Compliance Endpoints ✅ Live

The REST API exposes two EUDR-specific custom actions:

- `GET /api/v1/farms/eudr-pending/` — farms that are **not compliance-ready**
  (`compliance_status != "compliant"`); this includes expired and
  evidence-invalid sign-offs, not just farms with the verification flag off
- `GET /api/v1/farms/high-risk/` — all farms with `deforestation_risk_status=high`

Both endpoints are tenant-scoped and JWT-authenticated. On the `FarmSerializer`,
`is_eudr_verified`, `verified_date`, `verification_expiry`, and
`deforestation_risk_status` are **read-only** — a sign-off is the manager-only
action above, not a raw API write. See `/docs/design/api-contract.md`.

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
4. **Dry-run upload** — GeoJSON, ZIP, or WKT CSV uploaded to AgriOps import page with "Validate only" checked. Before validation, the importer normalises all geometry: strips elevation (Z), removes duplicate GPS vertices, auto-closes rings, simplifies if > 200 vertices, and repairs self-intersecting boundaries via `buffer(0)`. Reports what would be created, any hard errors (unrepairable geometry, wrong coordinates, outside Nigeria bounds), and completeness warnings (missing LGA, farmer name, commodity) — without writing anything
5. **Review** — field officer or coordinator reviews the dry-run report, fixes issues if needed, re-runs
6. **Commit upload** — same file uploaded without "Validate only" to write farms to the registry
7. **History check** — upload appears in `/farms/import/history/` with all counts and per-row detail. Dry-run and commit pair is visible side by side
8. **Deforestation check** — the deforestation engine runs against each polygon (per-supplier preview, the detail-page "Run Check" button, or the `run_deforestation_checks` command), writing a `DeforestationCheck` and setting `deforestation_risk_status` from the evidence
9. **Review** — compliance officer reviews the polygon on the Leaflet map, confirms area, and — if the engine flagged a false positive, or the clearing predates the cut-off — a manager records a `land_cleared_after_cutoff` override with a documented reason
10. **Compliance Readiness sign-off** — once the evidence gate is clear, a manager signs off on the farm detail page; the action sets `is_eudr_verified`, `verified_by`, `verified_date`, and a 12-month `verification_expiry`

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
| Deforestation engine (Hansen GFC) + DeforestationCheck | — | ✅ Complete |
| Evidence-gated Compliance Readiness sign-off | — | ✅ Complete |
| ComplianceDocument tenant upload path | — | ⚠️ Partially built — model + read-only display only |
| Expiry alerting (email) | — | Planned |
| DDS submission to EU IS | — | Planned — trigger: active EU export volume |
| PostGIS polygon migration | — | Planned — trigger: farm count > 10,000 |

---

## Related Documents

- ADR 004 — Geolocation: JSONField over PostGIS
- ADR 005 — EUDR Farm Model Separation
- ADR 013 — Evidence-gated Compliance Readiness Sign-off
- Diagram: `/docs/diagrams/eudr-traceability-chain.mermaid`
- Data model: `/docs/design/data-model.md`
