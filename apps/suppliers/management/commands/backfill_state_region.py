"""
Backfill state_region on Farm records where it is blank or unset.

Strategy (in priority order):
  1. Farm has a linked Farmer with an LGA set → derive canonical state via
     canonicalise_lga_state(farmer.lga).
  2. No derivable state → report as still-unknown for manual correction.

This command never overwrites a state_region that already has a value.

Usage:
    python manage.py backfill_state_region
    python manage.py backfill_state_region --dry-run
    python manage.py backfill_state_region --company-id 3
"""
from django.core.management.base import BaseCommand
from apps.suppliers.models import Farm
from apps.suppliers.ng_geodata import canonicalise_lga_state


class Command(BaseCommand):
    help = 'Backfill state_region on Farm records where it is blank.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report changes without writing to the database.')
        parser.add_argument('--company-id', type=int, default=None,
                            help='Limit to a single company (optional).')

    def handle(self, *args, **options):
        dry_run    = options['dry_run']
        company_id = options['company_id']

        qs = Farm.objects.filter(
            state_region__in=['', None]
        ).select_related('farmer')
        if company_id:
            qs = qs.filter(company_id=company_id)

        total    = qs.count()
        updated  = 0
        skipped  = 0

        self.stdout.write(f'Scanning {total} farm(s) with blank state_region...\n')

        for farm in qs.iterator():
            derived = None

            if farm.farmer and farm.farmer.lga:
                _, canonical_state = canonicalise_lga_state(farm.farmer.lga, '')
                if canonical_state:
                    derived = canonical_state

            if derived:
                self.stdout.write(
                    f'  {"[DRY RUN] " if dry_run else ""}Farm {farm.id} '
                    f'"{farm.name}": state_region → "{derived}"'
                    f'{" (via farmer LGA: " + farm.farmer.lga + ")" if farm.farmer else ""}'
                )
                if not dry_run:
                    Farm.objects.filter(pk=farm.pk).update(state_region=derived)
                updated += 1
            else:
                self.stdout.write(
                    f'  [MANUAL] Farm {farm.id} "{farm.name}": no derivable state'
                    f' (farmer: {"no farmer linked" if not farm.farmer else "farmer has no LGA"})'
                )
                skipped += 1

        mode = 'Would update' if dry_run else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'\nDone. {mode} {updated} record(s). {skipped} still unknown — require manual correction.'
        ))
        if skipped:
            self.stdout.write(
                '  → Edit each flagged farm directly at /suppliers/farms/<id>/edit/ to set state_region.'
            )
