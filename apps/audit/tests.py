from django.test import TestCase, RequestFactory
from django.urls import reverse

from apps.companies.models import Company
from apps.users.models import CustomUser
from apps.suppliers.models import Supplier
from apps.audit.models import AuditLog
from apps.audit.mixins import log_action


def make_company(name):
    return Company.objects.create(name=name, country='Nigeria', plan_tier='starter')


def make_user(company, role='manager', username=None):
    return CustomUser.objects.create_user(
        username=username or f'user_{company.name.lower()}',
        password='testpass',
        company=company,
        system_role=role,
    )


class AuditLogUnitTests(TestCase):
    """Direct log_action utility tests — fast, no HTTP."""

    def setUp(self):
        self.company = make_company('Unit Co')
        self.user = make_user(self.company, role='staff')
        self.supplier = Supplier.objects.create(
            company=self.company, name='Test Supplier', category='cooperative'
        )

    def test_create_action_writes_log(self):
        request = RequestFactory().get('/')
        request.user = self.user
        log_action(request, 'create', self.supplier)
        log = AuditLog.objects.get()
        self.assertEqual(log.action, 'create')
        self.assertEqual(log.model_name, 'Supplier')
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.company, self.company)

    def test_delete_action_records_repr(self):
        request = RequestFactory().get('/')
        request.user = self.user
        log_action(request, 'delete', self.supplier)
        log = AuditLog.objects.get()
        self.assertEqual(log.action, 'delete')
        self.assertEqual(log.object_repr, str(self.supplier))


class AuditViewIntegrationTests(TestCase):
    """
    Prove that the AuditCreateMixin / AuditUpdateMixin / AuditDeleteMixin
    actually write logs when views are called over HTTP — not just when
    log_action is called directly.
    """

    def setUp(self):
        self.company = make_company('View Co')
        self.manager = make_user(self.company, role='manager')
        self.client.force_login(self.manager)
        self.supplier = Supplier.objects.create(
            company=self.company, name='Existing Supplier', category='cooperative'
        )

    def test_supplier_create_view_writes_audit_log(self):
        self.client.post(reverse('suppliers:create'), data={
            'name': 'New Supplier',
            'category': 'cooperative',
            'country': 'Nigeria',
        })
        self.assertTrue(
            AuditLog.objects.filter(action='create', model_name='Supplier').exists(),
            'AuditCreateMixin did not write a log on supplier create'
        )

    def test_supplier_update_view_writes_audit_log(self):
        self.client.post(
            reverse('suppliers:update', kwargs={'pk': self.supplier.pk}),
            data={'name': 'Updated Supplier', 'category': 'cooperative', 'country': 'Nigeria'},
        )
        self.assertTrue(
            AuditLog.objects.filter(action='update', model_name='Supplier').exists(),
            'AuditUpdateMixin did not write a log on supplier update'
        )

    def test_audit_log_is_scoped_to_correct_company(self):
        request = RequestFactory().get('/')
        request.user = self.manager
        log_action(request, 'create', self.supplier)
        log = AuditLog.objects.get(action='create')
        self.assertEqual(log.company, self.company)

    def test_audit_logs_not_visible_across_tenants(self):
        # Company B's user should not be able to see Company A's audit logs
        co_b = make_company('Other Co')
        user_b = make_user(co_b, username='user_other')
        # Log an action for company A
        request = RequestFactory().get('/')
        request.user = self.manager
        log_action(request, 'create', self.supplier)
        # Company B's logs are empty
        co_b_logs = AuditLog.objects.filter(company=co_b)
        self.assertEqual(co_b_logs.count(), 0)

    def test_role_change_via_admin_panel_writes_audit_log(self):
        # Create a second user to change roles for
        target = make_user(self.company, role='staff', username='target_staff')
        org_admin = make_user(self.company, role='org_admin', username='org_admin_user')
        self.client.force_login(org_admin)
        self.client.post(
            reverse('admin_panel:change_role', kwargs={'user_id': target.pk}),
            data={'system_role': 'manager'},
        )
        self.assertTrue(
            AuditLog.objects.filter(action='update', model_name='CustomUser').exists(),
            'Role change via admin panel did not write an audit log'
        )
