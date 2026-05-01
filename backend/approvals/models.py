from django.db import models

from common.models import TimestampedModel


class ApprovalRequest(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = 'pending', '待审批'
        APPROVED = 'approved', '已通过'
        REJECTED = 'rejected', '已退回'
        CANCELLED = 'cancelled', '已取消'

    target_type = models.CharField(max_length=64)
    target_id = models.UUIDField()
    title = models.CharField(max_length=255)
    requester = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='approval_requests')
    department = models.ForeignKey('orgs.Department', on_delete=models.PROTECT, related_name='approval_requests')
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    current_node = models.PositiveIntegerField(default=1)
    submitted_version_label = models.CharField(max_length=64, blank=True)
    dashboard_context = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = '审批请求'
        verbose_name_plural = '审批请求'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ApprovalStep(TimestampedModel):
    class Action(models.TextChoices):
        PENDING = 'pending', '待处理'
        APPROVED = 'approved', '通过'
        REJECTED = 'rejected', '退回'

    request = models.ForeignKey(ApprovalRequest, on_delete=models.CASCADE, related_name='steps')
    node = models.PositiveIntegerField()
    approver = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='approval_steps')
    action = models.CharField(max_length=32, choices=Action.choices, default=Action.PENDING)
    comment = models.TextField(blank=True)
    acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = '审批节点'
        verbose_name_plural = '审批节点'
        unique_together = [('request', 'node', 'approver')]
        ordering = ['request', 'node']

    def __str__(self):
        return f'{self.request} - {self.approver}'

# Create your models here.
