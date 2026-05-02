from django.contrib import admin

from .models import DemandSheet, DemandTemplate


@admin.register(DemandTemplate)
class DemandTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'cycle', 'expense_type', 'status', 'target_mode', 'target_department')
    list_filter = ('cycle', 'status', 'target_mode')
    search_fields = ('name',)


@admin.register(DemandSheet)
class DemandSheetAdmin(admin.ModelAdmin):
    list_display = ('template', 'target_department', 'requested_by', 'status', 'due_at', 'generated_budget_book')
    list_filter = ('template__cycle', 'status')
    search_fields = ('template__name', 'target_department__name', 'target_department__code')
