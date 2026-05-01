from django.db import models

from common.models import TimestampedModel


class BudgetCycle(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', '草稿'
        ACTIVE = 'active', '编制中'
        REVIEWING = 'reviewing', '审核中'
        LOCKED = 'locked', '终版锁定'
        ARCHIVED = 'archived', '已归档'

    year = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=128)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = '预算周期'
        verbose_name_plural = '预算周期'
        ordering = ['-year']

    def __str__(self):
        return self.name


class BudgetTask(TimestampedModel):
    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', '未开始'
        DRAFTING = 'drafting', '编制中'
        SECONDARY_REVIEW = 'secondary_review', '待二级部门负责人审批'
        SECONDARY_REJECTED = 'secondary_rejected', '二级部门负责人退回'
        SECONDARY_APPROVED = 'secondary_approved', '二级部门负责人已审批'
        PULLED_TO_PRIMARY = 'pulled_to_primary', '已被一级部门拉取'
        PRIMARY_REVIEW = 'primary_review', '一级预算审核中'
        FINAL_LOCKED = 'final_locked', '终版锁定'

    cycle = models.ForeignKey(BudgetCycle, on_delete=models.CASCADE, related_name='tasks')
    department = models.ForeignKey('orgs.Department', on_delete=models.PROTECT, related_name='budget_tasks')
    owner = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_budget_tasks')
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.NOT_STARTED)
    due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = '预算任务'
        verbose_name_plural = '预算任务'
        unique_together = [('cycle', 'department')]
        ordering = ['cycle', 'department__sort_order']

    def __str__(self):
        return f'{self.cycle} - {self.department}'

# Create your models here.
