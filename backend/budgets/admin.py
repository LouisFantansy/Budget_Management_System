from django.contrib import admin

from .models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion


class BudgetMonthlyPlanInline(admin.TabularInline):
    model = BudgetMonthlyPlan
    extra = 0


@admin.register(BudgetBook)
class BudgetBookAdmin(admin.ModelAdmin):
    list_display = ('cycle', 'department', 'expense_type', 'source_type', 'status', 'latest_approved_version')
    list_filter = ('expense_type', 'source_type', 'status', 'cycle')
    search_fields = ('department__name',)


@admin.register(BudgetVersion)
class BudgetVersionAdmin(admin.ModelAdmin):
    list_display = ('book', 'version_no', 'status', 'submitted_by', 'approved_by', 'submitted_at', 'approved_at')
    list_filter = ('status',)
    search_fields = ('book__department__name',)


@admin.register(BudgetLine)
class BudgetLineAdmin(admin.ModelAdmin):
    list_display = ('description', 'version', 'department', 'category', 'project', 'total_quantity', 'total_amount', 'editable_by_secondary')
    list_filter = ('editable_by_secondary', 'department', 'category')
    search_fields = ('description', 'budget_no')
    inlines = [BudgetMonthlyPlanInline]


@admin.register(BudgetMonthlyPlan)
class BudgetMonthlyPlanAdmin(admin.ModelAdmin):
    list_display = ('line', 'month', 'quantity', 'amount')
    list_filter = ('month',)

# Register your models here.
