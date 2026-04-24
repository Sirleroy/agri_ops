"""
One-time backfill: run normalise_commodity() against every existing Farm record
and update commodity where the stored value differs from the canonical form.

Farms created before the normalisation engine was built may have non-canonical
values (e.g. 'Soy' instead of 'Soybeans'). This command corrects them without
touching geometry, hashes, or any other field.

Usage:
    python manage.py normalise_commodity_backfill
    python manage.py normalise_commodity_backfill --dry-run
"""
from django.core.management.base import BaseCommand
from apps.suppliers.models import Farm
from apps.suppliers.ng_geodata import normalise_commodity


class Command(BaseCommand):
    help = 'Backfill commodity normalisation on all existing Farm records.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing to the database.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        updated = 0
        skipped = 0

        farms = Farm.objects.only('id', 'name', 'commodity')
        total = farms.count()

        self.stdout.write(f'Scanning {total} farm records...')

        for farm in farms.iterator():
            if not farm.commodity:
                skipped += 1
                continue
            canonical = normalise_commodity(farm.commodity)
            if canonical != farm.commodity:
                self.stdout.write(
                    f'  {"[DRY RUN] " if dry_run else ""}Farm {farm.id} '
                    f'"{farm.name}": "{farm.commodity}" → "{canonical}"'
                )
                if not dry_run:
                    Farm.objects.filter(pk=farm.pk).update(commodity=canonical)
                updated += 1
            else:
                skipped += 1

        mode = 'Would update' if dry_run else 'Updated'
        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. {mode} {updated} record(s). {skipped} already canonical or blank.'
            )
        )
