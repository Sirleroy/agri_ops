from django.db import models
from apps.companies.models import Company
from apps.suppliers.models import Supplier


class Product(models.Model):

    CATEGORY_CHOICES = [
        ('seeds', 'Seeds'),
        ('fertilizer', 'Fertilizer'),
        ('equipment', 'Equipment'),
        ('livestock_feed', 'Livestock Feed'),
        ('chemicals', 'Chemicals'),
        ('packaging', 'Packaging'),
        ('other', 'Other'),
    ]

    UNIT_CHOICES = [
        ('kg', 'Kilograms'),
        ('g', 'Grams'),
        ('litre', 'Litres'),
        ('piece', 'Piece'),
        ('bag', 'Bag'),
        ('tonne', 'Tonne'),
        ('box', 'Box'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='products'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='other'
    )
    unit = models.CharField(
        max_length=20,
        choices=UNIT_CHOICES,
        default='kg'
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_unit_display()})"
