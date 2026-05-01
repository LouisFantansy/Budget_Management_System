from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import RoleAssignment, User


@admin.register(User)
class BudgetUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('研发预算系统', {'fields': ('employee_id', 'display_name', 'primary_department')}),
    )
    list_display = ('username', 'display_name', 'employee_id', 'primary_department', 'is_staff')
    search_fields = ('username', 'display_name', 'employee_id', 'email')


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'is_primary')
    list_filter = ('role', 'is_primary')
    search_fields = ('user__username', 'user__display_name', 'department__name')

# Register your models here.
