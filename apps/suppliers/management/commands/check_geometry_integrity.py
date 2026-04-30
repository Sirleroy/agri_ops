"""
Scan all farms with geolocation and verify the stored geometry_hash
matches a freshly computed SHA-256. Flags any drift, regardless of
how it got there (admin edit, direct DB write, API bypass).

Usage:
    python manage.py check_geometry_integrity
    python manage.py check_geometry_integrity --company-id 3
    python manage.py check_geometry_integrity --fix
"""
import hashlib
import json

from django.core.management.base import BaseCommand

from apps.suppliers.models import Farm


def _compute_hash(geolocation):
    canonical = json.dumps(geolocation, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


class Command(BaseCommand):
    help = 'Verify geometry_hash integrity across all farms'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id', type=int, default=None,
            help='Limit check to a single company',
        )
        parser.add_argument(
            '--fix', action='store_true',
            help='Rewrite drifted hashes in place (use after confirming drift is not tampering)',
        )

    def handle(self, *args, **options):
        company_id = options['company_id']
        fix        = options['fix']

        qs = Farm.objects.exclude(geolocation=None).select_related('company')
        if company_id:
            qs = qs.filter(company_id=company_id)

        total     = qs.count()
        ok        = 0
        drifted   = []
        missing   = []
        errored   = 0

        if total == 0:
            self.stdout.write(self.style.WARNING('No farms with geolocation found.'))
            return

        self.stdout.write(f'Checking {total} farm(s)…')

        for farm in qs.iterator():
            try:
                computed = _compute_hash(farm.geolocation)
            except (TypeError, ValueError) as e:
                self.stdout.write(
                    self.style.ERROR(f'  Farm {farm.pk} ({farm.name}): cannot hash geolocation — {e}')
                )
                errored += 1
                continue

            if not farm.geometry_hash:
                missing.append(farm)
            elif farm.geometry_hash != computed:
                drifted.append((farm, farm.geometry_hash, computed))
            else:
                ok += 1

        # --- Report ---
        self.stdout.write(f'\n  ✓ Clean:   {ok}')
        self.stdout.write(f'  ⚠ Missing: {len(missing)}')
        self.stdout.write(f'  ✕ Drifted: {len(drifted)}')
        if errored:
            self.stdout.write(self.style.ERROR(f'  ! Errors:  {errored}'))

        if missing:
            self.stdout.write(self.style.WARNING('\nFarms with no stored hash (run backfill_geometry_hashes):'))
            for farm in missing:
                self.stdout.write(f'  Farm {farm.pk} [{farm.company.name}] {farm.name}')

        if drifted:
            self.stdout.write(self.style.ERROR('\nFarms with DRIFTED hash (geometry may have changed):'))
            for farm, stored, computed in drifted:
                self.stdout.write(
                    f'  Farm {farm.pk} [{farm.company.name}] {farm.name}\n'
                    f'    stored:   {stored[:32]}…\n'
                    f'    computed: {computed[:32]}…'
                )
                if fix:
                    Farm.objects.filter(pk=farm.pk).update(geometry_hash=computed)
                    self.stdout.write(self.style.WARNING(f'    → hash updated'))

        if not drifted and not missing and not errored:
            self.stdout.write(self.style.SUCCESS('\nAll geometry hashes are clean.'))
        elif drifted and not fix:
            self.stdout.write(self.style.ERROR(
                f'\n{len(drifted)} drifted hash(es) detected. '
                'Investigate before using --fix.'
            ))
