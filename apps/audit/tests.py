from django.test import TestCase, RequestFactory
from django.urls import reverse

from apps.companies.models import Company
from apps.users.models import CustomUser
from apps.suppliers.models import Supplier, Farm
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


class AuditLogChangesRenderingTests(TestCase):
    """
    The eye icon and detail modal on the audit log page must:
      1. Always render (never hidden when changes is empty/null)
      2. Carry valid JSON in the data-changes attribute so JSON.parse can read it
    """

    def setUp(self):
        self.company = make_company('Render Co')
        self.staff = make_user(self.company, role='staff', username='render_staff')
        self.supplier = Supplier.objects.create(
            company=self.company, name='Render Supplier', category='cooperative'
        )

    def _log_with_changes(self, changes):
        request = RequestFactory().get('/')
        request.user = self.staff
        log_action(request, 'update', self.supplier, changes=changes)
        return AuditLog.objects.latest('timestamp')

    def test_to_json_filter_emits_valid_json_for_diff(self):
        from apps.audit.templatetags.audit_extras import to_json
        import json
        changes = {'fvf_land_tenure': {'from': 'title_deed', 'to': 'village_consent'}}
        rendered = str(to_json(changes))
        # HTML-escaped JSON: parse after unescaping double-quote entities
        unescaped = rendered.replace('&quot;', '"')
        parsed = json.loads(unescaped)
        self.assertEqual(parsed, changes)

    def test_to_json_filter_handles_none(self):
        from apps.audit.templatetags.audit_extras import to_json
        rendered = str(to_json(None))
        self.assertIn('{}', rendered)

    def test_to_json_filter_handles_empty_dict(self):
        from apps.audit.templatetags.audit_extras import to_json
        rendered = str(to_json({}))
        self.assertIn('{}', rendered)

    def test_eye_icon_renders_on_row_with_diff(self):
        self._log_with_changes(
            {'fvf_land_tenure': {'from': 'title_deed', 'to': 'village_consent'}}
        )
        self.client.force_login(self.staff)
        r = self.client.get(reverse('audit:list'))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        # Eye-icon button is identifiable by its title and click handler
        self.assertIn('title="View changes"', body)
        # data-changes carries the field name (HTML-escaped JSON)
        self.assertIn('fvf_land_tenure', body)

    def test_eye_icon_renders_on_row_without_changes(self):
        # Log an entry with no changes dict at all (mimicking actions whose
        # diff was not captured — the case the user hit on the farm update)
        request = RequestFactory().get('/')
        request.user = self.staff
        log_action(request, 'update', self.supplier, changes=None)
        self.client.force_login(self.staff)
        r = self.client.get(reverse('audit:list'))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        # Icon must render — the operator should always have a path to the modal
        self.assertIn('title="View changes"', body)

    def test_data_changes_attribute_uses_double_quotes_not_python_repr(self):
        """Regression guard: rendered changes must be JSON, not Python repr."""
        self._log_with_changes(
            {'fvf_land_tenure': {'from': 'title_deed', 'to': 'village_consent'}}
        )
        self.client.force_login(self.staff)
        r = self.client.get(reverse('audit:list'))
        body = r.content.decode()
        # Python repr would emit single-quoted dict syntax. Valid JSON would
        # emit double quotes (HTML-escaped to &quot;). The single-quoted
        # token is the signature of the bug we just fixed.
        self.assertNotIn(
            "{&#x27;fvf_land_tenure&#x27;",
            body,
            'data-changes is rendering Python repr instead of JSON — JSON.parse will fail'
        )
        # Positive check: HTML-escaped JSON form is present
        self.assertIn('&quot;fvf_land_tenure&quot;', body)


class CSPMapTilesTests(TestCase):
    """
    The CSP img-src directive must allow the tile providers used by the
    Leaflet maps on the farm form and farm detail pages. A missing host
    silently blocks tile loading — the map container renders but tiles
    are blank — which is exactly the failure mode we hit when CSP shipped.
    """

    def setUp(self):
        self.company = make_company('CSP Co')
        self.staff = make_user(self.company, role='staff', username='csp_staff')

    def _csp_header(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse('audit:list'))
        return r.headers.get('Content-Security-Policy', '')

    def test_csp_allows_openstreetmap_tile_host(self):
        self.assertIn('*.tile.openstreetmap.org', self._csp_header())

    def test_csp_allows_esri_world_imagery_tile_host(self):
        """Regression: Esri ArcGIS World Imagery powers the satellite layer
        on every farm map. Missing from img-src → blank satellite tiles."""
        self.assertIn('server.arcgisonline.com', self._csp_header())

    def test_csp_img_src_includes_self_and_data(self):
        csp = self._csp_header()
        self.assertIn("img-src 'self'", csp)
        self.assertIn('data:', csp)


class CSPCoverageTests(TestCase):
    """
    Locks the full inventory of external resource hosts the platform loads,
    each in its correct CSP directive. When a new CDN dependency is added,
    update both the template and the row in EXPECTED below — failure to do
    so produces a clear, single-line test failure rather than a silent
    blocked-load regression like the satellite-tiles incident.
    """

    # (host_substring, directive_keyword) — both must appear inside the
    # CSP directive section for the test to pass
    EXPECTED = [
        # Scripts
        ('cdn.tailwindcss.com',         'script-src'),
        ('cdn.jsdelivr.net',            'script-src'),
        ('cdnjs.cloudflare.com',        'script-src'),
        ('unpkg.com',                   'script-src'),
        # Styles
        ('cdn.jsdelivr.net',            'style-src'),
        ('cdnjs.cloudflare.com',        'style-src'),
        ('unpkg.com',                   'style-src'),
        ('fonts.googleapis.com',        'style-src'),
        # Fonts
        ('fonts.gstatic.com',           'font-src'),
        # Image / tile sources
        ('tile.openstreetmap.org',      'img-src'),
        ('server.arcgisonline.com',     'img-src'),
    ]

    def setUp(self):
        self.company = make_company('Coverage Co')
        self.staff = make_user(self.company, role='staff', username='coverage_staff')

    def test_every_known_loading_host_is_in_correct_csp_directive(self):
        from apps.audit.middleware import _CSP
        import re
        failures = []
        for host, directive in self.EXPECTED:
            m = re.search(rf'{directive}([^;]+);', _CSP)
            if not m:
                failures.append(f"directive '{directive}' missing from CSP entirely")
                continue
            if host not in m.group(1):
                failures.append(
                    f"host '{host}' missing from CSP {directive} — "
                    f"current directive: {directive}{m.group(1).strip()}"
                )
        if failures:
            self.fail(
                "CSP allowlist drift detected:\n  " +
                "\n  ".join(failures) +
                "\n\nFix: update _CSP in apps/audit/middleware.py, OR if the host "
                "was deliberately removed, update CSPCoverageTests.EXPECTED to match."
            )


class UserFacingPageSmokeTests(TestCase):
    """
    HTTP-level smoke tests for canonical user-facing pages — assert HTTP 200
    + key rendering markers present in the response body. Catches template
    render errors and silent feature breakage before users see them.

    These do NOT execute JavaScript; they assert that the URLs and markup
    the JS depends on are emitted by the server. Combined with CSPCoverageTests
    above, that guards against the most common silent-failure modes:
      - Template can't render (HTTP 500)
      - Critical markup missing (regression in template)
      - Asset URL missing from page (would-be CSP block silently OK because
        nothing tries to load it)
    """

    def setUp(self):
        self.company = make_company('Smoke Co')
        self.org_admin = make_user(self.company, role='org_admin', username='smoke_admin')
        self.staff = make_user(self.company, role='staff', username='smoke_staff')

    def test_login_page_renders_with_csrf(self):
        r = self.client.get(reverse('login'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'csrfmiddlewaretoken')

    def test_dashboard_renders_for_staff(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse('dashboard:index'))
        self.assertEqual(r.status_code, 200)

    def test_audit_log_renders_eye_icon_button(self):
        """Eye icon must be in markup — guards against the {% if log.changes %}
        guard regression and the to_json filter being removed."""
        # Seed at least one audit log entry so the table renders rows
        supplier = Supplier.objects.create(
            company=self.company, name='Smoke Supplier Audit', category='cooperative'
        )
        request = RequestFactory().get('/')
        request.user = self.staff
        log_action(request, 'create', supplier)

        self.client.force_login(self.staff)
        r = self.client.get(reverse('audit:list'))
        self.assertEqual(r.status_code, 200)
        # The icon's title attribute is a stable identifier
        self.assertContains(r, 'title="View changes"')

    def test_farm_list_renders(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse('suppliers:farm_list'))
        self.assertEqual(r.status_code, 200)

    def test_farm_create_form_renders_map_with_both_tile_sources(self):
        """Farm form Leaflet map must reference both tile providers in markup —
        guards against template regressions or accidental removal of either
        layer. Combined with CSPCoverageTests, this proves end-to-end:
        URL is on the page AND CSP allows the load."""
        self.client.force_login(self.staff)
        r = self.client.get(reverse('suppliers:farm_create'))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('geo-map', body)                       # map container
        self.assertIn('tile.openstreetmap.org', body)         # street layer URL
        self.assertIn('server.arcgisonline.com', body)        # satellite layer URL

    def test_farm_detail_renders_map_with_satellite_default(self):
        """Farm detail map defaults to the satellite layer. The Esri URL must
        be present in markup; if this fails the satellite-tile regression has
        recurred."""
        supplier = Supplier.objects.create(
            company=self.company, name='Smoke Supplier', category='cooperative'
        )
        farm = Farm.objects.create(
            company=self.company, supplier=supplier, name='Smoke Farm',
            country='Nigeria', commodity='Soy',
            geolocation={
                'type': 'Polygon',
                'coordinates': [[[7.0, 9.0], [7.1, 9.0], [7.1, 9.1], [7.0, 9.1], [7.0, 9.0]]],
            },
        )
        self.client.force_login(self.staff)
        r = self.client.get(reverse('suppliers:farm_detail', kwargs={'pk': farm.pk}))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('farm-map', body)
        self.assertIn('server.arcgisonline.com', body)
        self.assertIn('farm-geojson', body)  # json_script element id
