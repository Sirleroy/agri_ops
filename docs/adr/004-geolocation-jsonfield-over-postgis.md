# ADR 004 — Geolocation: JSONField over PostGIS (Interim Strategy)

**Date:** March 2026
**Status:** Accepted — scheduled for revision at Phase 4
**Author:** Ezinna (Founder)

---

## Context

AgriOps requires farm geolocation data to support EUDR (EU Deforestation Regulation) compliance. The regulation mandates that operators trading in specific commodities (including soy) must provide geolocation data for the plots of land where the commodity was produced. This means storing farm boundary polygons — not just a single point — and associating them with supply chain records.

The question is how to store this geolocation data in the database.

---

## Decision Drivers

- EUDR compliance requires farm boundary polygons (perimeter mapping), not just lat/long points
- Field teams use SW Maps and NCAN Farm Mapper for data collection — both export GeoJSON format
- Infrastructure complexity must remain low during Phase 1 and 2 — solo founder, local development
- Data must be stored in a format that supports seamless migration to a proper GIS database in Phase 4
- PostgreSQL extension PostGIS provides the correct long-term solution but adds significant setup overhead

---

## Options Considered

### Option 1 — PostGIS + PointField / PolygonField (django.contrib.gis)
Django's GeoDjango framework with PostGIS extension provides native GIS field types.

**Pros:**
- Correct long-term solution — spatial queries, distance calculations, intersection checks
- Industry standard for GIS data in PostgreSQL
- Full Django ORM support via GeoDjango

**Cons:**
- Requires PostGIS extension installed on PostgreSQL — additional setup on every environment
- Requires GDAL/GEOS system libraries installed on the host OS
- Docker configuration significantly more complex — custom base image required
- Not available on all managed PostgreSQL providers without additional configuration
- Overkill for Phase 2 requirements — we need to store and display polygons, not run spatial queries yet
- Risk: blocks development progress disproportionate to current feature need

### Option 2 — JSONField storing GeoJSON ✅ Chosen (interim)
Store farm geolocation as a `JSONField` containing a GeoJSON-format object.

**Pros:**
- Zero additional infrastructure — JSONField is native PostgreSQL JSONB, no extensions required
- GeoJSON is the standard export format of SW Maps and NCAN Farm Mapper — no conversion needed
- Data is immediately ready for PostGIS migration in Phase 4 — GeoJSON is what PostGIS ingests natively
- Works identically in local development, Docker, and all managed PostgreSQL providers
- Sufficient for Phase 2 and 3 requirements: store, display, export polygon data

**Cons:**
- No native spatial queries — cannot do "find all farms within 50km" without parsing JSON manually
- No geometry validation at database level
- Mitigation: spatial queries are a Phase 4 requirement, not Phase 2

### Option 3 — Separate lat/long fields (FloatField x2)
Store only a centroid point as two float fields.

**Pros:** Simplest possible implementation.

**Cons:** Does not meet EUDR requirements — the regulation requires the actual plot boundary, not a point. Confirmed by internal company process: "you will have to measure the perimeter of the farm and document the GPS." Rejected outright.

---

## Decision

**Use JSONField storing GeoJSON-format data** as the interim geolocation storage strategy for Phase 2 and Phase 3. Migrate to PostGIS PolygonField in Phase 4 when deploying to a managed cloud PostgreSQL instance with PostGIS support.

---

## GeoJSON Storage Format

All farm geolocation data is stored in the following standard GeoJSON structure:

```json
{
  "type": "Polygon",
  "coordinates": [
    [
      [8.8583, 9.8965],
      [8.8601, 9.8965],
      [8.8601, 9.8982],
      [8.8583, 9.8982],
      [8.8583, 9.8965]
    ]
  ],
  "properties": {
    "area_hectares": 12.4,
    "mapped_by": "field_agent_name",
    "mapped_date": "2026-03-11",
    "source_app": "SW Maps",
    "accuracy_metres": 3
  }
}
```

This format is:
- The native export format of SW Maps (strong preference confirmed by field team)
- Compatible with NCAN Farm Mapper exports
- Directly ingestible by PostGIS in Phase 4 without data transformation
- Renderable by Leaflet.js / Mapbox for farm boundary visualisation in the UI

---

## Field Implementation

```python
class Farm(models.Model):
    geolocation = models.JSONField(
        null=True,
        blank=True,
        help_text="GeoJSON Polygon. Exported from SW Maps or NCAN Farm Mapper."
    )
```

---

## Phase 4 Migration Path

```
Phase 2-3: JSONField (GeoJSON stored as JSONB)
Phase 4:   Add PostGIS extension to managed PostgreSQL
           Add PolygonField alongside JSONField
           Data migration: parse JSONField → populate PolygonField
           Remove JSONField after validation
```

No data loss during migration — GeoJSON in JSONField maps directly to PostGIS Polygon geometry.

---

## Consequences

- SW Maps and NCAN Farm Mapper exports can be ingested directly without transformation
- Farm boundary display in the UI uses Leaflet.js parsing GeoJSON from the API response
- Spatial queries (proximity, intersection, area calculations) deferred to Phase 4
- EUDR compliance reporting uses stored GeoJSON coordinates directly in export documents
- All developers must store geolocation in the defined GeoJSON format — no ad hoc structures

---

## Related Decisions

- ADR 001 — Django + PostgreSQL stack
- ADR 005 — EUDR Farm Model Separation
- Design doc: `/docs/design/compliance-module.md`
