from decimal import Decimal

from .diff import TRACKED_FIELDS, compare_versions
from .models import BudgetVersion


FIELD_LABELS = {
    'description': '条目描述',
    'cost_center_code': '成本中心',
    'gl_amount_code': 'GL 科目',
    'unit_price': '单价',
    'total_quantity': '数量',
    'total_amount': '金额',
}


def build_version_analysis(book):
    versions = list(
        book.versions.select_related('base_version')
        .prefetch_related('lines__monthly_plans')
        .all()
    )
    children = {}
    for version in versions:
        if version.base_version_id:
            children.setdefault(str(version.base_version_id), []).append(version)

    ordered_versions = []
    depths = {}

    def walk(version, depth):
        version_id = str(version.id)
        depths[version_id] = depth
        ordered_versions.append(version)
        for child in sorted(children.get(version_id, []), key=_version_sort_key):
            walk(child, depth + 1)

    root_versions = sorted([version for version in versions if not version.base_version_id], key=_version_sort_key)
    for root_version in root_versions:
        walk(root_version, 0)

    # Defensive fallback in case of unexpected orphaned relationships.
    for version in sorted(versions, key=_version_sort_key):
        version_id = str(version.id)
        if version_id not in depths:
            walk(version, 0)

    diff_payloads = {}
    for version in ordered_versions:
        if not version.base_version_id:
            continue
        diff_payloads[str(version.id)] = compare_versions(version.base_version, version)

    default_focus = _default_focus_version(book, ordered_versions)
    default_focus_diff = diff_payloads.get(str(default_focus.id)) if default_focus else None

    version_payloads = []
    for version in ordered_versions:
        version_id = str(version.id)
        summary = diff_payloads.get(version_id, {}).get('summary')
        version_payloads.append(
            {
                'id': version_id,
                'label': _version_label(version),
                'status': version.status,
                'status_label': version.get_status_display(),
                'version_no': version.version_no,
                'base_version_id': str(version.base_version_id) if version.base_version_id else None,
                'base_version_label': _version_label(version.base_version) if version.base_version_id else None,
                'depth': depths.get(version_id, 0),
                'created_at': version.created_at.isoformat(),
                'submitted_at': version.submitted_at.isoformat() if version.submitted_at else None,
                'approved_at': version.approved_at.isoformat() if version.approved_at else None,
                'notes': version.notes,
                'line_count': version.lines.count(),
                'total_amount': _version_total_amount(version),
                'is_current_draft': book.current_draft_id == version.id,
                'is_latest_approved': book.latest_approved_version_id == version.id,
                'child_count': len(children.get(version_id, [])),
                'change_summary': summary,
                'change_amount_delta': _diff_amount_delta(diff_payloads.get(version_id)) if summary else '0.00',
            }
        )

    return {
        'book': {
            'id': str(book.id),
            'cycle_id': str(book.cycle_id),
            'cycle_name': book.cycle.name,
            'department_id': str(book.department_id),
            'department_name': book.department.name,
            'expense_type': book.expense_type,
            'expense_type_label': book.get_expense_type_display(),
            'source_type': book.source_type,
            'source_type_label': book.get_source_type_display(),
            'status': book.status,
            'status_label': book.get_status_display(),
            'template_id': str(book.template_id),
            'template_name': book.template.name,
            'current_draft_id': str(book.current_draft_id) if book.current_draft_id else None,
            'latest_approved_version_id': str(book.latest_approved_version_id) if book.latest_approved_version_id else None,
        },
        'stats': {
            'total_versions': len(ordered_versions),
            'revision_rounds': sum(1 for version in ordered_versions if version.base_version_id),
            'approved_versions': sum(1 for version in ordered_versions if version.status == BudgetVersion.Status.APPROVED),
            'draft_versions': sum(1 for version in ordered_versions if version.status == BudgetVersion.Status.DRAFT),
            'submitted_versions': sum(1 for version in ordered_versions if version.status == BudgetVersion.Status.SUBMITTED),
            'rejected_versions': sum(1 for version in ordered_versions if version.status == BudgetVersion.Status.REJECTED),
            'final_versions': sum(1 for version in ordered_versions if version.status == BudgetVersion.Status.FINAL),
            'branch_roots': len(root_versions),
            'branch_heads': sum(
                1
                for version in ordered_versions
                if not children.get(str(version.id))
            ),
            'max_depth': (max(depths.values()) + 1) if depths else 0,
            'iteration_span_days': _iteration_span_days(ordered_versions),
            'focus_change_count': default_focus_diff['summary']['total_changes'] if default_focus_diff else 0,
            'focus_amount_delta': _diff_amount_delta(default_focus_diff),
        },
        'versions': version_payloads,
        'heatmap': _build_heatmap(ordered_versions, diff_payloads),
        'default_focus_version_id': str(default_focus.id) if default_focus else None,
        'default_base_version_id': str(default_focus.base_version_id) if default_focus and default_focus.base_version_id else None,
    }


def _build_heatmap(versions, diff_payloads):
    columns = []
    row_buckets = {
        'added_lines': {'label': '新增条目', 'scope': 'summary', 'cells': []},
        'deleted_lines': {'label': '删除条目', 'scope': 'summary', 'cells': []},
    }
    for field in TRACKED_FIELDS:
        row_buckets[field] = {'label': FIELD_LABELS.get(field, field), 'scope': 'field', 'cells': []}
    for month in range(1, 13):
        row_buckets[f'month_{month}'] = {'label': f'{month}月', 'scope': 'month', 'cells': []}

    for version in versions:
        if not version.base_version_id:
            continue
        version_id = str(version.id)
        diff_payload = diff_payloads[version_id]
        columns.append(
            {
                'version_id': version_id,
                'label': _version_label(version),
                'status': version.status,
                'status_label': version.get_status_display(),
                'base_version_id': str(version.base_version_id),
                'base_version_label': _version_label(version.base_version),
                'total_changes': diff_payload['summary']['total_changes'],
                'amount_delta': _diff_amount_delta(diff_payload),
            }
        )

        counts = {key: 0 for key in row_buckets}
        amount_deltas = {key: Decimal('0') for key in row_buckets}
        for change in diff_payload['changes']:
            if change['type'] == 'added':
                counts['added_lines'] += 1
                amount_deltas['added_lines'] += Decimal(change.get('amount_delta') or '0')
                continue
            if change['type'] == 'deleted':
                counts['deleted_lines'] += 1
                amount_deltas['deleted_lines'] += Decimal(change.get('amount_delta') or '0')
                continue

            for field_change in change['field_changes']:
                row_key = field_change['field']
                if row_key not in counts:
                    continue
                counts[row_key] += 1
                if field_change['delta']:
                    amount_deltas[row_key] += Decimal(field_change['delta'])

            for monthly_change in change['monthly_changes']:
                row_key = f"month_{monthly_change['month']}"
                counts[row_key] += 1
                amount_deltas[row_key] += Decimal(monthly_change['amount_delta'])

        for row_key, bucket in row_buckets.items():
            bucket['cells'].append(
                {
                    'version_id': version_id,
                    'count': counts[row_key],
                    'amount_delta': _format_decimal(amount_deltas[row_key]),
                }
            )

    if not columns:
        return {'columns': [], 'rows': []}

    rows = []
    for row_key, bucket in row_buckets.items():
        total = sum(cell['count'] for cell in bucket['cells'])
        if total == 0:
            continue
        rows.append(
            {
                'key': row_key,
                'label': bucket['label'],
                'scope': bucket['scope'],
                'total': total,
                'cells': bucket['cells'],
            }
        )

    return {'columns': columns, 'rows': rows}


def _default_focus_version(book, ordered_versions):
    if book.current_draft_id:
        return next((version for version in ordered_versions if version.id == book.current_draft_id), None)
    if book.latest_approved_version_id and book.latest_approved_version and book.latest_approved_version.base_version_id:
        return next((version for version in ordered_versions if version.id == book.latest_approved_version_id), None)
    comparable_versions = [version for version in ordered_versions if version.base_version_id]
    if comparable_versions:
        return comparable_versions[-1]
    return None


def _diff_amount_delta(diff_payload):
    if not diff_payload:
        return '0.00'

    total = Decimal('0')
    for change in diff_payload['changes']:
        if change['type'] in {'added', 'deleted'}:
            total += Decimal(change.get('amount_delta') or '0')
            continue
        for field_change in change['field_changes']:
            if field_change['field'] == 'total_amount' and field_change['delta']:
                total += Decimal(field_change['delta'])
    return _format_decimal(total)


def _format_decimal(value):
    return f'{Decimal(value):.2f}'


def _iteration_span_days(versions):
    if not versions:
        return 0
    start = min(version.created_at for version in versions)
    end = max(version.updated_at for version in versions)
    return max((end - start).days, 0)


def _version_total_amount(version):
    total = sum((line.total_amount for line in version.lines.all()), Decimal('0'))
    return _format_decimal(total)


def _version_label(version):
    if version is None:
        return ''
    if version.status in {BudgetVersion.Status.APPROVED, BudgetVersion.Status.FINAL} and version.version_no:
        return f'V{version.version_no}'
    if version.status == BudgetVersion.Status.SUBMITTED:
        return 'Submitted Draft'
    if version.status == BudgetVersion.Status.REJECTED:
        return 'Rejected Draft'
    return 'Draft'


def _version_sort_key(version):
    return (version.created_at, version.version_no, str(version.id))
