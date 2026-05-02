from copy import deepcopy

from django.db import transaction

from budget_cycles.models import BudgetCycle

from .models import BudgetTemplate, TemplateField


@transaction.atomic
def create_template_revision(template):
    template = BudgetTemplate.objects.select_for_update().prefetch_related('fields').get(id=template.id)
    next_schema_version = (
        BudgetTemplate.objects.filter(cycle=template.cycle, expense_type=template.expense_type)
        .exclude(id=template.id)
        .order_by('-schema_version')
        .values_list('schema_version', flat=True)
        .first()
        or template.schema_version
    ) + 1
    revision = BudgetTemplate.objects.create(
        cycle=template.cycle,
        name=template.name,
        expense_type=template.expense_type,
        schema_version=next_schema_version,
        status=BudgetTemplate.Status.DRAFT,
        copied_from=template,
    )
    _clone_fields(template, revision)
    return revision


@transaction.atomic
def bootstrap_cycle_templates(cycle):
    cycle = BudgetCycle.objects.select_for_update().get(id=cycle.id)
    previous_cycle = (
        BudgetCycle.objects.filter(year__lt=cycle.year)
        .order_by('-year', '-created_at')
        .first()
    )
    if previous_cycle is None:
        raise ValueError('当前没有可复制的上一周期模板。')

    created = []
    for expense_type in [BudgetTemplate.ExpenseType.OPEX, BudgetTemplate.ExpenseType.CAPEX]:
        if BudgetTemplate.objects.filter(cycle=cycle, expense_type=expense_type).exists():
            continue
        source_template = (
            BudgetTemplate.objects.filter(cycle=previous_cycle, expense_type=expense_type)
            .order_by('-status', '-schema_version', '-created_at')
            .first()
        )
        if source_template is None:
            continue
        cloned = BudgetTemplate.objects.create(
            cycle=cycle,
            name=source_template.name,
            expense_type=source_template.expense_type,
            schema_version=1,
            status=BudgetTemplate.Status.ACTIVE,
            copied_from=source_template,
        )
        _clone_fields(source_template, cloned)
        created.append(cloned)
    return previous_cycle, created


def _clone_fields(source_template, target_template):
    for field in source_template.fields.order_by('order', 'code'):
        TemplateField.objects.create(
            template=target_template,
            code=field.code,
            label=field.label,
            data_type=field.data_type,
            input_type=field.input_type,
            required=field.required,
            order=field.order,
            width=field.width,
            frozen=field.frozen,
            option_source=field.option_source,
            formula=field.formula,
            visible_rules=deepcopy(field.visible_rules or {}),
            editable_rules=deepcopy(field.editable_rules or {}),
            approval_included=field.approval_included,
            dashboard_enabled=field.dashboard_enabled,
            import_aliases=deepcopy(field.import_aliases or []),
        )
