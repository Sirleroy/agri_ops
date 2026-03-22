from django.db import models


class Company(models.Model):

    PLAN_CHOICES = [
        ('free', 'Free'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]

    name = models.CharField(max_length=255)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    plan_tier = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default='free'
    )
    # Nigerian export compliance
    nepc_registration_number = models.CharField(
        max_length=50, blank=True,
        help_text="Nigerian Export Promotion Council registration number. Required before any export transaction."
    )
    nepc_registration_expiry = models.DateField(
        null=True, blank=True,
        help_text="NEPC registration expiry date."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_plan_tier_display()})"
