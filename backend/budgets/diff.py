from decimal import Decimal

from .models import BudgetLine, BudgetVersion


TRACKED_FIELDS = [
    'description',
    'cost_center_code',
    'gl_amount_code',
    'unit_price',
    'total_quantity',
    'total_amount',
]


def compare_versions(base_version, target_version):
    if base_version.book_id != target_version.book_id:
        raise ValueError('只能比较同一预算表下的版本。')

    base_lines = _line_map(base_version)
    target_lines = _line_map(target_version)
    base_keys = set(base_lines)
    target_keys = set(target_lines)

    changes = []
    for key in sorted(target_keys - base_keys):
        changes.append(_line_change('added', key, None, target_lines[key]))
    for key in sorted(base_keys - target_keys):
        changes.append(_line_change('deleted', key, base_lines[key], None))
    for key in sorted(base_keys & target_keys):
        field_changes = _field_changes(base_lines[key], target_lines[key])
        monthly_changes = _monthly_changes(base_lines[key], target_lines[key])
        if field_changes or monthly_changes:
            changes.append(
                {
                    'type': 'modified',
                    'key': key,
                    'budget_no': target_lines[key].budget_no,
                    'line_id': str(target_lines[key].id),
                    'description': target_lines[key].description,
                    'field_changes': field_changes,
                    'monthly_changes': monthly_changes,
                }
            )

    return {
        'base_version_id': str(base_version.id),
        'target_version_id': str(target_version.id),
        'summary': {
            'added': sum(1 for change in changes if change['type'] == 'added'),
            'deleted': sum(1 for change in changes if change['type'] == 'deleted'),
            'modified': sum(1 for change in changes if change['type'] == 'modified'),
            'total_changes': len(changes),
        },
        'changes': changes,
    }


def _line_map(version):
    lines = BudgetLine.objects.filter(version=version).prefetch_related('monthly_plans')
    return {line.budget_no or str(line.id): line for line in lines}


def _line_change(change_type, key, base_line, target_line):
    line = target_line or base_line
    return {
        'type': change_type,
        'key': key,
        'budget_no': line.budget_no,
        'line_id': str(line.id),
        'description': line.description,
        'amount_delta': str(_decimal(target_line.total_amount if target_line else 0) - _decimal(base_line.total_amount if base_line else 0)),
        'field_changes': [],
        'monthly_changes': [],
    }


def _field_changes(base_line, target_line):
    changes = []
    for field in TRACKED_FIELDS:
        old_value = getattr(base_line, field)
        new_value = getattr(target_line, field)
        if old_value != new_value:
            changes.append(
                {
                    'field': field,
                    'old': _stringify(old_value),
                    'new': _stringify(new_value),
                    'delta': str(_decimal(new_value) - _decimal(old_value)) if _is_number_like(old_value, new_value) else '',
                }
            )
    return changes


def _monthly_changes(base_line, target_line):
    base_months = {plan.month: plan for plan in base_line.monthly_plans.all()}
    target_months = {plan.month: plan for plan in target_line.monthly_plans.all()}
    changes = []
    for month in sorted(set(base_months) | set(target_months)):
        base_plan = base_months.get(month)
        target_plan = target_months.get(month)
        old_quantity = base_plan.quantity if base_plan else Decimal('0')
        new_quantity = target_plan.quantity if target_plan else Decimal('0')
        old_amount = base_plan.amount if base_plan else Decimal('0')
        new_amount = target_plan.amount if target_plan else Decimal('0')
        if old_quantity != new_quantity or old_amount != new_amount:
            changes.append(
                {
                    'month': month,
                    'old_quantity': str(old_quantity),
                    'new_quantity': str(new_quantity),
                    'quantity_delta': str(new_quantity - old_quantity),
                    'old_amount': str(old_amount),
                    'new_amount': str(new_amount),
                    'amount_delta': str(new_amount - old_amount),
                }
            )
    return changes


def _is_number_like(*values):
    try:
        for value in values:
            Decimal(str(value))
    except Exception:
        return False
    return True


def _decimal(value):
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


def _stringify(value):
    if value is None:
        return ''
    return str(value)
