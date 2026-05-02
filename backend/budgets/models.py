from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.models import TimestampedModel


class BudgetBook(TimestampedModel):
    class ExpenseType(models.TextChoices):
        OPEX = 'opex', 'OPEX'
        CAPEX = 'capex', 'CAPEX'

    class SourceType(models.TextChoices):
        SELF_BUILT = 'self_built', '二级部门自编'
        SPECIAL = 'special', '专题生成'
        SS_PUBLIC = 'ss_public', 'SS public'
        GROUP_ALLOCATION = 'group_allocation', '集团分摊'
        PRIMARY_CONSOLIDATED = 'primary_consolidated', '一级总表'

    class Status(models.TextChoices):
        DRAFTING = 'drafting', '编制中'
        REVIEWING = 'reviewing', '审核中'
        APPROVED = 'approved', '已审批'
        LOCKED = 'locked', '已锁定'

    cycle = models.ForeignKey('budget_cycles.BudgetCycle', on_delete=models.CASCADE, related_name='budget_books')
    department = models.ForeignKey('orgs.Department', on_delete=models.PROTECT, related_name='budget_books')
    expense_type = models.CharField(max_length=16, choices=ExpenseType.choices)
    source_type = models.CharField(max_length=32, choices=SourceType.choices, default=SourceType.SELF_BUILT)
    template = models.ForeignKey('budget_templates.BudgetTemplate', on_delete=models.PROTECT, related_name='budget_books')
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFTING)
    current_draft = models.ForeignKey(
        'budgets.BudgetVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='draft_for_books',
    )
    latest_approved_version = models.ForeignKey(
        'budgets.BudgetVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_for_books',
    )

    class Meta:
        verbose_name = '预算表'
        verbose_name_plural = '预算表'
        unique_together = [('cycle', 'department', 'expense_type', 'source_type')]
        ordering = ['cycle', 'department__sort_order', 'expense_type']

    def __str__(self):
        return f'{self.cycle} - {self.department} - {self.get_expense_type_display()}'


class BudgetVersion(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', '送审中'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', '已退回'
        FINAL = 'final', 'Final'

    book = models.ForeignKey(BudgetBook, on_delete=models.CASCADE, related_name='versions')
    version_no = models.PositiveIntegerField(default=0, help_text='Draft 可为 0，审批通过后生成正式版本号。')
    base_version = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='derived_versions')
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    submitted_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_budget_versions')
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_budget_versions')
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    snapshot_hash = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = '预算版本'
        verbose_name_plural = '预算版本'
        ordering = ['book', '-created_at']

    def __str__(self):
        label = 'Draft' if self.status == self.Status.DRAFT else f'V{self.version_no}'
        return f'{self.book} - {label}'


class BudgetLine(TimestampedModel):
    version = models.ForeignKey(BudgetVersion, on_delete=models.CASCADE, related_name='lines')
    line_no = models.PositiveIntegerField(default=0)
    budget_no = models.CharField(max_length=128, blank=True)
    department = models.ForeignKey('orgs.Department', on_delete=models.PROTECT, related_name='budget_lines')
    cost_center_code = models.CharField(max_length=64, blank=True)
    category = models.ForeignKey('masterdata.Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='budget_lines')
    category_l1 = models.ForeignKey('masterdata.Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='budget_l1_lines')
    category_l2 = models.ForeignKey('masterdata.Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='budget_l2_lines')
    gl_amount_code = models.CharField(max_length=64, blank=True)
    project = models.ForeignKey('masterdata.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='budget_lines')
    project_category = models.ForeignKey('masterdata.ProjectCategory', on_delete=models.SET_NULL, null=True, blank=True, related_name='budget_lines')
    product_line = models.ForeignKey('masterdata.ProductLine', on_delete=models.SET_NULL, null=True, blank=True, related_name='budget_lines')
    description = models.CharField(max_length=255)
    vendor = models.ForeignKey('masterdata.Vendor', on_delete=models.SET_NULL, null=True, blank=True, related_name='budget_lines')
    reason = models.TextField(blank=True)
    region = models.ForeignKey('masterdata.Region', on_delete=models.SET_NULL, null=True, blank=True, related_name='budget_lines')
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    dynamic_data = models.JSONField(default=dict, blank=True)
    local_comments = models.JSONField(default=dict, blank=True)
    admin_annotations = models.JSONField(default=dict, blank=True)
    source_ref_type = models.CharField(max_length=64, blank=True)
    source_ref_id = models.UUIDField(null=True, blank=True)
    editable_by_secondary = models.BooleanField(default=True)

    class Meta:
        verbose_name = '预算条目'
        verbose_name_plural = '预算条目'
        ordering = ['version', 'line_no']

    def __str__(self):
        return self.description


class BudgetMonthlyPlan(TimestampedModel):
    line = models.ForeignKey(BudgetLine, on_delete=models.CASCADE, related_name='monthly_plans')
    month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        verbose_name = '预算月度计划'
        verbose_name_plural = '预算月度计划'
        unique_together = [('line', 'month')]
        ordering = ['line', 'month']

    def __str__(self):
        return f'{self.line} - {self.month}月'


class ImportJob(TimestampedModel):
    class Mode(models.TextChoices):
        APPEND = 'append', '追加导入'
        REPLACE = 'replace', '覆盖导入'

    class Status(models.TextChoices):
        PROCESSING = 'processing', '处理中'
        SUCCESS = 'success', '成功'
        FAILED = 'failed', '失败'

    version = models.ForeignKey('budgets.BudgetVersion', on_delete=models.CASCADE, related_name='import_jobs')
    requester = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_jobs',
    )
    source_name = models.CharField(max_length=255, blank=True)
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.APPEND)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROCESSING)
    total_rows = models.PositiveIntegerField(default=0)
    imported_rows = models.PositiveIntegerField(default=0)
    error_rows = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = '导入任务'
        verbose_name_plural = '导入任务'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.version} - {self.get_status_display()}'


class AllocationUpload(TimestampedModel):
    class Status(models.TextChoices):
        SUCCESS = 'success', '成功'
        FAILED = 'failed', '失败'

    cycle = models.ForeignKey('budget_cycles.BudgetCycle', on_delete=models.CASCADE, related_name='allocation_uploads')
    requester = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='allocation_uploads',
    )
    source_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUCCESS)
    total_rows = models.PositiveIntegerField(default=0)
    imported_rows = models.PositiveIntegerField(default=0)
    error_rows = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = '集团分摊上传任务'
        verbose_name_plural = '集团分摊上传任务'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.cycle} - {self.source_name or "allocation"}'

# Create your models here.
