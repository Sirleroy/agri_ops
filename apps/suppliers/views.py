from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Supplier
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin


class SupplierListView(StaffRequiredMixin, ListView):
    model = Supplier
    template_name = 'suppliers/list.html'
    context_object_name = 'suppliers'

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)


class SupplierDetailView(StaffRequiredMixin, DetailView):
    model = Supplier
    template_name = 'suppliers/detail.html'
    context_object_name = 'supplier'

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class SupplierCreateView(StaffRequiredMixin, CreateView):
    model = Supplier
    template_name = 'suppliers/form.html'
    fields = ['name', 'category', 'contact_person', 'phone', 'email',
              'country', 'city', 'address', 'is_active']
    success_url = reverse_lazy('suppliers:list')

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)


class SupplierUpdateView(StaffRequiredMixin, UpdateView):
    model = Supplier
    template_name = 'suppliers/form.html'
    fields = ['name', 'category', 'contact_person', 'phone', 'email',
              'country', 'city', 'address', 'is_active']
    success_url = reverse_lazy('suppliers:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class SupplierDeleteView(ManagerRequiredMixin, DeleteView):
    model = Supplier
    template_name = 'suppliers/confirm_delete.html'
    success_url = reverse_lazy('suppliers:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj
