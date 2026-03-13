from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):

    ROLE_CHOICES = [
        ('ceo', 'CEO'),
        ('operations_manager', 'Operations Manager'),
        ('regional_lead', 'Regional Lead'),
        ('executive_assistant', 'Executive Assistant'),
        ('admin', 'Admin'),
        ('staff', 'Staff'),
    ]

    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        blank=True
    )
    phone = models.CharField(max_length=20, blank=True)
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees'
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
