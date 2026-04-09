"""
Management command: import_farms
Imports farm records from a SW Maps GeoJSON FeatureCollection export.

Usage:
    python manage.py import_farms --file /path/to/farms.geojson --company "Ake Collective" --supplier "Sahel Seeds Co-op" --commodity Soy
    python manage.py import_farms --file /path/to/farms.geojson --company "Ake Collective" --supplier "Sahel Seeds Co-op" --commodity Soy --dry-run

The GeoJSON file should be a FeatureCollection where each Feature represents one farm.

Expected properties (all optional — falls back to defaults):
    farm_name       → Farm.name
    farmer_name     → Farm.farmer_name
    commodity       → Farm.commodity (overrides --commodity flag if present)
    state_region    → Farm.state_region
    country         → Farm.country (overrides --country flag if present)
    area_ha         → Farm.area_hectares
    risk            → Farm.deforestation_risk_status (low/standard/high)

The geometry is stored as-is in Farm.geolocation.
"""

import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.suppliers.forms import normalize_sw_maps_geometry


class Command(BaseCommand):
    help = 'Import farms from a SW Maps GeoJSON FeatureCollection'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Path to GeoJSON file')
        parser.add_argument('--company', required=True, help='Company name (exact match)')
        parser.add_argument('--supplier', required=True, help='Supplier name (exact match)')
        parser.add_argument('--commodity', required=True, help='Default commodity if not in properties')
        parser.add_argument('--country', default='Nigeria', help='Default country (default: Nigeria)')
        parser.add_argument('--dry-run', action='store_true', help='Validate without saving')
        parser.add_argument('--batch-size', type=int, default=50, help='Batch size for bulk create')

    def handle(self, *args, **options):
        from apps.companies.models import Company
        from apps.suppliers.models import Supplier, Farm

        # ── Resolve company and supplier ──────────────────────
        try:
            company = Company.objects.get(name=options['company'])
        except Company.DoesNotExist:
            raise CommandError(f"Company not found: {options['company']}")

        try:
            supplier = Supplier.objects.get(name=options['supplier'], company=company)
        except Supplier.DoesNotExist:
            raise CommandError(f"Supplier not found: {options['supplier']} in {company.name}")

        # ── Load GeoJSON ──────────────────────────────────────
        try:
            with open(options['file'], 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"File not found: {options['file']}")
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON: {e}")

        if data.get('type') != 'FeatureCollection':
            raise CommandError("File must be a GeoJSON FeatureCollection")

        features = data.get('features', [])
        if not features:
            raise CommandError("FeatureCollection contains no features")

        self.stdout.write(f"  Found {len(features)} features in {options['file']}")
        self.stdout.write(f"  Company: {company.name}")
        self.stdout.write(f"  Supplier: {supplier.name}")
        self.stdout.write(f"  Default commodity: {options['commodity']}")
        self.stdout.write(f"  Dry run: {options['dry_run']}")
        self.stdout.write("")

        # ── Parse features ────────────────────────────────────
        to_create = []
        to_update = []
        skipped   = []
        errors    = []

        for i, feature in enumerate(features):
            try:
                props = feature.get('properties') or {}
                geometry = feature.get('geometry')

                # Farm name — required
                name = (
                    props.get('farm_name') or
                    props.get('name') or
                    props.get('Farm Name') or
                    props.get('Name') or
                    f"Farm {i + 1}"
                )

                # Commodity
                commodity = (
                    props.get('commodity') or
                    props.get('Commodity') or
                    options['commodity']
                )

                # Country
                country = (
                    props.get('country') or
                    props.get('Country') or
                    options['country']
                )

                # Risk status
                raw_risk = str(props.get('risk') or props.get('Risk') or 'standard').lower()
                risk = raw_risk if raw_risk in ('low', 'standard', 'high') else 'standard'

                # Area
                area = None
                raw_area = props.get('area_ha') or props.get('area') or props.get('Area')
                if raw_area:
                    try:
                        area = float(raw_area)
                    except (ValueError, TypeError):
                        pass

                farm_data = {
                    'company':                   company,
                    'supplier':                  supplier,
                    'name':                      name,
                    'farmer_name':               props.get('farmer_name') or props.get('Farmer Name') or '',
                    'geolocation':               normalize_sw_maps_geometry(geometry) if geometry else geometry,
                    'area_hectares':             area,
                    'country':                   country,
                    'state_region':              props.get('state_region') or props.get('State') or props.get('Region') or '',
                    'commodity':                 commodity,
                    'deforestation_risk_status': risk,
                    'is_eudr_verified':          False,
                }

                # Check if farm already exists by name + supplier
                existing = Farm.objects.filter(
                    company=company,
                    supplier=supplier,
                    name=name
                ).first()

                if existing:
                    to_update.append((existing, farm_data))
                    self.stdout.write(f"  [UPDATE] {name}")
                else:
                    to_create.append(Farm(**farm_data))
                    self.stdout.write(f"  [CREATE] {name}")

            except Exception as e:
                errors.append(f"Feature {i + 1}: {e}")
                self.stdout.write(self.style.ERROR(f"  [ERROR] Feature {i + 1}: {e}"))

        # ── Summary before save ───────────────────────────────
        self.stdout.write("")
        self.stdout.write(f"  To create: {len(to_create)}")
        self.stdout.write(f"  To update: {len(to_update)}")
        self.stdout.write(f"  Skipped:   {len(skipped)}")
        self.stdout.write(f"  Errors:    {len(errors)}")

        if options['dry_run']:
            self.stdout.write(self.style.WARNING("\n  Dry run — nothing saved."))
            return

        if errors and not to_create and not to_update:
            raise CommandError("All features had errors. Nothing imported.")

        # ── Save in batches ───────────────────────────────────
        batch_size = options['batch_size']

        with transaction.atomic():
            # Bulk create
            created_count = 0
            for i in range(0, len(to_create), batch_size):
                batch = to_create[i:i + batch_size]
                Farm.objects.bulk_create(batch)
                created_count += len(batch)
                self.stdout.write(f"  Created batch {i // batch_size + 1} — {created_count} farms so far")

            # Update existing
            updated_count = 0
            for existing, farm_data in to_update:
                for field, value in farm_data.items():
                    setattr(existing, field, value)
                existing.save()
                updated_count += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Import complete — {created_count} created, {updated_count} updated, {len(errors)} errors"
        ))
