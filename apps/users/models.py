from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):

    SYSTEM_ROLE_CHOICES = [
        ('org_admin', 'Organisation Admin'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
        ('viewer', 'Viewer'),
    ]

    system_role = models.CharField(
        max_length=30,
        choices=SYSTEM_ROLE_CHOICES,
        default='staff',
        help_text="Controls permissions. Never accept from user input directly."
    )
    job_title = models.CharField(
        max_length=100,
        blank=True,
        help_text="Display title within the organisation. No permission bearing."
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
        return f"{self.username} ({self.get_system_role_display()})"

    @property
    def is_org_admin(self):
        return self.system_role == 'org_admin'

    @property
    def is_manager_or_above(self):
        return self.system_role in ('org_admin', 'manager')

    @property
    def is_staff_or_above(self):
        return self.system_role in ('org_admin', 'manager', 'staff')
