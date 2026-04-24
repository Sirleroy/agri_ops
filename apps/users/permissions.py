from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    required_role = None

    ROLE_HIERARCHY = {
        'viewer':    1,
        'staff':     2,
        'manager':   3,
        'org_admin': 4,
    }

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.company:
            raise PermissionDenied("No organisation assigned to this user.")
        if not request.user.company.is_active:
            from django.contrib import messages
            from django.contrib.auth import logout
            from django.shortcuts import redirect
            from django.conf import settings
            logout(request)
            messages.error(
                request,
                'Your organisation account has been suspended. '
                'Please contact AgriOps support to restore access.'
            )
            return redirect(settings.LOGIN_URL)
        if self.required_role:
            user_level = self.ROLE_HIERARCHY.get(request.user.system_role, 0)
            required_level = self.ROLE_HIERARCHY.get(self.required_role, 0)
            if user_level < required_level:
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class StaffRequiredMixin(RoleRequiredMixin):
    required_role = 'staff'


class ManagerRequiredMixin(RoleRequiredMixin):
    required_role = 'manager'


class OrgAdminRequiredMixin(RoleRequiredMixin):
    required_role = 'org_admin'


class OtherRevealMixin:
    """
    Add data-other attr to select fields so the global JS can show/hide
    a free-text input when the user picks 'Other'.
    Set other_reveal_fields = ['category'] (or similar) in the view.
    """
    other_reveal_fields = []

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name in self.other_reveal_fields:
            if field_name in form.fields:
                form.fields[field_name].widget.attrs['data-other'] = f'id_{field_name}_other'
        return form


class DatePickerMixin:
    """Replace all DateField widgets with HTML5 date pickers."""
    def get_form(self, form_class=None):
        from django import forms
        form = super().get_form(form_class)
        for field in form.fields.values():
            if isinstance(field, forms.DateField):
                field.widget = forms.DateInput(
                    attrs={'type': 'date'},
                    format='%Y-%m-%d',
                )
        return form
