from django.contrib import admin

from .models import BudgetTemplate, TemplateField


class TemplateFieldInline(admin.TabularInline):
    model = TemplateField
    extra = 0


@admin.register(BudgetTemplate)
class BudgetTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'cycle', 'expense_type', 'schema_version', 'status')
    list_filter = ('expense_type', 'status', 'cycle')
    search_fields = ('name',)
    inlines = [TemplateFieldInline]


@admin.register(TemplateField)
class TemplateFieldAdmin(admin.ModelAdmin):
    list_display = ('template', 'code', 'label', 'data_type', 'input_type', 'required', 'dashboard_enabled')
    list_filter = ('data_type', 'input_type', 'required', 'dashboard_enabled')
    search_fields = ('code', 'label', 'template__name')

# Register your models here.
