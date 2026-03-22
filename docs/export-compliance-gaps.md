---
layout: default
title: Export Compliance Gaps — v1
---
# Export Compliance Gaps — v1

Analysis against Nigerian export requirements and EU market regulations beyond EUDR. Identified March 2026.

---

## Gap Summary

| Gap | Priority | Where it belongs |
|---|---|---|
| NAQS phytosanitary certificate per batch | **High** | Batch detail — linked certificate record |
| Lab test results (MRL, aflatoxin) per batch | **High** | Batch detail — quality log |
| NEPC exporter registration number | Medium | Company model |
| Certificate of Origin reference per shipment | Medium | Sales order |
| NXP reference per sales order | Medium | Sales order |
| NAFDAC registration per product | Medium | Product model |
| Farm certifications (Organic, GlobalG.A.P., etc.) | Medium | Farm model — multi-certification records |
| EU Novel Food status per product | Low | Product model |
| ISCC certification status | Low | Covered by FarmCertification model |

---

## The Two Gaps That Block Sales

Before any EU ingredient buyer completes supplier onboarding, they will request:

1. **Aflatoxin and MRL test certificates** — non-negotiable for food ingredient buyers. Without them, no procurement team can approve a new supplier regardless of traceability.
2. **Phytosanitary certificates** — required by Nigerian law and verified at EU customs. A buyer cannot import without this documentation.

Everything else can be built incrementally. These two must be in place before first commercial shipment.

---

## Detailed Gaps

### 1. NAQS Phytosanitary Certificate per Batch — HIGH

**Regulation:** All agricultural commodity exports from Nigeria require a Phytosanitary Certificate issued by the Nigerian Agricultural Quarantine Service (NAQS). This is a pre-shipment requirement — no certificate, no export.

**Applies to:** All AgriOps commodities — gum arabic, baobab, soy, fonio.

**What's needed:**
- `PhytosanitaryCertificate` model linked to Batch
- Fields: certificate number, issuing NAQS office, inspector name, inspection date, issue date, expiry date
- `is_current` property — flags expired certs
- Batch detail page section: shows status, current/expired badge, Add/Edit/Delete actions

---

### 2. Lab Quality Tests (MRL + Aflatoxin) per Batch — HIGH

**Regulation:** EU Regulation (EC) 396/2005 (pesticide MRL limits) and Regulation (EC) 1881/2006 (aflatoxin limits) are enforced at EU border entry. Non-compliance triggers RASFF alerts and border rejection. Nigeria has a documented aflatoxin risk profile — EU buyers from West African supply chains are alert to this.

**Applies to:** All batches destined for EU food use. Nexira, Alland & Robert, and other gum arabic buyers will ask for this before they even sample the product.

**What's needed:**
- `BatchQualityTest` model linked to Batch
- Test types: Pesticide MRL (EU 396/2005), Aflatoxin (EU 1881/2006), Moisture Content, Heavy Metals, Microbiological, Other
- Fields: lab name, certificate reference, test date, pass/fail/pending result
- Batch detail page section: shows all tests, pass/fail colour coding, Add/Edit/Delete actions

---

### 3. NEPC Exporter Registration — MEDIUM

**Regulation:** All Nigerian exporters must be registered with the Nigerian Export Promotion Council (NEPC) before any export transaction. Registration must be renewed.

**What's needed:**
- `nepc_registration_number` on Company model
- `nepc_registration_expiry` on Company model
- Exposed in company settings form

---

### 4. Certificate of Origin + NXP Reference on Sales Order — MEDIUM

**Regulation:** Nigerian Customs requires a Combined Certificate of Value and Origin (CCVO) per shipment. The CBN Form NXP must be completed through an authorised dealer bank before export, registering the export proceeds obligation (repatriation required within 90 days).

**What's needed:**
- `certificate_of_origin_ref` on SalesOrder — CoO number from Chamber of Commerce / Customs
- `nxp_reference` on SalesOrder — CBN Form NXP reference number
- Both exposed in sales order create/edit form

---

### 5. NAFDAC Registration per Product — MEDIUM

**Regulation:** NAFDAC has jurisdiction over food and agricultural products. Processed agricultural products (powders, extracts, refined grades) may require NAFDAC registration or export notification. Applies primarily to baobab powder and refined gum arabic grades.

**What's needed:**
- `nafdac_registration_number` on Product model
- Exposed in product create/edit form

---

### 6. Farm Certifications (Organic, GlobalG.A.P., etc.) — MEDIUM

**Regulation:** Not legally required but functionally mandatory for EU premium buyers. GlobalG.A.P. is required by major European retailers. Organic certification unlocks significantly higher prices and buyer segments conventional supply cannot reach. Entire supply chain from farm to export must be certified under EU Organic Regulation (EU) 2018/848.

**Multiple certification types may exist simultaneously on the same farm.**

**What's needed:**
- `FarmCertification` model linked to Farm
- Cert types: Organic EU (2018/848), GlobalG.A.P., Fairtrade, Rainforest Alliance, ISCC, Other
- Fields: certifying body, certificate number, issue date, expiry date
- `is_current` property — flags expired certs
- Farm detail page section: shows all certifications, Add / Delete actions

---

### 7. EU Novel Food Status per Product — LOW

**Regulation:** Baobab fruit pulp was approved as a novel food in the EU in 2008 (Commission Decision 2008/575/EC). This is a selling point — it means EU buyers can legally use it. The approval has conditions: dried baobab fruit pulp specifically, maximum use levels per food category, must be labelled as "baobab fruit pulp".

**What's needed:**
- `eu_novel_food_status` (BooleanField) on Product — flags products with EU Novel Food approval
- `eu_novel_food_ref` on Product — approval reference (e.g. Commission Decision 2008/575/EC)
- Exposed in product form with help text

---

## Regulatory Scope — Nigerian Export Chain

| Step | Requirement | Party |
|---|---|---|
| NEPC registration | Before first export | Exporter (AgriOps tenant) |
| NAQS phytosanitary inspection | Per consignment, pre-shipment | NAQS (exporter books) |
| CBN Form NXP | Per export transaction, before shipment | Exporter via authorised bank |
| Customs CCVO + SGD | Per shipment | Nigerian Customs |
| MRL testing | Per batch, pre-shipment | External accredited lab |
| Aflatoxin testing | Per batch, pre-shipment | External accredited lab |
| EU customs declaration | At EU border | EU buyer / freight forwarder |
| EUDR due diligence statement | At EU border | EU buyer (operator) |

**AgriOps role:** Generates the documentation that enables the exporter and EU buyer to complete their respective obligations. AgriOps does not submit to regulators directly.

---

## What AgriOps Does Not Cover (By Design)

- **NEPC registration itself** — administrative process, AgriOps records the number
- **NAQS inspection booking** — operational workflow, AgriOps records the certificate
- **Bank NXP submission** — finance/treasury workflow, AgriOps records the reference
- **Lab testing** — contracted externally, AgriOps records the result and certificate
- **EU due diligence statement submission** — EU buyer's legal obligation, AgriOps generates the evidence

---

*Identified: March 2026 — Target: Phase 4.5 before first commercial shipment*
