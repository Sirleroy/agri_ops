---
layout: default
title: EUDR Compliance Gaps — v1
---
# EUDR Compliance Gaps — v1

Analysis against EU Regulation 2023/1115 (EUDR), Article 9. Identified March 2026.

---

## Gap Summary

| Gap | Priority | Model Change | UI Change |
|---|---|---|---|
| Deforestation cut-off date reference | High | Farm: `deforestation_reference_date`, `land_cleared_after_cutoff` | Farm form + certificate PDF |
| HS code on products | Medium | Product: `hs_code` | Product form + certificate PDF |
| Quantity in kg on batch | Medium | Batch: `quantity_kg` | Batch form + certificate PDF |
| Production date range | Medium | Farm: `harvest_year` | Farm form |
| EUDR commodity scope flag | Medium | None (lookup list in code) | Compliance warnings on batch/farm |
| Supplier address + email on certificate | Low-Medium | Verify/add to Supplier model | Certificate PDF |
| 5-year record retention / batch locking | Low | Batch: `is_locked` | Delete guards |

---

## Detailed Gaps

### 1. Deforestation Cut-Off Date Reference — HIGH

**What's missing:** `deforestation_risk_status` is a current snapshot (low/standard/high). EUDR requires evidence that land was not subject to deforestation after **31 December 2020** specifically. `verified_date` records when AgriOps verified, not what the land status was at the cut-off date.

**What's needed:**
- `deforestation_reference_date` — DateField, default `2020-12-31`
- `land_cleared_after_cutoff` — BooleanField (nullable), explicit disqualification flag

A farm verified today as "low risk" is not the same as a farm with documented evidence of its status as of 31 December 2020.

---

### 2. HS Code on Products — MEDIUM

**What's missing:** No `hs_code` field on Product. The due diligence statement requires HS codes per commodity.

Soy reference codes: `1201` (soya beans), `1208 10` (soya flour), `1507` (soya bean oil), `2304` (soya bean meal).

**What's needed:** `hs_code = CharField(max_length=20, blank=True)` on Product. Surface on traceability certificate PDF and batch export.

---

### 3. Quantity in KG on Batch — MEDIUM

**What's missing:** Batch has no quantity field. EUDR requires net mass in kilograms. Quantities live in `SalesOrderItem.quantity` with `Product.unit` which can be kg, g, litre, tonne — no single kg figure on the batch.

**What's needed:** `quantity_kg = DecimalField(10, 3, null=True, blank=True)` on Batch. Explicit user-entered field — operator confirms dispatched quantity for the due diligence statement.

---

### 4. Production Date Range per Farm — MEDIUM

**What's missing:** Article 9(1)(d) requires "the date or time range of production" for each plot. Farm has `mapping_date` (when the boundary was drawn), not when the commodity was harvested.

**What's needed:** `harvest_year` on Farm as a practical proxy for the production period.

---

### 5. EUDR Commodity Scope Flag — MEDIUM

**What's missing:** Platform treats all commodities equally. No distinction between EUDR-regulated commodities (soy, cocoa, coffee, palm oil, rubber, cattle, wood) and non-regulated commodities (gum arabic, baobab, fonio).

**What's needed:** A lookup list in code (no model field required). Used to:
- Show compliance warnings on farm/batch pages
- Filter the EUDR report correctly
- Distinguish buyer-requested traceability from the regulatory report

---

### 6. Supplier Address + Email on Certificate — LOW-MEDIUM

**What's missing:** Article 9 requires name, postal address, and email of each supplier in the chain. Current certificate shows company name and country only.

**What's needed:** Verify Supplier model has `address` and `email` fields. If present, add to certificate PDF. If absent, add to model.

---

### 7. 5-Year Record Retention / Batch Locking — LOW

**What's missing:** No retention policy. EUDR requires records kept for 5 years from date of placing on market. Currently nothing prevents deletion of batches, farms, or sales orders.

**What's needed:** `is_locked` flag on Batch, set automatically when status reaches `dispatched` or `completed`. Locked batches block delete operations.

---

## Monitoring Action — Nigeria Risk Classification

Not a platform gap but an operational one. Nigeria's classification was due from the EU Commission by 30 December 2024. If Nigeria is assigned high-risk status, EU buyers face 9% audit rates on imported commodities.

**Action required:** Check the current EU country classification list and surface Nigeria's status as a static notice in the EUDR report header.

---

*Identified: March 2026 — Target: Phase 4.5 before Buyer Portal launch*
