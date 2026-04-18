"""
Management command: seed_messy_demo

End-to-end import of intentionally messy GeoJSON field data for Ake Collective,
then builds the full traceability chain through to a locked batch with a
downloadable EUDR certificate.

8 features in one file — every import pipeline path is exercised:

  ROW 1  Haruna Musa Farm — Alkaleri
         commodity "soy bean" → Soybeans  ·  phone 08XXXXXXXX → +234  ·  LGA "alkaleri" → Alkaleri
         RESULT: created  ·  2 transformation events

  ROW 2  Fatima Yakubu Plot C
         commodity "soybeans" (no correction needed)  ·  no phone, no NIN
         RESULT: created  ·  incomplete-farmer nudge (phone + NIN missing)

  ROW 3  Aliyu Ibrahim Large Plot
         commodity "cacao" → Cocoa  ·  LGA "Tafawa-Balewa" → Tafawa Balewa (fuzzy)
         area ~245 ha  ·  RESULT: created  ·  warning: unusually large area

  ROW 4  Haruna Musa Farm — Alkaleri  (name collision with row 1 in same file)
         RESULT: DUPLICATE blocked  ·  intra-batch name guard

  ROW 5  Overlap Test Plot — Musawa  (polygon overlaps row 1)
         RESULT: BLOCKED  ·  intra-batch overlap guard

  ROW 6  Plot Ref D — Dass  (no first/last name in properties)
         RESULT: created  ·  warning: no farmer name found

  ROW 7  Zainab Garba Holdings  (no commodity column)
         Zainab Garba pre-exists with crops "Sesame, Soybeans"
         RESULT: created  ·  commodity fallback → Sesame  ·  transformation event

  ROW 8  Bad Geometry Farm  (LineString exported instead of Polygon — operator traced a path)
         RESULT: ERROR — type must be Polygon or MultiPolygon, got 'LineString'

Post-import chain:
  → Farm 1 (Haruna Musa) + Farm 7 (Zainab Garba) verified, FVF & certifications added
  → Farms 2, 6 remain pending  ·  Farm 3 marked high risk
  → Product / Inventory / PO built from Bauchi Soy Farmers Coop
  → EU Sales Order → Batch → Phyto cert → 2 quality tests (MRL pass + Aflatoxin pending)
  → FarmImportLog written  ·  AuditLog entries created
  → Batch locked

Usage:
    python manage.py seed_messy_demo
    python manage.py seed_messy_demo --flush   # wipe and rebuild
"""

import datetime
from django.core.management.base import BaseCommand
from django.db import transaction

SUPPLIER_NAME  = 'Bauchi Soy Farmers Coop'
SO_NUMBER      = 'AKE-SO-2026-003'
PO_NUMBER      = 'AKE-PO-2026-003'
PRODUCT_NAME   = 'Raw Soybean — Bauchi Origin'
FILENAME       = 'messy_bauchi_survey_2026.geojson'

# ── GeoJSON features ──────────────────────────────────────────────────────────
# All coordinates in [lng, lat] (GeoJSON spec). Bauchi State, Nigeria.

FEATURES = [
    # Coordinates: Ilorin area, Kwara State (4.55°E, 8.48°N base).
    # Using Kwara to avoid any overlap with GREFAMCO / Ake farms already in DB
    # which are in Bauchi / Plateau State territory.

    # ROW 1 — valid, triggers commodity + phone + LGA normalisation
    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [4.5510, 8.4805], [4.5520, 8.4805],
                [4.5520, 8.4815], [4.5510, 8.4815],
                [4.5510, 8.4805],
            ]],
        },
        "properties": {
            "Name": "Haruna Musa Farm — Alkaleri",
            "First Name": "haruna",
            "Last Name": "musa",
            "Phone Number": "08134567801",
            "Village": "Alkaleri",
            "LGA": "alkaleri",
            "Commodity": "soy bean",
        },
    },
    # ROW 2 — valid, no phone/NIN → incomplete-farmer nudge
    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [4.5530, 8.4805], [4.5540, 8.4805],
                [4.5540, 8.4815], [4.5530, 8.4815],
                [4.5530, 8.4805],
            ]],
        },
        "properties": {
            "Name": "Fatima Yakubu Plot C",
            "First Name": "Fatima",
            "Last Name": "Yakubu",
            "Village": "Bogoro",
            "LGA": "Bogoro",
            "Commodity": "soybeans",
        },
    },
    # ROW 3 — valid, large polygon (~245 ha) + cacao→Cocoa + fuzzy LGA
    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [4.6000, 8.5000], [4.6142, 8.5000],
                [4.6142, 8.5142], [4.6000, 8.5142],
                [4.6000, 8.5000],
            ]],
        },
        "properties": {
            "Name": "Aliyu Ibrahim Large Plot",
            "First Name": "Aliyu",
            "Last Name": "Ibrahim",
            "Village": "Tafawa Balewa",
            "LGA": "Tafawa-Balewa",
            "Commodity": "cacao",
        },
    },
    # ROW 4 — same name as row 1, same supplier → DUPLICATE (intra-batch)
    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [4.5560, 8.4805], [4.5570, 8.4805],
                [4.5570, 8.4815], [4.5560, 8.4815],
                [4.5560, 8.4805],
            ]],
        },
        "properties": {
            "Name": "Haruna Musa Farm — Alkaleri",
            "First Name": "haruna",
            "Last Name": "musa",
            "Village": "Alkaleri",
            "LGA": "Alkaleri",
            "Commodity": "Soybeans",
        },
    },
    # ROW 5 — polygon overlaps row 1 → BLOCKED (intra-batch overlap)
    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [4.5515, 8.4800], [4.5525, 8.4800],
                [4.5525, 8.4812], [4.5515, 8.4812],
                [4.5515, 8.4800],
            ]],
        },
        "properties": {
            "Name": "Overlap Test Plot — Musawa",
            "First Name": "Musa",
            "Last Name": "Adamu",
            "Village": "Musawa",
            "LGA": "Alkaleri",
            "Commodity": "Soybeans",
        },
    },
    # ROW 6 — valid, no first/last name → warning: no farmer name found
    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [4.5550, 8.4805], [4.5560, 8.4805],
                [4.5560, 8.4815], [4.5550, 8.4815],
                [4.5550, 8.4805],
            ]],
        },
        "properties": {
            "Name": "Plot Ref D — Dass",
            "Village": "Dass",
            "LGA": "Dass",
            "Commodity": "groundnut",
        },
    },
    # ROW 7 — no commodity column; Zainab Garba pre-exists with crops → fallback
    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [4.5570, 8.4805], [4.5580, 8.4805],
                [4.5580, 8.4815], [4.5570, 8.4815],
                [4.5570, 8.4805],
            ]],
        },
        "properties": {
            "Name": "Zainab Garba Holdings",
            "First Name": "Zainab",
            "Last Name": "Garba",
            "Village": "Ganjuwa",
            "LGA": "Ganjuwa",
        },
    },
    # ROW 8 — LineString exported instead of Polygon (operator traced a path, not a boundary)
    #          → ERROR: "GeoJSON type must be Polygon or MultiPolygon — got 'LineString'"
    {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [9.3110, 10.3605], [9.3120, 10.3605], [9.3115, 10.3615],
            ],
        },
        "properties": {
            "Name": "Bad Geometry Farm",
            "First Name": "Test",
            "Last Name": "Placeholder",
            "LGA": "Bauchi",
            "Commodity": "Soybeans",
        },
    },
]


class Command(BaseCommand):
    help = 'Seed messy field-condition demo data for Ake Collective'

    def add_arguments(self, parser):
        parser.add_argument('--flush', action='store_true',
                            help='Delete messy demo records and rebuild from scratch')

    def handle(self, *args, **options):
        if options['flush']:
            self._flush()
        with transaction.atomic():
            self._seed()
        self.stdout.write(self.style.SUCCESS('Messy demo seed complete.'))

    # ─────────────────────────────────────
    def _flush(self):
        from apps.companies.models import Company
        from apps.suppliers.models import Supplier, Farmer, FarmImportLog
        from apps.sales_orders.models import SalesOrder
        from apps.purchase_orders.models import PurchaseOrder
        from apps.products.models import Product

        try:
            ake = Company.objects.get(name='Ake Collective')
        except Company.DoesNotExist:
            self.stdout.write('  Ake Collective not found — nothing to flush.')
            return

        Supplier.objects.filter(name=SUPPLIER_NAME, company=ake).delete()
        SalesOrder.objects.filter(order_number=SO_NUMBER, company=ake).delete()
        PurchaseOrder.objects.filter(order_number=PO_NUMBER, company=ake).delete()
        Product.objects.filter(name=PRODUCT_NAME, company=ake).delete()
        Farmer.objects.filter(
            first_name='Zainab', last_name='Garba', company=ake
        ).delete()
        self.stdout.write('  Flushed messy demo records.')

    # ─────────────────────────────────────
    def _seed(self):
        from apps.companies.models import Company
        from apps.suppliers.models import (
            Supplier, Farm, Farmer, FarmImportLog, FarmCertification,
        )
        from apps.users.models import CustomUser
        from apps.products.models import Product
        from apps.inventory.models import Inventory
        from apps.purchase_orders.models import PurchaseOrder, PurchaseOrderItem
        from apps.sales_orders.models import SalesOrder, SalesOrderItem
        from apps.sales_orders.batch import Batch
        from apps.sales_orders.quality import PhytosanitaryCertificate, BatchQualityTest
        from apps.audit.models import AuditLog
        from apps.suppliers.import_pipeline import run_farm_geojson_import

        # ── Tenant ───────────────────────────────────────────────────────────
        try:
            ake = Company.objects.get(name='Ake Collective')
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                '  Ake Collective not found — run seed_data first.'
            ))
            return

        ake_staff = CustomUser.objects.filter(
            username='ake_staff', company=ake
        ).first()
        ake_mgr = CustomUser.objects.filter(
            username='ake_manager', company=ake
        ).first()

        # ── Supplier ─────────────────────────────────────────────────────────
        coop, _ = Supplier.objects.get_or_create(
            name=SUPPLIER_NAME, company=ake,
            defaults={
                'category': 'cooperative',
                'contact_person': 'Malam Garba Sule',
                'phone': '+234 803 900 0101',
                'email': 'contact@bauchisoy.ng',
                'country': 'Nigeria',
                'city': 'Bauchi',
                'is_active': True,
            }
        )
        self.stdout.write(f'  Supplier: {coop}')

        # ── Pre-create Zainab Garba (tests commodity fallback from farmer.crops) ──
        Farmer.objects.get_or_create(
            first_name='Zainab', last_name='Garba', company=ake,
            defaults={
                'gender': 'F',
                'village': 'Ganjuwa',
                'lga': 'Ganjuwa',
                'crops': 'Sesame, Soybeans',
                'consent_given': True,
                'consent_date': datetime.date(2026, 4, 1),
            }
        )
        self.stdout.write('  Pre-created: Zainab Garba (crops: Sesame, Soybeans)')

        # ── Run import pipeline ───────────────────────────────────────────────
        result = run_farm_geojson_import(
            company=ake,
            supplier=coop,
            features=FEATURES,
            default_commodity='',
            dry_run=False,
        )

        # Write FarmImportLog exactly as the view does
        FarmImportLog.objects.create(
            company=ake,
            uploaded_by=ake_staff,
            supplier=coop,
            filename=FILENAME,
            dry_run=False,
            total=result['total'],
            created=result['created'],
            would_create=result['would_create'],
            duplicates=result['duplicates'],
            blocked=result['blocked'],
            errors=result['errors'],
            auto_corrected=result['auto_corrected'],
            warning_count=len(result['warnings']),
            error_detail=result['error_detail'],
            blocked_detail=result['blocked_detail'],
            warning_detail=result['warnings'],
            transformation_log=result['transformations'],
        )

        # Write AuditLog for the import
        if result['created'] and ake_staff:
            AuditLog.objects.create(
                company=ake,
                user=ake_staff,
                action='import',
                model_name='Farm',
                object_repr=f"{result['created']} farms — {FILENAME}"[:255],
                changes={
                    'created':    result['created'],
                    'duplicates': result['duplicates'],
                    'blocked':    result['blocked'],
                    'errors':     result['errors'],
                    'supplier':   coop.name,
                    'file':       FILENAME,
                },
                ip_address='127.0.0.1',
            )

        self.stdout.write(
            f'  Import: {result["created"]} created · '
            f'{result["duplicates"]} duplicates · '
            f'{result["blocked"]} blocked · '
            f'{result["errors"]} errors · '
            f'{len(result["warnings"])} warnings · '
            f'{result["auto_corrected"]} auto-corrected'
        )
        for t in result['transformations']:
            self.stdout.write(
                f'    ↳ row {t["row"]} [{t["farm"]}] '
                f'{t["field"]}: "{t["from"]}" → "{t["to"]}" ({t["reason"]})'
            )

        # ── Post-import: verify, certify, flag ───────────────────────────────
        farm_haruna  = Farm.objects.filter(
            company=ake, supplier=coop, name='Haruna Musa Farm — Alkaleri'
        ).first()
        farm_zainab  = Farm.objects.filter(
            company=ake, supplier=coop, name='Zainab Garba Holdings'
        ).first()
        farm_fatima  = Farm.objects.filter(
            company=ake, supplier=coop, name='Fatima Yakubu Plot C'
        ).first()
        farm_aliyu   = Farm.objects.filter(
            company=ake, supplier=coop, name='Aliyu Ibrahim Large Plot'
        ).first()

        if farm_haruna:
            Farm.objects.filter(pk=farm_haruna.pk).update(
                deforestation_risk_status='low',
                deforestation_reference_date=datetime.date(2020, 12, 31),
                land_cleared_after_cutoff=False,
                mapping_date=datetime.date(2026, 4, 5),
                mapped_by=ake_staff,
                is_eudr_verified=True,
                verified_by=ake_mgr,
                verified_date=datetime.date(2026, 4, 10),
                verification_expiry=datetime.date(2027, 4, 10),
                harvest_year=2025,
                fvf_consent_given=True,
                fvf_consent_date=datetime.date(2026, 4, 5),
                fvf_land_acquisition='purchased',
                fvf_land_tenure='owned',
                fvf_years_farming=8,
                fvf_untouched_forest=False,
                fvf_expansion_intent=False,
            )
            AuditLog.objects.create(
                company=ake, user=ake_mgr, action='update',
                model_name='Farm',
                object_repr=str(farm_haruna),
                changes={'is_eudr_verified': True, 'fvf_consent_given': True},
                ip_address='127.0.0.1',
            )
            self.stdout.write(f'  Verified: {farm_haruna.name}')

        if farm_zainab:
            Farm.objects.filter(pk=farm_zainab.pk).update(
                deforestation_risk_status='low',
                deforestation_reference_date=datetime.date(2020, 12, 31),
                land_cleared_after_cutoff=False,
                mapping_date=datetime.date(2026, 4, 5),
                mapped_by=ake_staff,
                is_eudr_verified=True,
                verified_by=ake_mgr,
                verified_date=datetime.date(2026, 4, 12),
                verification_expiry=datetime.date(2027, 4, 12),
                harvest_year=2025,
                fvf_consent_given=True,
                fvf_consent_date=datetime.date(2026, 4, 5),
            )
            # FarmCertification — Fairtrade on Zainab's farm
            FarmCertification.objects.get_or_create(
                company=ake, farm=farm_zainab,
                cert_type='fairtrade',
                certifying_body='Fairtrade Africa',
                defaults={
                    'certificate_number': 'FTA-NG-2025-8841',
                    'issued_date': datetime.date(2025, 6, 1),
                    'expiry_date': datetime.date(2027, 5, 31),
                }
            )
            self.stdout.write(f'  Verified + Fairtrade cert: {farm_zainab.name}')

        if farm_aliyu:
            Farm.objects.filter(pk=farm_aliyu.pk).update(
                deforestation_risk_status='high',
                mapping_date=datetime.date(2026, 4, 5),
                mapped_by=ake_staff,
                is_eudr_verified=False,
            )
            self.stdout.write(f'  Flagged high-risk (large plot): {farm_aliyu.name}')

        # ── Product / Inventory / Purchase Order ──────────────────────────────
        prod, _ = Product.objects.get_or_create(
            name=PRODUCT_NAME, company=ake,
            defaults={
                'supplier': coop,
                'category': 'produce',
                'unit': 'kg',
                'unit_price': 620.00,
                'description': 'Clean, dried soybeans. Bauchi State. 2025 harvest.',
                'is_active': True,
            }
        )

        inv, _ = Inventory.objects.get_or_create(
            company=ake, product=prod, warehouse_location='Bauchi Collection Point',
            defaults={'quantity': 18000, 'low_stock_threshold': 2000}
        )

        po, _ = PurchaseOrder.objects.get_or_create(
            order_number=PO_NUMBER, company=ake,
            defaults={
                'supplier': coop,
                'status': 'received',
                'notes': 'First coop delivery — April 2026 harvest.',
            }
        )
        self.stdout.write(f'  PO: {po.order_number}  ·  Product: {prod.name}')

        # ── EU Sales Order ────────────────────────────────────────────────────
        so, _ = SalesOrder.objects.get_or_create(
            order_number=SO_NUMBER, company=ake,
            defaults={
                'customer_name': 'Olam Agri B.V.',
                'customer_email': 'procurement@olam.eu',
                'customer_phone': '+31 20 000 0099',
                'status': 'confirmed',
                'is_eu_export': True,
                'nxp_reference': 'NXP-2026-00441',
                'notes': (
                    'Bauchi soy — Alkaleri + Ganjuwa LGAs. '
                    'EUDR DDS required before shipment. '
                    '2 verified farms, 1 high-risk farm excluded from batch.'
                ),
            }
        )

        # Add a line item so the batch commodity link works
        if not so.items.exists():
            SalesOrderItem.objects.create(
                sales_order=so,
                product=prod,
                quantity=15000,
                unit_price=620.00,
            )

        self.stdout.write(f'  SO: {so.order_number}  ·  Customer: {so.customer_name}')

        # ── Batch ─────────────────────────────────────────────────────────────
        if not Batch.objects.filter(company=ake, sales_order=so).exists():
            batch = Batch(
                company=ake,
                sales_order=so,
                commodity='Soybeans',
                quantity_kg=15000.000,
                notes=(
                    'Bauchi State, 2025 harvest. '
                    'Farms: Alkaleri LGA (Haruna Musa) + Ganjuwa LGA (Zainab Garba). '
                    'High-risk large plot (Aliyu Ibrahim) excluded — pending re-verification.'
                ),
            )
            batch.save()
            linked_farms = [f for f in [farm_haruna, farm_zainab] if f]
            batch.farms.set(linked_farms)

            AuditLog.objects.create(
                company=ake, user=ake_mgr, action='create',
                model_name='Batch',
                object_repr=str(batch),
                changes={'farms_linked': len(linked_farms), 'quantity_kg': 15000},
                ip_address='127.0.0.1',
            )
            self.stdout.write(
                f'  Batch: {batch.batch_number}  ·  15,000 kg  ·  '
                f'{len(linked_farms)} farm(s) linked'
            )

            # Phytosanitary certificate
            PhytosanitaryCertificate.objects.get_or_create(
                company=ake, batch=batch,
                certificate_number='NAQS/BCH/2026/00719',
                defaults={
                    'issuing_office': 'NAQS Bauchi State Office',
                    'inspector_name': 'Insp. Mohammed Bello',
                    'inspection_date': datetime.date(2026, 4, 14),
                    'issued_date':     datetime.date(2026, 4, 15),
                    'expiry_date':     datetime.date(2026, 10, 14),
                    'notes': 'Soybean — 15,000 kg. Visually clean, no visible pest damage.',
                }
            )

            # Quality tests
            BatchQualityTest.objects.get_or_create(
                company=ake, batch=batch, test_type='mrl',
                defaults={
                    'lab_name': 'SGS Nigeria Ltd',
                    'lab_certificate_ref': 'SGS-NGR-2026-MRL-4419',
                    'test_date': datetime.date(2026, 4, 13),
                    'result': 'pass',
                    'notes': 'All pesticide residues below EU MRL (Reg. 396/2005). Report on file.',
                }
            )
            BatchQualityTest.objects.get_or_create(
                company=ake, batch=batch, test_type='aflatoxin',
                defaults={
                    'lab_name': 'Intertek Nigeria',
                    'lab_certificate_ref': '',
                    'test_date': None,
                    'result': 'pending',
                    'notes': 'Sample submitted 16 Apr 2026 — awaiting result from Intertek Lagos.',
                }
            )
            self.stdout.write(
                f'  Compliance docs: NAQS cert (current) · '
                f'MRL test (pass) · Aflatoxin (pending)'
            )

            # Lock the batch
            batch.is_locked = True
            batch.save(update_fields=['is_locked', 'updated_at'])
            AuditLog.objects.create(
                company=ake, user=ake_mgr, action='update',
                model_name='Batch',
                object_repr=str(batch),
                changes={'is_locked': True},
                ip_address='127.0.0.1',
            )
            self.stdout.write(f'  Batch locked. Trace URL: {batch.trace_url}')

        else:
            self.stdout.write('  Batch already exists — skipped.')
