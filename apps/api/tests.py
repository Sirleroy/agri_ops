"""
API tenant isolation, authentication, role-permission, and action tests.

Run: python manage.py test apps.api.tests --keepdb
"""
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.companies.models import Company
from apps.users.models import CustomUser
from apps.suppliers.models import Supplier, Farm
from apps.products.models import Product
from apps.inventory.models import Inventory
from apps.purchase_orders.models import PurchaseOrder
from apps.sales_orders.models import SalesOrder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_company(name, active=True):
    return Company.objects.create(
        name=name, country='Nigeria', plan_tier='starter', is_active=active
    )


def make_user(company, role='staff', username=None):
    if username is None:
        username = f"user_{company.name.lower().replace(' ', '_')}_{role}"
    return CustomUser.objects.create_user(
        username=username, password='testpass', company=company, system_role=role
    )


def jwt_client(user):
    """Return an APIClient authenticated with a JWT for the given user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ---------------------------------------------------------------------------
# Base test data shared across suites
# ---------------------------------------------------------------------------

class APITestBase(TestCase):
    def setUp(self):
        self.co_a = make_company('Alpha Co')
        self.co_b = make_company('Beta Co')

        self.user_a   = make_user(self.co_a, 'staff',   'staff_a')
        self.manager_a = make_user(self.co_a, 'manager', 'manager_a')
        self.viewer_a  = make_user(self.co_a, 'viewer',  'viewer_a')
        self.user_b    = make_user(self.co_b, 'staff',   'staff_b')

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
            deforestation_risk_status='high',
        )

        self.product_a = Product.objects.create(company=self.co_a, name='Soybeans',    unit='kg')
        self.product_b = Product.objects.create(company=self.co_b, name='Cocoa Beans', unit='kg')

        self.inv_a = Inventory.objects.create(
            company=self.co_a, product=self.product_a, quantity=100, low_stock_threshold=200
        )
        self.inv_b = Inventory.objects.create(
            company=self.co_b, product=self.product_b, quantity=50
        )

        self.po_a = PurchaseOrder.objects.create(
            company=self.co_a, supplier=self.sup_a, order_number='2026-0001'
        )
        self.po_b = PurchaseOrder.objects.create(
            company=self.co_b, supplier=self.sup_b, order_number='2026-0001'
        )

        self.so_a = SalesOrder.objects.create(
            company=self.co_a, customer_name='Buyer Alpha', order_number='SO-001'
        )
        self.so_b = SalesOrder.objects.create(
            company=self.co_b, customer_name='Buyer Beta', order_number='SO-001'
        )

        self.client_a  = jwt_client(self.user_a)
        self.client_b  = jwt_client(self.user_b)
        self.client_mgr = jwt_client(self.manager_a)
        self.anon       = APIClient()


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------

class APIAuthTests(APITestBase):
    """Unauthenticated requests must be rejected."""

    def test_unauthenticated_supplier_list_returns_401(self):
        r = self.anon.get('/api/v1/suppliers/')
        self.assertEqual(r.status_code, 401)

    def test_unauthenticated_farm_list_returns_401(self):
        r = self.anon.get('/api/v1/farms/')
        self.assertEqual(r.status_code, 401)

    def test_unauthenticated_inventory_list_returns_401(self):
        r = self.anon.get('/api/v1/inventory/')
        self.assertEqual(r.status_code, 401)

    def test_unauthenticated_token_refresh_requires_valid_token(self):
        r = self.anon.post('/api/v1/token/refresh/', {'refresh': 'bad'})
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Tenant isolation tests
# ---------------------------------------------------------------------------

class APITenantIsolationTests(APITestBase):
    """List endpoints return only the authenticated user's company data."""

    def test_supplier_list_excludes_other_tenant(self):
        r = self.client_a.get('/api/v1/suppliers/')
        self.assertEqual(r.status_code, 200)
        names = [s['name'] for s in r.data['results'] if 'results' in r.data] or [s['name'] for s in r.data]
        self.assertIn('Sup Alpha', names)
        self.assertNotIn('Sup Beta', names)

    def test_farm_list_excludes_other_tenant(self):
        r = self.client_a.get('/api/v1/farms/')
        self.assertEqual(r.status_code, 200)
        data = r.data if isinstance(r.data, list) else r.data.get('results', r.data)
        names = [f['name'] for f in data]
        self.assertIn('Farm Alpha', names)
        self.assertNotIn('Farm Beta', names)

    def test_product_list_excludes_other_tenant(self):
        r = self.client_a.get('/api/v1/products/')
        self.assertEqual(r.status_code, 200)
        data = r.data if isinstance(r.data, list) else r.data.get('results', r.data)
        names = [p['name'] for p in data]
        self.assertIn('Soybeans', names)
        self.assertNotIn('Cocoa Beans', names)

    def test_inventory_list_excludes_other_tenant(self):
        r = self.client_a.get('/api/v1/inventory/')
        self.assertEqual(r.status_code, 200)
        data = r.data if isinstance(r.data, list) else r.data.get('results', r.data)
        pks = [i['id'] for i in data]
        self.assertIn(self.inv_a.pk, pks)
        self.assertNotIn(self.inv_b.pk, pks)

    def test_purchase_order_list_excludes_other_tenant(self):
        r = self.client_a.get('/api/v1/purchase-orders/')
        self.assertEqual(r.status_code, 200)
        data = r.data if isinstance(r.data, list) else r.data.get('results', r.data)
        pks = [o['id'] for o in data]
        self.assertIn(self.po_a.pk, pks)
        self.assertNotIn(self.po_b.pk, pks)

    def test_sales_order_list_excludes_other_tenant(self):
        r = self.client_a.get('/api/v1/sales-orders/')
        self.assertEqual(r.status_code, 200)
        data = r.data if isinstance(r.data, list) else r.data.get('results', r.data)
        pks = [o['id'] for o in data]
        self.assertIn(self.so_a.pk, pks)
        self.assertNotIn(self.so_b.pk, pks)

    def test_supplier_detail_other_tenant_is_404(self):
        r = self.client_a.get(f'/api/v1/suppliers/{self.sup_b.pk}/')
        self.assertEqual(r.status_code, 404)

    def test_farm_detail_other_tenant_is_404(self):
        r = self.client_a.get(f'/api/v1/farms/{self.farm_b.pk}/')
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# Suspended company tests
# ---------------------------------------------------------------------------

class APISuspendedCompanyTests(APITestBase):
    """Suspended-company users are blocked at the API layer."""

    def setUp(self):
        super().setUp()
        self.co_suspended = make_company('Suspended Co', active=False)
        self.suspended_user = make_user(self.co_suspended, 'staff', 'suspended_user')
        self.client_suspended = jwt_client(self.suspended_user)

    def test_suspended_company_cannot_list_suppliers(self):
        r = self.client_suspended.get('/api/v1/suppliers/')
        self.assertEqual(r.status_code, 403)

    def test_suspended_company_cannot_list_farms(self):
        r = self.client_suspended.get('/api/v1/farms/')
        self.assertEqual(r.status_code, 403)

    def test_suspended_company_cannot_create_supplier(self):
        r = self.client_suspended.post('/api/v1/suppliers/', {'name': 'X', 'category': 'cooperative'})
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
# Role-based permission tests
# ---------------------------------------------------------------------------

class APIRolePermissionTests(APITestBase):
    """
    GET: any authenticated tenant member.
    POST/PUT/PATCH: staff or above.
    DELETE: manager or above.
    """

    def test_viewer_can_read_suppliers(self):
        client = jwt_client(self.viewer_a)
        r = client.get('/api/v1/suppliers/')
        self.assertEqual(r.status_code, 200)

    def test_viewer_cannot_create_supplier(self):
        client = jwt_client(self.viewer_a)
        r = client.post('/api/v1/suppliers/', {'name': 'New', 'category': 'cooperative'})
        self.assertEqual(r.status_code, 403)

    def test_staff_can_create_supplier(self):
        r = self.client_a.post('/api/v1/suppliers/', {'name': 'New Sup', 'category': 'cooperative'})
        self.assertIn(r.status_code, [200, 201])

    def test_staff_cannot_delete_supplier(self):
        r = self.client_a.delete(f'/api/v1/suppliers/{self.sup_a.pk}/')
        self.assertEqual(r.status_code, 403)

    def test_manager_can_delete_supplier(self):
        sup = Supplier.objects.create(company=self.co_a, name='To Delete', category='cooperative')
        r = self.client_mgr.delete(f'/api/v1/suppliers/{sup.pk}/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Supplier.objects.filter(pk=sup.pk).exists())

    def test_manager_cannot_delete_other_tenant_supplier(self):
        r = self.client_mgr.delete(f'/api/v1/suppliers/{self.sup_b.pk}/')
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# Farm custom action tests
# ---------------------------------------------------------------------------

class APIFarmActionTests(APITestBase):
    """eudr-pending and high-risk custom actions scope to the current tenant."""

    def setUp(self):
        super().setUp()
        self.farm_eudr = Farm.objects.create(
            company=self.co_a, supplier=self.sup_a,
            name='Unverified Farm', country='Nigeria', commodity='Soy',
            is_eudr_verified=False, deforestation_risk_status='low',
        )
        self.farm_highrisk = Farm.objects.create(
            company=self.co_a, supplier=self.sup_a,
            name='High Risk Farm', country='Nigeria', commodity='Soy',
            deforestation_risk_status='high',
        )
        # Farm belonging to co_b with same risk — must NOT appear in co_a results
        self.farm_b_highrisk = Farm.objects.create(
            company=self.co_b, supplier=self.sup_b,
            name='Beta High Risk', country='Nigeria', commodity='Cocoa',
            deforestation_risk_status='high',
        )

    def test_eudr_pending_returns_unverified_farms_only(self):
        r = self.client_a.get('/api/v1/farms/eudr-pending/')
        self.assertEqual(r.status_code, 200)
        data = r.data if isinstance(r.data, list) else r.data.get('results', r.data)
        names = [f['name'] for f in data]
        self.assertIn('Unverified Farm', names)
        # Verified farms from co_a must not appear
        for name in names:
            self.assertNotIn('Beta', name)

    def test_eudr_pending_excludes_other_tenant(self):
        Farm.objects.create(
            company=self.co_b, supplier=self.sup_b,
            name='Beta Unverified', country='Nigeria', commodity='Cocoa',
            is_eudr_verified=False, deforestation_risk_status='low',
        )
        r = self.client_a.get('/api/v1/farms/eudr-pending/')
        data = r.data if isinstance(r.data, list) else r.data.get('results', r.data)
        names = [f['name'] for f in data]
        self.assertNotIn('Beta Unverified', names)

    def test_high_risk_returns_only_co_a_farms(self):
        r = self.client_a.get('/api/v1/farms/high-risk/')
        self.assertEqual(r.status_code, 200)
        data = r.data if isinstance(r.data, list) else r.data.get('results', r.data)
        names = [f['name'] for f in data]
        self.assertIn('High Risk Farm', names)
        self.assertNotIn('Beta High Risk', names)


# ---------------------------------------------------------------------------
# Inventory custom action tests
# ---------------------------------------------------------------------------

class APIInventoryActionTests(APITestBase):
    """low-stock action respects tenant isolation."""

    def setUp(self):
        super().setUp()
        # inv_a already has quantity=100, threshold=200 → low stock

    def test_low_stock_returns_only_co_a_items(self):
        r = self.client_a.get('/api/v1/inventory/low-stock/')
        self.assertEqual(r.status_code, 200)
        data = r.data if isinstance(r.data, list) else r.data.get('results', r.data)
        pks = [i['id'] for i in data]
        self.assertIn(self.inv_a.pk, pks)
        self.assertNotIn(self.inv_b.pk, pks)

    def test_low_stock_excludes_items_above_threshold(self):
        other_product = Product.objects.create(company=self.co_a, name='Rice', unit='kg')
        healthy = Inventory.objects.create(
            company=self.co_a, product=other_product, quantity=500, low_stock_threshold=100
        )
        r = self.client_a.get('/api/v1/inventory/low-stock/')
        data = r.data if isinstance(r.data, list) else r.data.get('results', r.data)
        pks = [i['id'] for i in data]
        self.assertNotIn(healthy.pk, pks)


# ---------------------------------------------------------------------------
# JWT token endpoint smoke test
# ---------------------------------------------------------------------------

class APITokenTests(TestCase):
    def setUp(self):
        self.co = make_company('Token Co')
        self.user = make_user(self.co, 'staff', 'token_user')

    def test_obtain_token_with_valid_credentials(self):
        r = self.client.post('/api/v1/token/', {
            'username': 'token_user', 'password': 'testpass'
        }, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.json())
        self.assertIn('refresh', r.json())

    def test_obtain_token_with_wrong_password_returns_401(self):
        r = self.client.post('/api/v1/token/', {
            'username': 'token_user', 'password': 'wrongpass'
        }, content_type='application/json')
        self.assertEqual(r.status_code, 401)

    def test_refresh_token(self):
        obtain = self.client.post('/api/v1/token/', {
            'username': 'token_user', 'password': 'testpass'
        }, content_type='application/json')
        refresh_token = obtain.json()['refresh']
        r = self.client.post('/api/v1/token/refresh/', {
            'refresh': refresh_token
        }, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.json())
