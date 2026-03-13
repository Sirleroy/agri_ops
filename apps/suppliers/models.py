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
        ('other', 'Other'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='suppliers'
    )
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='other'
    )
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} — {self.get_category_display()}"
