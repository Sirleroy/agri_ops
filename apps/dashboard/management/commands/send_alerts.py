"""
Management command: send_alerts
Sends low stock and EUDR expiry warnings.
Run daily via cron or Render scheduled job.

Usage:
    python manage.py send_alerts
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import F
from datetime import timedelta


class Command(BaseCommand):
    help = 'Send low stock and EUDR expiry alert emails'

    def handle(self, *args, **options):
        from apps.inventory.models import Inventory
        from apps.suppliers.models import Farm
        from apps.users.models import CustomUser
        from apps.dashboard.notifications import (
            send_low_stock_alert, send_eudr_expiry_warning
        )

        today = timezone.now().date()
        in_30 = today + timedelta(days=30)

        # ── Low stock alerts ──────────────────────────────────
        low_stock = Inventory.objects.filter(
            quantity__lte=F('low_stock_threshold')
        ).select_related('product', 'company')

        for item in low_stock:
            managers = CustomUser.objects.filter(
                company=item.company,
                system_role__in=['org_admin', 'manager'],
                is_active=True
            ).exclude(email='').values_list('email', flat=True)

            if managers:
                try:
                    send_low_stock_alert(item, list(managers))
                    self.stdout.write(f'  Low stock alert sent: {item.product.name}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Failed: {item.product.name} — {e}'))

        # ── EUDR expiry warnings ──────────────────────────────
        expiring = Farm.objects.filter(
            is_eudr_verified=True,
            verification_expiry__lte=in_30,
            verification_expiry__gte=today,
        ).select_related('supplier', 'company')

        for farm in expiring:
            managers = CustomUser.objects.filter(
                company=farm.company,
                system_role__in=['org_admin', 'manager'],
                is_active=True
            ).exclude(email='').values_list('email', flat=True)

            if managers:
                try:
                    send_eudr_expiry_warning(farm, list(managers))
                    self.stdout.write(f'  EUDR expiry alert sent: {farm.name}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Failed: {farm.name} — {e}'))

        self.stdout.write(self.style.SUCCESS('Alert run complete.'))
