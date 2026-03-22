from django.core.management.base import BaseCommand
from datetime import date

class Command(BaseCommand):
    help = 'Seed demo supply chain data for Savanna Agro Trading Ltd'

    def handle(self, *args, **options):
        from apps.companies.models import Company
        from apps.users.models import CustomUser
        from apps.suppliers.models import Supplier, Farm
        from apps.products.models import Product
        from apps.inventory.models import Inventory
        from apps.purchase_orders.models import PurchaseOrder, PurchaseOrderItem
        from apps.sales_orders.models import SalesOrder, SalesOrderItem

        try:
            company = Company.objects.get(name='Savanna Agro Trading Ltd')
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR('Savanna Agro Trading Ltd not found.'))
            return

        admin = CustomUser.objects.filter(company=company, system_role='org_admin').first()

        # ── Products ──────────────────────────────────────────
        self.stdout.write('Creating products...')
        products_data = [
            {'name': 'Soybean Grade A',   'unit': 'kg', 'description': 'Premium grade soybean for export'},
            {'name': 'Sesame Grade 1',    'unit': 'kg', 'description': 'High-oil sesame seed for export'},
            {'name': 'Cashew Grade W320', 'unit': 'kg', 'description': 'Whole cashew kernel grade W320'},
            {'name': 'White Maize',       'unit': 'kg', 'description': 'Dried white maize grain'},
        ]
        products = {}
        for p in products_data:
            obj, created = Product.objects.get_or_create(
                name=p['name'], company=company,
                defaults={'unit': p['unit'], 'description': p['description']}
            )
            products[p['name']] = obj
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Product: {p["name"]}'))

        # ── Suppliers ─────────────────────────────────────────
        self.stdout.write('Creating suppliers...')
        suppliers_data = [
            {'name': 'Kano Agro Cooperative',     'contact': 'Malam Sani Abubakar', 'phone': '08031234567', 'reliability_score': 92},
            {'name': 'Kaduna Farm Collective',    'contact': 'Ibrahim Musa',         'phone': '08041234567', 'reliability_score': 85},
            {'name': 'Niger State Farmers Union', 'contact': 'Abdullahi Bello',      'phone': '08051234567', 'reliability_score': 78},
            {'name': 'Benue Agri Producers',      'contact': 'Emmanuel Terver',      'phone': '08061234567', 'reliability_score': 88},
            {'name': 'Kebbi Grain Merchants',     'contact': 'Usman Gwandu',         'phone': '08071234567', 'reliability_score': 95},
            {'name': 'Zamfara Farm Network',      'contact': 'Garba Shinkafi',       'phone': '08081234567', 'reliability_score': 71},
        ]
        suppliers = []
        for s in suppliers_data:
            obj, created = Supplier.objects.get_or_create(
                name=s['name'], company=company,
                defaults={
                    'contact_person': s['contact'],
                    'phone': s['phone'],
                    'country': 'Nigeria',
                    'reliability_score': s['reliability_score'],
                }
            )
            suppliers.append(obj)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Supplier: {s["name"]}'))

        # ── Farms ─────────────────────────────────────────────
        self.stdout.write('Creating farms...')
        farms_data = [
            {'supplier': 0, 'name': 'Kano North Plot A', 'area': 12.5, 'lat': 12.0022, 'lng': 8.5919,  'risk': 'low',      'state': 'Kano',    'commodity': 'Soybean'},
            {'supplier': 0, 'name': 'Kano North Plot B', 'area': 8.3,  'lat': 12.0150, 'lng': 8.6100,  'risk': 'low',      'state': 'Kano',    'commodity': 'Soybean'},
            {'supplier': 0, 'name': 'Kano South Farm',   'area': 15.0, 'lat': 11.9800, 'lng': 8.5700,  'risk': 'standard', 'state': 'Kano',    'commodity': 'Soybean'},
            {'supplier': 1, 'name': 'Kaduna East Farm',  'area': 20.0, 'lat': 10.5222, 'lng': 7.4383,  'risk': 'low',      'state': 'Kaduna',  'commodity': 'Soybean'},
            {'supplier': 1, 'name': 'Kaduna West Plot',  'area': 11.0, 'lat': 10.5000, 'lng': 7.4000,  'risk': 'standard', 'state': 'Kaduna',  'commodity': 'Soybean'},
            {'supplier': 2, 'name': 'Minna Farm Block',  'area': 18.5, 'lat': 9.6139,  'lng': 6.5569,  'risk': 'standard', 'state': 'Niger',   'commodity': 'Sesame'},
            {'supplier': 2, 'name': 'Bida North Plot',   'area': 9.0,  'lat': 9.0800,  'lng': 6.0100,  'risk': 'low',      'state': 'Niger',   'commodity': 'Sesame'},
            {'supplier': 3, 'name': 'Makurdi Farm A',    'area': 22.0, 'lat': 7.7300,  'lng': 8.5200,  'risk': 'low',      'state': 'Benue',   'commodity': 'Cashew'},
            {'supplier': 3, 'name': 'Gboko Plot',        'area': 14.0, 'lat': 7.3167,  'lng': 9.0000,  'risk': 'standard', 'state': 'Benue',   'commodity': 'Cashew'},
            {'supplier': 4, 'name': 'Birnin Kebbi Farm', 'area': 25.0, 'lat': 12.4539, 'lng': 4.1975,  'risk': 'low',      'state': 'Kebbi',   'commodity': 'Sesame'},
            {'supplier': 4, 'name': 'Argungu Plot',      'area': 16.0, 'lat': 12.7400, 'lng': 4.5200,  'risk': 'low',      'state': 'Kebbi',   'commodity': 'Sesame'},
            {'supplier': 4, 'name': 'Zuru Farm',         'area': 10.5, 'lat': 11.4333, 'lng': 5.2333,  'risk': 'standard', 'state': 'Kebbi',   'commodity': 'Sesame'},
            {'supplier': 5, 'name': 'Gusau Farm Block',  'area': 13.0, 'lat': 12.1704, 'lng': 6.6649,  'risk': 'high',     'state': 'Zamfara', 'commodity': 'Maize'},
            {'supplier': 5, 'name': 'Kaura Namoda Plot', 'area': 7.5,  'lat': 12.5833, 'lng': 6.5833,  'risk': 'standard', 'state': 'Zamfara', 'commodity': 'Maize'},
        ]
        for f in farms_data:
            geolocation = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [f['lng'],       f['lat']],
                        [f['lng']+0.01,  f['lat']],
                        [f['lng']+0.01,  f['lat']+0.01],
                        [f['lng'],       f['lat']+0.01],
                        [f['lng'],       f['lat']],
                    ]]
                }
            }
            obj, created = Farm.objects.get_or_create(
                name=f['name'], supplier=suppliers[f['supplier']],
                defaults={
                    'company': company,
                    'area_hectares': f['area'],
                    'state_region': f['state'],
                    'country': 'Nigeria',
                    'commodity': f['commodity'],
                    'deforestation_risk_status': f['risk'],
                    'geolocation': geolocation,
                    'mapping_date': date(2024, 6, 1),
                    'mapped_by': admin,
                    'verification_expiry': date(2026, 12, 31),
                    'deforestation_reference_date': date(2020, 12, 31),
                    'harvest_year': 2024,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Farm: {f["name"]}'))

        # ── Inventory ─────────────────────────────────────────
        self.stdout.write('Creating inventory...')
        inventory_data = [
            {'product': 'Soybean Grade A',   'qty': 45000, 'lot': 'LOT-SOY-2024-001', 'moisture': 12.5, 'grade': 'A',    'harvest': date(2024, 11, 15), 'origin': 'Kano',    'warehouse': 'Kano Warehouse A'},
            {'product': 'Soybean Grade A',   'qty': 32000, 'lot': 'LOT-SOY-2024-002', 'moisture': 13.0, 'grade': 'A',    'harvest': date(2024, 11, 20), 'origin': 'Kaduna',  'warehouse': 'Kaduna Store B'},
            {'product': 'Sesame Grade 1',    'qty': 18000, 'lot': 'LOT-SES-2024-001', 'moisture': 6.0,  'grade': '1',    'harvest': date(2024, 10, 10), 'origin': 'Niger',   'warehouse': 'Minna Depot'},
            {'product': 'Sesame Grade 1',    'qty': 12000, 'lot': 'LOT-SES-2024-002', 'moisture': 5.8,  'grade': '1',    'harvest': date(2024, 10, 25), 'origin': 'Kebbi',   'warehouse': 'Kebbi Store'},
            {'product': 'Cashew Grade W320', 'qty': 8500,  'lot': 'LOT-CSW-2024-001', 'moisture': 8.0,  'grade': 'W320', 'harvest': date(2024, 4, 20),  'origin': 'Benue',   'warehouse': 'Makurdi Cold Store'},
            {'product': 'White Maize',       'qty': 60000, 'lot': 'LOT-MZE-2024-001', 'moisture': 14.0, 'grade': 'A',    'harvest': date(2024, 9, 5),   'origin': 'Zamfara', 'warehouse': 'Gusau Silo'},
            {'product': 'White Maize',       'qty': 25000, 'lot': 'LOT-MZE-2024-002', 'moisture': 13.5, 'grade': 'B',    'harvest': date(2024, 9, 15),  'origin': 'Benue',   'warehouse': 'Benue Store B'},
        ]
        for i in inventory_data:
            obj, created = Inventory.objects.get_or_create(
                lot_number=i['lot'], warehouse_location=i['warehouse'], company=company,
                defaults={
                    'product': products[i['product']],
                    'quantity': i['qty'],
                    'moisture_content': i['moisture'],
                    'quality_grade': i['grade'],
                    'harvest_date': i['harvest'],
                    'origin_state': i['origin'],
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Inventory: {i["lot"]} — {i["qty"]}kg'))

        # ── Purchase Orders ───────────────────────────────────
        self.stdout.write('Creating purchase orders...')
        po_data = [
            {'ref': 'PO-2024-001', 'supplier': 0, 'status': 'received',  'date': date(2024, 10, 1),  'delivery': date(2024, 11, 15), 'items': [('Soybean Grade A', 45000, 280)]},
            {'ref': 'PO-2024-002', 'supplier': 1, 'status': 'received',  'date': date(2024, 10, 8),  'delivery': date(2024, 11, 20), 'items': [('Soybean Grade A', 32000, 275)]},
            {'ref': 'PO-2024-003', 'supplier': 2, 'status': 'received',  'date': date(2024, 9, 15),  'delivery': date(2024, 10, 10), 'items': [('Sesame Grade 1', 18000, 520)]},
            {'ref': 'PO-2024-004', 'supplier': 4, 'status': 'received',  'date': date(2024, 9, 20),  'delivery': date(2024, 10, 25), 'items': [('Sesame Grade 1', 12000, 515)]},
            {'ref': 'PO-2024-005', 'supplier': 3, 'status': 'received',  'date': date(2024, 3, 10),  'delivery': date(2024, 4, 20),  'items': [('Cashew Grade W320', 8500, 1850)]},
            {'ref': 'PO-2024-006', 'supplier': 5, 'status': 'received',  'date': date(2024, 8, 1),   'delivery': date(2024, 9, 5),   'items': [('White Maize', 60000, 95)]},
            {'ref': 'PO-2024-007', 'supplier': 3, 'status': 'received',  'date': date(2024, 8, 15),  'delivery': date(2024, 9, 15),  'items': [('White Maize', 25000, 98)]},
            {'ref': 'PO-2025-001', 'supplier': 0, 'status': 'pending',   'date': date(2025, 1, 10),  'delivery': date(2025, 3, 1),   'items': [('Soybean Grade A', 50000, 290)]},
            {'ref': 'PO-2025-002', 'supplier': 4, 'status': 'confirmed', 'date': date(2025, 1, 20),  'delivery': date(2025, 2, 28),  'items': [('Sesame Grade 1', 20000, 530)]},
        ]
        for po in po_data:
            obj, created = PurchaseOrder.objects.get_or_create(
                order_number=po['ref'], company=company,
                defaults={
                    'supplier': suppliers[po['supplier']],
                    'status': po['status'],
                    'order_date': po['date'],
                    'expected_delivery': po['delivery'],
                }
            )
            if created:
                for item in po['items']:
                    PurchaseOrderItem.objects.create(
                        purchase_order=obj,
                        product=products[item[0]],
                        quantity=item[1],
                        unit_price=item[2],
                    )
                self.stdout.write(self.style.SUCCESS(f'  PO: {po["ref"]}'))

        # ── Sales Orders ──────────────────────────────────────
        self.stdout.write('Creating sales orders...')
        so_data = [
            {'ref': 'SO-2024-001', 'customer': 'Olam Nigeria Ltd',     'status': 'completed', 'date': date(2024, 11, 25), 'delivery': date(2024, 12, 15), 'items': [('Soybean Grade A', 20000, 420)]},
            {'ref': 'SO-2024-002', 'customer': 'Cargill West Africa',  'status': 'completed', 'date': date(2024, 12, 1),  'delivery': date(2024, 12, 20), 'items': [('Soybean Grade A', 15000, 425)]},
            {'ref': 'SO-2024-003', 'customer': 'Meridian Commodities', 'status': 'completed', 'date': date(2024, 11, 10), 'delivery': date(2024, 11, 30), 'items': [('Sesame Grade 1', 10000, 780)]},
            {'ref': 'SO-2024-004', 'customer': 'Tradin Organic BV',    'status': 'completed', 'date': date(2024, 11, 15), 'delivery': date(2024, 12, 5),  'items': [('Sesame Grade 1', 8000, 795)]},
            {'ref': 'SO-2024-005', 'customer': 'Kerry Group Ireland',  'status': 'completed', 'date': date(2024, 5, 10),  'delivery': date(2024, 6, 1),   'items': [('Cashew Grade W320', 5000, 2800)]},
            {'ref': 'SO-2024-006', 'customer': 'Dangote Flour Mills',  'status': 'dispatched','date': date(2024, 10, 1),  'delivery': date(2024, 10, 20), 'items': [('White Maize', 40000, 145)]},
            {'ref': 'SO-2025-001', 'customer': 'Olam Nigeria Ltd',     'status': 'confirmed', 'date': date(2025, 1, 15),  'delivery': date(2025, 3, 10),  'items': [('Soybean Grade A', 25000, 435)]},
            {'ref': 'SO-2025-002', 'customer': 'Nexira France',        'status': 'pending',   'date': date(2025, 2, 1),   'delivery': date(2025, 4, 1),   'items': [('Sesame Grade 1', 15000, 810)]},
        ]
        for so in so_data:
            obj, created = SalesOrder.objects.get_or_create(
                order_number=so['ref'], company=company,
                defaults={
                    'customer_name': so['customer'],
                    'status': so['status'],
                    'order_date': so['date'],
                    'expected_delivery': so['delivery'],
                    'created_by': admin,
                }
            )
            if created:
                for item in so['items']:
                    SalesOrderItem.objects.create(
                        sales_order=obj,
                        product=products[item[0]],
                        quantity=item[1],
                        unit_price=item[2],
                    )
                self.stdout.write(self.style.SUCCESS(f'  SO: {so["ref"]} — {so["customer"]}'))

        self.stdout.write(self.style.SUCCESS('\nDone. Products: 4 | Suppliers: 6 | Farms: 14 | Inventory: 7 | POs: 9 | SOs: 8'))
