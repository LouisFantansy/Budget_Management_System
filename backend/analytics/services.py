from decimal import Decimal

from django.db.models import Count, Sum

from budgets.models import BudgetBook, BudgetLine, BudgetMonthlyPlan


EMPTY_VALUE = '__none__'


def budget_overview(version_context='latest_approved', department_ids=None, expense_type=None):
    versions = _versions_for_context(
        version_context,
        department_ids=department_ids,
        expense_type=expense_type,
    )
    lines = _lines_queryset(versions)
    monthly_plans = BudgetMonthlyPlan.objects.filter(line__version_id__in=versions)

    totals = lines.aggregate(line_count=Count('id'), total_amount=Sum('total_amount'))
    return {
        'version_context': version_context,
        'expense_type': expense_type or '',
        'line_count': totals['line_count'] or 0,
        'total_amount': _string_amount(totals['total_amount']),
        'by_department': _aggregate_dimension(
            lines,
            'department_id',
            'department__name',
            'department_id',
            'department_name',
        ),
        'by_category': _aggregate_dimension(
            lines,
            'category_id',
            'category__name',
            'category_id',
            'category_name',
            default_name='未分类',
        ),
        'by_project': _aggregate_dimension(
            lines,
            'project_id',
            'project__name',
            'project_id',
            'project_name',
            default_name='未关联项目',
        ),
        'by_project_category': _aggregate_dimension(
            lines,
            'project_category_id',
            'project_category__name',
            'project_category_id',
            'project_category_name',
            default_name='未分类项目',
        ),
        'by_product_line': _aggregate_dimension(
            lines,
            'product_line_id',
            'product_line__name',
            'product_line_id',
            'product_line_name',
            default_name='未关联产品线',
        ),
        'by_expense_type': _aggregate_dimension(
            lines,
            'version__book__expense_type',
            'version__book__expense_type',
            'expense_type',
            'expense_type_label',
            label_map={
                BudgetBook.ExpenseType.OPEX: 'OPEX',
                BudgetBook.ExpenseType.CAPEX: 'CAPEX',
            },
        ),
        'monthly': [
            {
                'month': row['month'],
                'amount': _string_amount(row['amount']),
                'quantity': _string_amount(row['quantity']),
            }
            for row in monthly_plans.values('month')
            .annotate(amount=Sum('amount'), quantity=Sum('quantity'))
            .order_by('month')
        ],
    }


def budget_drilldown(
    *,
    version_context='latest_approved',
    department_ids=None,
    dimension='department',
    value='',
    expense_type=None,
    limit=200,
):
    versions = _versions_for_context(
        version_context,
        department_ids=department_ids,
        expense_type=expense_type,
    )
    lines = _lines_queryset(versions)
    filtered_lines = _apply_dimension_filter(lines, dimension=dimension, value=value)
    totals = filtered_lines.aggregate(line_count=Count('id'), total_amount=Sum('total_amount'))

    return {
        'version_context': version_context,
        'expense_type': expense_type or '',
        'dimension': dimension,
        'value': value,
        'line_count': totals['line_count'] or 0,
        'total_amount': _string_amount(totals['total_amount']),
        'rows': [_serialize_line(line) for line in filtered_lines[:limit]],
    }


def _versions_for_context(version_context, department_ids=None, expense_type=None):
    books = BudgetBook.objects.all()
    if department_ids is not None:
        books = books.filter(department_id__in=department_ids)
    if expense_type:
        books = books.filter(expense_type=expense_type)
    if version_context == 'current_draft':
        return list(books.exclude(current_draft=None).values_list('current_draft_id', flat=True))
    return list(books.exclude(latest_approved_version=None).values_list('latest_approved_version_id', flat=True))


def _lines_queryset(version_ids):
    return (
        BudgetLine.objects.filter(version_id__in=version_ids)
        .select_related(
            'department',
            'category',
            'project',
            'project_category',
            'product_line',
            'version',
            'version__book',
        )
        .prefetch_related('monthly_plans')
        .order_by('-total_amount', 'budget_no', 'line_no')
    )


def _aggregate_dimension(
    queryset,
    value_field,
    name_field,
    result_value_key,
    result_name_key,
    *,
    default_name='未配置',
    label_map=None,
):
    rows = (
        queryset.values(value_field, name_field)
        .annotate(line_count=Count('id'), total_amount=Sum('total_amount'))
        .order_by('-total_amount', name_field)
    )
    payload = []
    for row in rows:
        raw_value = row[value_field]
        raw_name = row[name_field]
        if label_map:
            name = label_map.get(raw_name, raw_name or default_name)
        else:
            name = raw_name or default_name
        payload.append(
            {
                result_value_key: '' if raw_value is None else str(raw_value),
                result_name_key: name,
                'line_count': row['line_count'],
                'total_amount': _string_amount(row['total_amount']),
            }
        )
    return payload


def _apply_dimension_filter(queryset, *, dimension, value):
    if dimension == 'department':
        return queryset.filter(department_id=value) if value else queryset.filter(department=None)
    if dimension == 'category':
        return _nullable_relation_filter(queryset, 'category_id', value)
    if dimension == 'project':
        return _nullable_relation_filter(queryset, 'project_id', value)
    if dimension == 'project_category':
        return _nullable_relation_filter(queryset, 'project_category_id', value)
    if dimension == 'product_line':
        return _nullable_relation_filter(queryset, 'product_line_id', value)
    if dimension == 'expense_type':
        return queryset.filter(version__book__expense_type=value)
    if dimension == 'month':
        try:
            month = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError('月份筛选无效。') from error
        return queryset.filter(monthly_plans__month=month).distinct()
    raise ValueError('不支持的下钻维度。')


def _nullable_relation_filter(queryset, field_name, value):
    if value in ('', EMPTY_VALUE):
        return queryset.filter(**{f'{field_name}__isnull': True})
    return queryset.filter(**{field_name: value})


def _serialize_line(line):
    return {
        'id': str(line.id),
        'budget_no': line.budget_no,
        'description': line.description,
        'department_name': line.department.name if line.department else '',
        'category_name': line.category.name if line.category else '未分类',
        'project_name': line.project.name if line.project else '未关联项目',
        'project_category_name': line.project_category.name if line.project_category else '未分类项目',
        'product_line_name': line.product_line.name if line.product_line else '未关联产品线',
        'expense_type': line.version.book.expense_type,
        'version_id': str(line.version_id),
        'version_label': _version_label(line.version),
        'total_amount': _string_amount(line.total_amount),
        'total_quantity': _string_amount(line.total_quantity),
        'month_count': line.monthly_plans.count(),
    }


def _version_label(version):
    if version.status == version.Status.DRAFT:
        return 'Draft'
    if version.status == version.Status.FINAL:
        return f'Final V{version.version_no}'
    return f'V{version.version_no}'


def _string_amount(value):
    return str(value or Decimal('0'))
