from django.db import models

from common.models import TimestampedModel


class Notification(TimestampedModel):
    class Category(models.TextChoices):
        APPROVAL_TODO = 'approval_todo', '审批待办'
        APPROVAL_RESULT = 'approval_result', '审批结果'
        SYSTEM = 'system', '系统通知'

    class Status(models.TextChoices):
        UNREAD = 'unread', '未读'
        READ = 'read', '已读'

    recipient = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='notifications')
    category = models.CharField(max_length=32, choices=Category.choices)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNREAD)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.UUIDField(null=True, blank=True)
    department = models.ForeignKey(
        'orgs.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
    )
    extra = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = '通知'
        verbose_name_plural = '通知'
        ordering = ['status', '-created_at']

    def __str__(self):
        return f'{self.recipient} - {self.title}'

