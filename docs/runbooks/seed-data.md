# Runbook — Seed Data

**Last Updated:** March 2026
**Applies to:** Phase 2 codebase

---

## Overview

The seed data management command populates the database with realistic test data reflecting the Nigerian agricultural context. It is used for:

- Local development testing
- Demo environment setup
- UI/UX review with realistic data
- Beta user onboarding demonstrations

The command is **idempotent** — running it multiple times will not create duplicate records.

---

## Usage
```bash
python manage.py seed_data
```

To wipe existing seed data and rebuild from scratch:
```bash
python manage.py seed_data --flush
```

---

## What Gets Created

### Companies (2)

| Company | Plan | City |
|---|---|---|
| Ake Collective | Pro | Kano |
| Agro Foods Nigeria Ltd | Free | Ibadan |

### Users (6)

| Username | Role | Company | Password |
|---|---|---|---|
| ake_admin | org_admin | Ake Collective | agriops2026! |
| ake_manager | manager | Ake Collective | agriops2026! |
| ake_staff | staff | Ake Collective | agriops2026! |
| ake_viewer | viewer | Ake Collective | agriops2026! |
| agro_admin | org_admin | Agro Foods Nigeria Ltd | agriops2026! |
| agro_staff | staff | Agro Foods Nigeria Ltd | agriops2026! |

**Never use seed passwords in production.**

### Suppliers (4 total)

**Ake Collective:**
- Kano Agro Inputs Ltd — fertilizer
- Sahel Seeds Co-op — seeds
- West Africa Packaging — packaging

**Agro Foods Nigeria Ltd:**
- Oyo Agro Supplies — fertilizer

### Farms (2 — EUDR compliance data)

| Farm | Supplier | Commodity | Risk | Verified |
|---|---|---|---|---|
| Sule Family Farm | Sahel Seeds Co-op | Soy | Low | ✅ Yes |
| Abubakar Cooperative Plot B | Sahel Seeds Co-op | Maize | Standard | ❌ No |

### Products (4 total)

**Ake Collective:** NPK Fertilizer 20-10-10 (bag), Certified Soybean Seed (kg), Woven Polypropylene Bag 50kg (piece)

**Agro Foods Nigeria Ltd:** Urea Fertilizer 46% (bag)

### Inventory

One record per product with realistic quantities and low-stock thresholds. Certified Soybean Seed is intentionally seeded below threshold to demonstrate the low-stock alert.

### Purchase Orders (2 — Ake Collective)

- AKE-PO-2026-001 — Kano Agro Inputs Ltd — delivered
- AKE-PO-2026-002 — Sahel Seeds Co-op — pending

### Sales Orders (1 — Ake Collective)

- AKE-SO-2026-001 — Kano State Farmers Cooperative — confirmed

---

## Demo Scenario

The seed data tells a coherent story designed to demonstrate all platform features:

**Ake Collective** is a Pro-tier agricultural cooperative in Kano procuring fertilizer, seeds, and packaging from Nigerian suppliers. They have two farms registered — one EUDR-verified, one pending — demonstrating the compliance workflow. Their soybean seed inventory is below threshold, triggering the low-stock API endpoint. They have an active purchase order and a confirmed sales order.

**Agro Foods Nigeria Ltd** is a Free-tier operator in Ibadan with minimal data — useful for demonstrating tenant isolation (their data is completely invisible to Ake Collective users and vice versa).

---

## Tenant Isolation Test

To verify tenant isolation is working:

1. Log in as `ake_admin` — you should see only Ake Collective's data
2. Log in as `agro_admin` — you should see only Agro Foods data
3. Attempt to access `http://localhost:8001/suppliers/1/` as `agro_admin` — should return 404

---

## Notes

- Seed data is for development and demo only
- Never run `seed_data` on a production database
- The `--flush` flag deletes by username and company name — it will not affect manually created records with different names
- Seed user passwords are intentionally simple — they are not valid in a production environment
