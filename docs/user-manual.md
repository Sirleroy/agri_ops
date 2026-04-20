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
1. Download the **CSV Template** from the import page, or export directly from your field data collection app if farmer data was collected there
2. Fill it in — one row per farmer (SW Maps exports are accepted as-is — column names are recognised automatically)
3. Upload and review the summary
4. Any rows with errors are listed — download the error file, fix the rows, and re-upload

**Column names recognised automatically (SW Maps exports):** `first name` · `last name` · `phone number` · `Village` · `LGA` · `commodity` · `NIN`. Column matching is case-insensitive — you do not need to reformat SW Maps exports before uploading.

**Farmer profile completeness:** After importing farmers, any record missing phone, NIN, or village shows an amber **Incomplete** badge on the farmer list. The farmer detail page shows exactly which fields are missing and links directly to the edit form. Fill these in before your first compliance audit.

---

## Farms

Farms are the GPS-mapped plots of land where commodities are grown. They are the core EUDR compliance unit.

### Adding a single farm

1. Go to **Suppliers → Farms**
2. Click **New Farm**
3. Select the supplier (cooperative) this farm belongs to
4. Link a farmer if they are already registered, or enter a name manually
5. Enter the commodity (e.g. Soy), country, state, and area in hectares
6. Paste the GeoJSON polygon from your mapping app into the Geolocation field
7. Set the deforestation risk status (Standard is the default)
8. Click **Save**

### Bulk farm polygon import

This is the recommended workflow for field mapping exercises.

**Accepted file formats:**
- **GeoJSON** (`.geojson` / `.json`) — exported from any mapping app
- **ZIP archive** (`.zip`) — exported directly from SW Maps or any app that zips GeoJSON; multiple GeoJSON files inside a single ZIP are merged automatically
- **WKT CSV** (`.csv`) — apps that export polygon geometry as WKT in a `geometry` column (SW Maps, QGIS, Avenza Maps)

You can select **multiple files at once** by holding Ctrl (Windows/Linux) or Cmd (Mac) in the file picker. Features from all files are merged into one import run — useful when a field team records several areas in separate sessions.

No conversion needed — the importer normalises coordinates, removes duplicate GPS points, and auto-corrects common geometry issues before validation. SW Maps property keys are matched case-insensitively (`first name`, `last name`, `phone number`, etc. are all recognised automatically).

**Step 1 — Validate first (dry run)**
1. Go to **Suppliers → Farms → Import**
2. Select the supplier
3. Set a default commodity (used for any polygon that doesn't have a Commodity column)
4. Choose your file(s) (GeoJSON, ZIP, or CSV)
5. Tick **Validate only — don't save yet**
6. Click **Upload and Validate**

Review the results:
- **Green (Would create)** — polygons that passed all checks
- **Red (Errors)** — polygons that failed validation. Check the "What went wrong" column for the specific reason
- **Orange (Overlap blocked)** — polygons that overlap an existing farm
- **Amber (Warnings)** — polygons that will import but are missing data (no LGA, no farmer name, etc.). Farm names in the warning list are clickable — tap to open that farm's edit page directly


**Step 2 — Commit**
Once satisfied with the dry-run results, tap the green **Commit N Farms** bar fixed at the bottom of the screen. The farms are saved immediately — no need to re-upload the file. The bar stays visible as you scroll through the results.

**After a successful commit**, two amber sections may appear below the summary:
- **Incomplete farm data** — farms missing LGA, farmer name, or commodity. Each farm name is a link to its edit page. Tap, fill in the missing field, save — you return directly to the import page.
- **Incomplete farmer profiles** — farmer records created during this import that are missing phone, NIN, or village. Same pattern — tap the name, fill in the fields, save.

**What the importer fixes automatically**

The importer applies a three-tier model to every polygon before anything touches the database:

| Tier | What happens | Visible in UI |
|---|---|---|
| **Auto-corrected** | Input normalised silently — safe to proceed | Blue "Auto-corrected" count |
| **Flagged** | Record accepted but incomplete — operator review required | Amber nudge links |
| **Rejected** | Record blocked — unrecoverable error | Red error / orange overlap rows |

Auto-corrections are counted and shown on the import result page. They are never silently discarded — the count confirms the pipeline ran.

Specific issues corrected silently before validation — you do not need to fix your file:

| Issue | What happens |
|---|---|
| 3D coordinates `[lon, lat, elevation]` | Elevation stripped — 2D coordinates stored |
| GPS-pause duplicate vertices | Consecutive identical points removed |
| Unclosed ring (first ≠ last point) | Closing vertex appended automatically |
| Too many vertices (> 200 after dedup) | Simplified via Ramer–Douglas–Peucker at ≈ 1 m tolerance |
| Self-intersecting boundary (GPS track crossed itself) | `buffer(0)` repair applied — boundary resolved into valid geometry, may be stored as MultiPolygon |
| Abbreviated or misspelled LGA (e.g. "T. Balewa") | Fuzzy-matched to canonical LGA name and state auto-filled |
| Numeric phone exported as scientific notation (e.g. `9.088E9`) | Coerced to integer string before E.164 normalisation |
| Mixed-case GeoJSON property keys (`FIRST NAME`, `First Name`, etc.) | Normalised to lowercase before field mapping — no reformatting needed |

**Warnings — accepted but flagged for review**

Some issues do not block an import but are surfaced as warnings because they require a human decision:

| Warning | What it means |
|---|---|
| LGA matched at low confidence | The LGA was fuzzy-matched but the match is below 90% confidence. The correct value has been applied — verify it is accurate before completing EUDR verification. |
| Commodity is not an EUDR Annex I product | The commodity recorded (e.g. Sesame, Groundnut) is outside the six regulated commodities (Cattle, Cocoa, Coffee, Palm Oil, Soybeans, Wood, Rubber). Standard EUDR due-diligence rules do not apply to this farm — confirm the commodity is correct before filing any compliance reports. |
| Declared area unusually large | Farm area exceeds 200 ha — likely a geometry error rather than a real farm boundary. Review the polygon before committing. |

**Hard validation errors** (polygon cannot import — action required)

| Error | What it means | Fix |
|---|---|---|
| Falls outside Nigeria | Polygon centroid is outside lon 2.5–15°E / lat 4–14.2°N — likely swapped lat/lon or wrong map projection | Confirm your app is set to WGS84; check coordinate order |
| Fewer than 4 points | Too few GPS points to form a valid polygon | Re-map the farm — walk the full boundary |
| Unrepairable self-intersection | GPS track crossed itself in a way `buffer(0)` cannot resolve | Re-walk the farm boundary |
| Duplicate farm name | A farm with this name already exists under this supplier | Check for double-entry; rename if a different plot |
| Overlaps existing farm | Boundary shares area with a farm already in the system | Review both farms — adjust if a mapping error |

**Upload history and Transformation Log**

Every import attempt is saved. See the **Recent Uploads** table at the bottom of the import page, or click **View all →** for the full history with expandable detail rows.

Click **Details** on any import row to expand the full audit panel. It shows four sections when relevant:

- **Errors** — rows that were rejected, with the reason
- **Overlap blocked** — rows that would have overlapped an existing farm
- **Warnings** — rows that were accepted but need operator review (low-confidence LGA, non-EUDR commodity, large area)
- **Transformation records** — a complete log of every normalisation or validation event for every farm in that import

The Transformation Log is the chain of custody for your farm data. For each farm and field it records:

| Event type | What it means |
|---|---|
| `geometry validated — clean` | Polygon passed all checks without any modification — stored exactly as received |
| `geometry normalised` | Polygon was corrected before storage. The detail line shows exactly what ran: 3D→2D, duplicate vertices removed, topology repaired, vertex count before/after, area change %, centroid shift in metres |
| `LGA fuzzy-matched` | LGA name was corrected. The detail line shows the match confidence score. Low confidence matches are also surfaced as warnings |
| `canonical name` | Commodity spelling was corrected to the controlled vocabulary (e.g. "soy bean" → "Soybeans") |
| `source area vs computed` | The device-reported AREA value was compared against the polygon we computed. Shows device value, computed area in ha, inferred unit (m² or ha), and the delta % |
| `linked to existing farmer` | A matching farmer record was found in the registry and linked to this farm |
| `new farmer created` | No matching farmer found — a new record was created from the import data |
| `from farmer profile` | Commodity was missing in the file but filled from the farmer's registered crops |

This log is the answer to the compliance question: *"What exactly happened to this farm's data between the GPS device and your database?"* Every correction is recorded with quantitative evidence — not just that something changed, but by how much.

### Field officer provenance

When farms are imported from a GeoJSON file, the import pipeline automatically extracts two provenance fields that are critical for EUDR accountability:

- **Field Officer** — the name of the person who physically mapped the farm. Recognised from any of these property names in the file: `Field Officer Name`, `Field Officer`, `Officer Name`, `Surveyor`, `Mapped By`. Shown on the farm detail page under the Mapping Date.
- **Mapping Date** — the date the boundary was recorded. Recognised from: `Mapping Date`, `Survey Date`, `Date Mapped`.

These fields can also be set or corrected manually on the farm edit page. For EUDR Section 6 compliance, both should be filled in before a farm is marked as verified — they establish who is accountable for the boundary data and confirm it was captured within the relevant period.

### Exporting farm data

Use the **Export** button on the farm list page to download:

- **CSV** — flat spreadsheet with all farm fields (EUDR status, FVF data, compliance dates)
- **PDF** — printable farm registry with colour-coded compliance status
- **GeoJSON** — all farm polygons as a FeatureCollection (import into QGIS, SW Maps, or any GIS tool). Includes all EUDR and FVF fields as feature properties. Farms without a mapped polygon export with `"geometry": null` — valid GeoJSON that will not render on a map but preserves the record.

### Field Verification Form (FVF)

The FVF is completed during the farm mapping exercise — field officers fill in the paper form with the farmer and return it. Once back at base, the data is entered into AgriOps via the farm edit page.

The FVF section appears on the **Edit Farm** page (not the create page — enter FVF data after the farm is imported):

| Field | What to record |
|---|---|
| **Land Acquisition** | How the farmer acquired the land — Inherited, Bought from neighbour, Granted by local leader |
| **Land Tenure** | Documentation basis — Title Deed or Village Consent |
| **Years Farming** | How many years the farmer has been working this plot |
| **Untouched Forest Present** | Is there any primary forest remaining on the farm? (Yes = risk flag) |
| **Expansion Intent** | Does the farmer plan to expand? (Yes = forward risk flag — shown in red on the farm record) |
| **Consent Given + Date** | Record that the farmer gave informed consent for GPS mapping and data collection |

> The paper form is the legal record (it carries the farmer's and village head's signatures). AgriOps holds the searchable digital copy.

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
3. **Map farms** → field mapping exercise → dry-run import → commit import
4. **Verify farms** → set risk status, upload satellite evidence, mark EUDR verified
5. **Create purchase order** → buy the commodity from the supplier → mark Received
6. **Create sales order** → EU buyer order → link farms → batch is created
7. **Lock batch** → after dispatch
8. **Download compliance PDF** → filter by sales order → share with buyer

### Field mapping exercise

1. Brief field officers on farm naming convention before going out
2. Field officer fills the **Field Verification Form (FVF)** with each farmer on-site (paper copy stays with farmer; officer retains a copy)
3. Map all farms in your field mapping app (e.g. SW Maps, Avenza Maps), recording farmer first name, last name, phone number, village, LGA, and commodity in the feature properties
4. Export as GeoJSON, ZIP, or CSV — all formats are accepted. You can select multiple files at once in the file picker (Ctrl/Cmd + click)
5. **Dry-run upload** first — review errors and warnings
6. Fix any issues flagged; re-map or re-export if geometry errors persist
7. Tap the green **Commit N Farms** bar to save — no re-upload needed
8. Fill in any remaining missing data (LGA, FVF fields) using the amber links on the import result page
9. Confirm farm count in Upload History

---

## Getting Help

- **Platform issues or access problems** — contact your Org Admin
- **Bug reports or feature requests** — [github.com/Sirleroy/agri_ops/issues](https://github.com/Sirleroy/agri_ops/issues)
- **Documentation** — [docs.agriops.io](https://docs.agriops.io)

---

*AgriOps · [app.agriops.io](https://app.agriops.io) · Version 1.3 · April 2026*
