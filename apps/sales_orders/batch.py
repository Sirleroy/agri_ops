"""
Batch model — links a SalesOrder to a set of Farms for EUDR traceability.
Generates a unique batch number and a public token for QR code URL.
"""
import uuid
from django.db import models
from apps.companies.models import Company
from apps.suppliers.models import Farm


def generate_batch_number(company_name, commodity):
    """Generate a batch number like SOY-AKE-2026-0001"""
    from django.utils import timezone
    from apps.sales_orders.models import Batch
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
    farms        = models.ManyToManyField(Farm, blank=True, related_name='batches')
    batch_number = models.CharField(max_length=50, unique=True)
    commodity    = models.CharField(max_length=100)
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Batches'

    def __str__(self):
        return self.batch_number

    @property
    def trace_url(self):
        from django.conf import settings
        site_url = getattr(settings, 'SITE_URL', 'https://app.agriops.io')
        return f"{site_url}/trace/{self.public_token}/"

    def save(self, *args, **kwargs):
        if not self.batch_number:
            self.batch_number = generate_batch_number(
                self.company.name, self.commodity
            )
        super().save(*args, **kwargs)
