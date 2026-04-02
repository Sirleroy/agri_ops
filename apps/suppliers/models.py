import datetime
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.companies.models import Company


# Commodities covered by EU Deforestation Regulation (EU) 2023/1115
EUDR_COMMODITIES = {
    'cattle', 'cocoa', 'coffee', 'oil palm', 'palm oil', 'rubber', 'soya', 'soy', 'wood',
}


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

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

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

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} — {self.get_category_display()}"


class Farm(models.Model):
    RISK_CHOICES = [
        ('low',      'Low Risk'),
        ('standard', 'Standard Risk'),
        ('high',     'High Risk'),
    ]

    company        = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='farms')
    supplier       = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='farms')
    name           = models.CharField(max_length=255)
    farmer         = models.ForeignKey(Farmer, null=True, blank=True, on_delete=models.SET_NULL, related_name='farms')
    farmer_name    = models.CharField(max_length=255, blank=True)
    geolocation    = models.JSONField(
                       null=True, blank=True,
                       help_text="GeoJSON Polygon. Export from SW Maps or NCAN Farm Mapper."
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
    mapping_date   = models.DateField(null=True, blank=True)
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

    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} — {self.supplier.name}"

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
    file        = models.FileField(upload_to='compliance_docs/%Y/%m/')
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
