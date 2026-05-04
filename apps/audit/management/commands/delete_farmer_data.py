"""
Right-to-erasure — delete all personal data held on a farmer.

What this does:
  - Deletes the Farmer record (removes NIN, name, phone, village, LGA, consent)
  - Farm records are preserved (GPS polygon is land data, not personal data)
    but their farmer FK is set to NULL automatically (SET_NULL on the FK)
  - AuditLog entries referencing this farmer have their object_repr anonymised
    so the audit trail is preserved without retaining the farmer's name

Dry-run by default. Pass --confirm to execute.

Usage:
    python manage.py delete_farmer_data --farmer-id 42
    python manage.py delete_farmer_data --farmer-id 42 --confirm
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Erase personal data held on a farmer (NDPA right-to-erasure)'

    def add_arguments(self, parser):
        parser.add_argument('--farmer-id', type=int, required=True)
        parser.add_argument(
            '--confirm', action='store_true',
            help='Actually perform the deletion (omit for a dry run)',
        )

    def handle(self, *args, **options):
        from apps.suppliers.models import Farmer
        from apps.audit.models import AuditLog

        farmer_id = options['farmer_id']
        confirm   = options['confirm']

        try:
            farmer = Farmer.objects.select_related('company').get(pk=farmer_id)
        except Farmer.DoesNotExist:
            raise CommandError(f"No farmer with id {farmer_id}")

        farm_count  = farmer.farms.count()
        audit_count = AuditLog.objects.filter(model_name='Farmer', object_id=farmer_id).count()
        label       = f"{farmer.first_name} {farmer.last_name}".strip() or f"Farmer {farmer_id}"

        self.stdout.write(f'\nFarmer:       {label} (id={farmer_id})')
        self.stdout.write(f'Company:      {farmer.company.name if farmer.company else "—"}')
        self.stdout.write(f'Linked farms: {farm_count} (will be kept, farmer FK → NULL)')
        self.stdout.write(f'Audit logs:   {audit_count} (object_repr will be anonymised)')

        if not confirm:
            self.stdout.write(self.style.WARNING(
                '\nDRY RUN — no data has been changed. '
                'Pass --confirm to execute the erasure.'
            ))
            return

        with transaction.atomic():
            # Anonymise audit log reprs before the farmer is deleted
            AuditLog.objects.filter(
                model_name='Farmer', object_id=farmer_id
            ).update(object_repr='[farmer deleted — data erased]')

            farmer.delete()

            # Log the erasure itself so there is an auditable record
            from django.utils import timezone
            AuditLog.objects.create(
                company=farmer.company if farmer.company_id else None,
                user=None,
                action='delete',
                model_name='Farmer',
                object_id=farmer_id,
                object_repr=f'[erasure] Farmer id={farmer_id} — data erased per right-to-erasure request',
                changes={
                    'erased_fields': ['first_name', 'last_name', 'phone', 'nin', 'village', 'lga', 'consent_date'],
                    'farms_unlinked': farm_count,
                    'audit_logs_anonymised': audit_count,
                },
                ip_address=None,
            )

        self.stdout.write(self.style.SUCCESS(
            f'\nErasure complete. Farmer id={farmer_id} deleted, '
            f'{farm_count} farm(s) unlinked, {audit_count} audit log(s) anonymised.'
        ))
