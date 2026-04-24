"""
Supplier app forms — Farmer and Farm with data quality validation.

Validation layers applied here:
  Layer 1 — GeoJSON structural validity (type, closed ring, coordinate range)
  Layer 2 — Business rule sanity (area > 0, dates logical, harvest year not future)
  Layer 3 — Duplicate detection (NIN uniqueness, name+location collision, farm name+supplier)
  Layer 4 — Spatial overlap detection (shapely — no PostGIS required)
"""
import datetime
import math
from django import forms

from .models import Farm, Farmer, Supplier


def _compute_area_ha(geojson_geometry):
    """
    Compute farm area in hectares from a GeoJSON Polygon geometry dict.
    Uses the spherical excess / Shoelace formula on WGS-84 coordinates.
    Returns a rounded float, or None if the geometry is missing/invalid.
    """
    if not geojson_geometry:
        return None
    try:
        coords = geojson_geometry.get('coordinates', [])
        if not coords:
            return None
        ring = coords[0]  # outer ring only
        if len(ring) < 4:
            return None

        R = 6_371_009  # Earth mean radius in metres
        n = len(ring)
        area_m2 = 0.0
        for i in range(n - 1):
            lon1, lat1 = math.radians(ring[i][0]),   math.radians(ring[i][1])
            lon2, lat2 = math.radians(ring[i + 1][0]), math.radians(ring[i + 1][1])
            area_m2 += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))

        area_m2 = abs(area_m2) * R * R / 2.0
        return round(area_m2 / 10_000, 4)  # → hectares
    except Exception:
        return None


# ── Farmer ────────────────────────────────────────────────────────────────────

CROP_CHOICES = [
    ('Coffee', 'Coffee'),
    ('Oil Palm', 'Oil Palm'),
    ('Guinea Corn/Dawa', 'Guinea Corn/Dawa'),
    ('Acha', 'Acha'),
    ('Soybeans', 'Soybeans'),
    ('Potato', 'Potato'),
    ('Groundnut', 'Groundnut'),
    ('Cocoa', 'Cocoa'),
    ('Cattle', 'Cattle'),
    ('Goat', 'Goat'),
    ('Sheep', 'Sheep'),
    ('Other', 'Other'),
]

_KNOWN_CROPS = {c[0] for c in CROP_CHOICES if c[0] != 'Other'}


class FarmerForm(forms.ModelForm):
    crops = forms.MultipleChoiceField(
        choices=CROP_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Crops / Livestock',
    )
    crops_other = forms.CharField(
        required=False,
        label='Specify other crop / livestock',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Cassava, Yam'}),
    )

    class Meta:
        model  = Farmer
        fields = [
            'first_name', 'last_name', 'gender', 'phone', 'village', 'lga', 'nin',
            'crops', 'consent_given', 'consent_date',
        ]

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        # Pre-populate crops checkboxes from comma-separated model value
        if self.instance and self.instance.pk and self.instance.crops:
            existing = [c.strip() for c in self.instance.crops.split(',') if c.strip()]
            known    = [c for c in existing if c in _KNOWN_CROPS]
            other    = ', '.join(c for c in existing if c not in _KNOWN_CROPS)
            if other:
                known.append('Other')
                self.initial['crops_other'] = other
            self.initial['crops'] = known

    def clean_crops(self):
        crops       = self.cleaned_data.get('crops', [])
        crops_other = self.data.get('crops_other', '').strip()
        known       = [c for c in crops if c != 'Other']
        if 'Other' in crops and crops_other:
            known.append(crops_other)
        return ', '.join(known) if known else ''

    def clean_nin(self):
        import re as _re
        nin = self.cleaned_data.get('nin', '').strip()
        if nin:
            # Canonicalise: strip spaces, dashes, uppercase
            nin = _re.sub(r'[^A-Z0-9]', '', nin.upper())
            # NIN is 11 digits
            if not _re.fullmatch(r'\d{11}', nin):
                raise forms.ValidationError(
                    "NIN must be exactly 11 digits. Remove any spaces or dashes."
                )
            qs = Farmer.objects.filter(company=self.company, nin=nin)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                existing = qs.first()
                raise forms.ValidationError(
                    f"NIN {nin} is already registered to {existing.full_name}. "
                    "Each farmer must have a unique National Identification Number."
                )
        return nin

    def clean(self):
        cleaned_data  = super().clean()
        first_name    = cleaned_data.get('first_name', '').strip()
        last_name     = cleaned_data.get('last_name', '').strip()
        village       = cleaned_data.get('village', '').strip()
        lga           = cleaned_data.get('lga', '').strip()
        f"{first_name} {last_name}".strip()

        if first_name and village and lga:
            qs = Farmer.objects.filter(
                company=self.company,
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                village__iexact=village,
                lga__iexact=lga,
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                existing = qs.first()
                raise forms.ValidationError(
                    f"A farmer with the same name, village, and LGA is already registered "
                    f"({existing.full_name}, {existing.village}, {existing.lga}). "
                    "If this is a different person, add a distinguishing detail to the name."
                )
        return cleaned_data


# ── GeoJSON validation (shared) ───────────────────────────────────────────────

def _validate_geojson_polygon(value):
    """
    Structural validation for a GeoJSON Polygon or MultiPolygon.
    Checks: type, coordinates present, rings closed, lat/lon in valid range.
    The JSONField has already parsed the string to a dict by the time this runs.
    """
    if not value:
        return value

    geo_type = value.get('type')
    if not geo_type:
        raise forms.ValidationError(
            "GeoJSON must include a 'type' field (Polygon or MultiPolygon)."
        )

    # Unwrap Feature if the mapping app exports one
    if geo_type == 'Feature':
        geometry = value.get('geometry') or {}
        geo_type = geometry.get('type')
        coordinates = geometry.get('coordinates')
        if not geo_type or not coordinates:
            raise forms.ValidationError(
                "GeoJSON Feature has no geometry. Re-export the polygon boundary from your mapping app."
            )
    else:
        coordinates = value.get('coordinates')

    if geo_type not in ('Polygon', 'MultiPolygon'):
        raise forms.ValidationError(
            f"GeoJSON type must be Polygon or MultiPolygon — got '{geo_type}'. "
            "Export the farm boundary, not a point or track line."
        )

    if not coordinates:
        raise forms.ValidationError("GeoJSON is missing coordinates.")

    rings = coordinates if geo_type == 'Polygon' else [
        ring for polygon in coordinates for ring in polygon
    ]

    for ring_idx, ring in enumerate(rings, start=1):
        if len(ring) < 4:
            raise forms.ValidationError(
                f"Ring {ring_idx} has only {len(ring)} point(s) — a valid polygon needs at least 4. "
                "The boundary may be incomplete."
            )

        if ring[0] != ring[-1]:
            raise forms.ValidationError(
                f"Ring {ring_idx} is not closed — the first and last coordinate must be identical. "
                "Re-export from your mapping app to fix this."
            )

        for coord_idx, coord in enumerate(ring, start=1):
            if len(coord) < 2:
                raise forms.ValidationError(
                    f"Coordinate {coord_idx} in ring {ring_idx} is malformed (expected [lon, lat])."
                )
            try:
                lon, lat = float(coord[0]), float(coord[1])
            except (ValueError, TypeError):
                raise forms.ValidationError(
                    f"Coordinate {coord_idx} in ring {ring_idx} contains malformed values. "
                    "Ensure GPS data is in standard decimal format (e.g. 7.4951), not scientific notation."
                )
            if not (-180 <= lon <= 180):
                raise forms.ValidationError(
                    f"Longitude {lon} at coordinate {coord_idx} is out of range. "
                    "GeoJSON uses [longitude, latitude] order — your values may be reversed."
                )
            if not (-90 <= lat <= 90):
                raise forms.ValidationError(
                    f"Latitude {lat} at coordinate {coord_idx} is out of range. "
                    "GeoJSON uses [longitude, latitude] order — your values may be reversed."
                )

    # Nigeria bounding box check — catches wrong CRS or swapped lat/lon
    # Uses centroid of the outer ring to avoid false positives on border farms
    _NGA_LON_MIN, _NGA_LON_MAX = 2.5, 15.0
    _NGA_LAT_MIN, _NGA_LAT_MAX = 4.0, 14.2
    outer = rings[0]
    avg_lon = sum(float(c[0]) for c in outer) / len(outer)
    avg_lat = sum(float(c[1]) for c in outer) / len(outer)
    if not (_NGA_LON_MIN <= avg_lon <= _NGA_LON_MAX and _NGA_LAT_MIN <= avg_lat <= _NGA_LAT_MAX):
        raise forms.ValidationError(
            f"This polygon's centre ({avg_lat:.4f}°N, {avg_lon:.4f}°E) falls outside Nigeria. "
            "Check that your GPS app is set to WGS84 and that coordinates are in "
            "[longitude, latitude] order — they are often exported reversed."
        )

    # Self-intersection check — catches figure-8 / crossed-boundary polygons
    # that pass structural checks but produce corrupt area calculations downstream
    try:
        from shapely.geometry import shape as shapely_shape
        poly = shapely_shape({'type': geo_type, 'coordinates': coordinates})
        if not poly.is_valid:
            raise forms.ValidationError(
                "This polygon's boundary crosses itself (self-intersecting geometry) "
                "and could not be repaired automatically. The GPS track likely looped "
                "back across itself in a way that cannot be resolved without re-mapping. "
                "Re-walk the farm boundary and re-export."
            )
    except forms.ValidationError:
        raise
    except ImportError:
        pass  # Shapely not installed — skip check silently
    except Exception:
        raise forms.ValidationError(
            "This polygon could not be processed — the geometry may be degenerate or malformed. "
            "Re-export from your mapping app and try again."
        )

    return value


# ── Field GPS geometry normalisation ─────────────────────────────────────────

def strip_z_coordinates(geometry, precision=6):
    """
    Thin wrapper kept for backwards compatibility.
    Prefer normalize_field_gps_geometry() for new call sites.
    """
    return normalize_field_gps_geometry(geometry, precision=precision)


def normalize_field_gps_geometry(geometry, max_vertices=200, simplify_tolerance=0.00005, precision=6):
    """
    Pre-process field GPS GeoJSON before validation.
    Handles output from any field mapping app (SW Maps, Avenza Maps, ODK Collect,
    QGIS, etc.). Safe to call on any GeoJSON geometry dict; returns geometry
    unchanged if the type is not Polygon or MultiPolygon.

    Applied in order per ring:
      1. Strip elevation (Z) — field GPS apps typically export [lon, lat, elev]
      2. Round to `precision` decimal places (6 ≈ 11 cm — more than enough for
         farm boundary work; also prevents float bloat from Shapely repairs)
      3. Remove consecutive duplicate vertices — GPS pauses produce long runs of
         identical coordinates that inflate vertex counts without adding information
      4. Auto-close the ring if first != last — some apps omit the closing vertex
      5. Simplify if ring still exceeds max_vertices — uses Ramer–Douglas–Peucker
         via Shapely with a default tolerance of 0.00005° (≈ 5 m); falls back to
         the un-simplified ring if Shapely is unavailable or simplification fails

    Applied to the full polygon after ring processing:
      6. Self-intersection repair via buffer(0) — GPS tracks that loop back across
         themselves produce self-intersecting polygons. buffer(0) resolves the
         crossing without altering the farm's actual extent. Falls back silently if
         Shapely is unavailable or the geometry is too degenerate to repair (the
         validator will then surface a clear error message).
    """
    if not geometry:
        return geometry

    geo_type = geometry.get('type')
    coords   = geometry.get('coordinates')
    if not coords:
        return geometry

    def _process_ring(ring):
        # Step 1+2: strip Z and round
        pts = [[round(float(c[0]), precision), round(float(c[1]), precision)] for c in ring]

        # Step 3: remove consecutive duplicates
        deduped = []
        for pt in pts:
            if not deduped or pt != deduped[-1]:
                deduped.append(pt)

        # Step 4: auto-close
        if deduped and deduped[0] != deduped[-1]:
            deduped.append(deduped[0])

        # Step 5: simplify if too many vertices
        if len(deduped) > max_vertices:
            try:
                from shapely.geometry import Polygon as _ShapelyPolygon
                exterior = deduped[:-1]  # Shapely Polygon takes ring without closing repeat
                simplified = _ShapelyPolygon(exterior).exterior.simplify(
                    simplify_tolerance, preserve_topology=True
                )
                simplified_coords = [
                    [round(c[0], precision), round(c[1], precision)]
                    for c in simplified.coords
                ]
                # Shapely's .coords on a LinearRing already closes the ring
                if simplified_coords and simplified_coords[0] != simplified_coords[-1]:
                    simplified_coords.append(simplified_coords[0])
                deduped = simplified_coords
            except Exception:
                pass  # fall back to deduped-but-unsimplified ring

        return deduped

    if geo_type == 'Polygon':
        clean = [_process_ring(ring) for ring in coords]
    elif geo_type == 'MultiPolygon':
        clean = [[_process_ring(ring) for ring in polygon] for polygon in coords]
    else:
        return geometry

    # Step 6: repair self-intersecting geometry before handing to the validator.
    # buffer(0) can produce a MultiPolygon from a Polygon input (e.g. a GPS track
    # that crossed itself splits the area into two valid sub-polygons). We accept
    # that type change — the validator handles MultiPolygon, and the area is correct.
    try:
        from shapely.geometry import shape as _shape, mapping as _mapping
        shp = _shape({'type': geo_type, 'coordinates': clean})
        if not shp.is_valid:
            repaired = shp.buffer(0)
            if repaired.is_valid and repaired.area > 0:
                repaired_geo    = dict(_mapping(repaired))
                repaired_type   = repaired_geo['type']   # may differ from geo_type
                repaired_coords = repaired_geo['coordinates']

                def _reround_ring(ring):
                    return [
                        [round(float(c[0]), precision), round(float(c[1]), precision)]
                        for c in ring
                    ]

                if repaired_type == 'Polygon':
                    clean    = [_reround_ring(r) for r in repaired_coords]
                    geo_type = 'Polygon'
                elif repaired_type == 'MultiPolygon':
                    clean    = [[_reround_ring(r) for r in poly] for poly in repaired_coords]
                    geo_type = 'MultiPolygon'
    except Exception:
        pass  # fall back to pre-repair geometry; validator surfaces a clear error

    return {**geometry, 'type': geo_type, 'coordinates': clean}


# ── Spatial overlap detection (Layer 4) ──────────────────────────────────────

def _geojson_to_shape(geojson):
    """
    Convert a GeoJSON dict (Polygon, MultiPolygon, or Feature wrapper) to a
    shapely geometry. Returns None if conversion fails.
    """
    from shapely.geometry import shape
    if not geojson:
        return None
    try:
        if geojson.get('type') == 'Feature':
            geometry = geojson.get('geometry')
            return shape(geometry) if geometry else None
        return shape(geojson)
    except Exception:
        return None


def _find_overlapping_farm(geojson, company, exclude_pk=None, pct_threshold=0.0):
    """
    Check whether the given GeoJSON polygon overlaps with any existing farm
    in the same company by more than pct_threshold percent of the smaller polygon.

    Returns (Farm, overlap_pct) for the first match above threshold, or (None, 0.0).
    pct_threshold=0.0 means any area overlap triggers a match (used by form validation).
    """
    new_shape = _geojson_to_shape(geojson)
    if new_shape is None:
        return None, 0.0

    if not new_shape.is_valid:
        new_shape = new_shape.buffer(0)

    qs = Farm.objects.filter(company=company).exclude(geolocation__isnull=True)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    for farm in qs.select_related('supplier'):
        if not farm.geolocation:
            continue
        existing_shape = _geojson_to_shape(farm.geolocation)
        if existing_shape is None:
            continue
        try:
            if not existing_shape.is_valid:
                existing_shape = existing_shape.buffer(0)
            intersection_area = new_shape.intersection(existing_shape).area
            if intersection_area <= 0:
                continue
            min_area = min(new_shape.area, existing_shape.area)
            pct = round(intersection_area / min_area * 100, 1) if min_area > 0 else 0.0
            if pct > pct_threshold:
                return farm, pct
        except Exception:
            continue

    return None, 0.0


def _build_farm_overlap_index(company):
    """
    Load all existing farm geometries for a company into a Shapely STRtree.
    Used by the import pipeline to avoid per-row DB queries during overlap checks.
    Returns (STRtree | None, list[shape], list[Farm]).
    """
    from shapely.strtree import STRtree
    farms = list(
        Farm.objects.filter(company=company)
        .exclude(geolocation__isnull=True)
        .select_related('supplier')
    )
    shapes, refs = [], []
    for f in farms:
        s = _geojson_to_shape(f.geolocation)
        if s is not None:
            if not s.is_valid:
                s = s.buffer(0)
            shapes.append(s)
            refs.append(f)
    tree = STRtree(shapes) if shapes else None
    return tree, shapes, refs


def _check_overlap_strtree(new_shape, tree, shapes, refs, pct_threshold=0.0):
    """
    Check new_shape against a pre-built STRtree index.
    Returns (Farm, overlap_pct) for the first match above pct_threshold, or (None, 0.0).
    """
    if tree is None or new_shape is None:
        return None, 0.0
    import numpy as _np
    candidates = tree.query(new_shape)
    for idx in (candidates.tolist() if hasattr(candidates, 'tolist') else candidates):
        existing = shapes[idx]
        try:
            intersection_area = new_shape.intersection(existing).area
            if intersection_area <= 0:
                continue
            min_area = min(new_shape.area, existing.area)
            pct = round(intersection_area / min_area * 100, 1) if min_area > 0 else 0.0
            if pct > pct_threshold:
                return refs[idx], pct
        except Exception:
            continue
    return None, 0.0


# ── Farm (create) ─────────────────────────────────────────────────────────────

class FarmForm(forms.ModelForm):
    class Meta:
        model  = Farm
        fields = [
            'supplier', 'name', 'farmer', 'country', 'state_region',
            'commodity', 'harvest_year',
            'deforestation_risk_status', 'deforestation_reference_date',
            'land_cleared_after_cutoff', 'mapping_date', 'mapped_by_name', 'geolocation',
        ]

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields['name'].label = 'Farm / Plot Name'
        self.fields['mapped_by_name'].label = 'Field Officer'
        if company:
            self.fields['supplier'].queryset = Supplier.objects.filter(company=company)
            self.fields['farmer'].queryset   = Farmer.objects.filter(company=company)

    # ── Layer 1: GeoJSON structural check ─────────────────────────────────────

    def clean_geolocation(self):
        value = self.cleaned_data.get('geolocation')
        value = normalize_field_gps_geometry(value)  # strip Z, dedup, close, simplify
        return _validate_geojson_polygon(value)

    # ── Layer 2: Business rule checks ─────────────────────────────────────────

    def clean_harvest_year(self):
        year = self.cleaned_data.get('harvest_year')
        if year is not None:
            current_year = datetime.date.today().year
            if year > current_year:
                raise forms.ValidationError(
                    f"Harvest year {year} is in the future. "
                    "Enter the most recent completed harvest year."
                )
            if year < 1900:
                raise forms.ValidationError("Harvest year is not valid.")
        return year

    def clean_deforestation_reference_date(self):
        ref_date = self.cleaned_data.get('deforestation_reference_date')
        if ref_date and ref_date > datetime.date(2020, 12, 31):
            raise forms.ValidationError(
                "Deforestation reference date must be on or before 31 December 2020 "
                "for EUDR compliance."
            )
        return ref_date

    # ── Layer 3 + 4: Duplicate detection and spatial overlap ──────────────────

    def clean(self):
        cleaned_data = super().clean()
        name     = cleaned_data.get('name', '').strip()
        supplier = cleaned_data.get('supplier')
        geojson  = cleaned_data.get('geolocation')
        exclude_pk = self.instance.pk if self.instance and self.instance.pk else None

        # Layer 3: duplicate name+supplier
        if name and supplier:
            qs = Farm.objects.filter(
                company=self.company,
                name__iexact=name,
                supplier=supplier,
            )
            if exclude_pk:
                qs = qs.exclude(pk=exclude_pk)
            if qs.exists():
                raise forms.ValidationError(
                    f"A farm named '{name}' is already registered under {supplier.name}. "
                    "Check if this is a duplicate entry."
                )

        # Layer 4: spatial overlap
        # On edit, only check if the polygon was actually changed — farms that
        # already exist in the DB with overlapping boundaries (e.g. imported in
        # the same batch) should not block unrelated metadata edits.
        if geojson and self.company:
            geometry_changed = True
            if exclude_pk and self.instance and self.instance.geolocation:
                import json
                geometry_changed = (
                    json.dumps(geojson, sort_keys=True)
                    != json.dumps(self.instance.geolocation, sort_keys=True)
                )
            if geometry_changed:
                overlapping, overlap_pct = _find_overlapping_farm(
                    geojson, self.company, exclude_pk=exclude_pk
                )
                if overlapping:
                    raise forms.ValidationError(
                        f"This farm boundary overlaps with '{overlapping.name}' "
                        f"({overlapping.supplier.name}) by {overlap_pct}%. "
                        "Overlapping boundaries produce inaccurate area totals and "
                        "invalid compliance records. Adjust the boundary before saving."
                    )

        return cleaned_data


# ── Farm (update — adds verification fields) ──────────────────────────────────

class FarmUpdateForm(FarmForm):
    class Meta(FarmForm.Meta):
        fields = FarmForm.Meta.fields + [
            'is_eudr_verified', 'verified_by', 'verified_date', 'verification_expiry',
            'fvf_land_acquisition', 'fvf_land_tenure', 'fvf_years_farming',
            'fvf_untouched_forest', 'fvf_expansion_intent',
            'fvf_consent_given', 'fvf_consent_date',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.company:
            from apps.users.models import CustomUser
            self.fields['verified_by'].queryset = CustomUser.objects.filter(company=self.company)

    def clean(self):
        cleaned_data = super().clean()
        verified_date      = cleaned_data.get('verified_date')
        verification_expiry = cleaned_data.get('verification_expiry')

        if verified_date and verification_expiry and verification_expiry <= verified_date:
            self.add_error(
                'verification_expiry',
                "Verification expiry must be after the verified date."
            )

        return cleaned_data
