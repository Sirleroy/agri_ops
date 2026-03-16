from django.test import TestCase, RequestFactory
from apps.companies.models import Company
from apps.users.models import CustomUser
from apps.suppliers.models import Supplier
from apps.audit.models import AuditLog
from apps.audit.mixins import log_action


class AuditLogTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.company = Company.objects.create(
            name='Test Company', country='Nigeria', plan_tier='free'
        )
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='testpass123',
            system_role='staff',
            company=self.company
        )
        self.supplier = Supplier.objects.create(
            company=self.company,
            name='Test Supplier',
            category='seeds'
        )

    def test_audit_log_created_on_action(self):
        request = self.factory.get('/')
        request.user = self.user
        log_action(request, 'create', self.supplier)
        self.assertEqual(AuditLog.objects.count(), 1)
        log = AuditLog.objects.first()
        self.assertEqual(log.action, 'create')
        self.assertEqual(log.model_name, 'Supplier')
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.company, self.company)

    def test_audit_log_delete_action(self):
        request = self.factory.get('/')
        request.user = self.user
        log_action(request, 'delete', self.supplier)
        log = AuditLog.objects.first()
        self.assertEqual(log.action, 'delete')
        self.assertEqual(log.object_repr, str(self.supplier))
