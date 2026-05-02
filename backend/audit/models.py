from django.db import models

from common.models import TimestampedModel


class AuditLog(TimestampedModel):
    class Category(models.TextChoices):
        BUDGET = 'budget', '预算'
        APPROVAL = 'approval', '审批'
        DEMAND = 'demand', '专题需求'
        IMPORT = 'import', '导入'
        SYSTEM = 'system', '系统'

    actor = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    category = models.CharField(max_length=32, choices=Category.choices)
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=64)
    target_id = models.UUIDField(null=True, blank=True)
    target_label = models.CharField(max_length=255, blank=True)
    department = models.ForeignKey(
        'orgs.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    book = models.ForeignKey(
        'budgets.BudgetBook',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    version = models.ForeignKey(
        'budgets.BudgetVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = '审计日志'
        verbose_name_plural = '审计日志'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.category}:{self.action}:{self.target_type}'
