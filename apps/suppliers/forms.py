"""
Supplier app forms — Farmer and Farm with data quality validation.

Validation layers applied here:
  Layer 1 — GeoJSON structural validity (type, closed ring, coordinate range)
  Layer 2 — Business rule sanity (area > 0, dates logical, harvest year not future)
  Layer 3 — Duplicate detection (NIN uniqueness, name+location collision, farm name+supplier)
  Layer 4 — Spatial overlap detection (shapely — no PostGIS required)
"""
import datetime
from django import forms

from .models import Farm, Farmer, Supplier


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
        nin = self.cleaned_data.get('nin', '').strip()
        if nin:
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
        full_name     = f"{first_name} {last_name}".strip()

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
            lon, lat = coord[0], coord[1]
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

    return value


# ── Z-coordinate stripping (SW Maps exports [lon, lat, elevation]) ───────────

def strip_z_coordinates(geometry):
    """
    Remove the elevation (Z) value from GeoJSON polygon coordinates.
    SW Maps exports 3D coordinates [lon, lat, elevation] — strip to [lon, lat]
    for clean storage and compatibility with Shapely/validators.
    """
    if not geometry:
        return geometry
    geo_type = geometry.get('type')
    coords   = geometry.get('coordinates')
    if not coords:
        return geometry

    def _strip_ring(ring):
        return [[c[0], c[1]] for c in ring]

    if geo_type == 'Polygon':
        clean = [_strip_ring(ring) for ring in coords]
    elif geo_type == 'MultiPolygon':
        clean = [[_strip_ring(ring) for ring in polygon] for polygon in coords]
    else:
        return geometry

    return {**geometry, 'coordinates': clean}


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


def _find_overlapping_farm(geojson, company, exclude_pk=None):
    """
    Check whether the given GeoJSON polygon overlaps (shares area, not just
    a boundary edge) with any existing farm in the same company.
    Returns the first overlapping Farm instance, or None.
    """
    new_shape = _geojson_to_shape(geojson)
    if new_shape is None:
        return None

    # Attempt to repair self-intersections before comparison
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
            # intersection.area > 0 catches containment and overlap; ignores shared edges
            if new_shape.intersection(existing_shape).area > 0:
                return farm
        except Exception:
            continue  # skip malformed stored polygons — don't block the submission

    return None


# ── Farm (create) ─────────────────────────────────────────────────────────────

class FarmForm(forms.ModelForm):
    class Meta:
        model  = Farm
        fields = [
            'supplier', 'name', 'farmer', 'country', 'state_region',
            'commodity', 'area_hectares', 'harvest_year',
            'deforestation_risk_status', 'deforestation_reference_date',
            'land_cleared_after_cutoff', 'mapping_date', 'mapped_by', 'geolocation',
        ]

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields['name'].label = 'Farm / Plot Name'
        if company:
            self.fields['supplier'].queryset = Supplier.objects.filter(company=company)
            self.fields['farmer'].queryset   = Farmer.objects.filter(company=company)
            from apps.users.models import CustomUser
            self.fields['mapped_by'].queryset = CustomUser.objects.filter(company=company)

    # ── Layer 1: GeoJSON structural check ─────────────────────────────────────

    def clean_geolocation(self):
        return _validate_geojson_polygon(self.cleaned_data.get('geolocation'))

    # ── Layer 2: Business rule checks ─────────────────────────────────────────

    def clean_area_hectares(self):
        area = self.cleaned_data.get('area_hectares')
        if area is not None and area <= 0:
            raise forms.ValidationError("Area must be greater than 0 hectares.")
        return area

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
        if geojson and self.company:
            overlapping = _find_overlapping_farm(geojson, self.company, exclude_pk=exclude_pk)
            if overlapping:
                raise forms.ValidationError(
                    f"This farm boundary overlaps with '{overlapping.name}' "
                    f"({overlapping.supplier.name}). Overlapping boundaries produce "
                    "inaccurate area totals and invalid compliance records. "
                    "Adjust the boundary before saving."
                )

        return cleaned_data


# ── Farm (update — adds verification fields) ──────────────────────────────────

class FarmUpdateForm(FarmForm):
    class Meta(FarmForm.Meta):
        fields = FarmForm.Meta.fields + [
            'is_eudr_verified', 'verified_by', 'verified_date', 'verification_expiry',
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
