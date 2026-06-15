from django.contrib import admin
from .models import AccessRequest, RequestItem

class RequestItemInline(admin.TabularInline):
    model = RequestItem
    extra = 0
    raw_id_fields = ['application']

@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'requester', 'status', 'created_at', 'deadline', 'reviewed_by', 'reviewed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['requester__email', 'requester__first_name', 'requester__last_name']
    readonly_fields = ['created_at']
    raw_id_fields = ['requester', 'reviewed_by']
    inlines = [RequestItemInline]

@admin.register(RequestItem)
class RequestItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'access_request', 'application']
    search_fields = ['application__name', 'application__code', 'access_request__requester__email']
    raw_id_fields = ['access_request', 'application']
