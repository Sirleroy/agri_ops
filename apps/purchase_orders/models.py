from django.db import models
from apps.companies.models import Company
from apps.companies.managers import TenantManager
from apps.suppliers.models import Supplier
from apps.products.models import Product


class PurchaseOrder(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('ordered', 'Ordered'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='purchase_orders'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        related_name='purchase_orders'
    )
    order_number = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    order_date = models.DateField(auto_now_add=True)
    expected_delivery = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-created_at']
        unique_together = [('company', 'order_number')]
        indexes = [
            models.Index(fields=['company', '-order_date'], name='po_company_date_idx'),
            models.Index(fields=['company', 'status'], name='po_company_status_idx'),
        ]

    def __str__(self):
        return f"PO-{self.order_number} — {self.supplier} ({self.get_status_display()})"


class PurchaseOrderItem(models.Model):

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='purchase_items'
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
