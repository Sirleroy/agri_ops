"""
Batch model — links a SalesOrder to a set of Farms for EUDR traceability.
Generates a unique batch number and a public token for QR code URL.
"""
import uuid
from django.db import models, IntegrityError
from django.core.validators import MinValueValidator
from apps.companies.models import Company
from apps.companies.managers import TenantManager
from apps.suppliers.models import Farm
from apps.purchase_orders.models import PurchaseOrder


def generate_batch_number(company_name, commodity):
    """Generate a batch number like SOY-AKE-2026-0001"""
    from django.utils import timezone
    from django.apps import apps
    Batch = apps.get_model('sales_orders', 'Batch')
    prefix = commodity[:3].upper()
    company_code = ''.join(w[0] for w in company_name.split()[:2]).upper()
    year = timezone.now().year
    count = Batch.objects.filter(
        company__name=company_name,
        batch_number__startswith=f"{prefix}-{company_code}-{year}-"
    ).count() + 1
    return f"{prefix}-{company_code}-{year}-{count:04d}"


class Batch(models.Model):
    company      = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='batches')
    sales_order  = models.ForeignKey(
                     'sales_orders.SalesOrder', on_delete=models.SET_NULL,
                     null=True, blank=True, related_name='batches'
                   )
    farms          = models.ManyToManyField(Farm, blank=True, related_name='batches')
    purchase_orders = models.ManyToManyField(PurchaseOrder, blank=True, related_name='batches')
    batch_number = models.CharField(max_length=50, unique=True)
    commodity    = models.CharField(max_length=100)
    quantity_kg  = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Net mass in kilograms — required for EUDR due diligence statement (Article 9)."
    )
    is_locked    = models.BooleanField(
        default=False,
        help_text="Locked batches cannot be deleted. Set automatically on dispatch; manual lock also supported."
    )
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Batches'
        indexes = [
            models.Index(fields=['company', '-created_at'], name='batch_company_created_idx'),
            models.Index(fields=['company', 'commodity'], name='batch_company_commodity_idx'),
            models.Index(fields=['is_locked'], name='batch_locked_idx'),
        ]

    def __str__(self):
        return self.batch_number

    @property
    def trace_url(self):
        from django.conf import settings
        site_url = getattr(settings, 'SITE_URL', 'https://app.agriops.io')
        return f"{site_url}/trace/{self.public_token}/"

    def delete(self, *args, **kwargs):
        if self.is_locked:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("This batch is locked and cannot be deleted. Locked batches must be retained for 5 years under EUDR Article 9.")
        super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.batch_number:
            for _ in range(10):
                self.batch_number = generate_batch_number(
                    self.company.name, self.commodity
                )
                try:
                    super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    self.batch_number = ''
            raise IntegrityError("Could not generate a unique batch number after 10 attempts.")
        super().save(*args, **kwargs)
