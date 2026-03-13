from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Supplier


class SupplierListView(LoginRequiredMixin, ListView):
    model = Supplier
    template_name = 'suppliers/list.html'
    context_object_name = 'suppliers'
    paginate_by = 20


class SupplierDetailView(LoginRequiredMixin, DetailView):
    model = Supplier
    template_name = 'suppliers/detail.html'
    context_object_name = 'supplier'


class SupplierCreateView(LoginRequiredMixin, CreateView):
    model = Supplier
    template_name = 'suppliers/form.html'
    fields = ['company', 'name', 'category', 'contact_person', 'phone', 'email', 'country', 'city', 'address', 'is_active']
    success_url = reverse_lazy('suppliers:list')


class SupplierUpdateView(LoginRequiredMixin, UpdateView):
    model = Supplier
    template_name = 'suppliers/form.html'
    fields = ['company', 'name', 'category', 'contact_person', 'phone', 'email', 'country', 'city', 'address', 'is_active']
    success_url = reverse_lazy('suppliers:list')


class SupplierDeleteView(LoginRequiredMixin, DeleteView):
    model = Supplier
    template_name = 'suppliers/confirm_delete.html'
    success_url = reverse_lazy('suppliers:list')
