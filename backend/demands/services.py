from django.utils import timezone
from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework.exceptions import ValidationError

from audit.services import create_audit_log
from budget_templates.models import BudgetTemplate
from budgets.models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion
from orgs.models import Department

from .models import DemandSheet, DemandTemplate
from .schema import hash_demand_payload, normalize_demand_payload


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
def submit_demand_sheet(sheet: DemandSheet, requester=None, comment=''):
    sheet = (
        DemandSheet.objects.select_for_update()
        .select_related('template', 'target_department')
        .get(id=sheet.id)
    )
    if sheet.status != DemandSheet.Status.DRAFT:
        raise ValidationError({'status': '只有草稿状态的专题需求表可以提交。'})
    normalize_demand_payload(
        sheet.payload,
        sheet.schema_snapshot or sheet.template.schema,
        user=None,
        enforce_all_required=False,
    )
    now = timezone.now()
    sheet.status = DemandSheet.Status.SUBMITTED
    sheet.submitted_by = requester if requester and requester.is_authenticated else None
    sheet.submitted_at = now
    sheet.latest_comment = comment or sheet.latest_comment
    sheet.save(update_fields=['status', 'submitted_by', 'submitted_at', 'latest_comment', 'updated_at'])
    create_audit_log(
        actor=requester,
        category='demand',
        action='demand_sheet_submitted',
        target_type='demand_sheet',
        target_id=sheet.id,
        target_label=sheet.template.name,
        department=sheet.target_department,
        details={'status': sheet.status, 'comment': comment},
    )
    return sheet


@transaction.atomic
def confirm_demand_sheet(sheet: DemandSheet, requester=None, comment=''):
    sheet = (
        DemandSheet.objects.select_for_update()
        .select_related('template', 'target_department')
        .get(id=sheet.id)
    )
    if sheet.status not in {DemandSheet.Status.DRAFT, DemandSheet.Status.SUBMITTED}:
        raise ValidationError({'status': '只有草稿或已提交状态的专题需求表可以确认。'})
    normalize_demand_payload(
        sheet.payload,
        sheet.schema_snapshot or sheet.template.schema,
        user=None,
        enforce_all_required=True,
    )
    now = timezone.now()
    sheet.status = DemandSheet.Status.CONFIRMED
    sheet.confirmed_by = requester if requester and requester.is_authenticated else None
    sheet.confirmed_at = now
    sheet.latest_comment = comment or sheet.latest_comment
    sheet.save(update_fields=['status', 'confirmed_by', 'confirmed_at', 'latest_comment', 'updated_at'])
    create_audit_log(
        actor=requester,
        category='demand',
        action='demand_sheet_confirmed',
        target_type='demand_sheet',
        target_id=sheet.id,
        target_label=sheet.template.name,
        department=sheet.target_department,
        details={'status': sheet.status, 'comment': comment},
    )
    return sheet


@transaction.atomic
def reopen_demand_sheet(sheet: DemandSheet, requester=None, comment=''):
    sheet = (
        DemandSheet.objects.select_for_update()
        .select_related('template', 'target_department')
        .get(id=sheet.id)
    )
    if sheet.status not in {DemandSheet.Status.SUBMITTED, DemandSheet.Status.CONFIRMED, DemandSheet.Status.GENERATED}:
        raise ValidationError({'status': '当前状态不支持重新打开。'})
    sheet.status = DemandSheet.Status.DRAFT
    sheet.confirmed_by = None
    sheet.confirmed_at = None
    sheet.latest_comment = comment or sheet.latest_comment
    sheet.save(update_fields=['status', 'confirmed_by', 'confirmed_at', 'latest_comment', 'updated_at'])
    create_audit_log(
        actor=requester,
        category='demand',
        action='demand_sheet_reopened',
        target_type='demand_sheet',
        target_id=sheet.id,
        target_label=sheet.template.name,
        department=sheet.target_department,
        details={'status': sheet.status, 'comment': comment},
    )
    return sheet


@transaction.atomic
def generate_budget_lines_from_sheet(sheet: DemandSheet, requester=None, force_rebuild=True):
    sheet = (
        DemandSheet.objects.select_for_update()
        .select_related('template', 'template__cycle', 'target_department', 'requested_by')
        .get(id=sheet.id)
    )
    if sheet.status not in {DemandSheet.Status.CONFIRMED, DemandSheet.Status.GENERATED}:
        raise ValidationError({'status': '生成预算前必须先确认专题需求表。'})
    normalize_demand_payload(
        sheet.payload,
        sheet.schema_snapshot or sheet.template.schema,
        user=None,
        enforce_all_required=True,
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
    sheet.generated_by = requester if requester and requester.is_authenticated else None
    sheet.generated_at = timezone.now()
    sheet.generated_payload_hash = hash_demand_payload(sheet.payload)
    sheet.save(
        update_fields=[
            'status',
            'generated_budget_book',
            'generated_budget_version',
            'generated_line_count',
            'generated_by',
            'generated_at',
            'generated_payload_hash',
            'updated_at',
        ]
    )
    create_audit_log(
        actor=requester,
        category='demand',
        action='demand_budget_generated',
        target_type='demand_sheet',
        target_id=sheet.id,
        target_label=sheet.template.name,
        department=sheet.target_department,
        book=book,
        version=draft,
        details={
            'generated_line_count': len(created_lines),
            'book_id': str(book.id),
            'version_id': str(draft.id),
            'generated_for_department': budget_department.code,
        },
    )
    return {
        'book': book,
        'version': draft,
        'sheet': sheet,
        'generated_line_count': len(created_lines),
    }
