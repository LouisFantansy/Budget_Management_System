from django.db import models

from common.models import TimestampedModel


class DemandTemplate(TimestampedModel):
    class ExpenseType(models.TextChoices):
        OPEX = 'opex', 'OPEX'
        CAPEX = 'capex', 'CAPEX'

    class Status(models.TextChoices):
        DRAFT = 'draft', '草稿'
        ACTIVE = 'active', '启用'
        ARCHIVED = 'archived', '归档'

    class TargetMode(models.TextChoices):
        SECONDARY = 'secondary', '挂到二级部门'
        SS_PUBLIC = 'ss_public', '挂到 SS public'

    cycle = models.ForeignKey('budget_cycles.BudgetCycle', on_delete=models.CASCADE, related_name='demand_templates')
    name = models.CharField(max_length=128)
    expense_type = models.CharField(max_length=16, choices=ExpenseType.choices, default=ExpenseType.OPEX)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    target_mode = models.CharField(max_length=16, choices=TargetMode.choices, default=TargetMode.SECONDARY)
    target_department = models.ForeignKey(
        'orgs.Department',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='owned_demand_templates',
    )
    schema = models.JSONField(default=list, blank=True)
    default_payload = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = '专题需求模板'
        verbose_name_plural = '专题需求模板'
        ordering = ['cycle', 'name']

    def __str__(self):
        return self.name


class DemandSheet(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', '草稿'
        SUBMITTED = 'submitted', '已提交'
        CONFIRMED = 'confirmed', '已确认'
        GENERATED = 'generated', '已生成预算'

    template = models.ForeignKey('demands.DemandTemplate', on_delete=models.CASCADE, related_name='sheets')
    target_department = models.ForeignKey(
        'orgs.Department',
        on_delete=models.PROTECT,
        related_name='demand_sheets',
    )
    requested_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_demand_sheets',
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    due_at = models.DateTimeField(null=True, blank=True)
    schema_snapshot = models.JSONField(default=list, blank=True)
    payload = models.JSONField(default=list, blank=True)
    submitted_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_demand_sheets',
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_demand_sheets',
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    generated_budget_book = models.ForeignKey(
        'budgets.BudgetBook',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_demand_sheets',
    )
    generated_budget_version = models.ForeignKey(
        'budgets.BudgetVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_demand_sheets',
    )
    generated_line_count = models.PositiveIntegerField(default=0)
    generated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_demand_sheets',
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    generated_payload_hash = models.CharField(max_length=64, blank=True)
    latest_comment = models.TextField(blank=True)

    class Meta:
        verbose_name = '专题需求表'
        verbose_name_plural = '专题需求表'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.template.name} - {self.target_department.name}'
