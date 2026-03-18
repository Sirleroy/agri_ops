from django.db import models
from apps.companies.models import Company


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
    farmer_name    = models.CharField(max_length=255, blank=True)
    geolocation    = models.JSONField(
                       null=True, blank=True,
                       help_text="GeoJSON Polygon. Export from SW Maps or NCAN Farm Mapper."
                     )
    area_hectares  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    country        = models.CharField(max_length=100)
    state_region   = models.CharField(max_length=100, blank=True)
    commodity      = models.CharField(max_length=100, help_text="e.g. Soy, Maize, Cocoa")

    # EUDR compliance fields
    deforestation_risk_status = models.CharField(
        max_length=20, choices=RISK_CHOICES, default='standard'
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
    def is_verification_current(self):
        if not self.is_eudr_verified:
            return False
        if not self.verification_expiry:
            return True
        from django.utils import timezone
        return self.verification_expiry >= timezone.now().date()

    @property
    def compliance_status(self):
        if not self.is_eudr_verified:
            return 'pending'
        if not self.is_verification_current:
            return 'expired'
        if self.deforestation_risk_status == 'high':
            return 'high_risk'
        return 'compliant'


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
