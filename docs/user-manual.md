---
layout: manual
title: AgriOps User Manual
---

## What is AgriOps?

AgriOps is a supply chain management platform for agricultural companies. It helps you track everything from farm-level GPS mapping through to export compliance — suppliers, farmers, farms, stock, purchase orders, sales orders, and EUDR traceability certificates.

The platform runs at **[app.agriops.io](https://app.agriops.io)**.

---

## Roles and Access

Every user has one of four roles. Your role controls what you can see and do.

| Role | What you can do |
|---|---|
| **Viewer** | Read-only. See all records, download reports. Cannot create or edit anything. |
| **Staff** | Create and edit records. Cannot delete. Cannot manage users. |
| **Manager** | Create, edit, and delete records. Cannot manage company settings or users. |
| **Org Admin** | Full access including user management, company settings, and all reports. |

Your role is shown on your profile page. Contact your Org Admin if you need a different level of access.

---

## Logging In

1. Go to **[app.agriops.io](https://app.agriops.io)**
2. Enter your username and password
3. After 5 failed attempts your account is locked for 1 hour — contact your admin if locked out
4. Your session expires after 8 hours and you will be asked to log in again

---

## The Dashboard

The dashboard is your home screen. It gives you a live summary of your company's supply chain.

**Top row — core counts:**
- Suppliers, Products, Purchase Orders, Sales Orders

**Second row:**
- **Farms** — total registered plots, with total mapped hectares underneath
- **Farmers** — registered individual farmer records
- **Low Stock** — inventory items below their alert threshold (amber if any)
- **Verification Expiring** — farms whose EUDR verification lapses within 30 days (orange if any)

**Business Intelligence strip** — rotates through: top buyer, top supplier, farm compliance rate, top product, open sales, active procurement.

**Farm Compliance panel** — shows verified / pending / high risk / expiring farm counts, with a progress bar. Also shows the last bulk upload attempt (date, who, how many farms saved).

**Bottom panels:**
- Upcoming PO deliveries in the next 7 days
- Farms with verification expiring in 30 days (click to go to farm)
- Low stock items (click to go to inventory record)

**Compliance Report** — download a full PDF traceability report directly from the dashboard, with optional date filtering.

---

## Suppliers

Suppliers are the cooperatives, aggregators, or trading entities you buy from. Each farm belongs to a supplier.

**To add a supplier:**
1. Go to **Suppliers** in the left sidebar
2. Click **New Supplier**
3. Fill in name, category (e.g. Cooperative), contact details, country
4. Click **Save**

**Supplier categories:** Cooperative · Processor · Distributor · Exporter · Seeds · Fertilizer · Equipment · Other

**Reliability score (0–10):** Optional field you can update based on delivery history.

---

## Farmers

Farmers are the individual people who own or manage farm plots. Building a farmer registry before importing farms gives you cleaner data — farms can be linked to a farmer record rather than just a name.

**To add a farmer:**
1. Go to **Suppliers → Farmers**
2. Click **New Farmer**
3. Fill in first name, last name, phone, village, LGA, and crops
4. NIN (National Identification Number) is optional but useful for deduplication
5. Tick **Consent given** and record the consent date if you have verbal or written consent

**Bulk import:**
1. Download the **CSV Template** from the import page
2. Fill it in — one row per farmer
3. Upload and review the summary
4. Any rows with errors are listed — download the error file, fix the rows, and re-upload

---

## Farms

Farms are the GPS-mapped plots of land where commodities are grown. They are the core EUDR compliance unit.

### Adding a single farm

1. Go to **Suppliers → Farms**
2. Click **New Farm**
3. Select the supplier (cooperative) this farm belongs to
4. Link a farmer if they are already registered, or enter a name manually
5. Enter the commodity (e.g. Soy), country, state, and area in hectares
6. Paste the GeoJSON polygon from SW Maps into the Geolocation field
7. Set the deforestation risk status (Standard is the default)
8. Click **Save**

### Bulk import from SW Maps

This is the recommended workflow for field mapping exercises.

**Step 1 — Validate first (dry run)**
1. Go to **Suppliers → Farms → Import**
2. Select the supplier
3. Set a default commodity (used for any polygon that doesn't have a Commodity column)
4. Choose your GeoJSON file exported from SW Maps
5. Tick **Validate only — don't save yet**
6. Click **Upload and Validate**

Review the results:
- **Green (Would create)** — polygons that passed all checks
- **Red (Errors)** — polygons that failed validation. Check the "What went wrong" column for the specific reason
- **Orange (Overlap blocked)** — polygons that overlap an existing farm
- **Amber (Warnings)** — polygons that will import but are missing data (no LGA, no farmer name, etc.)

**Step 2 — Commit**
1. Once satisfied with the dry-run results, upload the same file again
2. This time leave **Validate only** unticked
3. Click **Upload and Validate** — farms are now saved

**Common validation errors:**

| Error | What it means | Fix |
|---|---|---|
| Falls outside Nigeria | Coordinates are wrong — likely swapped lat/lon or wrong map projection | Re-export from SW Maps with WGS84 setting |
| Ring is not closed | The polygon boundary doesn't close back on itself | Re-export the boundary from SW Maps |
| Only N points | Too few GPS points to make a valid polygon | Remap the farm — walk the full boundary |
| Overlaps existing farm | This plot's boundary crosses a farm already in the system | Review both farms — adjust if a mapping error |

**Upload history**
Every import attempt is saved. See the **Recent Uploads** table at the bottom of the import page, or click **View all →** for the full history with expandable error detail.

### EUDR verification

After a farm is registered, a compliance officer must verify it:

1. Open the farm record
2. Review the polygon on the map
3. Set **Deforestation Risk Status** — Low, Standard, or High
4. Set **Land Cleared After Cutoff** — must be No (cleared before 31 Dec 2020) for EUDR eligibility
5. Upload supporting documents (satellite image, land registry, farmer declaration) under **Compliance Documents**
6. Tick **EUDR Verified**, enter the verified date and set an expiry date for re-verification

Farms show a compliance status on the list page:
- **Compliant** (green) — verified, not expired, not high risk
- **Pending** (grey) — not yet verified
- **Expired** (orange) — verification lapsed
- **High Risk** (red) — flagged as high deforestation risk
- **Disqualified** — land was cleared after 31 Dec 2020

---

## Products

Products are the commodities you trade (Soy, Maize, Cocoa, etc.) and inputs you buy.

**To add a product:**
1. Go to **Products**
2. Click **New Product**
3. Enter the name, category, unit (kg / tonne / bag), and unit price
4. Add the HS code if this product will be exported to the EU — required for EUDR due diligence statements
5. Click **Save**

---

## Inventory

Inventory records track stock levels per product at a warehouse location.

**Stock is updated automatically** when a Purchase Order is marked as Received — you do not need to manually add stock entries for purchases.

**To check stock:**
- Go to **Inventory**
- Items shown in amber are at or below their low-stock threshold
- Click any item to see lot number, moisture content, quality grade, and origin

**To set a low-stock alert:**
- Open an inventory record and set the **Low Stock Threshold** field

---

## Purchase Orders

Purchase orders (POs) record procurement from suppliers.

**To create a PO:**
1. Go to **Purchase Orders → New Purchase Order**
2. Select the supplier
3. Add line items — product, quantity, and unit price
4. Set an expected delivery date
5. Save as **Draft**, then move to **Approved** → **Ordered** as the order progresses

**Marking as Received:**
1. Open the PO
2. Click **Mark as Received**
3. Stock is automatically added to Inventory for each line item
4. The PO status changes to Received

---

## Sales Orders

Sales orders record dispatches to buyers.

**To create a sales order:**
1. Go to **Sales Orders → New Sales Order**
2. Enter the customer name and contact details
3. Tick **EU Export** if this shipment is going to an EU buyer — this activates the EUDR compliance section
4. Add line items — product and quantity
5. Save

**Order statuses:** Pending → Confirmed → Dispatched → Completed

### Linking farms for EUDR traceability

If this is an EU export, you must link the farms that supplied the commodity:

1. Open the sales order detail page
2. Scroll to **Farm Traceability**
3. Select the farms that supplied the goods in this shipment
4. Click **Save Linked Farms** — a Batch record is created automatically with a unique batch number and QR code
5. The batch number can be shared with your EU buyer for traceability verification

**Batch locking:** Once a batch is dispatched, click **Lock Batch** on the batch detail page. Locked batches cannot be edited or deleted — this is required for EUDR 5-year record retention.

---

## EUDR Compliance Report

The compliance report is a full PDF traceability document covering your operator details, supplier network, all farms with GPS and verification status, purchase orders, batch traceability, sales orders, and a due diligence declaration.

**To download:**
1. From the Dashboard, click **Full Report** under Compliance Report
2. Or go to **Reports** in the sidebar
3. Filter by sales order, buyer name, or date range for a specific shipment report
4. Click **Generate PDF**

The report is formatted for submission to EU buyers and auditors. Each batch section now includes the HS code derived from your product catalogue.

> **Note on EU IS submission:** The AgriOps compliance PDF contains all the data fields required for an EU EUDR Information System Due Diligence Statement. For current export volumes, this PDF can be used as the basis for manual submission via the EU IS web portal. API-based DDS submission will be added to AgriOps when export volumes require it.

---

## Users and Team Management

*(Org Admin only)*

1. Go to **Users** in the sidebar
2. Click **Invite User** to add a team member
3. Set their role — see the Roles table at the top of this manual
4. Users receive a welcome email with login instructions

To change a user's role, open their profile and update the **System Role** field.

---

## Company Settings

*(Org Admin only)*

Go to **Company** in the sidebar to update:
- Company name, address, country, city
- Contact email and phone
- NEPC registration number and expiry (for Nigerian export compliance)

---

## Common Workflows

### End-to-end: farm to EUDR report

1. **Add supplier** → cooperative or aggregator
2. **Add farmers** → bulk import via CSV or add individually
3. **Map farms** → SW Maps field exercise → dry-run import → commit import
4. **Verify farms** → set risk status, upload satellite evidence, mark EUDR verified
5. **Create purchase order** → buy the commodity from the supplier → mark Received
6. **Create sales order** → EU buyer order → link farms → batch is created
7. **Lock batch** → after dispatch
8. **Download compliance PDF** → filter by sales order → share with buyer

### Field mapping exercise

1. Brief field officers on farm naming convention before going out
2. Map all farms in SW Maps, record farmer name, village, LGA, and commodity in SW Maps properties
3. Export as GeoJSON FeatureCollection from SW Maps
4. **Dry-run upload** first — review errors and warnings
5. Fix any issues flagged (re-export from SW Maps if geometry errors)
6. Commit upload — confirm farm count in Upload History
7. Fill in missing LGA, farmer links, and other warnings via the farm edit page

---

## Getting Help

- **Platform issues or access problems** — contact your Org Admin
- **Bug reports or feature requests** — [github.com/Sirleroy/agri_ops/issues](https://github.com/Sirleroy/agri_ops/issues)
- **Documentation** — [docs.agriops.io](https://docs.agriops.io)

---

*AgriOps · [app.agriops.io](https://app.agriops.io) · Version 1.0 · April 2026*
