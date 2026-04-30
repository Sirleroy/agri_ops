"""
Backfill geometry_hash on Farm records that have a geolocation polygon
but an empty or missing hash.

This covers farms created before the hash field was introduced, farms
imported via bulk ORM update() that bypassed save(), and any test or
seed data inserted directly.

Usage:
    python manage.py backfill_geometry_hashes
    python manage.py backfill_geometry_hashes --dry-run
    python manage.py backfill_geometry_hashes --company-id 3
"""
import hashlib
import json

from django.core.management.base import BaseCommand

from apps.suppliers.models import Farm


class Command(BaseCommand):
    help = 'Backfill geometry_hash for farms that have geolocation but no hash'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be updated without writing anything',
        )
        parser.add_argument(
            '--company-id', type=int, default=None,
            help='Limit backfill to a single company',
        )

    def handle(self, *args, **options):
        dry_run    = options['dry_run']
        company_id = options['company_id']

        qs = Farm.objects.exclude(geolocation=None).filter(geometry_hash='')
        if company_id:
            qs = qs.filter(company_id=company_id)

        total   = qs.count()
        updated = 0
        skipped = 0

        if total == 0:
            self.stdout.write(self.style.SUCCESS('No farms need backfilling.'))
            return

        self.stdout.write(f'Found {total} farm(s) with geolocation but no hash.')
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — no changes will be written.'))

        for farm in qs.iterator():
            try:
                canonical = json.dumps(farm.geolocation, sort_keys=True, separators=(',', ':'))
                new_hash  = hashlib.sha256(canonical.encode()).hexdigest()
            except (TypeError, ValueError) as e:
                self.stdout.write(
                    self.style.ERROR(f'  Farm {farm.pk} ({farm.name}): invalid geolocation — {e}')
                )
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f'  Would update Farm {farm.pk} ({farm.name}) → {new_hash[:16]}…')
            else:
                Farm.objects.filter(pk=farm.pk).update(geometry_hash=new_hash)
                updated += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'Dry run complete. {total - skipped} farms would be updated, {skipped} skipped.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Done. {updated} farm(s) updated, {skipped} skipped.'
            ))
