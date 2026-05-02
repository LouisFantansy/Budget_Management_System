from .models import BudgetLine


def budget_line_lineage(line: BudgetLine):
    lineage = {
        'line_id': str(line.id),
        'source': {
            'type': line.source_ref_type,
            'ref_id': str(line.source_ref_id) if line.source_ref_id else None,
            'department_code': (line.admin_annotations or {}).get('source_department'),
            'book_id': (line.admin_annotations or {}).get('source_book_id'),
            'version_id': (line.admin_annotations or {}).get('source_version_id'),
            'sheet_id': (line.admin_annotations or {}).get('source_sheet_id'),
            'template_id': (line.admin_annotations or {}).get('source_template_id'),
            'allocation_owner': (line.admin_annotations or {}).get('allocation_owner'),
            'generated_for_department': (line.admin_annotations or {}).get('generated_for_department'),
            'row_index': (line.admin_annotations or {}).get('row_index'),
        },
        'upstreams': [],
        'downstreams': [],
    }

    if line.source_ref_type == 'budget_version' and line.source_ref_id:
        lineage['upstreams'].append(
            {
                'kind': 'budget_version',
                'version_id': str(line.source_ref_id),
                'department_code': (line.admin_annotations or {}).get('source_department'),
            }
        )
    if line.source_ref_type == 'demand_sheet' and line.source_ref_id:
        lineage['upstreams'].append(
            {
                'kind': 'demand_sheet',
                'sheet_id': str(line.source_ref_id),
                'department_code': (line.admin_annotations or {}).get('source_department'),
            }
        )
    if line.source_ref_type == 'group_allocation':
        lineage['upstreams'].append(
            {
                'kind': 'group_allocation',
                'department_code': (line.admin_annotations or {}).get('allocation_owner'),
            }
        )

    downstream_lines = BudgetLine.objects.filter(source_ref_id=line.version_id).exclude(id=line.id)
    for downstream in downstream_lines:
        lineage['downstreams'].append(
            {
                'line_id': str(downstream.id),
                'version_id': str(downstream.version_id),
                'budget_no': downstream.budget_no,
                'description': downstream.description,
                'source_ref_type': downstream.source_ref_type,
                'department_code': (downstream.admin_annotations or {}).get('source_department'),
                'book_id': (downstream.admin_annotations or {}).get('source_book_id'),
            }
        )

    return lineage
