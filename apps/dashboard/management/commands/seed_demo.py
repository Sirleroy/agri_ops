"""
Management command: seed_demo
Builds a complete end-to-end demo chain for the AgriOps Trading LTD tenant:

  Plateau Soy Cooperative (supplier)
    → 3 farmers (with FVF data)
    → 3 GPS-mapped farms (Plateau State polygons, EUDR verified)
  Soybeans Export Grade product (HS 1201.90)
  Purchase Order → received → inventory (25 000 kg)
  Sales Order (EU export, Nexira SAS France)
    → SO line item (20 000 kg soybeans)
    → farms linked → Batch created

Safe to re-run — skips records that already exist.

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --flush   # remove demo chain and rebuild
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


# ── Demo polygon coordinates — Plateau State, Nigeria ─────────────────────────
# All coordinates are (longitude, latitude) — GeoJSON convention.
# Three smallholder plots near Shendam / Langtang LGAs.

FARM_GEODATA = [
    {
        'name': 'Sule Family Plot A',
        'area_hectares': 5.2,
        'fvf_land_acquisition': 'inherited',
        'fvf_land_tenure': 'village_consent',
        'fvf_years_farming': 14,
        'geolocation': {
            'type': 'Polygon',
            'coordinates': [[
                [9.5175, 8.8812],
                [9.5196, 8.8808],
                [9.5207, 8.8817],
                [9.5203, 8.8833],
                [9.5184, 8.8836],
                [9.5172, 8.8825],
                [9.5175, 8.8812],
            ]],
        },
    },
    {
        'name': 'Abubakar North Farm',
        'area_hectares': 3.8,
        'fvf_land_acquisition': 'bought',
        'fvf_land_tenure': 'title_deed',
        'fvf_years_farming': 7,
        'geolocation': {
            'type': 'Polygon',
            'coordinates': [[
                [9.4840, 8.9022],
                [9.4858, 8.9018],
                [9.4865, 8.9029],
                [9.4858, 8.9041],
                [9.4843, 8.9038],
                [9.4836, 8.9028],
                [9.4840, 8.9022],
            ]],
        },
    },
    {
        'name': 'Yusuf Main Farm',
        'area_hectares': 8.4,
        'fvf_land_acquisition': 'granted',
        'fvf_land_tenure': 'village_consent',
        'fvf_years_farming': 21,
        'geolocation': {
            'type': 'Polygon',
            'coordinates': [[
                [9.5408, 8.8697],
                [9.5441, 8.8692],
                [9.5456, 8.8703],
                [9.5453, 8.8722],
                [9.5438, 8.8731],
                [9.5415, 8.8728],
                [9.5403, 8.8714],
                [9.5408, 8.8697],
            ]],
        },
    },
]


class Command(BaseCommand):
    help = 'Seed a complete demo chain for the AgriOps Trading LTD tenant'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Remove all demo chain records before rebuilding',
        )

    def handle(self, *args, **options):
        from apps.companies.models import Company
        ake = Company.objects.filter(name='AgriOps Trading LTD').first()
        if not ake:
            raise CommandError(
                'AgriOps Trading LTD company not found. '
                'Check the company name in the admin panel.'
            )

        if options['flush']:
            self._flush(ake)

        with transaction.atomic():
            self._seed(ake)

        self.stdout.write(self.style.SUCCESS('\nDemo chain seeded. Ready for demo.'))
        self.stdout.write('  Login: ake_admin / agriops2026!')

    # ──────────────────────────────────────────────────────────────────────────

    def _flush(self, ake):
        from apps.suppliers.models import Supplier, Farm, Farmer
        from apps.products.models import Product
        from apps.purchase_orders.models import PurchaseOrder
        from apps.sales_orders.models import SalesOrder

        SalesOrder.objects.filter(
            company=ake, order_number='DEMO-SO-2026-001'
        ).delete()
        PurchaseOrder.objects.filter(
            company=ake, order_number='DEMO-PO-2026-001'
        ).delete()
        Product.objects.filter(
            company=ake, name='Soybeans Export Grade'
        ).delete()
        Farm.objects.filter(
            company=ake,
            name__in=[d['name'] for d in FARM_GEODATA],
        ).delete()
        Farmer.objects.filter(
            company=ake,
            first_name__in=['Haruna', 'Ramatu', 'Yusuf'],
            last_name__in=['Sule', 'Abubakar', 'Mohammed'],
        ).delete()
        Supplier.objects.filter(
            company=ake, name='Plateau Soy Cooperative'
        ).delete()
        self.stdout.write('  Flushed existing demo chain.')

    # ──────────────────────────────────────────────────────────────────────────

    def _seed(self, ake):
        import datetime
        from apps.companies.models import Company
        from apps.users.models import CustomUser
        from apps.suppliers.models import Supplier, Farm, Farmer
        from apps.products.models import Product
        from apps.inventory.models import Inventory
        from apps.purchase_orders.models import PurchaseOrder, PurchaseOrderItem
        from apps.sales_orders.models import SalesOrder, SalesOrderItem
        from apps.sales_orders.batch import Batch

        # Grab a staff user to act as mapped_by / verified_by
        staff = (
            CustomUser.objects.filter(company=ake, system_role='staff').first()
            or CustomUser.objects.filter(company=ake, system_role='org_admin').first()
        )
        manager = (
            CustomUser.objects.filter(company=ake, system_role='org_admin').first()
        )

        # ── Supplier ──────────────────────────────────────────────────────────
        sup, _ = Supplier.objects.get_or_create(
            name='Plateau Soy Cooperative', company=ake,
            defaults={
                'category': 'cooperative',
                'contact_person': 'Mallam Umar Sule',
                'phone': '+234 803 900 0101',
                'email': 'contact@plateausoy.ng',
                'country': 'Nigeria',
                'city': 'Shendam',
                'is_active': True,
                'reliability_score': 8,
            }
        )
        self.stdout.write(f'  Supplier: {sup}')

        # ── Farmers ───────────────────────────────────────────────────────────
        farmer_data = [
            {
                'first_name': 'Haruna', 'last_name': 'Sule',
                'gender': 'M', 'phone': '+234 803 111 9001',
                'village': 'Shendam Town', 'lga': 'Shendam',
                'nin': '98700000001', 'crops': 'Soybeans, Groundnut',
                'consent_given': True,
                'consent_date': datetime.date(2026, 3, 12),
            },
            {
                'first_name': 'Ramatu', 'last_name': 'Abubakar',
                'gender': 'F', 'phone': '+234 803 111 9002',
                'village': 'Gindiri', 'lga': 'Mangu',
                'nin': '98700000002', 'crops': 'Soybeans',
                'consent_given': True,
                'consent_date': datetime.date(2026, 3, 12),
            },
            {
                'first_name': 'Yusuf', 'last_name': 'Mohammed',
                'gender': 'M', 'phone': '+234 803 111 9003',
                'village': 'Langtang', 'lga': 'Langtang North',
                'nin': '98700000003', 'crops': 'Soybeans, Maize',
                'consent_given': True,
                'consent_date': datetime.date(2026, 3, 13),
            },
        ]

        farmers = []
        for fd in farmer_data:
            f, _ = Farmer.objects.get_or_create(
                first_name=fd['first_name'], last_name=fd['last_name'], company=ake,
                defaults={k: v for k, v in fd.items()
                          if k not in ('first_name', 'last_name')},
            )
            farmers.append(f)
        self.stdout.write(f'  Farmers: {", ".join(str(f) for f in farmers)}')

        # ── Farms ─────────────────────────────────────────────────────────────
        farms = []
        for i, gd in enumerate(FARM_GEODATA):
            farm, _ = Farm.objects.get_or_create(
                name=gd['name'], company=ake,
                defaults={
                    'supplier': sup,
                    'farmer': farmers[i],
                    'country': 'Nigeria',
                    'state_region': 'Plateau',
                    'commodity': 'Soy',
                    'area_hectares': gd['area_hectares'],
                    'geolocation': gd['geolocation'],
                    'harvest_year': 2025,
                    'deforestation_risk_status': 'low',
                    'deforestation_reference_date': datetime.date(2020, 12, 31),
                    'land_cleared_after_cutoff': False,
                    'mapping_date': datetime.date(2026, 3, 14),
                    'mapped_by': staff,
                    'is_eudr_verified': True,
                    'verified_by': manager,
                    'verified_date': datetime.date(2026, 3, 20),
                    'verification_expiry': datetime.date(2027, 3, 20),
                    # FVF — from per-farm data + farmer consent record
                    'fvf_land_acquisition': gd['fvf_land_acquisition'],
                    'fvf_land_tenure': gd['fvf_land_tenure'],
                    'fvf_years_farming': gd['fvf_years_farming'],
                    'fvf_untouched_forest': False,
                    'fvf_expansion_intent': False,
                    'fvf_consent_given': True,
                    'fvf_consent_date': farmers[i].consent_date,
                },
            )
            farms.append(farm)
        self.stdout.write(
            f'  Farms: {", ".join(f.name for f in farms)} '
            f'({sum(gd["area_hectares"] for gd in FARM_GEODATA):.1f} ha total)'
        )

        # ── Product ───────────────────────────────────────────────────────────
        prod, _ = Product.objects.get_or_create(
            name='Soybeans Export Grade', company=ake,
            defaults={
                'supplier': sup,
                'category': 'commodity',
                'unit': 'kg',
                'unit_price': 320.00,
                'hs_code': '1201.90',
                'description': 'Non-GMO soybeans, Plateau State origin, export grade',
                'is_active': True,
            }
        )
        self.stdout.write(f'  Product: {prod} (HS {prod.hs_code})')

        # ── Purchase Order → received ─────────────────────────────────────────
        po, po_created = PurchaseOrder.objects.get_or_create(
            order_number='DEMO-PO-2026-001', company=ake,
            defaults={
                'supplier': sup,
                'status': 'received',
                'expected_delivery': datetime.date(2026, 3, 25),
                'notes': 'Plateau State soy procurement — 2025 harvest, pre-export stock.',
            }
        )
        item, _ = PurchaseOrderItem.objects.get_or_create(
            purchase_order=po, product=prod,
            defaults={'quantity': 25000, 'unit_price': 320.00},
        )
        self.stdout.write(f'  PO: {po.order_number}  ·  25,000 kg  ·  status: {po.status}')

        # Inventory — mirror PO receipt
        inv, inv_created = Inventory.objects.get_or_create(
            company=ake, product=prod, warehouse_location='Shendam Warehouse',
            defaults={
                'quantity': 25000,
                'low_stock_threshold': 2000,
                'lot_number': 'SOY-2025-PLT-001',
                'moisture_content': 11.5,
                'quality_grade': 'A',
                'harvest_date': datetime.date(2025, 11, 15),
                'origin_state': 'Plateau',
            }
        )
        if inv_created:
            self.stdout.write(f'  Inventory: 25,000 kg  ·  lot {inv.lot_number}')
        else:
            self.stdout.write(f'  Inventory: already exists ({inv.quantity} kg on hand)')

        # ── Sales Order ───────────────────────────────────────────────────────
        so, so_created = SalesOrder.objects.get_or_create(
            order_number='DEMO-SO-2026-001', company=ake,
            defaults={
                'customer_name': 'Nexira SAS',
                'customer_email': 'procurement@nexira.eu',
                'customer_phone': '+33 1 4000 0099',
                'status': 'confirmed',
                'is_eu_export': True,
                'nxp_reference': 'NXP-2026-001',
                'certificate_of_origin_ref': 'COO-2026-0441',
                'notes': (
                    'EU export — EUDR due diligence required before dispatch. '
                    'Incoterms: FOB Lagos. Destination: Rouen, France.'
                ),
            }
        )
        SalesOrderItem.objects.get_or_create(
            sales_order=so, product=prod,
            defaults={'quantity': 20000, 'unit_price': 420.00},
        )
        self.stdout.write(
            f'  Sales Order: {so.order_number}  ·  Nexira SAS  ·  '
            f'20,000 kg  ·  EU export: {so.is_eu_export}'
        )

        # ── Batch — link all 3 farms ──────────────────────────────────────────
        existing_batch = Batch.objects.filter(company=ake, sales_order=so).first()
        if not existing_batch:
            batch = Batch(
                company=ake,
                sales_order=so,
                commodity='Soy',
                quantity_kg=20000.000,
                notes=(
                    'Plateau State soy — Shendam, Mangu and Langtang LGAs. '
                    '3 farms, 17.4 ha total. Pre-dispatch DDS verification in progress.'
                ),
            )
            batch.save()
            batch.farms.set(farms)
            self.stdout.write(
                f'  Batch: {batch.batch_number}  ·  20,000 kg  ·  '
                f'{len(farms)} farms  ·  17.4 ha'
            )
        else:
            self.stdout.write(
                f'  Batch: already exists ({existing_batch.batch_number})'
            )

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write('  Demo chain summary:')
        self.stdout.write(f'    Supplier  → Plateau Soy Cooperative')
        self.stdout.write(f'    Farmers   → {len(farmers)} (all with FVF + consent)')
        self.stdout.write(f'    Farms     → {len(farms)} (GPS mapped, EUDR verified, satellite-visible)')
        self.stdout.write(f'    Product   → Soybeans Export Grade (HS 1201.90)')
        self.stdout.write(f'    PO        → DEMO-PO-2026-001  ·  25,000 kg received')
        self.stdout.write(f'    SO        → DEMO-SO-2026-001  ·  Nexira SAS  ·  EU export')
        self.stdout.write(f'    Batch     → 3 farms linked  ·  20,000 kg  ·  DDS-ready')
