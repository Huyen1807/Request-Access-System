from django.contrib import admin
from .models import Department, Domain, Application


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'description']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'department', 'description']
    list_filter = ['department']
    search_fields = ['name', 'code', 'department__name']
    ordering = ['department', 'name']


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'domain', 'owner', 'is_active']
    list_filter = ['is_active', 'domain__department', 'domain']
    search_fields = ['name', 'code', 'domain__name', 'owner__email']
    ordering = ['domain', 'name']
    raw_id_fields = ['owner']
