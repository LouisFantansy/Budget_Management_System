from decimal import Decimal

from django.db.models import Count, Sum

from budgets.models import BudgetBook, BudgetLine, BudgetMonthlyPlan


def budget_overview(version_context='latest_approved', department_ids=None):
    versions = _versions_for_context(version_context, department_ids=department_ids)
    lines = BudgetLine.objects.filter(version_id__in=versions).select_related('department', 'category')
    monthly_plans = BudgetMonthlyPlan.objects.filter(line__version_id__in=versions)

    totals = lines.aggregate(line_count=Count('id'), total_amount=Sum('total_amount'))
    return {
        'version_context': version_context,
        'line_count': totals['line_count'] or 0,
        'total_amount': str(totals['total_amount'] or Decimal('0')),
        'by_department': [
            {
                'department_id': str(row['department_id']),
                'department_name': row['department__name'],
                'line_count': row['line_count'],
                'total_amount': str(row['total_amount'] or Decimal('0')),
            }
            for row in lines.values('department_id', 'department__name')
            .annotate(line_count=Count('id'), total_amount=Sum('total_amount'))
            .order_by('-total_amount', 'department__name')
        ],
        'by_category': [
            {
                'category_id': str(row['category_id']) if row['category_id'] else '',
                'category_name': row['category__name'] or '未分类',
                'line_count': row['line_count'],
                'total_amount': str(row['total_amount'] or Decimal('0')),
            }
            for row in lines.values('category_id', 'category__name')
            .annotate(line_count=Count('id'), total_amount=Sum('total_amount'))
            .order_by('-total_amount', 'category__name')
        ],
        'monthly': [
            {
                'month': row['month'],
                'amount': str(row['amount'] or Decimal('0')),
                'quantity': str(row['quantity'] or Decimal('0')),
            }
            for row in monthly_plans.values('month')
            .annotate(amount=Sum('amount'), quantity=Sum('quantity'))
            .order_by('month')
        ],
    }


def _versions_for_context(version_context, department_ids=None):
    books = BudgetBook.objects.all()
    if department_ids is not None:
        books = books.filter(department_id__in=department_ids)
    if version_context == 'current_draft':
        return list(books.exclude(current_draft=None).values_list('current_draft_id', flat=True))
    return list(books.exclude(latest_approved_version=None).values_list('latest_approved_version_id', flat=True))
