from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Product


class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'products/list.html'
    context_object_name = 'products'
    paginate_by = 20


class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'products/detail.html'
    context_object_name = 'product'


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    template_name = 'products/form.html'
    fields = ['company', 'supplier', 'name', 'description', 'category', 'unit', 'unit_price', 'is_active']
    success_url = reverse_lazy('products:list')


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    template_name = 'products/form.html'
    fields = ['company', 'supplier', 'name', 'description', 'category', 'unit', 'unit_price', 'is_active']
    success_url = reverse_lazy('products:list')


class ProductDeleteView(LoginRequiredMixin, DeleteView):
    model = Product
    template_name = 'products/confirm_delete.html'
    success_url = reverse_lazy('products:list')
