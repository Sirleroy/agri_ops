from django.db import models
from apps.companies.models import Company
from apps.companies.managers import TenantManager
from apps.products.models import Product
from django.conf import settings


class SalesOrder(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('dispatched', 'Dispatched'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='sales_orders'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_orders'
    )
    order_number = models.CharField(max_length=50, unique=True)
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    order_date = models.DateField(auto_now_add=True)
    # Export compliance references
    nxp_reference = models.CharField(
        max_length=50, blank=True,
        help_text="CBN Form NXP reference number — registers export proceeds obligation with authorised dealer bank."
    )
    certificate_of_origin_ref = models.CharField(
        max_length=50, blank=True,
        help_text="Certificate of Origin reference number issued by Nigerian Chamber of Commerce / Customs."
    )
    is_eu_export = models.BooleanField(
        default=False,
        help_text="Flag for EU-bound shipments. Enables EUDR compliance sections on traceability certificate."
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"SO-{self.order_number} — {self.customer_name} ({self.get_status_display()})"


class SalesOrderItem(models.Model):

    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='sales_items'
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


# Import Batch and quality models so Django discovers them all
from apps.sales_orders.batch import Batch
from apps.sales_orders.quality import PhytosanitaryCertificate, BatchQualityTest
