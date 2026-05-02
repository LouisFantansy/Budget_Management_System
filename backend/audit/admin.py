from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'category', 'action', 'target_type', 'target_label', 'actor', 'department')
    list_filter = ('category', 'action', 'target_type')
    search_fields = ('target_label', 'action', 'target_type', 'actor__username', 'actor__display_name')
