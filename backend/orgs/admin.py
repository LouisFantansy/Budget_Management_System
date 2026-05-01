from django.contrib import admin

from .models import Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'level', 'parent', 'cost_center_code', 'is_active')
    list_filter = ('level', 'is_active')
    search_fields = ('name', 'code', 'cost_center_code')

# Register your models here.
