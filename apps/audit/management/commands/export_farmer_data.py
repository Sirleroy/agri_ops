"""
Subject Access Request — export all personal data held on a farmer as JSON.

Usage:
    python manage.py export_farmer_data --farmer-id 42
    python manage.py export_farmer_data --nin 12345678901
    python manage.py export_farmer_data --farmer-id 42 --output /tmp/sar_42.json

Output: JSON bundle containing the Farmer record, linked Farms,
FarmCertifications, and AuditLog entries referencing this farmer.
"""
import json
import sys
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Export all personal data held on a farmer (Subject Access Request)'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--farmer-id', type=int)
        group.add_argument('--nin', type=str)
        parser.add_argument(
            '--output', type=str, default=None,
            help='Write JSON to this file path instead of stdout',
        )

    def handle(self, *args, **options):
        from apps.suppliers.models import Farmer, FarmCertification
        from apps.audit.models import AuditLog

        if options['farmer_id']:
            try:
                farmer = Farmer.objects.select_related('company').get(pk=options['farmer_id'])
            except Farmer.DoesNotExist:
                raise CommandError(f"No farmer with id {options['farmer_id']}")
        else:
            nin = options['nin'].strip().upper()
            try:
                farmer = Farmer.objects.select_related('company').get(nin=nin)
            except Farmer.DoesNotExist:
                raise CommandError(f"No farmer with NIN {nin}")
            except Farmer.MultipleObjectsReturned:
                raise CommandError(f"Multiple farmers found with NIN {nin} — use --farmer-id")

        farms = list(farmer.farms.prefetch_related('certifications').order_by('name'))

        farm_records = []
        for farm in farms:
            certs = [
                {
                    'cert_type':         cert.cert_type,
                    'certifying_body':   cert.certifying_body,
                    'certificate_number': cert.certificate_number,
                    'issued_date':       cert.issued_date.isoformat() if cert.issued_date else None,
                    'expiry_date':       cert.expiry_date.isoformat() if cert.expiry_date else None,
                }
                for cert in farm.certifications.all()
            ]
            farm_records.append({
                'id':                   farm.pk,
                'name':                 farm.name,
                'country':              farm.country,
                'state_region':         farm.state_region,
                'commodity':            farm.commodity,
                'area_hectares':        str(farm.area_hectares) if farm.area_hectares else None,
                'mapping_date':         farm.mapping_date.isoformat() if farm.mapping_date else None,
                'is_eudr_verified':     farm.is_eudr_verified,
                'deforestation_risk_status': farm.deforestation_risk_status,
                'created_at':           farm.created_at.isoformat(),
                'certifications':       certs,
            })

        farm_pks = [f.pk for f in farms]
        audit_entries = AuditLog.objects.filter(
            model_name='Farmer', object_id=farmer.pk
        ) | AuditLog.objects.filter(
            model_name='Farm', object_id__in=farm_pks
        )
        audit_records = [
            {
                'timestamp':   entry.timestamp.isoformat(),
                'action':      entry.action,
                'model':       entry.model_name,
                'object_repr': entry.object_repr,
                'ip_address':  entry.ip_address,
            }
            for entry in audit_entries.order_by('timestamp')
        ]

        bundle = {
            'generated_at': timezone.now().isoformat(),
            'request_type': 'Subject Access Request',
            'farmer': {
                'id':           farmer.pk,
                'first_name':   farmer.first_name,
                'last_name':    farmer.last_name,
                'gender':       farmer.gender,
                'phone':        farmer.phone,
                'village':      farmer.village,
                'lga':          farmer.lga,
                'nin':          farmer.nin,
                'crops':        farmer.crops,
                'consent_given': farmer.consent_given,
                'consent_date': farmer.consent_date.isoformat() if farmer.consent_date else None,
                'created_at':   farmer.created_at.isoformat(),
                'updated_at':   farmer.updated_at.isoformat(),
                'company':      farmer.company.name if farmer.company else None,
            },
            'farms':      farm_records,
            'audit_trail': audit_records,
        }

        output = json.dumps(bundle, indent=2, ensure_ascii=False)

        if options['output']:
            with open(options['output'], 'w', encoding='utf-8') as f:
                f.write(output)
            self.stdout.write(self.style.SUCCESS(
                f"SAR export written to {options['output']} "
                f"({len(farm_records)} farm(s), {len(audit_records)} audit entry(s))"
            ))
        else:
            sys.stdout.write(output + '\n')
