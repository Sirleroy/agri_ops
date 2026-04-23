# AgriOps Codebase Guide

This document is a contributor-oriented map of the AgriOps codebase, with extra focus on the farm import and geometry processing stack.

AgriOps is a multi-tenant Django application for agricultural supply-chain operations. Its core job is to keep farm, supplier, procurement, inventory, sales, and compliance data linked under a single tenant root (`Company`) while enforcing tenant isolation in both the web UI and API.

## Architecture Summary

### Platform shape

AgriOps is organized as a modular Django monolith:

```text
agri_ops/
├── agri_ops_project/      # Django project entrypoints
├── config/settings/       # base / development / production settings
├── apps/
│   ├── companies/         # tenant root (Company)
│   ├── users/             # CustomUser, RBAC
│   ├── suppliers/         # Supplier, Farmer, Farm, import pipeline
│   ├── products/          # product catalogue
│   ├── inventory/         # stock and warehouse records
│   ├── purchase_orders/   # procurement workflows
│   ├── sales_orders/      # orders, batches, traceability chain
│   ├── reports/           # PDFs and compliance output
│   ├── dashboard/         # aggregated tenant dashboards
│   ├── audit/             # write-action logging
│   └── api/               # DRF endpoints
├── ops_dashboard/         # internal ops/admin panel
├── templates/             # server-rendered HTML
└── static/                # static assets
```

### Core design principles

- `Company` is the tenant root. Nearly every business model belongs to exactly one company.
- Tenant isolation is enforced in querysets and object lookups rather than database-native row-level security.
- The app is primarily server-rendered Django templates, with DRF used for API access and integration.
- Geospatial data is stored as GeoJSON in a `JSONField`, not PostGIS geometry columns.

### Main domain chain

The high-level traceability model is:

```text
Company
  -> Users
  -> Suppliers
     -> Farmers
     -> Farms
  -> Products
  -> Inventory
  -> Purchase Orders
  -> Sales Orders
     -> Batches
        -> Traceability / EUDR reporting
```

The `suppliers` app is where the farm registry, farmer registry, geolocation storage, and GeoJSON import pipeline live.

## Bulk Import Pipeline End-to-End

The bulk import path starts in `apps/suppliers/farm_views.py`, passes through `apps/suppliers/import_pipeline.py`, reuses validation and geometry helpers from `apps/suppliers/forms.py`, and persists `Farm` rows defined in `apps/suppliers/models.py`.

### End-to-end flow

```text
upload
  -> FarmImportView.post()
  -> parse_file_to_features()
  -> run_farm_geojson_import()
     -> normalize_field_gps_geometry()
     -> _validate_geojson_polygon()
     -> overlap checks
     -> Farm(...) instances assembled
     -> bulk_create()
  -> FarmImportLog saved
  -> audit log saved for successful non-dry-run imports
```

### Upload to storage data flow

1. A staff user uploads one or more files in `FarmImportView.post()`.
2. Each file is converted into a list of GeoJSON-like feature dictionaries.
3. The merged feature list is passed into `run_farm_geojson_import()`.
4. Each feature is normalized, validated, checked for duplicates and overlaps, and converted into a `Farm` instance.
5. On dry run, nothing is written to `Farm`; the parsed features are cached in session for one-tap commit.
6. On commit, farms are written with `bulk_create()`.
7. A `FarmImportLog` row stores totals, errors, warnings, and the transformation log.

### Input formats accepted

`parse_file_to_features()` supports:

- `.geojson` / `.json`: GeoJSON `FeatureCollection` or raw feature list
- `.zip`: archive containing one or more `.geojson` / `.json` files
- `.csv`: WKT geometry in a `geometry`, `wkt`, or `geom` column

Example shape after parsing:

```python
{
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[10.0, 7.0], [10.1, 7.0], ...]]
    },
    "properties": {
        "first name": "Amina",
        "lga": "Bwari",
        "commodity": "Soy"
    }
}
```

## Data Flow: Upload -> Normalization -> Validation -> Storage

### 1. Upload and parse

`FarmImportView.post()` reads uploaded files and delegates all parsing to `parse_file_to_features()`.

Relevant responsibilities:

- validate supplier selection
- collect multiple uploaded files
- stop early on parse errors
- merge all parsed features into one list
- handle dry-run session caching

### 2. Row extraction and field normalization

Inside `run_farm_geojson_import()`:

- property keys are lowercased and stripped
- values are coerced to strings with float hotfixing for whole-number floats
- farm name, farmer name, phone, village, LGA, state, commodity, mapping date, and field officer are extracted from flexible source keys
- LGA and state are canonicalized
- commodity is normalized to controlled vocabulary

This lets the importer tolerate SW Maps and similar exports with inconsistent key casing and naming.

### 3. Geometry normalization

If the feature has geometry, it is sent to `normalize_field_gps_geometry()`.

Exact order:

1. Strip Z coordinates and keep only `[lon, lat]`
2. Round coordinates to 6 decimal places
3. Remove consecutive duplicate vertices
4. Auto-close open rings
5. Simplify rings if vertex count exceeds `max_vertices` (default `200`)
6. Repair invalid topology with `buffer(0)` if possible

The implementation intentionally allows `Polygon -> MultiPolygon` conversion during repair.

Example:

```python
raw = {
    "type": "Polygon",
    "coordinates": [[
        [10.974043333, 7.860608333, 183.8],
        [10.974043333, 7.860608333, 183.8],
        [10.974385000, 7.860673333, 186.3],
        [10.974038333, 7.860453333, 185.4]
    ]]
}

normalized = normalize_field_gps_geometry(raw)
```

### 4. Geometry audit metrics

Before and after normalization, the importer computes:

- vertex counts
- simple centroid
- raw Shapely validity
- area before and after normalization
- centroid shift in meters
- vertex reduction percentage

These metrics are stored in the transformation log attached to `FarmImportLog`.

### 5. Validation

Once geometry is normalized, `_validate_geojson_polygon()` applies the structural and geospatial rules.

### 6. Business checks

After geometry validation, the importer applies:

- duplicate farm-name check against existing farms for the supplier
- duplicate name check within the current batch
- overlap check against stored farms in the same tenant
- overlap check against already-accepted farms in the same import batch
- farmer linking / farmer auto-creation
- completeness warnings

### 7. Persistence

Accepted rows become `Farm(...)` model instances and are written in batches with `bulk_create()`.

The geometry stored in `Farm.geolocation` is the normalized geometry, not the raw upload geometry.

## Geometry Normalization Steps

The canonical implementation is `normalize_field_gps_geometry()` in `apps/suppliers/forms.py`.

### Exact execution order

```python
def normalize_field_gps_geometry(geometry, max_vertices=200,
                                 simplify_tolerance=0.00005,
                                 precision=6):
    # 1. strip Z
    # 2. round to 6dp
    # 3. remove consecutive duplicates
    # 4. auto-close
    # 5. simplify if too many vertices
    # 6. repair invalid topology via buffer(0)
```

### Why each step exists

- Z stripping: field GPS exports often contain elevation, but downstream validation and storage are 2D.
- Rounding: removes floating-point noise and stabilizes hashes and comparisons.
- Deduplication: repeated pause points from mobile GPS apps should not inflate geometry complexity.
- Ring closure: some field tools omit the final closing point.
- Simplification: caps extreme vertex counts while preserving topology.
- Topology repair: attempts to salvage self-crossing or slightly broken polygons before rejecting them.

## Validation Rules

Validation is split between form helpers and the import pipeline.

### `_validate_geojson_polygon()` rules

The geometry validator checks:

- `type` must be present
- `type` must be `Polygon` or `MultiPolygon`
- `coordinates` must exist
- each ring must contain at least 4 points
- each ring must be closed
- each coordinate must have at least two numeric values
- longitude must be within `[-180, 180]`
- latitude must be within `[-90, 90]`
- the polygon centroid must fall inside a Nigeria bounding box
- Shapely validity must pass after normalization

Example validation failure surfaces:

```python
raise forms.ValidationError(
    "Ring 1 is not closed — the first and last coordinate must be identical."
)
```

### Additional import-time checks

`run_farm_geojson_import()` adds:

- hard error if a feature has no geometry
- duplicate check: existing `Farm` with same company, supplier, and case-insensitive name
- duplicate check within the same batch
- overlap check against existing farms
- intra-batch overlap check
- warnings for missing farmer name, missing LGA, large area, non-EUDR commodity, ambiguous farmer match, and unknown commodity

### Severity escalation in transformation log

The transformation log uses `severity` values beyond `info` in four conditions:

- `review`: normalized geometry changed area by more than `0.5%`
- `review`: normalized geometry shifted centroid by more than `15m`
- `review`: LGA fuzzy-match confidence is below `0.90`
- `warning`: source `AREA` metadata differs from computed area by more than `0.1%`

## File Breakdown

### `apps/suppliers/import_pipeline.py`

This is the service layer for farm imports.

### What it does

- parses supported upload formats into features
- extracts and normalizes feature properties
- normalizes geometry
- validates geometry
- calculates area and transformation metrics
- detects duplicates and overlaps
- links or creates farmers
- assembles `Farm` instances
- writes accepted rows with `bulk_create()`
- returns a rich result object for UI and API callers

### Important functions

- `_wkt_csv_to_features()`: converts WKT CSV rows into GeoJSON features
- `parse_file_to_features()`: top-level file parser
- `_geom_vertex_count()`: counts vertices for audit metrics
- `_geom_centroid()`: approximate centroid for audit comparisons
- `_haversine_m()`: centroid shift measurement
- `_parse_mapping_date()`: flexible mapping-date parsing
- `run_farm_geojson_import()`: main pipeline

### Key design choices

- views stay thin; import logic is centralized
- dry-run and real import share one code path
- transformation logging is treated as first-class audit data
- geometry is normalized before validation

### `apps/suppliers/forms.py`

This file contains both standard Django forms and the shared geometry helpers used by the importer.

### Major responsibilities

- spherical area computation from GeoJSON
- GeoJSON structural validation
- geometry normalization
- overlap detection using Shapely
- manual farm create/update form validation

### Key helpers

- `_compute_area_ha()`: computes area from the outer ring
- `_validate_geojson_polygon()`: structural and geospatial validation
- `normalize_field_gps_geometry()`: canonical geometry normalization routine
- `_geojson_to_shape()`: GeoJSON -> Shapely conversion
- `_find_overlapping_farm()`: overlap check against stored farms

### Manual form path

Manual farm create/update uses:

```python
def clean_geolocation(self):
    value = self.cleaned_data.get("geolocation")
    value = normalize_field_gps_geometry(value)
    return _validate_geojson_polygon(value)
```

So the manual form path and bulk import path share the same geometry rules, but invoke them from different call sites.

### `apps/suppliers/models.py`

This file defines the suppliers domain model.

### Core models

- `Farmer`: farmer identity and registry data
- `Supplier`: supplier/trading entity
- `Farm`: farm plot and compliance unit
- `FarmImportLog`: audit record for every import attempt
- `FarmCertification`: certification metadata
- `ComplianceDocument`: file attachments for farm compliance

### `Farm` model behavior

`Farm` stores:

- `geolocation` as GeoJSON in `JSONField`
- `geometry_hash` for canonical geometry fingerprinting
- `area_hectares`
- commodity and EUDR fields
- verification and FVF fields

`Farm.save()` recomputes:

- normalized commodity label
- area from `geolocation`
- `geometry_hash` from canonical JSON

That matters for understanding the bulk import edge case below.

### `apps/suppliers/farm_views.py`

This file is the web layer for farm operations.

### Major view responsibilities

- `FarmImportView`: upload, dry-run, commit, import logging
- `FarmImportHistoryView`: list historical imports
- `FarmImportErrorsView`: export previous error rows as JSON
- `FarmExportView`: export registry as CSV/PDF/GeoJSON
- `FarmListView`, `FarmDetailView`: registry UI
- `FarmCreateView`, `FarmUpdateView`, `FarmDeleteView`: CRUD UI

### Import-specific behavior

`FarmImportView` is deliberately thin:

- parse files
- validate supplier
- call `run_farm_geojson_import()`
- persist `FarmImportLog`
- cache dry-run features in session
- write audit log for successful real imports

This keeps the import service testable and reusable from the API layer.

## Known Edge Cases and Caveats

### 1. `geometry=None`

This can still appear if an incoming feature already has `geometry=None` or a malformed upstream producer emits empty geometry.

Current importer behavior:

- hard error is raised at import-service level before structural validation
- the row is rejected with: `Feature has no geometry — cannot import.`

Important nuance:

- WKT CSV parsing no longer converts failed WKT rows into `geometry=None`; failed WKT rows are skipped during CSV-to-feature conversion
- direct GeoJSON input can still include a null `geometry`

### 2. `bulk_create()` bypasses `save()`

`run_farm_geojson_import()` persists farms with `Farm.objects.bulk_create(...)`.

That means Django does not call `Farm.save()` for each imported row. Normally that would skip:

- commodity canonicalization in `save()`
- area recomputation in `save()`
- `geometry_hash` recomputation in `save()`

Current mitigation in the importer:

- commodity is already normalized before model instantiation
- area is computed from normalized geometry before `Farm(...)` is built
- `geometry_hash` is computed manually and assigned before `bulk_create()`

So the caveat still exists architecturally, but the import pipeline currently compensates for it.

### 3. Dry-run stores parsed features, not normalized farms

Dry-run caches the parsed feature list in session. On commit, the same import pipeline runs again and redoes normalization, validation, overlap checks, and persistence.

Implication:

- dry-run results are predictive, not a serialized snapshot of pre-approved farm rows

### 4. Topology repair may change geometry type

Normalization may repair an invalid `Polygon` into a valid `MultiPolygon`. This is intentional and accepted by validation and storage.

### 5. Area metadata from source files is advisory only

If the import file includes `AREA`, the pipeline compares it to computed area and records a warning when they diverge materially, but stored `area_hectares` is always derived from the normalized geometry.

## Practical Mental Model for Contributors

When touching the import code, think in this order:

1. Can the upload be parsed into features?
2. Can each feature be normalized into canonical field and geometry values?
3. Does the normalized geometry pass structural and spatial validation?
4. Does the row conflict with existing tenant data?
5. Can the row be converted into a stable `Farm` record with auditable transformations?

If you change normalization or validation behavior, review all of these together:

- `apps/suppliers/import_pipeline.py`
- `apps/suppliers/forms.py`
- `apps/suppliers/models.py`
- `apps/suppliers/tests/test_normalize_geometry.py`
- `apps/suppliers/tests/test_geojson_validation.py`

That cluster defines the real ingest contract.
