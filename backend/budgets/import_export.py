import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.db import models
from django.db import transaction
from rest_framework.exceptions import ValidationError

from budget_templates.models import TemplateField
from budget_templates.validation import collect_dynamic_data_errors, resolve_dynamic_data
from masterdata.models import Category, ProductLine, Project, ProjectCategory, Region, Vendor

from .models import BudgetLine, BudgetMonthlyPlan, BudgetVersion, ImportJob


STANDARD_FIELD_ALIASES = {
    'budget_no': {'budget_no', '预算编号'},
    'cost_center_code': {'cost_center_code', 'depart 成本中心代码', '成本中心代码'},
    'category': {'category'},
    'category_l1': {'category l1'},
    'category_l2': {'category l2'},
    'gl_amount_code': {'gl amount', 'gl_amount', 'gl amount code', 'gl_amount_code'},
    'project': {'project'},
    'project_category': {'project category', '项目类别'},
    'product_line': {'product line', '产品线'},
    'description': {'预算条目描述', 'description'},
    'vendor': {'供应商', 'vendor'},
    'reason': {'采购原因', 'reason'},
    'region': {'地区', 'region'},
    'unit_price': {'单价', 'unit_price'},
    'total_quantity': {'总数量', 'total_quantity'},
    'total_amount': {'总价', '总金额', 'total_amount'},
    'local_comment': {'备注', 'local_comment', 'comment'},
}


@dataclass
class ParsedImportRow:
    department_name: str
    budget_no: str
    cost_center_code: str
    category: Optional[Category]
    category_l1: Optional[Category]
    category_l2: Optional[Category]
    gl_amount_code: str
    project: Optional[Project]
    project_category: Optional[ProjectCategory]
    product_line: Optional[ProductLine]
    description: str
    vendor: Optional[Vendor]
    reason: str
    region: Optional[Region]
    unit_price: Decimal
    total_quantity: Decimal
    total_amount: Decimal
    local_comment: str
    dynamic_data: dict
    monthly_quantities: list[Decimal]
    monthly_amounts: list[Decimal]


def budget_version_import_header(version: BudgetVersion) -> list[str]:
    template_fields = list(version.book.template.fields.order_by('order', 'code'))
    header = [
        '预算编号',
        '预算部门',
        '成本中心代码',
        'category',
        'category L1',
        'category L2',
        'GL Amount',
        'Project',
        'Project Category',
        'Product Line',
        '预算条目描述',
        '供应商',
        '采购原因',
        '地区',
        '单价',
        '总数量',
        '总金额',
        '备注',
    ]
    header.extend([f'{month}月采购数量' for month in range(1, 13)])
    header.extend([f'{month}月采购金额' for month in range(1, 13)])
    header.extend([field.label for field in template_fields])
    return header


def export_budget_version_csv(version: BudgetVersion) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    template_fields = list(version.book.template.fields.order_by('order', 'code'))
    writer.writerow(budget_version_import_header(version))

    for line in version.lines.select_related(
        'category',
        'category_l1',
        'category_l2',
        'project',
        'project_category',
        'product_line',
        'vendor',
        'region',
    ).prefetch_related('monthly_plans').all():
        monthly_map = {plan.month: plan for plan in line.monthly_plans.all()}
        row = [
            line.budget_no,
            line.department.name if line.department_id else version.book.department.name,
            line.cost_center_code,
            line.category.name if line.category else '',
            line.category_l1.name if line.category_l1 else '',
            line.category_l2.name if line.category_l2 else '',
            line.gl_amount_code,
            line.project.name if line.project else '',
            line.project_category.name if line.project_category else '',
            line.product_line.name if line.product_line else '',
            line.description,
            line.vendor.name if line.vendor else '',
            line.reason,
            line.region.name if line.region else '',
            str(line.unit_price),
            str(line.total_quantity),
            str(line.total_amount),
            str((line.local_comments or {}).get('comment', '')),
        ]
        row.extend([str(monthly_map.get(month).quantity if month in monthly_map else Decimal('0.00')) for month in range(1, 13)])
        row.extend([str(monthly_map.get(month).amount if month in monthly_map else Decimal('0.00')) for month in range(1, 13)])
        row.extend([stringify_dynamic_value(line.dynamic_data.get(field.code)) for field in template_fields])
        writer.writerow(row)
    return buffer.getvalue()


def export_budget_version_import_template_csv(version: BudgetVersion) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(budget_version_import_header(version))
    return buffer.getvalue()


def export_budget_version_import_sample_csv(version: BudgetVersion) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    template_fields = list(version.book.template.fields.order_by('order', 'code'))
    sample_dynamic_data = _sample_dynamic_payload(template_fields)
    sample_dynamic_data, formula_errors = resolve_dynamic_data(
        version.book.template,
        sample_dynamic_data,
        formula_context={
            'unit_price': '100.00',
            'total_quantity': '1.00',
            'total_amount': '100.00',
            'monthly_quantities': ['1.00'] + ['0.00'] * 11,
            'monthly_amounts': ['100.00'] + ['0.00'] * 11,
        },
    )
    if formula_errors:
        raise ValidationError({'dynamic_data': formula_errors})
    writer.writerow(budget_version_import_header(version))
    row = [
        'SAMPLE-001',
        version.book.department.name,
        'CC1001',
        '',
        '',
        '',
        'GL100',
        '',
        '',
        '',
        '示例预算条目',
        '',
        '示例采购原因',
        '',
        '100.00',
        '1.00',
        '100.00',
        '示例备注',
    ]
    row.extend(['1.00'] + ['0.00'] * 11)
    row.extend(['100.00'] + ['0.00'] * 11)
    row.extend([stringify_dynamic_value(sample_dynamic_data.get(field.code, '')) for field in template_fields])
    writer.writerow(row)
    return buffer.getvalue()


@transaction.atomic
def import_budget_lines(version: BudgetVersion, requester, *, source_name: str, raw_text: str, mode: str = ImportJob.Mode.APPEND):
    version = BudgetVersion.objects.select_for_update().select_related('book', 'book__template', 'book__department').get(id=version.id)
    if version.status != BudgetVersion.Status.DRAFT:
        raise ValidationError({'version': '只能向 Draft 版本导入预算条目。'})

    import_job = ImportJob.objects.create(
        version=version,
        requester=requester if requester and requester.is_authenticated else None,
        source_name=source_name,
        mode=mode,
        status=ImportJob.Status.PROCESSING,
    )

    try:
        rows = parse_import_text(raw_text)
        import_job.total_rows = len(rows)
        if not rows:
            raise ValidationError({'rows': '导入内容为空。'})

        parsed_rows, errors = _parse_rows(version, rows)
        if errors:
            import_job.status = ImportJob.Status.FAILED
            import_job.error_rows = len(errors)
            import_job.errors = errors
            import_job.summary = {'message': '导入失败，请修正错误后重试。'}
            import_job.save(update_fields=['status', 'total_rows', 'error_rows', 'errors', 'summary', 'updated_at'])
            return import_job

        imported_count = _apply_import(version, parsed_rows, mode=mode)
        import_job.status = ImportJob.Status.SUCCESS
        import_job.imported_rows = imported_count
        import_job.error_rows = 0
        import_job.summary = {
            'message': '导入成功。',
            'mode': mode,
            'imported_budget_nos': [row.budget_no for row in parsed_rows],
        }
        import_job.save(
            update_fields=[
                'status',
                'total_rows',
                'imported_rows',
                'error_rows',
                'summary',
                'updated_at',
            ]
        )
        return import_job
    except ValidationError as error:
        import_job.status = ImportJob.Status.FAILED
        import_job.summary = {'message': '导入失败。'}
        import_job.errors = [{'row': 0, 'errors': error.detail}]
        import_job.error_rows = 1
        import_job.save(update_fields=['status', 'summary', 'errors', 'error_rows', 'updated_at'])
        return import_job


def parse_import_text(raw_text: str) -> list[dict[str, str]]:
    lines = [line for line in (raw_text or '').splitlines() if line.strip()]
    if not lines:
        return []
    delimiter = '\t' if '\t' in lines[0] else ','
    reader = csv.reader(lines, delimiter=delimiter)
    rows = list(reader)
    header = [normalize_header(item) for item in rows[0]]
    results = []
    for values in rows[1:]:
        padded = values + [''] * (len(header) - len(values))
        results.append({header[index]: padded[index].strip() for index in range(len(header))})
    return results


def normalize_header(value: str) -> str:
    return ' '.join((value or '').strip().lower().split())


def stringify_dynamic_value(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def _sample_dynamic_value(field):
    if field.input_type == field.InputType.FORMULA:
        return ''
    if field.data_type == field.DataType.BOOLEAN:
        return 'false'
    if field.data_type in {field.DataType.NUMBER, field.DataType.MONEY}:
        return '0.00'
    if field.data_type == field.DataType.DATE:
        return '2029-01-01'
    if field.data_type == field.DataType.JSON:
        return '{}'
    if field.data_type == field.DataType.OPTION:
        return '示例选项'
    return '示例值'


def _parse_rows(version: BudgetVersion, rows: list[dict[str, str]]):
    template_fields = list(version.book.template.fields.order_by('order', 'code'))
    parsed_rows: list[ParsedImportRow] = []
    errors = []

    for row_no, row in enumerate(rows, start=2):
        try:
            parsed = _parse_single_row(version, row, template_fields)
            parsed_rows.append(parsed)
        except ValidationError as error:
            errors.append({'row': row_no, 'errors': error.detail})
    return parsed_rows, errors


def _parse_single_row(version: BudgetVersion, row: dict[str, str], template_fields):
    raw = lambda *aliases: first_present_value(row, aliases)
    dynamic_data = {}
    errors = {}
    monthly_quantities = []
    monthly_amounts = []

    for month in range(1, 13):
        quantity, quantity_error = _parse_decimal_field(
            raw(f'{month}月采购数量', f'{month} month qty', f'month {month} quantity'),
            f'{month}月采购数量',
        )
        amount, amount_error = _parse_decimal_field(
            raw(f'{month}月采购金额', f'{month} month amount', f'month {month} amount'),
            f'{month}月采购金额',
        )
        monthly_quantities.append(quantity)
        monthly_amounts.append(amount)
        if quantity_error:
            errors[f'month_{month}_quantity'] = quantity_error
        if amount_error:
            errors[f'month_{month}_amount'] = amount_error

    for field in template_fields:
        if field.input_type == TemplateField.InputType.FORMULA:
            continue
        aliases = {normalize_header(field.label), normalize_header(field.code)}
        aliases.update({normalize_header(alias) for alias in field.import_aliases})
        value = first_present_value(row, aliases)
        if value == '':
            continue
        try:
            normalized_value = _normalize_dynamic_value(field, value)
            dynamic_data[field.code] = normalized_value
        except ValidationError as error:
            errors.setdefault('dynamic_data', {})[field.code] = error.detail

    unit_price, unit_price_error = _parse_decimal_field(raw('单价', 'unit_price'), '单价')
    total_quantity, total_quantity_error = _parse_decimal_field(raw('总数量', 'total_quantity'), '总数量')
    total_amount, total_amount_error = _parse_decimal_field(raw('总价', '总金额', 'total_amount'), '总金额')
    if unit_price_error:
        errors['unit_price'] = unit_price_error
    if total_quantity_error:
        errors['total_quantity'] = total_quantity_error
    if total_amount_error:
        errors['total_amount'] = total_amount_error

    category, category_error = _lookup_named_object(Category, raw('category'), 'category')
    category_l1, category_l1_error = _lookup_named_object(Category, raw('category l1'), 'category_l1')
    category_l2, category_l2_error = _lookup_named_object(Category, raw('category l2'), 'category_l2')
    project, project_error = _lookup_named_object(Project, raw('project'), 'project')
    project_category, project_category_error = _lookup_named_object(
        ProjectCategory,
        raw('project category', '项目类别'),
        'project_category',
    )
    product_line, product_line_error = _lookup_named_object(
        ProductLine,
        raw('product line', '产品线'),
        'product_line',
    )
    vendor, vendor_error = _lookup_named_object(Vendor, raw('供应商', 'vendor'), 'vendor')
    region, region_error = _lookup_named_object(Region, raw('地区', 'region'), 'region')
    for field_name, field_error in (
        ('category', category_error),
        ('category_l1', category_l1_error),
        ('category_l2', category_l2_error),
        ('project', project_error),
        ('project_category', project_category_error),
        ('product_line', product_line_error),
        ('vendor', vendor_error),
        ('region', region_error),
    ):
        if field_error:
            errors[field_name] = field_error

    formula_context = {
        'unit_price': unit_price,
        'total_quantity': total_quantity,
        'total_amount': total_amount,
        'monthly_quantities': [str(item) for item in monthly_quantities],
        'monthly_amounts': [str(item) for item in monthly_amounts],
    }
    dynamic_data, formula_errors = resolve_dynamic_data(
        version.book.template,
        dynamic_data,
        formula_context=formula_context,
    )
    dynamic_errors = collect_dynamic_data_errors(version.book.template, dynamic_data)
    if dynamic_errors:
        errors.setdefault('dynamic_data', {}).update(dynamic_errors)
    if formula_errors:
        errors.setdefault('dynamic_data', {}).update(formula_errors)

    parsed = ParsedImportRow(
        department_name=raw('预算部门', 'department'),
        budget_no=raw('预算编号', 'budget no', 'budget_no'),
        cost_center_code=raw('成本中心代码', 'depart 成本中心代码', 'cost_center_code'),
        category=category,
        category_l1=category_l1,
        category_l2=category_l2,
        gl_amount_code=raw('gl amount', 'gl amount code', 'gl_amount_code'),
        project=project,
        project_category=project_category,
        product_line=product_line,
        description=raw('预算条目描述', 'description'),
        vendor=vendor,
        reason=raw('采购原因', 'reason'),
        region=region,
        unit_price=unit_price,
        total_quantity=total_quantity,
        total_amount=total_amount,
        local_comment=raw('备注', 'comment', 'local_comment'),
        dynamic_data=dynamic_data,
        monthly_quantities=monthly_quantities,
        monthly_amounts=monthly_amounts,
    )

    if not parsed.description:
        errors['description'] = '预算条目描述必填。'
    if not parsed.budget_no:
        errors['budget_no'] = '预算编号必填。'
    if parsed.department_name and parsed.department_name not in {version.book.department.name, version.book.department.code}:
        errors['department'] = '预算部门与当前版本所属部门不一致。'

    calculated_total_quantity = sum(monthly_quantities, Decimal('0.00'))
    calculated_total_amount = sum(monthly_amounts, Decimal('0.00'))
    if calculated_total_quantity != parsed.total_quantity:
        errors['total_quantity'] = '总数量必须等于 1-12 月采购数量之和。'
    if calculated_total_amount != parsed.total_amount:
        errors['total_amount'] = '总金额必须等于 1-12 月采购金额之和。'
    if parsed.total_quantity and parsed.unit_price * parsed.total_quantity != parsed.total_amount:
        errors['unit_price'] = '单价 * 总数量 必须等于总金额。'
    if dynamic_errors:
        errors['dynamic_data'] = dynamic_errors
    if errors:
        raise ValidationError(errors)
    return parsed


def _apply_import(version: BudgetVersion, parsed_rows: list[ParsedImportRow], *, mode: str):
    if mode == ImportJob.Mode.REPLACE:
        version.lines.all().delete()

    existing_by_budget_no = {
        line.budget_no: line
        for line in version.lines.all()
    }
    next_line_no = (version.lines.aggregate(max_line_no=models.Max('line_no')).get('max_line_no') or 0) + 1
    imported_count = 0
    for parsed in parsed_rows:
        line = existing_by_budget_no.get(parsed.budget_no)
        if line is None:
            line = BudgetLine(version=version, department=version.book.department, line_no=next_line_no)
            next_line_no += 1
        line.budget_no = parsed.budget_no
        line.cost_center_code = parsed.cost_center_code
        line.category = parsed.category
        line.category_l1 = parsed.category_l1
        line.category_l2 = parsed.category_l2
        line.gl_amount_code = parsed.gl_amount_code
        line.project = parsed.project
        line.project_category = parsed.project_category
        line.product_line = parsed.product_line
        line.description = parsed.description
        line.vendor = parsed.vendor
        line.reason = parsed.reason
        line.region = parsed.region
        line.unit_price = parsed.unit_price
        line.total_quantity = parsed.total_quantity
        line.total_amount = parsed.total_amount
        line.dynamic_data = parsed.dynamic_data
        line.local_comments = {'comment': parsed.local_comment} if parsed.local_comment else {}
        line.save()
        line.monthly_plans.all().delete()
        BudgetMonthlyPlan.objects.bulk_create(
            [
                BudgetMonthlyPlan(
                    line=line,
                    month=month,
                    quantity=parsed.monthly_quantities[month - 1],
                    amount=parsed.monthly_amounts[month - 1],
                )
                for month in range(1, 13)
            ]
        )
        imported_count += 1
    return imported_count


def first_present_value(row: dict[str, str], aliases) -> str:
    normalized_aliases = {normalize_header(alias) for alias in aliases}
    for key, value in row.items():
        if key in normalized_aliases:
            return value.strip()
    return ''


def _parse_decimal(value: str) -> Decimal:
    if value in ('', None):
        return Decimal('0.00')
    cleaned = str(value).replace(',', '').strip()
    try:
        return Decimal(cleaned).quantize(Decimal('0.00'))
    except (InvalidOperation, ValueError) as error:
        raise ValidationError({'number': f'无法解析数值: {value}'}) from error


def _parse_decimal_field(value: str, field_name: str):
    try:
        return _parse_decimal(value), ''
    except ValidationError:
        return Decimal('0.00'), f'{field_name} 不是合法数字。'


def _lookup_named_object(model, value: str, field_name: str):
    if not value:
        return None, ''
    candidate = model.objects.filter(name=value).first() or model.objects.filter(code=value).first()
    if not candidate:
        return None, f'{field_name} 找不到主数据: {value}'
    return candidate, ''


def _normalize_dynamic_value(field, value: str):
    if field.data_type == field.DataType.BOOLEAN:
        return value.strip().lower() in {'true', '1', 'yes', 'y', '是'}
    if field.data_type in {field.DataType.NUMBER, field.DataType.MONEY}:
        decimal_value, field_error = _parse_decimal_field(value, field.label)
        if field_error:
            raise ValidationError(field_error)
        return str(decimal_value)
    return value.strip()


def _sample_dynamic_payload(template_fields):
    payload = {}
    for field in template_fields:
        sample = _sample_dynamic_value(field)
        if sample != '':
            payload[field.code] = sample
    return payload
