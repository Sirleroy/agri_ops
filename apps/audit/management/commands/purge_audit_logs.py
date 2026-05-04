"""
Delete AuditLog entries older than --days (default 365).

Usage:
    python manage.py purge_audit_logs
    python manage.py purge_audit_logs --days 180
    python manage.py purge_audit_logs --dry-run
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime


class Command(BaseCommand):
    help = 'Purge AuditLog entries older than the retention window (default 365 days)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=365,
            help='Retain logs newer than this many days (default: 365)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report how many records would be deleted without deleting',
        )

    def handle(self, *args, **options):
        from apps.audit.models import AuditLog

        days     = options['days']
        dry_run  = options['dry_run']
        cutoff   = timezone.now() - datetime.timedelta(days=days)

        qs = AuditLog.objects.filter(timestamp__lt=cutoff)
        count = qs.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS(f'No audit logs older than {days} days. Nothing to purge.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN — {count} audit log(s) older than {days} days would be deleted '
                f'(cutoff: {cutoff:%Y-%m-%d}).'
            ))
            return

        qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'Purged {count} audit log(s) older than {days} days (cutoff: {cutoff:%Y-%m-%d}).'
        ))
