from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404


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


class CompanyOwnedMixin:
    """
    Tenant-isolation guard for DetailView / UpdateView / DeleteView.
    Raises 404 if the fetched object does not belong to the requesting
    user's company. Mandatory on any view that fetches a tenant-scoped
    object by pk — a missing check is a cross-tenant data leak.
    """
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.company != self.request.user.company:
            raise Http404
        return obj


class CompanySetMixin:
    """
    Stamps form.instance.company with the requesting user's company before
    save. Use on CreateView (and UpdateView where rebinding is desired).
    Subclasses that override form_valid should call super().form_valid(form)
    so the company stamp still runs.
    """
    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)


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
