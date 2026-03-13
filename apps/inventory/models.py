from django.db import models
from apps.companies.models import Company
from apps.products.models import Product


class Inventory(models.Model):

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='inventory'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='inventory'
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    warehouse_location = models.CharField(max_length=255, blank=True)
    low_stock_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=10.00
    )
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Inventories'
        ordering = ['product']
        unique_together = ['company', 'product', 'warehouse_location']

    @property
    def is_low_stock(self):
        return self.quantity <= self.low_stock_threshold

    def __str__(self):
        return f"{self.product.name} — {self.quantity} {self.product.unit}"
