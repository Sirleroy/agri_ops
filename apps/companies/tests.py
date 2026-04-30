"""
Tenant isolation and suspended-company tests.

These are the highest-risk tests in the codebase — one missed
.filter(company=...) in a view is a tenant data leak.
"""
from django.test import TestCase
from django.urls import reverse

from apps.companies.models import Company
from apps.users.models import CustomUser
from apps.suppliers.models import Supplier, Farm
from apps.purchase_orders.models import PurchaseOrder
from apps.products.models import Product
from apps.inventory.models import Inventory
from apps.sales_orders.models import SalesOrder
from apps.sales_orders.batch import Batch


def make_company(name, active=True):
    return Company.objects.create(
        name=name, country='Nigeria', plan_tier='starter', is_active=active
    )


def make_user(company, role='staff', username=None):
    if username is None:
        username = f"user_{company.name.lower().replace(' ', '_')}"
    return CustomUser.objects.create_user(
        username=username, password='testpass', company=company, system_role=role
    )


class TenantIsolationTests(TestCase):
    """
    Each major list view must only return objects belonging to the
    logged-in user's company. Each detail view must 404 for objects
    that belong to a different company.
    """

    def setUp(self):
        self.co_a = make_company('Alpha')
        self.co_b = make_company('Beta')
        self.user_a = make_user(self.co_a)
        self.user_b = make_user(self.co_b)

        self.sup_a = Supplier.objects.create(company=self.co_a, name='Sup Alpha', category='cooperative')
        self.sup_b = Supplier.objects.create(company=self.co_b, name='Sup Beta',  category='cooperative')

        self.farm_a = Farm.objects.create(
            company=self.co_a, supplier=self.sup_a,
            name='Farm Alpha', country='Nigeria', commodity='Soy',
            deforestation_risk_status='low',
        )
        self.farm_b = Farm.objects.create(
            company=self.co_b, supplier=self.sup_b,
            name='Farm Beta', country='Nigeria', commodity='Cocoa',
            deforestation_risk_status='low',
        )

        self.product_a = Product.objects.create(company=self.co_a, name='Soybeans',   unit='kg')
        self.product_b = Product.objects.create(company=self.co_b, name='Cocoa Beans', unit='kg')

        self.po_a = PurchaseOrder.objects.create(
            company=self.co_a, supplier=self.sup_a, order_number='001'
        )
        self.po_b = PurchaseOrder.objects.create(
            company=self.co_b, supplier=self.sup_b, order_number='001'
        )

        self.inv_a = Inventory.objects.create(company=self.co_a, product=self.product_a, quantity=100)
        self.inv_b = Inventory.objects.create(company=self.co_b, product=self.product_b, quantity=200)

        self.so_a = SalesOrder.objects.create(
            company=self.co_a, customer_name='Buyer Alpha', order_number='SO-001'
        )
        self.so_b = SalesOrder.objects.create(
            company=self.co_b, customer_name='Buyer Beta', order_number='SO-001'
        )

        self.batch_a = Batch.objects.create(
            company=self.co_a, commodity='Soy', quantity_kg=1000,
            batch_number='SOY-AL-2026-0001'
        )
        self.batch_b = Batch.objects.create(
            company=self.co_b, commodity='Cocoa', quantity_kg=500,
            batch_number='COC-BE-2026-0001'
        )

    # ── Supplier ──────────────────────────────────────────────

    def test_supplier_list_excludes_other_tenant(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('suppliers:list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Sup Alpha')
        self.assertNotContains(r, 'Sup Beta')

    def test_supplier_detail_other_tenant_is_404(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('suppliers:detail', kwargs={'pk': self.sup_b.pk}))
        self.assertEqual(r.status_code, 404)

    # ── Farm ──────────────────────────────────────────────────

    def test_farm_list_excludes_other_tenant(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('suppliers:farm_list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Farm Alpha')
        self.assertNotContains(r, 'Farm Beta')

    def test_farm_detail_other_tenant_is_404(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('suppliers:farm_detail', kwargs={'pk': self.farm_b.pk}))
        self.assertEqual(r.status_code, 404)

    # ── Purchase Orders ───────────────────────────────────────

    def test_purchase_order_list_excludes_other_tenant(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('purchase_orders:list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Sup Alpha')
        self.assertNotContains(r, 'Sup Beta')

    def test_purchase_order_detail_other_tenant_is_404(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('purchase_orders:detail', kwargs={'pk': self.po_b.pk}))
        self.assertEqual(r.status_code, 404)

    # ── Inventory ─────────────────────────────────────────────

    def test_inventory_list_excludes_other_tenant(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('inventory:list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Soybeans')
        self.assertNotContains(r, 'Cocoa Beans')

    def test_inventory_detail_other_tenant_is_404(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('inventory:detail', kwargs={'pk': self.inv_b.pk}))
        self.assertEqual(r.status_code, 404)

    # ── Sales Orders ──────────────────────────────────────────

    def test_sales_order_list_excludes_other_tenant(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('sales_orders:list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Buyer Alpha')
        self.assertNotContains(r, 'Buyer Beta')

    def test_sales_order_detail_other_tenant_is_404(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('sales_orders:detail', kwargs={'pk': self.so_b.pk}))
        self.assertEqual(r.status_code, 404)

    # ── Batches ───────────────────────────────────────────────

    def test_batch_list_excludes_other_tenant(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('sales_orders:batch_list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'SOY-AL-2026-0001')
        self.assertNotContains(r, 'COC-BE-2026-0001')

    def test_batch_detail_other_tenant_is_404(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse('sales_orders:batch_detail', kwargs={'pk': self.batch_b.pk}))
        self.assertEqual(r.status_code, 404)


class SuspendedCompanyTests(TestCase):
    """
    A suspended company (is_active=False) must be blocked at the web
    layer, the API layer, and the admin panel decorator.
    """

    def setUp(self):
        self.company = make_company('Suspended Co', active=False)
        self.user = make_user(self.company, role='manager')

    def test_web_view_logs_out_and_redirects(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('suppliers:list'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r['Location'])

    def test_dashboard_view_logs_out_and_redirects(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('dashboard:index'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r['Location'])

    def test_admin_panel_logs_out_and_redirects(self):
        admin = make_user(self.company, role='org_admin', username='suspended_org_admin')
        self.client.force_login(admin)
        r = self.client.get(reverse('admin_panel:overview'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r['Location'])

    def test_api_rejects_suspended_company(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken.for_user(self.user)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        r = api.get('/api/v1/farms/')
        self.assertEqual(r.status_code, 403)
