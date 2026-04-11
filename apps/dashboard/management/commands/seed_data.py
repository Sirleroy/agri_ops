"""
Management command: seed_data
Creates two demo tenants with realistic Nigerian agri-SME data.
Safe to run multiple times — skips existing records by name.

Usage:
    python manage.py seed_data
    python manage.py seed_data --flush   # wipe and rebuild
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Seed the database with two demo tenants and realistic AgriOps data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete all existing seed data before seeding'
        )

    def handle(self, *args, **options):
        if options['flush']:
            self._flush()
        with transaction.atomic():
            self._seed()
        self.stdout.write(self.style.SUCCESS('Seed complete.'))

    # ─────────────────────────────────────
    def _flush(self):
        from apps.companies.models import Company
        from apps.users.models import CustomUser
        names = ['Ake Collective', 'Agro Foods Nigeria Ltd']
        Company.objects.filter(name__in=names).delete()
        CustomUser.objects.filter(username__in=[
            'ake_admin', 'ake_manager', 'ake_staff', 'ake_viewer',
            'agro_admin', 'agro_staff',
        ]).delete()
        self.stdout.write('  Flushed existing seed data.')

    # ─────────────────────────────────────
    def _seed(self):
        import datetime
        from apps.companies.models import Company
        from apps.suppliers.models import Supplier, Farm, Farmer
        from apps.products.models import Product
        from apps.inventory.models import Inventory
        from apps.purchase_orders.models import PurchaseOrder
        from apps.sales_orders.models import SalesOrder
        from apps.sales_orders.batch import Batch

        # ── TENANT 1: Ake Collective ─────────────────────────────
        ake, _ = Company.objects.get_or_create(
            name='Ake Collective',
            defaults={
                'country': 'Nigeria',
                'city': 'Kano',
                'address': '12 Zaria Road, Kano',
                'phone': '+234 802 000 0001',
                'email': 'info@akecollective.ng',
                'plan_tier': 'pro',
                'is_active': True,
            }
        )
        self.stdout.write(f'  Company: {ake}')

        # Users — Ake
        self._make_user('ake_admin', 'Amara', 'Okafor',
                                    'org_admin', ake, 'Operations Director')
        ake_mgr   = self._make_user('ake_manager', 'Bello', 'Musa',
                                    'manager', ake, 'Procurement Manager')
        ake_staff = self._make_user('ake_staff', 'Chisom', 'Eze',
                                    'staff', ake, 'Field Officer')
        self._make_user('ake_viewer', 'Dayo', 'Adeyemi',
                                    'viewer', ake, 'Finance Analyst')

        # Suppliers — Ake
        sup1, _ = Supplier.objects.get_or_create(
            name='Kano Agro Inputs Ltd', company=ake,
            defaults={
                'category': 'fertilizer',
                'contact_person': 'Ibrahim Sule',
                'phone': '+234 803 111 0001',
                'email': 'ibrahim@kanoagroinputs.ng',
                'country': 'Nigeria', 'city': 'Kano',
                'is_active': True,
            }
        )
        sup2, _ = Supplier.objects.get_or_create(
            name='Sahel Seeds Co-op', company=ake,
            defaults={
                'category': 'seeds',
                'contact_person': 'Fatima Abubakar',
                'phone': '+234 804 222 0002',
                'email': 'fatima@sahelseeds.ng',
                'country': 'Nigeria', 'city': 'Sokoto',
                'is_active': True,
            }
        )
        sup3, _ = Supplier.objects.get_or_create(
            name='West Africa Packaging', company=ake,
            defaults={
                'category': 'packaging',
                'contact_person': 'Emeka Nwosu',
                'phone': '+234 805 333 0003',
                'email': 'emeka@wapackaging.ng',
                'country': 'Nigeria', 'city': 'Lagos',
                'is_active': True,
            }
        )
        self.stdout.write(f'  Suppliers: {sup1}, {sup2}, {sup3}')

        # Farmers — Ake (linked to farms)
        farmer1, _ = Farmer.objects.get_or_create(
            first_name='Haruna', last_name='Sule', company=ake,
            defaults={
                'gender': 'M',
                'phone': '+234 803 123 0001',
                'village': 'Shendam',
                'lga': 'Shendam',
                'nin': '12345000001',
                'crops': 'Soybeans, Groundnut',
                'consent_given': True,
                'consent_date': datetime.date(2026, 3, 10),
            }
        )
        farmer2, _ = Farmer.objects.get_or_create(
            first_name='Ramatu', last_name='Abubakar', company=ake,
            defaults={
                'gender': 'F',
                'phone': '+234 803 123 0002',
                'village': 'Langtang',
                'lga': 'Langtang North',
                'nin': '12345000002',
                'crops': 'Soybeans',
                'consent_given': True,
                'consent_date': datetime.date(2026, 3, 10),
            }
        )
        self.stdout.write(f'  Farmers: {farmer1}, {farmer2}')

        # Farms — Ake (EUDR traceability, fully filled for DDS)
        farm1, _ = Farm.objects.get_or_create(
            name='Sule Family Farm', company=ake,
            defaults={
                'supplier': sup2,
                'farmer': farmer1,
                'country': 'Nigeria',
                'state_region': 'Plateau',
                'commodity': 'Soy',
                'area_hectares': 12.50,
                'harvest_year': 2025,
                'deforestation_risk_status': 'low',
                'deforestation_reference_date': datetime.date(2020, 12, 31),
                'land_cleared_after_cutoff': False,
                'mapping_date': datetime.date(2026, 3, 15),
                'mapped_by': ake_staff,
                'is_eudr_verified': True,
                'verified_by': ake_mgr,
                'verified_date': datetime.date(2026, 3, 20),
                'verification_expiry': datetime.date(2027, 3, 20),
            }
        )
        farm2, _ = Farm.objects.get_or_create(
            name='Abubakar Cooperative Plot B', company=ake,
            defaults={
                'supplier': sup2,
                'farmer': farmer2,
                'country': 'Nigeria',
                'state_region': 'Plateau',
                'commodity': 'Soy',
                'area_hectares': 8.00,
                'harvest_year': 2025,
                'deforestation_risk_status': 'standard',
                'deforestation_reference_date': datetime.date(2020, 12, 31),
                'land_cleared_after_cutoff': False,
                'mapping_date': datetime.date(2026, 3, 15),
                'mapped_by': ake_staff,
                'is_eudr_verified': False,
            }
        )
        self.stdout.write(f'  Farms: {farm1}, {farm2}')

        # Products — Ake
        prod1, _ = Product.objects.get_or_create(
            name='NPK Fertilizer 20-10-10', company=ake,
            defaults={
                'supplier': sup1,
                'category': 'fertilizer',
                'unit': 'bag',
                'unit_price': 18500.00,
                'description': '50kg bag, suitable for cereals and legumes',
                'is_active': True,
            }
        )
        prod2, _ = Product.objects.get_or_create(
            name='Certified Soybean Seed (Improved)', company=ake,
            defaults={
                'supplier': sup2,
                'category': 'seeds',
                'unit': 'kg',
                'unit_price': 2200.00,
                'description': 'High-yield variety, certified by NASC',
                'is_active': True,
            }
        )
        prod3, _ = Product.objects.get_or_create(
            name='Woven Polypropylene Bag 50kg', company=ake,
            defaults={
                'supplier': sup3,
                'category': 'packaging',
                'unit': 'piece',
                'unit_price': 350.00,
                'description': 'Food-grade PP bag for grain packaging',
                'is_active': True,
            }
        )
        self.stdout.write(f'  Products: {prod1}, {prod2}, {prod3}')

        # Inventory — Ake
        Inventory.objects.get_or_create(
            company=ake, product=prod1, warehouse_location='Kano Main Store',
            defaults={'quantity': 120, 'low_stock_threshold': 20}
        )
        Inventory.objects.get_or_create(
            company=ake, product=prod2, warehouse_location='Kano Main Store',
            defaults={'quantity': 8, 'low_stock_threshold': 50}
        )
        Inventory.objects.get_or_create(
            company=ake, product=prod3, warehouse_location='Lagos Depot',
            defaults={'quantity': 500, 'low_stock_threshold': 100}
        )
        self.stdout.write('  Inventory seeded for Ake.')

        # Purchase Orders — Ake
        po1, _ = PurchaseOrder.objects.get_or_create(
            order_number='AKE-PO-2026-001', company=ake,
            defaults={
                'supplier': sup1,
                'status': 'delivered',
                'notes': 'Pre-season fertilizer stock-up',
            }
        )
        po2, _ = PurchaseOrder.objects.get_or_create(
            order_number='AKE-PO-2026-002', company=ake,
            defaults={
                'supplier': sup2,
                'status': 'pending',
                'notes': 'Planting season seed order',
            }
        )
        self.stdout.write(f'  Purchase Orders: {po1}, {po2}')

        # Sales Orders — Ake
        so1, _ = SalesOrder.objects.get_or_create(
            order_number='AKE-SO-2026-001', company=ake,
            defaults={
                'customer_name': 'Kano State Farmers Cooperative',
                'customer_email': 'procurement@kanofarmers.ng',
                'customer_phone': '+234 806 444 0001',
                'status': 'confirmed',
                'notes': 'Bulk fertilizer order for member farms',
            }
        )
        # EU export SO — EUDR compliance required
        so2, _ = SalesOrder.objects.get_or_create(
            order_number='AKE-SO-2026-002', company=ake,
            defaults={
                'customer_name': 'Nexira SAS',
                'customer_email': 'procurement@nexira.eu',
                'customer_phone': '+33 1 4000 0001',
                'status': 'confirmed',
                'is_eu_export': True,
                'notes': 'EU soybean export — EUDR due diligence statement required before dispatch.',
            }
        )
        self.stdout.write(f'  Sales Orders: {so1}, {so2}')

        # Batch — EUDR traceability chain: Farm → Batch → EU Sales Order
        if not Batch.objects.filter(company=ake, sales_order=so2).exists():
            batch = Batch(
                company=ake,
                sales_order=so2,
                commodity='Soy',
                quantity_kg=12500.000,
                notes='Plateau State soy — Shendam and Langtang LGAs. Pre-export DDS pending.',
            )
            batch.save()
            batch.farms.set([farm1])
            self.stdout.write(f'  Batch: {batch.batch_number}  ·  12,500 kg  ·  1 farm')

        # ── TENANT 2: Agro Foods Nigeria Ltd ────────────────────
        agro, _ = Company.objects.get_or_create(
            name='Agro Foods Nigeria Ltd',
            defaults={
                'country': 'Nigeria',
                'city': 'Ibadan',
                'address': '7 Challenge Road, Ibadan',
                'phone': '+234 807 555 0002',
                'email': 'info@agrofoods.ng',
                'plan_tier': 'free',
                'is_active': True,
            }
        )
        self.stdout.write(f'  Company: {agro}')

        self._make_user('agro_admin', 'Funke', 'Adebayo',
                                     'org_admin', agro, 'General Manager')
        self._make_user('agro_staff', 'Gbenga', 'Oladele',
                                     'staff', agro, 'Inventory Officer')

        sup4, _ = Supplier.objects.get_or_create(
            name='Oyo Agro Supplies', company=agro,
            defaults={
                'category': 'fertilizer',
                'contact_person': 'Taiwo Alabi',
                'phone': '+234 808 666 0004',
                'country': 'Nigeria', 'city': 'Ibadan',
                'is_active': True,
            }
        )

        prod4, _ = Product.objects.get_or_create(
            name='Urea Fertilizer 46%', company=agro,
            defaults={
                'supplier': sup4,
                'category': 'fertilizer',
                'unit': 'bag',
                'unit_price': 21000.00,
                'is_active': True,
            }
        )

        Inventory.objects.get_or_create(
            company=agro, product=prod4, warehouse_location='Ibadan Warehouse A',
            defaults={'quantity': 45, 'low_stock_threshold': 10}
        )
        self.stdout.write('  Tenant 2 (Agro Foods) seeded.')

    # ─────────────────────────────────────
    def _make_user(self, username, first, last, system_role, company, job_title):
        from apps.users.models import CustomUser
        user, created = CustomUser.objects.get_or_create(
            username=username,
            defaults={
                'first_name': first,
                'last_name': last,
                'system_role': system_role,
                'job_title': job_title,
                'company': company,
                'is_active': True,
            }
        )
        if created:
            user.set_password('agriops2026!')
            user.save()
            self.stdout.write(f'    User created: {username} / agriops2026!')
        return user
