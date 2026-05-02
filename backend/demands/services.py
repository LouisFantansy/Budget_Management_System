from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework.exceptions import ValidationError

from budget_templates.models import BudgetTemplate
from budgets.models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion
from orgs.models import Department

from .models import DemandSheet, DemandTemplate


def _resolve_special_budget_template(cycle):
    template = (
        BudgetTemplate.objects.filter(
            cycle=cycle,
            expense_type=BudgetTemplate.ExpenseType.SPECIAL,
            status=BudgetTemplate.Status.ACTIVE,
        )
        .order_by('-schema_version', '-created_at')
        .first()
    )
    if template:
        return template
    fallback = (
        BudgetTemplate.objects.filter(
            cycle=cycle,
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            status=BudgetTemplate.Status.ACTIVE,
        )
        .order_by('-schema_version', '-created_at')
        .first()
    )
    if fallback:
        return fallback
    raise ValidationError({'template': '当前周期缺少可用预算模板，无法生成专题预算。'})


def _quantize_amount(raw_value, field_name, row_index):
    try:
        return Decimal(str(raw_value)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError):
        raise ValidationError({'payload': f'第 {row_index} 行字段 {field_name} 不是有效数字。'})


def _resolve_target_book_department(sheet: DemandSheet):
    template = sheet.template
    if template.target_mode == DemandTemplate.TargetMode.SS_PUBLIC:
        ss_public = Department.objects.filter(level=Department.Level.SS_PUBLIC, code='SS_PUBLIC').first()
        if not ss_public:
            raise ValidationError({'department': '未找到 SS public 部门。'})
        return ss_public
    return sheet.target_department


@transaction.atomic
def generate_budget_lines_from_sheet(sheet: DemandSheet, requester=None, force_rebuild=True):
    sheet = (
        DemandSheet.objects.select_for_update()
        .select_related('template', 'template__cycle', 'target_department', 'requested_by')
        .get(id=sheet.id)
    )
    rows = sheet.payload or []
    if not rows:
        raise ValidationError({'payload': '专题需求表没有可生成的行。'})

    budget_department = _resolve_target_book_department(sheet)
    template = _resolve_special_budget_template(sheet.template.cycle)
    book, _ = BudgetBook.objects.get_or_create(
        cycle=sheet.template.cycle,
        department=budget_department,
        expense_type=sheet.template.expense_type,
        source_type=BudgetBook.SourceType.SPECIAL,
        defaults={'template': template, 'status': BudgetBook.Status.DRAFTING},
    )
    book.template = template
    book.status = BudgetBook.Status.DRAFTING

    if book.current_draft_id and force_rebuild:
        current_draft = BudgetVersion.objects.select_for_update().get(id=book.current_draft_id)
        current_draft.lines.filter(source_ref_type='demand_sheet', source_ref_id=sheet.id).delete()
        draft = current_draft
    elif book.current_draft_id:
        draft = BudgetVersion.objects.select_for_update().get(id=book.current_draft_id)
    else:
        draft = BudgetVersion.objects.create(
            book=book,
            version_no=0,
            base_version=book.latest_approved_version,
            status=BudgetVersion.Status.DRAFT,
            submitted_by=requester if requester and requester.is_authenticated else None,
            notes=f'专题需求表 {sheet.template.name} 生成预算 Draft',
        )

    if draft.status != BudgetVersion.Status.DRAFT:
        raise ValidationError({'version': '专题预算仅支持生成到 Draft 版本。'})

    start_line_no = (draft.lines.order_by('-line_no').values_list('line_no', flat=True).first() or 0) + 1
    created_lines = []
    for row_index, row in enumerate(rows, start=1):
        total_amount = _quantize_amount(row.get('total_amount'), 'total_amount', row_index)
        unit_price = _quantize_amount(row.get('unit_price', total_amount), 'unit_price', row_index)
        total_quantity = _quantize_amount(row.get('total_quantity', 1), 'total_quantity', row_index)
        dynamic_data = dict(row)
        dynamic_data.setdefault('source_department', sheet.target_department.code)
        line = BudgetLine.objects.create(
            version=draft,
            line_no=start_line_no,
            budget_no=str(row.get('budget_no', f'DEM-{sheet.target_department.code}-{row_index:03d}')),
            department=budget_department,
            description=str(row.get('description', '')).strip(),
            reason=str(row.get('reason', '')).strip(),
            unit_price=unit_price,
            total_quantity=total_quantity,
            total_amount=total_amount,
            dynamic_data=dynamic_data,
            admin_annotations={
                'source_sheet_id': str(sheet.id),
                'source_template_id': str(sheet.template_id),
                'source_department': sheet.target_department.code,
                'generated_for_department': budget_department.code,
                'row_index': row_index,
            },
            source_ref_type='demand_sheet',
            source_ref_id=sheet.id,
            editable_by_secondary=False,
        )
        monthly_plans = row.get('monthly_plans') or []
        if isinstance(monthly_plans, list):
            plan_rows = []
            for monthly in monthly_plans:
                if not isinstance(monthly, dict) or 'month' not in monthly or 'amount' not in monthly:
                    continue
                month = int(monthly['month'])
                if month < 1 or month > 12:
                    raise ValidationError({'payload': f'第 {row_index} 行 monthly_plans.month 必须在 1-12 之间。'})
                plan_rows.append(
                    BudgetMonthlyPlan(
                        line=line,
                        month=month,
                        quantity=_quantize_amount(monthly.get('quantity', 0), 'monthly_plans.quantity', row_index),
                        amount=_quantize_amount(monthly['amount'], 'monthly_plans.amount', row_index),
                    )
                )
            if plan_rows:
                BudgetMonthlyPlan.objects.bulk_create(plan_rows)
        created_lines.append(line)
        start_line_no += 1

    book.current_draft = draft
    book.save(update_fields=['template', 'status', 'current_draft', 'updated_at'])

    sheet.status = DemandSheet.Status.GENERATED
    sheet.generated_budget_book = book
    sheet.generated_budget_version = draft
    sheet.generated_line_count = len(created_lines)
    sheet.save(
        update_fields=[
            'status',
            'generated_budget_book',
            'generated_budget_version',
            'generated_line_count',
            'updated_at',
        ]
    )
    return {
        'book': book,
        'version': draft,
        'sheet': sheet,
        'generated_line_count': len(created_lines),
    }
