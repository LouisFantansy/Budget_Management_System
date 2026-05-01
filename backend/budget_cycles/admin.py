from django.contrib import admin

from .models import BudgetCycle, BudgetTask


@admin.register(BudgetCycle)
class BudgetCycleAdmin(admin.ModelAdmin):
    list_display = ('year', 'name', 'status', 'start_at', 'end_at')
    list_filter = ('status',)
    search_fields = ('name',)


@admin.register(BudgetTask)
class BudgetTaskAdmin(admin.ModelAdmin):
    list_display = ('cycle', 'department', 'owner', 'status', 'due_at')
    list_filter = ('status', 'cycle')
    search_fields = ('department__name', 'owner__username', 'owner__display_name')

# Register your models here.
