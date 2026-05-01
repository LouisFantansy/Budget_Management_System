from django.db import models

from common.models import TimestampedModel


class BudgetTemplate(TimestampedModel):
    class ExpenseType(models.TextChoices):
        OPEX = 'opex', 'OPEX'
        CAPEX = 'capex', 'CAPEX'
        SPECIAL = 'special', '专题表单'

    class Status(models.TextChoices):
        DRAFT = 'draft', '草稿'
        ACTIVE = 'active', '启用'
        ARCHIVED = 'archived', '归档'

    cycle = models.ForeignKey('budget_cycles.BudgetCycle', on_delete=models.CASCADE, related_name='templates')
    name = models.CharField(max_length=128)
    expense_type = models.CharField(max_length=16, choices=ExpenseType.choices)
    schema_version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    copied_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='copied_templates')

    class Meta:
        verbose_name = '预算模板'
        verbose_name_plural = '预算模板'
        unique_together = [('cycle', 'expense_type', 'schema_version')]
        ordering = ['cycle', 'expense_type', 'schema_version']

    def __str__(self):
        return f'{self.name} v{self.schema_version}'


class TemplateField(TimestampedModel):
    class DataType(models.TextChoices):
        TEXT = 'text', '文本'
        NUMBER = 'number', '数字'
        MONEY = 'money', '金额'
        DATE = 'date', '日期'
        BOOLEAN = 'boolean', '布尔'
        OPTION = 'option', '选项'
        JSON = 'json', 'JSON'

    class InputType(models.TextChoices):
        TEXT = 'text', '文本输入'
        NUMBER = 'number', '数字输入'
        SELECT = 'select', '下拉'
        MULTI_SELECT = 'multi_select', '多选'
        DATE = 'date', '日期'
        FORMULA = 'formula', '公式'
        USER = 'user', '用户选择'
        DEPARTMENT = 'department', '部门选择'
        PROJECT = 'project', '项目选择'

    template = models.ForeignKey(BudgetTemplate, on_delete=models.CASCADE, related_name='fields')
    code = models.CharField(max_length=64)
    label = models.CharField(max_length=128)
    data_type = models.CharField(max_length=16, choices=DataType.choices)
    input_type = models.CharField(max_length=32, choices=InputType.choices, default=InputType.TEXT)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=160)
    option_source = models.CharField(max_length=128, blank=True)
    formula = models.CharField(max_length=512, blank=True)
    visible_rules = models.JSONField(default=dict, blank=True)
    editable_rules = models.JSONField(default=dict, blank=True)
    approval_included = models.BooleanField(default=True)
    dashboard_enabled = models.BooleanField(default=False)
    import_aliases = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = '模板字段'
        verbose_name_plural = '模板字段'
        unique_together = [('template', 'code')]
        ordering = ['template', 'order', 'code']

    def __str__(self):
        return f'{self.template} - {self.label}'

# Create your models here.
