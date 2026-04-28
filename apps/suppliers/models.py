import datetime
import os
import re
from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.companies.models import Company
from apps.companies.managers import TenantManager


_COMPLIANCE_DOC_ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.geojson', '.json'}
_COMPLIANCE_DOC_MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_compliance_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in _COMPLIANCE_DOC_ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(_COMPLIANCE_DOC_ALLOWED_EXTENSIONS))
        raise ValidationError(f"File type '{ext}' is not allowed. Accepted types: {allowed}.")
    if file.size > _COMPLIANCE_DOC_MAX_SIZE:
        raise ValidationError("File must not exceed 10 MB.")


# Commodities covered by EU Deforestation Regulation (EU) 2023/1115 as amended by (EU) 2025/2650
EUDR_COMMODITIES = {
    'cattle', 'cocoa', 'coffee', 'oil palm', 'palm oil', 'rubber', 'soya', 'soy', 'wood',
}


def _normalise_ng_phone(raw):
    """
    Normalise a Nigerian phone number to E.164 format (+234XXXXXXXXXX).
    Accepts:  08012345678 · 8012345678 · +2348012345678 · 234 801 234 5678
    Returns:  +2348012345678  or the original string if it doesn't look Nigerian.
    """
    if not raw:
        return raw
    digits = re.sub(r'\D', '', str(raw))
    if len(digits) == 11 and digits.startswith('0'):
        return '+234' + digits[1:]          # 08012345678  → +2348012345678
    if len(digits) == 13 and digits.startswith('234'):
        return '+' + digits                 # 2348012345678 → +2348012345678
    if len(digits) == 14 and digits.startswith('2340'):
        return '+234' + digits[4:]          # rare: 23408012345678 double-prefix
    return raw  # not a recognisable Nigerian number — store as-is


class Farmer(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]

    company        = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='farmers')
    first_name     = models.CharField(max_length=150)
    last_name      = models.CharField(max_length=150, blank=True)
    gender         = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    phone          = models.CharField(max_length=20, blank=True)
    village        = models.CharField(max_length=100, blank=True)
    lga            = models.CharField(max_length=100, blank=True, verbose_name="LGA")
    nin            = models.CharField(max_length=20, blank=True, verbose_name="NIN",
                                      help_text="National Identification Number")
    crops          = models.CharField(max_length=255, blank=True,
                                      help_text="Comma-separated list of crops/livestock")
    consent_given  = models.BooleanField(default=False)
    consent_date   = models.DateField(null=True, blank=True)
    # Bank details — parked, no UI until tenant request
    bank_name      = models.CharField(max_length=150, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    objects = TenantManager()

    def save(self, *args, **kwargs):
        # Name — title-case, strip whitespace
        if self.first_name:
            self.first_name = self.first_name.strip().title()
        if self.last_name:
            self.last_name = self.last_name.strip().title()
        # Phone — E.164 normalisation
        if self.phone:
            self.phone = _normalise_ng_phone(self.phone)
        # NIN — digits only, uppercase, strip spaces/dashes
        if self.nin:
            import re as _re
            self.nin = _re.sub(r'[^A-Z0-9]', '', self.nin.strip().upper())
        # LGA / State — canonical lookup
        if self.lga or self.village:
            from apps.suppliers.ng_geodata import canonicalise_lga_state
            canonical_lga, canonical_state = canonicalise_lga_state(
                self.lga or '', getattr(self, 'state_region', '') or ''
            )
            if canonical_lga:
                self.lga = canonical_lga
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_phone(self):
        """Local format (08XXXXXXXXXX) — compact for display and PDF."""
        if self.phone and self.phone.startswith('+234'):
            return '0' + self.phone[4:]
        return self.phone or '—'

    @property
    def missing_fields(self):
        """Fields required for a complete farmer profile (phone, NIN, village)."""
        missing = []
        if not self.phone:
            missing.append('Phone')
        if not self.nin:
            missing.append('NIN')
        if not self.village:
            missing.append('Village')
        return missing

    @property
    def is_complete(self):
        return not self.missing_fields

    def __str__(self):
        return self.full_name or f"Farmer #{self.pk}"


class Supplier(models.Model):
    CATEGORY_CHOICES = [
        ('seeds', 'Seeds'),
        ('fertilizer', 'Fertilizer'),
        ('equipment', 'Equipment'),
        ('livestock_feed', 'Livestock Feed'),
        ('chemicals', 'Chemicals'),
        ('packaging', 'Packaging'),
        ('cooperative', 'Cooperative'),
        ('processor', 'Processor'),
        ('distributor', 'Distributor'),
        ('exporter', 'Exporter'),
        ('other', 'Other'),
    ]
    company        = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='suppliers')
    name           = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    phone          = models.CharField(max_length=20, blank=True)
    email          = models.EmailField(blank=True)
    category       = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    country        = models.CharField(max_length=100, blank=True)
    city           = models.CharField(max_length=100, blank=True)
    address        = models.TextField(blank=True)
    is_active      = models.BooleanField(default=True)
    reliability_score = models.DecimalField(
        max_digits=4, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Reliability score 0-10. Updated based on delivery history."
    )
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if self.phone:
            self.phone = _normalise_ng_phone(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} — {self.get_category_display()}"


class Farm(models.Model):
    RISK_CHOICES = [
        ('low',      'Low Risk'),
        ('standard', 'Standard Risk'),
        ('high',     'High Risk'),
    ]

    company        = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='farms')
    supplier       = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name='farms')
    name           = models.CharField(max_length=255)
    farmer         = models.ForeignKey(Farmer, null=True, blank=True, on_delete=models.SET_NULL, related_name='farms')
    farmer_name    = models.CharField(max_length=255, blank=True)
    geolocation    = models.JSONField(
                       null=True, blank=True,
                       help_text="GeoJSON Polygon. Export from SW Maps or NCAN Farm Mapper."
                     )
    raw_geolocation = models.JSONField(
                       null=True, blank=True,
                       help_text="Original pre-normalisation geometry from the import file. Null when geometry was not modified or farm was created manually."
                     )
    geometry_hash  = models.CharField(
                       max_length=64, blank=True, default='',
                       help_text="SHA-256 of the canonical geolocation JSON. Immutability verification."
                     )
    area_hectares  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    country        = models.CharField(max_length=100)
    state_region   = models.CharField(max_length=100, blank=True)
    commodity      = models.CharField(max_length=100, help_text="e.g. Soy, Maize, Cocoa")

    # EUDR compliance fields
    deforestation_risk_status = models.CharField(
        max_length=20, choices=RISK_CHOICES, default='standard'
    )
    # Cut-off date evidence: must confirm land status as of 31 Dec 2020 (Article 2(28))
    deforestation_reference_date = models.DateField(
        null=True, blank=True,
        default=datetime.date(2020, 12, 31),
        help_text="Date of the evidence baseline for deforestation status. Must be on or before 31 Dec 2020 for EUDR compliance."
    )
    land_cleared_after_cutoff = models.BooleanField(
        null=True, blank=True,
        help_text="Was this land cleared or subject to deforestation after 31 December 2020? Yes = disqualified from EUDR."
    )
    harvest_year   = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Most recent harvest year on this plot (e.g. 2024). Required for EUDR due diligence statement."
    )
    mapping_date    = models.DateField(null=True, blank=True)
    mapped_by_name  = models.CharField(
                        max_length=150, blank=True, default='',
                        help_text="Field officer name as recorded in the import file (free text — not a platform user)."
                      )
    mapped_by      = models.ForeignKey(
                       'users.CustomUser', null=True, blank=True,
                       on_delete=models.SET_NULL,
                       related_name='farms_mapped'
                     )
    is_eudr_verified  = models.BooleanField(default=False)
    verified_by       = models.ForeignKey(
                          'users.CustomUser', null=True, blank=True,
                          on_delete=models.SET_NULL,
                          related_name='farms_verified'
                        )
    verified_date     = models.DateField(null=True, blank=True)
    verification_expiry = models.DateField(null=True, blank=True)

    # Field Verification Form (FVF) — answers transcribed from signed paper form
    FVF_ACQUISITION_CHOICES = [
        ('inherited', 'Inherited'),
        ('bought',    'Bought from neighbour'),
        ('granted',   'Granted by local leader'),
    ]
    FVF_TENURE_CHOICES = [
        ('title_deed',       'Title Deed'),
        ('village_consent',  'Village Consent'),
    ]
    fvf_land_acquisition = models.CharField(
        max_length=20, choices=FVF_ACQUISITION_CHOICES, blank=True,
        help_text="How did the farmer acquire this land?"
    )
    fvf_land_tenure = models.CharField(
        max_length=20, choices=FVF_TENURE_CHOICES, blank=True,
        help_text="Does the farmer hold a title deed or village consent?"
    )
    fvf_years_farming = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="How many years has the farmer been planting on this plot?"
    )
    fvf_untouched_forest = models.BooleanField(
        null=True, blank=True,
        help_text="Is there any untouched forest remaining on this property?"
    )
    fvf_expansion_intent = models.BooleanField(
        null=True, blank=True,
        help_text="To expand, would the farmer cut trees? (forward deforestation risk)"
    )
    fvf_consent_given = models.BooleanField(
        default=False,
        help_text="Farmer has signed the FVF consent block. Paper form is on file."
    )
    fvf_consent_date = models.DateField(
        null=True, blank=True,
        help_text="Date the farmer signed the FVF consent (ties digital record to paper)."
    )

    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['company', 'is_eudr_verified'], name='farm_company_eudr_idx'),
            models.Index(fields=['company', 'commodity'], name='farm_company_commodity_idx'),
            models.Index(fields=['company', 'deforestation_risk_status'], name='farm_company_risk_idx'),
            models.Index(fields=['company', 'supplier'], name='farm_company_supplier_idx'),
        ]

    def __str__(self):
        return f"{self.name} — {self.supplier.name}"

    def save(self, *args, **kwargs):
        # Commodity — canonical name
        if self.commodity:
            from apps.suppliers.ng_geodata import normalise_commodity
            self.commodity = normalise_commodity(self.commodity)
        # Area + geometry hash — computed from polygon boundary
        if self.geolocation:
            import hashlib, json as _json
            from apps.suppliers.forms import _compute_area_ha
            computed = _compute_area_ha(self.geolocation)
            if computed is not None:
                self.area_hectares = computed
            canonical = _json.dumps(self.geolocation, sort_keys=True, separators=(',', ':'))
            self.geometry_hash = hashlib.sha256(canonical.encode()).hexdigest()
        else:
            self.geometry_hash = ''
        super().save(*args, **kwargs)

    @property
    def is_eudr_commodity(self):
        """True if this farm's commodity falls under EUDR 2023/1115 scope."""
        return self.commodity.lower().strip() in EUDR_COMMODITIES

    @property
    def is_disqualified(self):
        """True if land was cleared after the 31 Dec 2020 cut-off — automatically ineligible for EUDR."""
        return self.land_cleared_after_cutoff is True

    @property
    def is_verification_current(self):
        if not self.is_eudr_verified:
            return False
        if not self.verification_expiry:
            return True
        from django.utils import timezone
        return self.verification_expiry >= timezone.now().date()

    @property
    def compliance_status(self):
        if self.is_disqualified:
            return 'disqualified'
        if not self.is_eudr_verified:
            return 'pending'
        if not self.is_verification_current:
            return 'expired'
        if self.deforestation_risk_status == 'high':
            return 'high_risk'
        return 'compliant'


class FarmImportLog(models.Model):
    company       = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='farm_import_logs')
    uploaded_by   = models.ForeignKey(
                      'users.CustomUser', on_delete=models.SET_NULL,
                      null=True, blank=True, related_name='farm_import_logs'
                    )
    supplier      = models.ForeignKey(
                      Supplier, on_delete=models.SET_NULL,
                      null=True, blank=True, related_name='farm_import_logs'
                    )
    filename      = models.CharField(max_length=255, blank=True)
    dry_run       = models.BooleanField(default=False)
    total         = models.PositiveIntegerField(default=0)
    created       = models.PositiveIntegerField(default=0)
    would_create  = models.PositiveIntegerField(default=0)
    duplicates    = models.PositiveIntegerField(default=0)
    blocked       = models.PositiveIntegerField(default=0)
    errors        = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    auto_corrected = models.PositiveIntegerField(default=0)
    error_detail       = models.JSONField(default=list)
    blocked_detail     = models.JSONField(default=list)
    warning_detail     = models.JSONField(default=list)
    transformation_log = models.JSONField(default=list)
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        label = 'DRY RUN' if self.dry_run else f'{self.created} created'
        return f"{self.created_at:%Y-%m-%d %H:%M} — {self.supplier} — {label}"


class FarmCertification(models.Model):
    CERT_TYPE_CHOICES = [
        ('organic_eu',          'Organic EU (2018/848)'),
        ('globalgap',           'GlobalG.A.P.'),
        ('fairtrade',           'Fairtrade'),
        ('rainforest_alliance', 'Rainforest Alliance'),
        ('iscc',                'ISCC (Sustainability & Carbon)'),
        ('other',               'Other'),
    ]

    company          = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='farm_certifications')
    farm             = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='certifications')
    cert_type        = models.CharField(max_length=30, choices=CERT_TYPE_CHOICES)
    certifying_body  = models.CharField(max_length=255, help_text="e.g. ECOCERT, Control Union, SGS")
    certificate_number = models.CharField(max_length=100, blank=True)
    issued_date      = models.DateField(null=True, blank=True)
    expiry_date      = models.DateField(null=True, blank=True)
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['cert_type']

    def __str__(self):
        return f"{self.get_cert_type_display()} — {self.farm.name}"

    @property
    def is_current(self):
        if not self.expiry_date:
            return True
        from django.utils import timezone
        return self.expiry_date >= timezone.now().date()


class ComplianceDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ('farm_map',        'Farm Map'),
        ('satellite_image', 'Satellite Image'),
        ('land_registry',   'Land Registry'),
        ('certification',   'Third-Party Certification'),
        ('declaration',     'Farmer Declaration'),
        ('other',           'Other'),
    ]

    company     = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='compliance_docs')
    farm        = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='documents')
    doc_type    = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    file        = models.FileField(upload_to='compliance_docs/%Y/%m/', validators=[validate_compliance_file])
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
                    'users.CustomUser', on_delete=models.SET_NULL,
                    null=True, blank=True
                  )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_current  = models.BooleanField(default=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.get_doc_type_display()} — {self.farm.name}"
