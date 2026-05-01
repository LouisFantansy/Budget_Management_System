from django.contrib import admin

from .models import ApprovalRequest, ApprovalStep


class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 0


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_type', 'requester', 'department', 'status', 'submitted_version_label')
    list_filter = ('status', 'target_type')
    search_fields = ('title', 'requester__username', 'requester__display_name')
    inlines = [ApprovalStepInline]


@admin.register(ApprovalStep)
class ApprovalStepAdmin(admin.ModelAdmin):
    list_display = ('request', 'node', 'approver', 'action', 'acted_at')
    list_filter = ('action',)
    search_fields = ('request__title', 'approver__username', 'approver__display_name')

# Register your models here.
