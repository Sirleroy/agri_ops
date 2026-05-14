import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.companies.models import Company
from apps.suppliers.models import Supplier, Farm, DeforestationCheck
from apps.users.models import CustomUser


class SupplierTenantIsolationTest(TestCase):

    def setUp(self):
        self.company1 = Company.objects.create(
            name='Company One', country='Nigeria', plan_tier='starter'
        )
        self.company2 = Company.objects.create(
            name='Company Two', country='Nigeria', plan_tier='starter'
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


_POLYGON = {
    'type': 'Polygon',
    'coordinates': [[
        [8.50, 9.00], [8.51, 9.00], [8.51, 9.01], [8.50, 9.01], [8.50, 9.00],
    ]],
}


class FarmComplianceTest(TestCase):
    """
    Compliance Readiness is evidence-backed: a sign-off (`is_eudr_verified`)
    only counts as `compliant` when a clear, current, non-stale deforestation
    check sits behind it. These tests guard that gate and the readiness/
    disqualification lifecycle the deforestation engine drives.
    """

    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company', country='Nigeria', plan_tier='starter'
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
            geolocation=_POLYGON,
            deforestation_risk_status='low',
            is_eudr_verified=False,
        )

    def _make_check(self, risk_status='clear', stale=False):
        return DeforestationCheck.objects.create(
            farm=self.farm,
            company=self.company,
            risk_status=risk_status,
            engine_status='complete',
            geometry_hash_at_assessment=(
                'stale-hash-0000' if stale else self.farm.geometry_hash
            ),
            assessed_at=timezone.now(),
        )

    def _sign_off(self):
        self.farm.is_eudr_verified = True
        self.farm.verified_date = datetime.date.today()
        self.farm.save()
        self.farm.refresh_from_db()

    # ── compliance_status ────────────────────────────────────────────────────

    def test_unverified_farm_is_pending(self):
        self.assertEqual(self.farm.compliance_status, 'pending')

    def test_verified_with_clear_current_check_is_compliant(self):
        self._make_check('clear')
        self._sign_off()
        self.assertEqual(self.farm.compliance_status, 'compliant')

    def test_verified_without_any_check_is_not_compliant(self):
        # The credibility hole this work closes: a sign-off with no evidence.
        self._sign_off()
        self.assertEqual(self.farm.compliance_status, 'pending')

    def test_verified_with_stale_check_is_not_compliant(self):
        self._make_check('clear', stale=True)
        self._sign_off()
        self.assertEqual(self.farm.compliance_status, 'pending')

    def test_flagged_check_disqualifies_farm(self):
        self._make_check('flagged')
        self.assertTrue(self.farm.is_disqualified)
        self.assertEqual(self.farm.compliance_status, 'disqualified')

    def test_expired_signoff_is_expired(self):
        self._make_check('clear')
        self.farm.is_eudr_verified = True
        self.farm.verification_expiry = datetime.date.today() - datetime.timedelta(days=1)
        self.farm.save()
        self.assertEqual(self.farm.compliance_status, 'expired')

    # ── disqualification: engine + manual override ───────────────────────────

    def test_manual_override_true_disqualifies(self):
        self.farm.land_cleared_after_cutoff = True
        self.assertTrue(self.farm.is_disqualified)

    def test_manual_override_false_beats_flagged_engine_check(self):
        self._make_check('flagged')
        self.farm.land_cleared_after_cutoff = False
        self.assertFalse(self.farm.is_disqualified)

    def test_no_override_defers_to_engine(self):
        self.assertIsNone(self.farm.land_cleared_after_cutoff)
        self._make_check('clear')
        self.assertFalse(self.farm.is_disqualified)

    # ── readiness_state lifecycle ────────────────────────────────────────────

    def test_readiness_not_ready_without_check(self):
        self.assertEqual(self.farm.readiness_state, 'not_ready')
        self.assertTrue(self.farm.readiness_blockers)

    def test_readiness_awaiting_signoff_with_clear_check(self):
        self._make_check('clear')
        self.assertEqual(self.farm.readiness_state, 'awaiting_signoff')
        self.assertEqual(self.farm.readiness_blockers, [])

    def test_readiness_ready_after_signoff(self):
        self._make_check('clear')
        self._sign_off()
        self.assertEqual(self.farm.readiness_state, 'ready')

    def test_readiness_disqualified_with_flagged_check(self):
        self._make_check('flagged')
        self.assertEqual(self.farm.readiness_state, 'disqualified')

    # ── auto-invalidation ────────────────────────────────────────────────────

    def test_geometry_change_voids_signoff(self):
        self._make_check('clear')
        self._sign_off()
        self.assertTrue(self.farm.is_eudr_verified)
        # Edit the polygon — the sign-off no longer matches the boundary on file.
        moved = {
            'type': 'Polygon',
            'coordinates': [[
                [8.60, 9.10], [8.61, 9.10], [8.61, 9.11], [8.60, 9.11], [8.60, 9.10],
            ]],
        }
        self.farm.geolocation = moved
        self.farm.save()
        self.farm.refresh_from_db()
        self.assertFalse(self.farm.is_eudr_verified)
        self.assertIsNone(self.farm.verified_date)

    def test_flagged_recheck_voids_signoff(self):
        from unittest.mock import patch
        from apps.suppliers import deforestation_engine

        self._make_check('clear')
        self._sign_off()
        self.assertTrue(self.farm.is_eudr_verified)

        # A fresh engine run that comes back flagged must withdraw the sign-off.
        flagged_result = {
            'pixels': 120, 'loss_pixels': 6, 'loss_area_ha': 0.48,
            'loss_years': [21], 'risk_status': 'flagged', 'error': None,
        }
        with patch.object(deforestation_engine, 'intersect_farm', return_value=flagged_result):
            deforestation_engine.run_check(self.farm)

        self.farm.refresh_from_db()
        self.assertFalse(self.farm.is_eudr_verified)
        self.assertIsNone(self.farm.verified_date)
        self.assertEqual(self.farm.compliance_status, 'disqualified')

        # The engine-triggered sign-off withdrawal must land in the audit log,
        # the same as a manual withdrawal would.
        from apps.audit.models import AuditLog
        log = (
            AuditLog.objects
            .filter(company=self.company, model_name='Farm', object_id=self.farm.pk)
            .order_by('-timestamp')
            .first()
        )
        self.assertIsNotNone(log)
        self.assertEqual(
            log.changes.get('compliance_readiness'), 'sign-off withdrawn — automated'
        )


class ComplianceReadinessSignoffTests(TestCase):
    """
    Compliance Readiness sign-off is an evidence-gated, manager-only,
    audit-logged action — not a free checkbox. These tests guard the evidence
    gate, the permission boundary, and tenant isolation.
    """

    def setUp(self):
        self.company = Company.objects.create(
            name='Sign-off Co', country='Nigeria', plan_tier='starter'
        )
        self.other_company = Company.objects.create(
            name='Other Co', country='Nigeria', plan_tier='starter'
        )
        self.supplier = Supplier.objects.create(
            company=self.company, name='Sign-off Supplier', category='cooperative'
        )
        self.manager = CustomUser.objects.create_user(
            username='signoff_mgr', password='testpass',
            company=self.company, system_role='manager',
        )
        self.staff = CustomUser.objects.create_user(
            username='signoff_staff', password='testpass',
            company=self.company, system_role='staff',
        )
        self.farm = Farm.objects.create(
            company=self.company, supplier=self.supplier, name='Sign-off Farm',
            country='Nigeria', commodity='Soy', geolocation=_POLYGON,
            deforestation_risk_status='low',
        )

    def _clear_check(self, farm=None):
        farm = farm or self.farm
        return DeforestationCheck.objects.create(
            farm=farm, company=farm.company, risk_status='clear',
            engine_status='complete',
            geometry_hash_at_assessment=farm.geometry_hash,
            assessed_at=timezone.now(),
        )

    def _confirm_url(self, farm=None):
        return reverse('suppliers:farm_confirm_readiness', kwargs={'pk': (farm or self.farm).pk})

    def _withdraw_url(self, farm=None):
        return reverse('suppliers:farm_withdraw_readiness', kwargs={'pk': (farm or self.farm).pk})

    def test_manager_can_sign_off_evidenced_farm(self):
        self._clear_check()
        self.client.force_login(self.manager)
        r = self.client.post(self._confirm_url())
        self.assertEqual(r.status_code, 302)
        self.farm.refresh_from_db()
        self.assertTrue(self.farm.is_eudr_verified)
        self.assertEqual(self.farm.verified_by, self.manager)
        self.assertEqual(self.farm.verified_date, datetime.date.today())
        self.assertEqual(
            self.farm.verification_expiry,
            datetime.date.today() + datetime.timedelta(days=365),
        )

    def test_signoff_rejected_without_evidence(self):
        # Farm has a polygon but no deforestation check — readiness has blockers.
        self.client.force_login(self.manager)
        r = self.client.post(self._confirm_url())
        self.assertEqual(r.status_code, 302)
        self.farm.refresh_from_db()
        self.assertFalse(self.farm.is_eudr_verified)

    def test_signoff_rejected_when_disqualified(self):
        DeforestationCheck.objects.create(
            farm=self.farm, company=self.company, risk_status='flagged',
            engine_status='complete',
            geometry_hash_at_assessment=self.farm.geometry_hash,
            assessed_at=timezone.now(),
        )
        self.client.force_login(self.manager)
        r = self.client.post(self._confirm_url())
        self.assertEqual(r.status_code, 302)
        self.farm.refresh_from_db()
        self.assertFalse(self.farm.is_eudr_verified)

    def test_staff_cannot_sign_off(self):
        self._clear_check()
        self.client.force_login(self.staff)
        r = self.client.post(self._confirm_url())
        self.assertEqual(r.status_code, 403)
        self.farm.refresh_from_db()
        self.assertFalse(self.farm.is_eudr_verified)

    def test_signoff_cross_tenant_is_404(self):
        other_supplier = Supplier.objects.create(
            company=self.other_company, name='Other Supplier', category='cooperative'
        )
        other_farm = Farm.objects.create(
            company=self.other_company, supplier=other_supplier, name='Other Farm',
            country='Nigeria', commodity='Soy', geolocation=_POLYGON,
        )
        self._clear_check(other_farm)
        self.client.force_login(self.manager)
        r = self.client.post(self._confirm_url(other_farm))
        self.assertEqual(r.status_code, 404)
        other_farm.refresh_from_db()
        self.assertFalse(other_farm.is_eudr_verified)

    def test_manager_can_withdraw_signoff(self):
        self._clear_check()
        self.client.force_login(self.manager)
        self.client.post(self._confirm_url())
        self.farm.refresh_from_db()
        self.assertTrue(self.farm.is_eudr_verified)
        r = self.client.post(self._withdraw_url())
        self.assertEqual(r.status_code, 302)
        self.farm.refresh_from_db()
        self.assertFalse(self.farm.is_eudr_verified)
        self.assertIsNone(self.farm.verified_by)

    def test_signoff_is_audit_logged(self):
        from apps.audit.models import AuditLog
        self._clear_check()
        self.client.force_login(self.manager)
        self.client.post(self._confirm_url())
        log = (
            AuditLog.objects
            .filter(company=self.company, model_name='Farm', object_id=self.farm.pk)
            .order_by('-timestamp')
            .first()
        )
        self.assertIsNotNone(log)
        self.assertEqual(log.changes.get('compliance_readiness'), 'signed off')

    def test_run_deforestation_check_is_audit_logged(self):
        """A manual 'Run Check' is a user action on a tenant record — it must
        appear in the central audit log, not only as a DeforestationCheck row."""
        from unittest.mock import patch
        from apps.suppliers import deforestation_engine
        from apps.audit.models import AuditLog

        clear_result = {
            'pixels': 200, 'loss_pixels': 0, 'loss_area_ha': 0,
            'loss_years': [], 'risk_status': 'clear', 'error': None,
        }
        self.client.force_login(self.staff)
        with patch.object(deforestation_engine, 'intersect_farm', return_value=clear_result):
            r = self.client.post(
                reverse('suppliers:run_deforestation_check', kwargs={'pk': self.farm.pk})
            )
        self.assertEqual(r.status_code, 302)
        log = (
            AuditLog.objects
            .filter(company=self.company, model_name='Farm', object_id=self.farm.pk)
            .order_by('-timestamp')
            .first()
        )
        self.assertIsNotNone(log)
        self.assertEqual(log.changes.get('deforestation_check_run'), 'clear')
