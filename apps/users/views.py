from django.views.generic import ListView, DetailView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import CustomUser


class UserListView(LoginRequiredMixin, ListView):
    model = CustomUser
    template_name = 'users/list.html'
    context_object_name = 'users'
    ordering = ['last_name', 'first_name']


class UserDetailView(LoginRequiredMixin, DetailView):
    model = CustomUser
    template_name = 'users/detail.html'
    context_object_name = 'profile'


class UserUpdateView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    template_name = 'users/form.html'
    fields = ['username', 'first_name', 'last_name', 'email', 'role', 'phone', 'company', 'is_active']
    success_url = reverse_lazy('users:list')


class UserDeleteView(LoginRequiredMixin, DeleteView):
    model = CustomUser
    template_name = 'users/confirm_delete.html'
    success_url = reverse_lazy('users:list')
