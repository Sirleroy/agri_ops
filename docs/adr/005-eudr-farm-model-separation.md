# ADR 005 — EUDR Farm Model Separation from Supplier

**Date:** March 2026
**Status:** Accepted
**Author:** Ezinna (Founder)

---

## Context

AgriOps initially modelled agricultural supply chains with `Supplier` as the entity you procure from. During EUDR compliance planning, a critical distinction emerged: the **Supplier** is the trading entity (cooperative, aggregator, processor) you have a commercial relationship with, while the **Farm** is the physical plot of land where the commodity was actually produced.

These are not the same thing. A single Supplier may aggregate produce from dozens or hundreds of individual farms. EUDR compliance requires traceability to the farm of origin — not just the supplier entity. This distinction is explicitly required by the regulation.

This was confirmed by internal operational experience: the company's own EUDR compliance process involves physically mapping individual farms using SW Maps, collecting GPS perimeter data per farm, and maintaining farm-level compliance documentation — separate from the supplier commercial record.

---

## Decision Drivers

- EUDR Article 3 requires operators to verify that commodities originate from land that has not been subject to deforestation after December 31, 2020
- Verification must be at the plot level — geolocation coordinates of the specific land parcel
- A single Supplier record cannot hold multiple farm polygons cleanly as fields — it requires a separate model
- Farm-level compliance status (risk classification, documentation, verification date) is distinct from supplier commercial data
- Due Diligence Statements filed with EU customs reference farm-level geolocation, not supplier addresses
- Internal field process already treats farms as distinct entities from suppliers

---

## Options Considered

### Option 1 — Add geolocation fields directly to Supplier model
Store farm geolocation, risk status, and compliance documents directly on the existing `Supplier` model.

**Pros:** Simple — no new model required.

**Cons:**
- A supplier may have many farms — one-to-one assumption breaks immediately for any cooperative with multiple member farms
- Supplier model becomes bloated with compliance fields that are irrelevant to non-EUDR use cases
- Cannot store multiple farm polygons per supplier
- Does not reflect operational reality — field teams map farms, not suppliers
- Fundamentally non-compliant with EUDR requirements for multi-farm suppliers

### Option 2 — Separate Farm model with ForeignKey to Supplier ✅ Chosen
A dedicated `Farm` model sits between `Company` and commodity flows, linked to `Supplier` via ForeignKey.

**Pros:**
- Accurately models the real-world relationship: one supplier, many farms
- Farm-level compliance data is cleanly separated from supplier commercial data
- Each farm has its own geolocation polygon, risk status, compliance documents, and audit trail
- Scales correctly — a cooperative with 200 member farms has 200 Farm records linked to one Supplier
- EUDR Due Diligence Statement can reference specific Farm records by ID
- Consistent with how field teams already work

**Cons:**
- Additional model and migration required
- UI requires a Farm management interface alongside Supplier management
- Slightly more complex traceability query: Company → Supplier → Farm → Product → Inventory → Order

---

## Decision

**Implement a dedicated `Farm` model** with a ForeignKey to both `Company` (tenant isolation) and `Supplier` (commercial relationship). Farm is the unit of EUDR compliance verification.

---

## Data Model

```python
class Farm(models.Model):
    RISK_CHOICES = [
        ('low', 'Low Risk'),
        ('standard', 'Standard Risk'),
        ('high', 'High Risk'),
    ]

    company         = models.ForeignKey(Company, on_delete=models.CASCADE)
    supplier        = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='farms')
    name            = models.CharField(max_length=255)
    farmer_name     = models.CharField(max_length=255, blank=True)
    geolocation     = models.JSONField(null=True, blank=True)  # GeoJSON Polygon — see ADR 004
    area_hectares   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    country         = models.CharField(max_length=100)
    state_region    = models.CharField(max_length=100, blank=True)
    commodity       = models.CharField(max_length=100)  # e.g. Soy, Maize, Cocoa

    # EUDR Compliance
    deforestation_risk_status = models.CharField(max_length=20, choices=RISK_CHOICES, default='standard')
    mapping_date    = models.DateField(null=True, blank=True)
    mapped_by       = models.ForeignKey(
                        CustomUser, null=True, blank=True,
                        on_delete=models.SET_NULL,
                        related_name='farms_mapped'
                      )
    is_eudr_verified = models.BooleanField(default=False)
    verified_by     = models.ForeignKey(
                        CustomUser, null=True, blank=True,
                        on_delete=models.SET_NULL,
                        related_name='farms_verified'
                      )
    verified_date   = models.DateField(null=True, blank=True)
    verification_expiry = models.DateField(null=True, blank=True)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} — {self.supplier.name}"
```

---

## Traceability Chain

The full EUDR traceability chain through the AgriOps data model:

```
Company (Tenant)
  └── Supplier (Trading entity)
        └── Farm (Physical plot — EUDR unit)
              └── Product (Commodity type)
                    └── Inventory (Stock held)
                          └── PurchaseOrder (Procurement record)
                                └── SalesOrder (Dispatch to buyer)
```

This chain supports generation of the EUDR Due Diligence Statement by joining:
- Farm geolocation polygon
- Farm risk classification
- Farm compliance documents
- Product (commodity type)
- Purchase Order (volume, date)
- Sales Order (destination, buyer)

---

## Consequences

- `Farm` model added to schema in Phase 2 alongside auth and RBAC work
- Supplier detail view updated to list associated farms
- Farm CRUD module added to the Admin section of the navigation
- EUDR compliance report queries the Farm model as the primary compliance record
- Due Diligence Statement export (Phase 3) sources all geolocation data from Farm records
- Field teams log farm mapping against Farm records — not Supplier records
- All Farm records inherit tenant isolation from Company ForeignKey per ADR 003

---

## Real-World Validation

This decision is validated by the founder's direct operational experience. The company's soy contract with an EU buyer explicitly requires EUDR compliance including farm-level geolocation. The internal compliance process — using SW Maps and NCAN Farm Mapper to physically measure farm perimeters — maps directly to the `Farm` model designed here. AgriOps is digitising a process the founder has personally managed.

---

## Related Decisions

- ADR 003 — Tenant Isolation Strategy
- ADR 004 — Geolocation: JSONField over PostGIS
- Design doc: `/docs/design/compliance-module.md`
- Diagram: `/docs/diagrams/eudr-traceability-chain.mermaid`
