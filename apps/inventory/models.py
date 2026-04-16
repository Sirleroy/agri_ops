from django.db import models
from apps.companies.models import Company
from apps.companies.managers import TenantManager
from apps.products.models import Product


class Inventory(models.Model):

    QUALITY_GRADE_CHOICES = [
        ('A', 'Grade A — Premium'),
        ('B', 'Grade B — Standard'),
        ('C', 'Grade C — Below Standard'),
        ('off', 'Off Grade'),
    ]

    company             = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='inventory')
    product             = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory')
    quantity            = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    warehouse_location  = models.CharField(max_length=255, blank=True)
    low_stock_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)

    # ── Phase 4 commodity fields ──────────────────────────────
    lot_number      = models.CharField(
                        max_length=50, blank=True,
                        help_text="e.g. FN-2026-004. Auto-generated if left blank."
                      )
    moisture_content = models.DecimalField(
                        max_digits=5, decimal_places=2,
                        null=True, blank=True,
                        help_text="Moisture percentage at time of intake"
                      )
    quality_grade   = models.CharField(
                        max_length=10,
                        choices=QUALITY_GRADE_CHOICES,
                        blank=True,
                        help_text="Quality grade assigned at intake inspection"
                      )
    harvest_date    = models.DateField(null=True, blank=True)
    origin_state    = models.CharField(
                        max_length=100, blank=True,
                        help_text="State or region of origin e.g. Benue, Kano"
                      )

    last_updated    = models.DateTimeField(auto_now=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        verbose_name_plural = 'Inventories'
        ordering = ['product']
        unique_together = ['company', 'product', 'warehouse_location']

    @property
    def is_low_stock(self):
        return self.quantity <= self.low_stock_threshold

    def __str__(self):
        lot = f" [{self.lot_number}]" if self.lot_number else ""
        return f"{self.product.name}{lot} — {self.quantity} {self.product.unit}"

    def save(self, *args, **kwargs):
        # Auto-generate lot number if not provided
        if not self.lot_number:
            from django.utils import timezone
            prefix = self.product.name[:2].upper() if self.product else "XX"
            self.lot_number = f"{prefix}-{timezone.now().strftime('%Y-%m-%d')}-{self.pk or '?'}"
        super().save(*args, **kwargs)
        # Fix lot number after first save when pk is now available
        if '?' in self.lot_number:
            prefix = self.product.name[:2].upper() if self.product else "XX"
            self.lot_number = f"{prefix}-{timezone.now().strftime('%Y-%m-%d')}-{self.pk}"
            Inventory.objects.filter(pk=self.pk).update(lot_number=self.lot_number)
