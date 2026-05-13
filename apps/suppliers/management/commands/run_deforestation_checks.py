"""
Run Hansen GFC deforestation checks against farm polygons.

Usage:
  python manage.py run_deforestation_checks
  python manage.py run_deforestation_checks --farm-id 42
  python manage.py run_deforestation_checks --company-id 7
  python manage.py run_deforestation_checks --recheck
  python manage.py run_deforestation_checks --dry-run
"""
from django.core.management.base import BaseCommand

from apps.suppliers.models import Farm
from apps.suppliers.deforestation_engine import run_check


class Command(BaseCommand):
    help = 'Run Hansen GFC deforestation checks against farm polygons.'

    def add_arguments(self, parser):
        parser.add_argument('--farm-id',    type=int, help='Check a single farm.')
        parser.add_argument('--company-id', type=int, help='Check all farms for a tenant.')
        parser.add_argument('--recheck',    action='store_true',
                            help='Re-run farms that already have a check result.')
        parser.add_argument('--dry-run',    action='store_true',
                            help='Report which farms would be checked without writing.')

    def handle(self, *args, **options):
        farm_id    = options['farm_id']
        company_id = options['company_id']
        recheck    = options['recheck']
        dry_run    = options['dry_run']

        qs = Farm.objects.select_related('company', 'supplier').filter(geolocation__isnull=False)

        if farm_id:
            qs = qs.filter(pk=farm_id)
        elif company_id:
            qs = qs.filter(company_id=company_id)

        if not recheck:
            checked_ids = set(
                Farm.objects.filter(
                    deforestation_checks__isnull=False
                ).values_list('pk', flat=True)
            )
            qs = qs.exclude(pk__in=checked_ids)

        farms = list(qs.order_by('company_id', 'name'))

        if dry_run:
            self.stdout.write(f'Dry run — {len(farms)} farm(s) would be checked:')
            for farm in farms:
                self.stdout.write(f'  [{farm.company.name}] {farm.name}')
            return

        clear = flagged = errors = skipped = 0

        for farm in farms:
            try:
                check = run_check(farm)
                if check.risk_status == 'clear':
                    clear += 1
                    self.stdout.write(f'  CLEAR    {farm.company.name} / {farm.name}')
                elif check.risk_status == 'flagged':
                    flagged += 1
                    self.stdout.write(self.style.WARNING(
                        f'  FLAGGED  {farm.company.name} / {farm.name} — '
                        f'{check.post_cutoff_loss_area_ha} ha loss'
                    ))
                elif check.risk_status == 'error':
                    errors += 1
                    self.stdout.write(self.style.ERROR(
                        f'  ERROR    {farm.company.name} / {farm.name} — {check.error_detail}'
                    ))
                else:
                    skipped += 1
                    self.stdout.write(f'  INCONCLUSIVE  {farm.company.name} / {farm.name}')
            except Exception as exc:
                errors += 1
                self.stdout.write(self.style.ERROR(f'  FAILED   {farm.name} — {exc}'))

        total = clear + flagged + errors + skipped
        self.stdout.write(
            f'\nDone. {total} checked — '
            f'{clear} clear, {flagged} flagged, {errors} errors, {skipped} inconclusive.'
        )
