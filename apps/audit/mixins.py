from .models import AuditLog


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_action(request, action, instance, changes=None):
    """
    Write a single audit log entry.
    Call this directly from form_valid() and delete() in views.
    """
    user = request.user if request.user.is_authenticated else None
    company = getattr(user, 'company', None)

    AuditLog.objects.create(
        company=company,
        user=user,
        action=action,
        model_name=instance.__class__.__name__,
        object_id=instance.pk,
        object_repr=str(instance),
        changes=changes,
        ip_address=get_client_ip(request),
    )


class AuditCreateMixin:
    """Add to CreateView — logs the creation after form_valid."""
    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request, 'create', self.object)
        return response


class AuditUpdateMixin:
    """Add to UpdateView — captures before/after changes and logs the update."""
    def form_valid(self, form):
        # Capture changed fields before saving
        changes = {}
        if form.changed_data:
            for field in form.changed_data:
                old_val = form.initial.get(field, '')
                new_val = form.cleaned_data.get(field, '')
                changes[field] = {
                    'from': str(old_val),
                    'to': str(new_val),
                }
        response = super().form_valid(form)
        log_action(self.request, 'update', self.object, changes=changes)
        return response


class AuditDeleteMixin:
    """Add to DeleteView — logs deletion before the object is removed."""
    def form_valid(self, form):
        log_action(self.request, 'delete', self.object)
        return super().form_valid(form)
