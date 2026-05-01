from django.contrib import admin

from .models import DashboardConfig


@admin.register(DashboardConfig)
class DashboardConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'scope', 'department', 'version_context', 'is_default')
    list_filter = ('scope', 'version_context', 'is_default')
    search_fields = ('name', 'owner__username', 'owner__display_name')

# Register your models here.
