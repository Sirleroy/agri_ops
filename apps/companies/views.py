from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Company


class CompanyListView(LoginRequiredMixin, ListView):
    model = Company
    template_name = 'companies/list.html'
    context_object_name = 'companies'
    paginate_by = 20


class CompanyDetailView(LoginRequiredMixin, DetailView):
    model = Company
    template_name = 'companies/detail.html'
    context_object_name = 'company'


class CompanyCreateView(LoginRequiredMixin, CreateView):
    model = Company
    template_name = 'companies/form.html'
    fields = ['name', 'country', 'city', 'address', 'phone', 'email', 'plan_tier', 'is_active']
    success_url = reverse_lazy('companies:list')


class CompanyUpdateView(LoginRequiredMixin, UpdateView):
    model = Company
    template_name = 'companies/form.html'
    fields = ['name', 'country', 'city', 'address', 'phone', 'email', 'plan_tier', 'is_active']
    success_url = reverse_lazy('companies:list')


class CompanyDeleteView(LoginRequiredMixin, DeleteView):
    model = Company
    template_name = 'companies/confirm_delete.html'
    success_url = reverse_lazy('companies:list')
