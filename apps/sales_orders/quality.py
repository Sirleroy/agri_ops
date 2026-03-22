"""
Batch quality and export compliance models.
- PhytosanitaryCertificate: NAQS phytosanitary cert per batch (required for all Nigerian agricultural exports)
- BatchQualityTest: Lab test records for MRL (EU 396/2005) and aflatoxin (EU 1881/2006) compliance
"""
from django.db import models
from apps.companies.models import Company


class PhytosanitaryCertificate(models.Model):
    company          = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='phytosanitary_certs')
    batch            = models.ForeignKey('sales_orders.Batch', on_delete=models.CASCADE, related_name='phytosanitary_certs')
    certificate_number = models.CharField(max_length=100)
    issuing_office   = models.CharField(
        max_length=255, blank=True,
        help_text="NAQS zonal office that issued the certificate (e.g. NAQS Apapa Seaport)"
    )
    inspector_name   = models.CharField(max_length=255, blank=True)
    inspection_date  = models.DateField(null=True, blank=True)
    issued_date      = models.DateField(null=True, blank=True)
    expiry_date      = models.DateField(null=True, blank=True)
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Phytosanitary Certificate'

    def __str__(self):
        return f"NAQS {self.certificate_number} — {self.batch.batch_number}"

    @property
    def is_current(self):
        if not self.expiry_date:
            return True
        from django.utils import timezone
        return self.expiry_date >= timezone.now().date()


class BatchQualityTest(models.Model):
    TEST_TYPE_CHOICES = [
        ('mrl',             'Pesticide MRL (EU 396/2005)'),
        ('aflatoxin',       'Aflatoxin (EU 1881/2006)'),
        ('moisture',        'Moisture Content'),
        ('heavy_metals',    'Heavy Metals'),
        ('microbiological', 'Microbiological'),
        ('other',           'Other'),
    ]
    RESULT_CHOICES = [
        ('pass',    'Pass — within limits'),
        ('fail',    'Fail — exceeds limits'),
        ('pending', 'Pending'),
    ]

    company          = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='batch_quality_tests')
    batch            = models.ForeignKey('sales_orders.Batch', on_delete=models.CASCADE, related_name='quality_tests')
    test_type        = models.CharField(max_length=30, choices=TEST_TYPE_CHOICES)
    lab_name         = models.CharField(max_length=255)
    lab_certificate_ref = models.CharField(max_length=100, blank=True)
    test_date        = models.DateField(null=True, blank=True)
    result           = models.CharField(max_length=10, choices=RESULT_CHOICES, default='pending')
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-test_date', 'test_type']
        verbose_name = 'Batch Quality Test'

    def __str__(self):
        return f"{self.get_test_type_display()} — {self.batch.batch_number} ({self.get_result_display()})"
