# Runbook — Seed Data

**Last Updated:** March 2026
**Applies to:** Phase 1 and Phase 2 codebase

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

Optional flags:
```bash
python manage.py seed_data --reset    # Clear existing seed data first
python manage.py seed_data --minimal  # Create minimum viable dataset only
```

---

## What Gets Created

### Companies (2)
- **Plateau Agri Collective** — Growth tier, Jos, Plateau State
- **Kano Grains Cooperative** — Free tier, Kano, Kano State

### Users (4)
| Username | Role | Company |
|---|---|---|
| admin_plateau | org_admin | Plateau Agri Collective |
| manager_plateau | manager | Plateau Agri Collective |
| staff_kano | staff | Kano Grains Cooperative |
| viewer_kano | viewer | Kano Grains Cooperative |

All seed users have password: `seedpass123` — **never use in production.**

### Suppliers (4 total — 2 per company)
- Ake Collective — cooperative, Jos
- Lamingo Farms Aggregator — farmer, Plateau State
- Danbatta Grain Suppliers — cooperative, Kano
- Hadejia Valley Produce — distributor, Kano

### Farms (6 total — EUDR compliance data)
- 3 farms linked to Ake Collective (soy, mixed risk)
- 2 farms linked to Lamingo Farms Aggregator
- 1 farm linked to Danbatta Grain Suppliers

Each farm includes a sample GeoJSON polygon in SW Maps export format.

### Products (6 total)
- Soy (tonne)
- White Maize (tonne)
- Guinea Corn / Sorghum (tonne)
- Groundnut (kg)
- Sesame (kg)
- Cowpea (kg)

### Inventory (6 records)
One inventory record per product with realistic stock levels and low-stock thresholds.

### Purchase Orders (4)
- 2 per company with 2–3 line items each
- Mixed statuses: draft, approved, received

### Sales Orders (3)
- 2 for Plateau Agri Collective (1 completed EU buyer order)
- 1 for Kano Grains Cooperative

---

## Demo Scenario

The seed data tells a coherent story:

**Plateau Agri Collective** is an agricultural cooperative in Jos that procures soy and maize from local farmers and cooperatives. They hold an EU soy supply contract and have completed EUDR farm mapping for their primary farms. They are in the process of verifying a third farm.

**Kano Grains Cooperative** is a smaller operation on the free tier, managing groundnut and sesame procurement for domestic buyers.

This scenario is specifically designed to demonstrate EUDR compliance features — verified farms, pending farms, and a completed sales order to an EU buyer.

---

## Resetting Seed Data

To remove all seed data and start fresh:

```bash
python manage.py seed_data --reset
```

This removes only records created by the seed command — identified by a `_seed` flag in a related metadata field. It does not affect manually created records.

---

## Notes

- Seed data is for development and demo only
- Never run seed_data on a production database
- Seed user passwords are intentionally weak — they are not valid in a production environment
- The `--reset` flag should never be available in the production settings module
