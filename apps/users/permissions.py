from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


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
