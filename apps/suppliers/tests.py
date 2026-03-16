from django.test import TestCase
from apps.companies.models import Company
from apps.users.models import CustomUser
from apps.suppliers.models import Supplier, Farm


class SupplierTenantIsolationTest(TestCase):

    def setUp(self):
        self.company1 = Company.objects.create(
            name='Company One', country='Nigeria', plan_tier='free'
        )
        self.company2 = Company.objects.create(
            name='Company Two', country='Nigeria', plan_tier='free'
        )
        self.supplier1 = Supplier.objects.create(
            company=self.company1, name='Supplier One', category='seeds'
        )
        self.supplier2 = Supplier.objects.create(
            company=self.company2, name='Supplier Two', category='fertilizer'
        )

    def test_supplier_scoped_to_company(self):
        company1_suppliers = Supplier.objects.filter(company=self.company1)
        self.assertEqual(company1_suppliers.count(), 1)
        self.assertEqual(company1_suppliers.first().name, 'Supplier One')

    def test_no_cross_tenant_leakage(self):
        company1_suppliers = Supplier.objects.filter(company=self.company1)
        self.assertNotIn(self.supplier2, company1_suppliers)


class FarmComplianceTest(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company', country='Nigeria', plan_tier='free'
        )
        self.supplier = Supplier.objects.create(
            company=self.company, name='Test Supplier', category='seeds'
        )
        self.farm = Farm.objects.create(
            company=self.company,
            supplier=self.supplier,
            name='Test Farm',
            country='Nigeria',
            commodity='Soy',
            deforestation_risk_status='low',
            is_eudr_verified=False,
        )

    def test_unverified_farm_compliance_status(self):
        self.assertEqual(self.farm.compliance_status, 'pending')

    def test_verified_farm_compliance_status(self):
        self.farm.is_eudr_verified = True
        self.assertEqual(self.farm.compliance_status, 'compliant')

    def test_high_risk_verified_farm(self):
        self.farm.is_eudr_verified = True
        self.farm.deforestation_risk_status = 'high'
        self.assertEqual(self.farm.compliance_status, 'high_risk')
