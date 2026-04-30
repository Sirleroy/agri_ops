
import datetime
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.companies.models import Company
from apps.purchase_orders.models import PurchaseOrder
from apps.sales_orders.batch import Batch
from apps.sales_orders.quality import PhytosanitaryCertificate, BatchQualityTest
from apps.suppliers.models import Farm, Supplier
from apps.users.models import CustomUser


class CertificateDownloadBlockerTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='Ake Collective',
            country='Nigeria',
            plan_tier='enterprise',
        )
        self.user = CustomUser.objects.create_user(
            username='ake_staff',
            password='testpass',
            company=self.company,
            system_role='staff',
        )
        self.supplier = Supplier.objects.create(
            company=self.company,
            name='Ake Supplier',
            category='cooperative',
        )
        self.batch = Batch.objects.create(
            company=self.company,
            commodity='Soy',
            quantity_kg=1000,
            batch_number='SOY-AK-2026-0001',
        )

    def make_compliant_farm(self, name='Verified Farm'):
        return Farm.objects.create(
            company=self.company,
            supplier=self.supplier,
            name=name,
            country='Nigeria',
            commodity='Soy',
            deforestation_risk_status='low',
            is_eudr_verified=True,
            verification_expiry=datetime.date.today() + datetime.timedelta(days=90),
        )

    def add_current_phyto(self):
        return PhytosanitaryCertificate.objects.create(
            company=self.company,
            batch=self.batch,
            certificate_number='NAQS-001',
            expiry_date=datetime.date.today() + datetime.timedelta(days=30),
        )

    def add_passing_quality_test(self):
        return BatchQualityTest.objects.create(
            company=self.company,
            batch=self.batch,
            test_type='mrl',
            lab_name='Agri Lab',
            result='pass',
        )

    def add_purchase_order(self):
        po = PurchaseOrder.objects.create(
            company=self.company,
            supplier=self.supplier,
            order_number='PO-001',
            status='received',
        )
        self.batch.purchase_orders.add(po)
        return po

    def make_download_ready_batch(self):
        self.batch.farms.add(self.make_compliant_farm())
        self.add_current_phyto()
        self.add_passing_quality_test()

    def test_certificate_readiness_blocks_unverified_farm(self):
        farm = Farm.objects.create(
            company=self.company,
            supplier=self.supplier,
            name='Unverified Farm',
            country='Nigeria',
            commodity='Soy',
            deforestation_risk_status='low',
            is_eudr_verified=False,
        )
        self.batch.farms.add(farm)
        self.add_current_phyto()
        self.add_passing_quality_test()

        readiness = self.batch.certificate_readiness()

        self.assertFalse(readiness['can_download_certificate'])
        self.assertFalse(readiness['farm_compliance'])
        self.assertIn('Unverified Farm', ' '.join(readiness['blockers']))

    def test_certificate_readiness_blocks_expired_phytosanitary_certificate(self):
        self.batch.farms.add(self.make_compliant_farm())
        PhytosanitaryCertificate.objects.create(
            company=self.company,
            batch=self.batch,
            certificate_number='NAQS-EXPIRED',
            expiry_date=datetime.date.today() - datetime.timedelta(days=1),
        )
        self.add_passing_quality_test()

        readiness = self.batch.certificate_readiness()

        self.assertFalse(readiness['can_download_certificate'])
        self.assertFalse(readiness['phyto'])
        self.assertIn('phytosanitary certificate on record is expired', ' '.join(readiness['blockers']))

    def test_certificate_download_redirects_when_readiness_is_blocked(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('sales_orders:batch_certificate', kwargs={'pk': self.batch.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            reverse('sales_orders:batch_detail', kwargs={'pk': self.batch.pk}),
        )

    @patch('apps.sales_orders.certificate_pdf.generate_certificate')
    def test_certificate_download_generates_pdf_when_readiness_passes(self, generate_certificate):
        generate_certificate.return_value = b'%PDF-1.4 test'
        self.make_download_ready_batch()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('sales_orders:batch_certificate', kwargs={'pk': self.batch.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        generate_certificate.assert_called_once_with(self.batch)

    @patch('apps.sales_orders.certificate_pdf.generate_certificate')
    def test_fully_attributed_batch_downloads_cleanly(self, generate_certificate):
        generate_certificate.return_value = b'%PDF-1.4 test'
        self.make_download_ready_batch()
        self.add_purchase_order()
        self.client.force_login(self.user)

        readiness = self.batch.certificate_readiness()
        response = self.client.get(
            reverse('sales_orders:batch_certificate', kwargs={'pk': self.batch.pk})
        )

        self.assertTrue(readiness['purchase_orders'])
        self.assertTrue(readiness['can_download_certificate'])
        self.assertEqual(response.status_code, 200)
        generate_certificate.assert_called_once_with(self.batch)

    def test_neutral_certificate_download_redirects_when_readiness_is_blocked(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('sales_orders:batch_neutral_certificate', kwargs={'pk': self.batch.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            reverse('sales_orders:batch_detail', kwargs={'pk': self.batch.pk}),
        )
