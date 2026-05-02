import csv
import io
from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework.exceptions import ValidationError

from audit.services import create_audit_log
from orgs.models import Department

from .models import AllocationUpload, BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion


def parse_group_allocation_text(raw_text: str) -> list[dict[str, str]]:
    lines = [line for line in (raw_text or '').splitlines() if line.strip()]
    if not lines:
        return []
    delimiter = '\t' if '\t' in lines[0] else ','
    reader = csv.reader(lines, delimiter=delimiter)
    rows = list(reader)
    header = [_normalize_header(item) for item in rows[0]]
    results = []
    for values in rows[1:]:
        padded = values + [''] * (len(header) - len(values))
        results.append({header[index]: padded[index].strip() for index in range(len(header))})
    return results


@transaction.atomic
def import_group_allocations(cycle, requester, *, source_name: str, raw_text: str):
    rows = parse_group_allocation_text(raw_text)
    upload = AllocationUpload.objects.create(
        cycle=cycle,
        requester=requester if requester and requester.is_authenticated else None,
        source_name=source_name,
        status=AllocationUpload.Status.SUCCESS,
    )
    upload.total_rows = len(rows)
    if not rows:
        upload.status = AllocationUpload.Status.FAILED
        upload.error_rows = 1
        upload.errors = [{'row': 0, 'errors': {'rows': '导入内容为空。'}}]
        upload.summary = {'message': '集团分摊导入失败。'}
        upload.save(update_fields=['status', 'total_rows', 'error_rows', 'errors', 'summary', 'updated_at'])
        return upload

    try:
        primary_department = Department.objects.filter(level=Department.Level.PRIMARY, code='SS').first()
        if not primary_department:
            raise ValidationError({'department': '未找到一级部门 SS。'})

        department_rows = _parse_allocation_rows(rows)
        template = _resolve_allocation_template(cycle)
        book, version = _reset_group_allocation_book(cycle, primary_department, template, requester=requester)
        _create_allocation_lines(version, department_rows)
        upload.imported_rows = len(department_rows)
        upload.error_rows = 0
        upload.summary = {
            'message': '集团分摊导入成功。',
            'book_id': str(book.id),
            'version_id': str(version.id),
            'departments': [row['department'].code for row in department_rows],
        }
        upload.save(update_fields=['total_rows', 'imported_rows', 'error_rows', 'summary', 'updated_at'])
        create_audit_log(
            actor=requester,
            category='import',
            action='group_allocation_imported',
            target_type='allocation_upload',
            target_id=upload.id,
            target_label=source_name,
            department=primary_department,
            book=book,
            version=version,
            details={
                'imported_rows': len(department_rows),
                'departments': [row['department'].code for row in department_rows],
            },
        )
        return upload
    except ValidationError as error:
        detail = error.detail
        errors = detail.get('rows') if isinstance(detail, dict) and 'rows' in detail else [{'row': 0, 'errors': detail}]
        upload.status = AllocationUpload.Status.FAILED
        upload.error_rows = len(errors)
        upload.errors = errors
        upload.summary = {'message': '集团分摊导入失败。'}
        upload.save(update_fields=['status', 'total_rows', 'error_rows', 'errors', 'summary', 'updated_at'])
        create_audit_log(
            actor=requester,
            category='import',
            action='group_allocation_import_failed',
            target_type='allocation_upload',
            target_id=upload.id,
            target_label=source_name,
            details={'error_rows': len(errors)},
        )
        return upload


def export_group_allocation_template() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['预算部门', '预算编号', '预算条目描述', '总金额', '备注'])
    writer.writerow(['Arch', 'ALLOC-ARCH-001', '集团云资源分摊', '120000.00', '示例'])
    return buffer.getvalue()


def _parse_allocation_rows(rows):
    parsed = []
    errors = []
    for row_no, row in enumerate(rows, start=2):
        department_value = _first_present_value(row, '预算部门', 'department')
        budget_no = _first_present_value(row, '预算编号', 'budget_no')
        description = _first_present_value(row, '预算条目描述', 'description')
        total_amount_raw = _first_present_value(row, '总金额', 'total_amount')
        comment = _first_present_value(row, '备注', 'comment', 'local_comment')

        row_errors = {}
        department = Department.objects.filter(level=Department.Level.SECONDARY).filter(code=department_value).first() or Department.objects.filter(level=Department.Level.SECONDARY).filter(name=department_value).first()
        if not department:
            row_errors['department'] = f'找不到二级部门: {department_value}'
        if not budget_no:
            row_errors['budget_no'] = '预算编号必填。'
        if not description:
            row_errors['description'] = '预算条目描述必填。'
        try:
            total_amount = _parse_decimal(total_amount_raw)
        except ValidationError as error:
            row_errors['total_amount'] = error.detail.get('number') if isinstance(error.detail, dict) else error.detail
            total_amount = Decimal('0.00')
        if total_amount <= Decimal('0.00'):
            row_errors['total_amount'] = '总金额必须大于 0。'

        if row_errors:
            errors.append({'row': row_no, 'errors': row_errors})
            continue

        parsed.append(
            {
                'department': department,
                'budget_no': budget_no,
                'description': description,
                'total_amount': total_amount,
                'comment': comment,
            }
        )

    if errors:
        raise ValidationError({'rows': errors})
    return parsed


def _resolve_allocation_template(cycle):
    from budget_templates.models import BudgetTemplate

    template = (
        BudgetTemplate.objects.filter(
            cycle=cycle,
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            status=BudgetTemplate.Status.ACTIVE,
        )
        .order_by('schema_version')
        .first()
    )
    if not template:
        raise ValidationError({'template': '当前周期没有可复用的预算模板。'})
    return template


def _reset_group_allocation_book(cycle, primary_department, template, *, requester=None):
    book, _ = BudgetBook.objects.get_or_create(
        cycle=cycle,
        department=primary_department,
        expense_type=BudgetBook.ExpenseType.OPEX,
        source_type=BudgetBook.SourceType.GROUP_ALLOCATION,
        defaults={'template': template, 'status': BudgetBook.Status.DRAFTING},
    )
    book.template = template
    if book.current_draft_id:
        book.current_draft.lines.all().delete()
        book.current_draft.delete()
    version = BudgetVersion.objects.create(
        book=book,
        version_no=0,
        status=BudgetVersion.Status.DRAFT,
        submitted_by=requester if requester and requester.is_authenticated else None,
        notes='集团分摊导入生成',
    )
    book.current_draft = version
    book.status = BudgetBook.Status.DRAFTING
    book.save(update_fields=['template', 'current_draft', 'status', 'updated_at'])
    return book, version


def _create_allocation_lines(version, department_rows):
    for index, item in enumerate(department_rows, start=1):
        line = BudgetLine.objects.create(
            version=version,
            line_no=index,
            budget_no=item['budget_no'],
            department=item['department'],
            description=item['description'],
            total_amount=item['total_amount'],
            total_quantity=Decimal('1.00'),
            unit_price=item['total_amount'],
            dynamic_data={},
            local_comments={'comment': item['comment']} if item['comment'] else {},
            admin_annotations={'allocation_owner': item['department'].code},
            source_ref_type='group_allocation',
            editable_by_secondary=False,
        )
        BudgetMonthlyPlan.objects.create(
            line=line,
            month=1,
            quantity=Decimal('1.00'),
            amount=item['total_amount'],
        )


def _normalize_header(value: str) -> str:
    return ' '.join((value or '').strip().lower().split())


def _first_present_value(row: dict[str, str], *aliases) -> str:
    normalized_aliases = {_normalize_header(alias) for alias in aliases}
    for key, value in row.items():
        if key in normalized_aliases:
            return value.strip()
    return ''


def _parse_decimal(value: str) -> Decimal:
    if value in ('', None):
        raise ValidationError({'number': '金额不能为空。'})
    cleaned = str(value).replace(',', '').strip()
    try:
        return Decimal(cleaned).quantize(Decimal('0.00'))
    except (InvalidOperation, ValueError) as error:
        raise ValidationError({'number': f'无法解析数值: {value}'}) from error
