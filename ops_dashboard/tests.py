
from django.test import TestCase
from django.urls import reverse
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.users.models import CustomUser
from ops_dashboard.models import OpsEventLog


class OpsOtpFlowTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='ops_user',
            password='secret-pass',
            is_staff=True,
            system_role='staff',
        )

    def _current_token(self, device):
        totp = TOTP(
            device.bin_key,
            device.step,
            device.t0,
            device.digits,
            device.drift,
        )
        return str(totp.token()).zfill(device.digits)

    def test_otp_setup_marks_current_session_verified(self):
        self.client.force_login(self.user)
        self.client.get(reverse('ops_otp_setup'))
        device = TOTPDevice.objects.get(user=self.user, name='AgriOps Ops Dashboard')

        response = self.client.post(
            reverse('ops_otp_setup'),
            {'token': self._current_token(device)},
        )

        self.assertRedirects(
            response,
            reverse('ops_dashboard'),
            fetch_redirect_response=False,
        )
        device.refresh_from_db()
        self.assertTrue(device.confirmed)
        self.assertTrue(self.client.session.get('otp_verified'))
        self.assertTrue(
            OpsEventLog.objects.filter(user=self.user, event='otp_setup').exists()
        )

    def test_otp_verify_marks_current_session_verified(self):
        self.client.force_login(self.user)
        device = TOTPDevice.objects.create(
            user=self.user,
            name='AgriOps Ops Dashboard',
            confirmed=True,
        )

        response = self.client.post(
            reverse('ops_otp_verify'),
            {'token': self._current_token(device)},
        )

        self.assertRedirects(
            response,
            reverse('ops_dashboard'),
            fetch_redirect_response=False,
        )
        self.assertTrue(self.client.session.get('otp_verified'))
        self.assertTrue(
            OpsEventLog.objects.filter(user=self.user, event='otp_verified').exists()
        )
