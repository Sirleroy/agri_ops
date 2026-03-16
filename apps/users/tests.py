from django.test import TestCase
from apps.companies.models import Company
from apps.users.models import CustomUser


class CustomUserModelTest(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company',
            country='Nigeria',
            plan_tier='free'
        )
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='testpass123',
            system_role='staff',
            company=self.company
        )

    def test_user_str(self):
        self.assertEqual(str(self.user), 'testuser (Staff)')

    def test_system_role_default(self):
        user = CustomUser.objects.create_user(
            username='testuser2',
            password='testpass123',
        )
        self.assertEqual(user.system_role, 'staff')

    def test_is_org_admin_property(self):
        self.user.system_role = 'org_admin'
        self.assertTrue(self.user.is_org_admin)

    def test_is_manager_or_above(self):
        self.user.system_role = 'manager'
        self.assertTrue(self.user.is_manager_or_above)

    def test_viewer_is_not_manager(self):
        self.user.system_role = 'viewer'
        self.assertFalse(self.user.is_manager_or_above)
