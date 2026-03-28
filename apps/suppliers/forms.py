"""
Supplier app forms — Farmer and Farm with data quality validation.

Validation layers applied here:
  Layer 1 — GeoJSON structural validity (type, closed ring, coordinate range)
  Layer 2 — Business rule sanity (area > 0, dates logical, harvest year not future)
  Layer 3 — Duplicate detection (NIN uniqueness, name+location collision, farm name+supplier)
"""
import datetime
from django import forms

from .models import Farm, Farmer, Supplier


# ── Farmer ────────────────────────────────────────────────────────────────────

class FarmerForm(forms.ModelForm):
    class Meta:
        model  = Farmer
        fields = ['name', 'phone', 'village', 'lga', 'nin']

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company

    def clean_nin(self):
        nin = self.cleaned_data.get('nin', '').strip()
        if nin:
            qs = Farmer.objects.filter(company=self.company, nin=nin)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                existing = qs.first()
                raise forms.ValidationError(
                    f"NIN {nin} is already registered to {existing.name}. "
                    "Each farmer must have a unique National Identification Number."
                )
        return nin

    def clean(self):
        cleaned_data = super().clean()
        name    = cleaned_data.get('name', '').strip()
        village = cleaned_data.get('village', '').strip()
        lga     = cleaned_data.get('lga', '').strip()

        if name and village and lga:
            qs = Farmer.objects.filter(
                company=self.company,
                name__iexact=name,
                village__iexact=village,
                lga__iexact=lga,
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                existing = qs.first()
                raise forms.ValidationError(
                    f"A farmer with the same name, village, and LGA is already registered "
                    f"({existing.name}, {existing.village}, {existing.lga}). "
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

    # ── Layer 3: Duplicate farm detection ─────────────────────────────────────

    def clean(self):
        cleaned_data = super().clean()
        name     = cleaned_data.get('name', '').strip()
        supplier = cleaned_data.get('supplier')

        if name and supplier:
            qs = Farm.objects.filter(
                company=self.company,
                name__iexact=name,
                supplier=supplier,
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f"A farm named '{name}' is already registered under {supplier.name}. "
                    "Check if this is a duplicate entry."
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
