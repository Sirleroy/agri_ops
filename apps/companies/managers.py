"""
TenantManager — base manager for all company-scoped models.

Usage:
    class MyModel(models.Model):
        company = models.ForeignKey(Company, ...)
        objects = TenantManager()

    # Scoped (normal use in views):
    MyModel.objects.for_company(request.user.company)

    # Unscoped (Django admin, shell, migrations — use deliberately):
    MyModel.objects.all()

The manager does NOT override get_queryset() — it stays permissive so
Django admin, management commands, and migrations work without special
handling. The for_company() method is the convention that makes unscoped
access visible in code review: any .objects.filter() or .objects.get()
without .for_company() is a red flag.
"""
from django.db import models


class TenantManager(models.Manager):
    def for_company(self, company):
        """Return a queryset scoped to the given company. Use this in every view."""
        return self.get_queryset().filter(company=company)
