from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'category', 'status', 'department', 'created_at')
    list_filter = ('category', 'status', 'department')
    search_fields = ('title', 'message', 'recipient__username')

