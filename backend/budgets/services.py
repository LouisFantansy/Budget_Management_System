from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.access import is_global_budget_user
from approvals.models import ApprovalRequest, ApprovalStep
from audit.services import create_audit_log
from budget_templates.validation import collect_dynamic_data_errors
from notifications.models import Notification
from notifications.services import create_notification, create_notifications
from orgs.models import Department

from .approval_flow import (
    build_dashboard_context,
    build_step_notification,
    is_primary_consolidated_book,
    request_title_for_version,
    resolve_approval_nodes,
    source_department_ids_for_primary_version,
)
from .models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion


@transaction.atomic
def submit_budget_version(version, requester, approver_ids=None, comment=''):
    version = BudgetVersion.objects.select_for_update().select_related('book', 'book__department').get(id=version.id)
    book = BudgetBook.objects.select_for_update().get(id=version.book_id)

    if version.status != BudgetVersion.Status.DRAFT:
        raise ValidationError({'status': '只有 Draft 版本可以送审。'})
    if book.current_draft_id and book.current_draft_id != version.id:
        raise ValidationError({'current_draft': '预算表已有其他当前 Draft。'})
    _validate_version_before_submit(version, user=requester)

    approval_nodes = resolve_approval_nodes(version, approver_ids=approver_ids)

    now = timezone.now()
    version.status = BudgetVersion.Status.SUBMITTED
    version.submitted_by = requester
    version.submitted_at = now
    if comment:
        version.notes = comment
    version.save(update_fields=['status', 'submitted_by', 'submitted_at', 'notes', 'updated_at'])

    book.status = BudgetBook.Status.REVIEWING
    book.current_draft = version
    book.save(update_fields=['status', 'current_draft', 'updated_at'])

    approval_request = ApprovalRequest.objects.create(
        target_type='budget_version',
        target_id=version.id,
        title=request_title_for_version(version),
        requester=requester,
        department=book.department,
        current_node=approval_nodes[0][0],
        submitted_version_label='Draft',
        dashboard_context=build_dashboard_context(version, node=approval_nodes[0][0]),
    )
    ApprovalStep.objects.bulk_create(
        [
            ApprovalStep(request=approval_request, node=node, approver=approver)
            for node, approvers in approval_nodes
            for approver in approvers
        ]
    )
    first_node, first_approvers = approval_nodes[0]
    create_notifications(
        first_approvers,
        **build_step_notification(version, requester, first_node, approval_request),
    )
    _notify_budget_anomalies(version, requester=requester)
    create_audit_log(
        actor=requester,
        category='budget',
        action='version_submitted',
        target_type='budget_version',
        target_id=version.id,
        target_label=request_title_for_version(version),
        department=book.department,
        book=book,
        version=version,
        details={
            'approval_request_id': str(approval_request.id),
            'approver_count': sum(len(approvers) for _, approvers in approval_nodes),
            'comment': comment,
        },
    )
    _mark_budget_tasks_on_submit(version)
    return approval_request


def _validate_version_before_submit(version, user=None):
    template = version.book.template
    line_errors = {}
    for line in version.lines.all():
        dynamic_errors = collect_dynamic_data_errors(template, line.dynamic_data, user=user)
        if dynamic_errors:
            line_errors[str(line.id)] = {
                'budget_no': line.budget_no,
                'description': line.description,
                'dynamic_data': dynamic_errors,
            }
    if line_errors:
        raise ValidationError({'lines': line_errors, 'detail': '当前 Draft 存在未完成字段，不能送审。'})


@transaction.atomic
def create_revision_draft(book, requester=None, base_version=None):
    book = BudgetBook.objects.select_for_update().get(id=book.id)
    if book.current_draft_id:
        raise ValidationError({'current_draft': '预算表已有当前 Draft，不能重复创建修订。'})

    base_version = base_version or book.latest_approved_version
    if not base_version:
        raise ValidationError({'base_version': '没有可用于修订的 Approved 版本。'})
    if base_version.book_id != book.id or base_version.status not in [BudgetVersion.Status.APPROVED, BudgetVersion.Status.FINAL]:
        raise ValidationError({'base_version': '只能基于本预算表的 Approved / Final 版本创建修订。'})

    draft = BudgetVersion.objects.create(
        book=book,
        version_no=0,
        base_version=base_version,
        status=BudgetVersion.Status.DRAFT,
        submitted_by=requester if requester and requester.is_authenticated else None,
        notes=f'基于 V{base_version.version_no} 创建修订 Draft',
    )

    line_id_map = {}
    for source_line in base_version.lines.prefetch_related('monthly_plans').all():
        copied_line = BudgetLine.objects.create(
            version=draft,
            line_no=source_line.line_no,
            budget_no=source_line.budget_no,
            department=source_line.department,
            cost_center_code=source_line.cost_center_code,
            category=source_line.category,
            category_l1=source_line.category_l1,
            category_l2=source_line.category_l2,
            gl_amount_code=source_line.gl_amount_code,
            project=source_line.project,
            project_category=source_line.project_category,
            product_line=source_line.product_line,
            description=source_line.description,
            vendor=source_line.vendor,
            reason=source_line.reason,
            region=source_line.region,
            unit_price=source_line.unit_price,
            total_quantity=source_line.total_quantity,
            total_amount=source_line.total_amount,
            dynamic_data=source_line.dynamic_data,
            local_comments=source_line.local_comments,
            admin_annotations=source_line.admin_annotations,
            source_ref_type=source_line.source_ref_type,
            source_ref_id=source_line.source_ref_id,
            editable_by_secondary=source_line.editable_by_secondary,
        )
        line_id_map[source_line.id] = copied_line
        BudgetMonthlyPlan.objects.bulk_create(
            [
                BudgetMonthlyPlan(
                    line=copied_line,
                    month=plan.month,
                    quantity=plan.quantity,
                    amount=plan.amount,
                )
                for plan in source_line.monthly_plans.all()
            ]
        )

    book.current_draft = draft
    book.status = BudgetBook.Status.DRAFTING
    book.save(update_fields=['current_draft', 'status', 'updated_at'])
    if is_primary_consolidated_book(book):
        reopen_cycle_if_locked(book.cycle)
        _update_primary_tasks(draft, status='pulled_to_primary')
    else:
        _update_secondary_task(book, status='drafting')
    create_audit_log(
        actor=requester,
        category='budget',
        action='revision_draft_created',
        target_type='budget_version',
        target_id=draft.id,
        target_label=f'{book.department.name} 修订 Draft',
        department=book.department,
        book=book,
        version=draft,
        details={
            'base_version_id': str(base_version.id),
            'base_version_no': base_version.version_no,
            'line_count': draft.lines.count(),
        },
    )
    return draft


@transaction.atomic
def pull_primary_consolidated_book(cycle, expense_type, requester=None):
    primary_department = Department.objects.filter(level=Department.Level.PRIMARY, code='SS').first()
    if not primary_department:
        raise ValidationError({'department': '未找到一级部门 SS。'})

    source_books = list(
        BudgetBook.objects.select_related('latest_approved_version', 'department', 'template')
        .filter(
            cycle=cycle,
            expense_type=expense_type,
            source_type__in=[BudgetBook.SourceType.SELF_BUILT, BudgetBook.SourceType.GROUP_ALLOCATION],
            department__level=Department.Level.SECONDARY,
        )
        .exclude(latest_approved_version=None)
    )
    if expense_type == BudgetBook.ExpenseType.OPEX:
        source_books.extend(
            list(
                BudgetBook.objects.select_related('current_draft', 'department', 'template')
                .filter(
                    cycle=cycle,
                    expense_type=expense_type,
                    source_type=BudgetBook.SourceType.GROUP_ALLOCATION,
                )
                .exclude(current_draft=None)
            )
        )
    if not source_books:
        raise ValidationError({'latest_approved_version': '当前没有可拉取的已审批部门预算。'})

    template = source_books[0].template
    consolidated_book, _ = BudgetBook.objects.get_or_create(
        cycle=cycle,
        department=primary_department,
        expense_type=expense_type,
        source_type=BudgetBook.SourceType.PRIMARY_CONSOLIDATED,
        defaults={'template': template, 'status': BudgetBook.Status.DRAFTING},
    )

    if consolidated_book.current_draft_id:
        consolidated_book.current_draft.lines.all().delete()
        consolidated_book.current_draft.delete()

    base_version = consolidated_book.latest_approved_version
    draft = BudgetVersion.objects.create(
        book=consolidated_book,
        version_no=0,
        base_version=base_version,
        status=BudgetVersion.Status.DRAFT,
        submitted_by=requester if requester and requester.is_authenticated else None,
        notes='一级总表拉取最新 Approved 版本生成',
    )

    line_no = 1
    seen_book_ids = set()
    for source_book in source_books:
        if source_book.id in seen_book_ids:
            continue
        seen_book_ids.add(source_book.id)
        source_version = source_book.current_draft if source_book.source_type == BudgetBook.SourceType.GROUP_ALLOCATION else source_book.latest_approved_version
        if not source_version:
            continue
        for source_line in source_version.lines.prefetch_related('monthly_plans').all():
            copied_line = BudgetLine.objects.create(
                version=draft,
                line_no=line_no,
                budget_no=source_line.budget_no,
                department=source_line.department,
                cost_center_code=source_line.cost_center_code,
                category=source_line.category,
                category_l1=source_line.category_l1,
                category_l2=source_line.category_l2,
                gl_amount_code=source_line.gl_amount_code,
                project=source_line.project,
                project_category=source_line.project_category,
                product_line=source_line.product_line,
                description=source_line.description,
                vendor=source_line.vendor,
                reason=source_line.reason,
                region=source_line.region,
                unit_price=source_line.unit_price,
                total_quantity=source_line.total_quantity,
                total_amount=source_line.total_amount,
                dynamic_data=source_line.dynamic_data,
                local_comments={},
                admin_annotations={
                    'source_book_id': str(source_book.id),
                    'source_version_id': str(source_version.id),
                    'source_department': source_book.department.code,
                },
                source_ref_type=source_book.source_type if source_book.source_type == BudgetBook.SourceType.GROUP_ALLOCATION else 'budget_version',
                source_ref_id=source_version.id,
                editable_by_secondary=False,
            )
            BudgetMonthlyPlan.objects.bulk_create(
                [
                    BudgetMonthlyPlan(
                        line=copied_line,
                        month=plan.month,
                        quantity=plan.quantity,
                        amount=plan.amount,
                    )
                    for plan in source_line.monthly_plans.all()
                ]
            )
            line_no += 1

    consolidated_book.template = template
    consolidated_book.current_draft = draft
    consolidated_book.status = BudgetBook.Status.DRAFTING
    consolidated_book.save(update_fields=['template', 'current_draft', 'status', 'updated_at'])
    reopen_cycle_if_locked(cycle)

    source_department_ids = [
        book.department_id for book in source_books if book.source_type == BudgetBook.SourceType.SELF_BUILT
    ]
    _update_task_status(cycle, source_department_ids, status='pulled_to_primary')
    create_audit_log(
        actor=requester,
        category='budget',
        action='primary_consolidated_pulled',
        target_type='budget_version',
        target_id=draft.id,
        target_label=f'{cycle.name} {expense_type.upper()} 一级总表 Draft',
        department=primary_department,
        book=consolidated_book,
        version=draft,
        details={
            'source_book_ids': [str(book.id) for book in source_books],
            'source_version_ids': [str(book.current_draft_id if book.source_type == BudgetBook.SourceType.GROUP_ALLOCATION else book.latest_approved_version_id) for book in source_books],
            'line_count': draft.lines.count(),
        },
    )
    return draft


def primary_consolidated_sync_status(book: BudgetBook):
    if book.source_type != BudgetBook.SourceType.PRIMARY_CONSOLIDATED:
        raise ValidationError({'book': '仅一级总表支持同步状态检查。'})
    if not book.current_draft_id:
        return {'has_updates': False, 'departments': [], 'line_count': 0}

    referenced_versions = {}
    for line in book.current_draft.lines.all():
        source_department = (line.admin_annotations or {}).get('source_department')
        source_version_id = (line.admin_annotations or {}).get('source_version_id')
        if not source_department or not source_version_id:
            continue
        referenced_versions[source_department] = source_version_id

    stale_departments = []
    for department_code, source_version_id in referenced_versions.items():
        source_book = BudgetBook.objects.filter(
            cycle=book.cycle,
            expense_type=book.expense_type,
            source_type=BudgetBook.SourceType.SELF_BUILT,
            department__code=department_code,
        ).select_related('latest_approved_version', 'department').first()
        if not source_book or not source_book.latest_approved_version_id:
            continue
        if str(source_book.latest_approved_version_id) != str(source_version_id):
            stale_departments.append(
                {
                    'department_code': department_code,
                    'department_name': source_book.department.name,
                    'current_source_version_id': str(source_version_id),
                    'latest_approved_version_id': str(source_book.latest_approved_version_id),
                }
            )

    return {
        'has_updates': bool(stale_departments),
        'departments': stale_departments,
        'line_count': len(stale_departments),
    }


@transaction.atomic
def bulk_operate_budget_lines(version, line_ids, action, patch_data=None, request=None):
    version = BudgetVersion.objects.select_for_update().select_related('book', 'book__template').get(id=version.id)
    if version.status != BudgetVersion.Status.DRAFT:
        raise ValidationError({'version': '只能在 Draft 版本下批量维护预算条目。'})

    lines = list(
        BudgetLine.objects.select_for_update()
        .filter(version=version, id__in=line_ids)
        .prefetch_related('monthly_plans')
    )
    requested_ids = {str(line_id) for line_id in line_ids}
    found_ids = {str(line.id) for line in lines}
    missing_ids = sorted(requested_ids - found_ids)
    if missing_ids:
        raise ValidationError({'line_ids': f'存在不属于当前 Draft 的预算条目: {", ".join(missing_ids)}'})
    if request and not is_global_budget_user(request.user):
        locked_lines = [str(line.id) for line in lines if not line.editable_by_secondary]
        if locked_lines:
            raise ValidationError({'line_ids': '选中的预算条目包含锁定条目，需回到来源模块维护。'})

    if action == 'delete':
        deleted_count = len(lines)
        BudgetLine.objects.filter(id__in=[line.id for line in lines]).delete()
        return {'action': action, 'affected': deleted_count}

    if action == 'duplicate':
        return _duplicate_budget_lines(version, lines)

    if action == 'patch':
        return _patch_budget_lines(version, lines, patch_data or {}, request=request)

    raise ValidationError({'action': '不支持的批量操作。'})


def _duplicate_budget_lines(version, lines):
    next_line_no = (
        BudgetLine.objects.filter(version=version).aggregate(max_line_no=Max('line_no'))['max_line_no'] or 0
    ) + 1
    created_ids = []
    for source_line in sorted(lines, key=lambda item: item.line_no):
        copied_line = BudgetLine.objects.create(
            version=version,
            line_no=next_line_no,
            budget_no=f'{source_line.budget_no}-COPY',
            department=source_line.department,
            cost_center_code=source_line.cost_center_code,
            category=source_line.category,
            category_l1=source_line.category_l1,
            category_l2=source_line.category_l2,
            gl_amount_code=source_line.gl_amount_code,
            project=source_line.project,
            project_category=source_line.project_category,
            product_line=source_line.product_line,
            description=f'{source_line.description}（复制）',
            vendor=source_line.vendor,
            reason=source_line.reason,
            region=source_line.region,
            unit_price=source_line.unit_price,
            total_quantity=source_line.total_quantity,
            total_amount=source_line.total_amount,
            dynamic_data=source_line.dynamic_data,
            local_comments=source_line.local_comments,
            admin_annotations=source_line.admin_annotations,
            source_ref_type=source_line.source_ref_type,
            source_ref_id=source_line.source_ref_id,
            editable_by_secondary=source_line.editable_by_secondary,
        )
        BudgetMonthlyPlan.objects.bulk_create(
            [
                BudgetMonthlyPlan(
                    line=copied_line,
                    month=plan.month,
                    quantity=plan.quantity,
                    amount=plan.amount,
                )
                for plan in source_line.monthly_plans.all()
            ]
        )
        created_ids.append(str(copied_line.id))
        next_line_no += 1
    return {'action': 'duplicate', 'affected': len(created_ids), 'created_ids': created_ids}


def _patch_budget_lines(version, lines, patch_data, request=None):
    from .serializers import BudgetLineSerializer

    updated_ids = []
    for line in lines:
        payload = dict(patch_data)
        if 'local_comments' in patch_data:
            merged_comments = dict(line.local_comments or {})
            merged_comments.update(patch_data['local_comments'] or {})
            payload['local_comments'] = merged_comments
        serializer = BudgetLineSerializer(line, data=payload, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        updated_ids.append(str(line.id))
    return {'action': 'patch', 'affected': len(updated_ids), 'updated_ids': updated_ids}


def reopen_cycle_if_locked(cycle):
    from budget_cycles.models import BudgetCycle

    if cycle.status != BudgetCycle.Status.LOCKED:
        return
    cycle.status = BudgetCycle.Status.ACTIVE
    cycle.save(update_fields=['status', 'updated_at'])


def mark_budget_approved(version):
    if is_primary_consolidated_book(version.book):
        _update_primary_tasks(version, status='final_locked')
        _set_cycle_status(version.book.cycle, 'locked')
        return
    _update_secondary_task(version.book, status='secondary_approved')


def mark_budget_rejected(version):
    if is_primary_consolidated_book(version.book):
        _update_primary_tasks(version, status='pulled_to_primary')
        _set_cycle_status(version.book.cycle, 'active')
        return
    _update_secondary_task(version.book, status='secondary_rejected')


def _mark_budget_tasks_on_submit(version):
    if is_primary_consolidated_book(version.book):
        _update_primary_tasks(version, status='primary_review')
        _set_cycle_status(version.book.cycle, 'reviewing')
        return
    _update_secondary_task(version.book, status='secondary_review')


def _update_primary_tasks(version, status):
    department_ids = source_department_ids_for_primary_version(version)
    _update_task_status(version.book.cycle, department_ids, status=status)


def _update_secondary_task(book, status):
    _update_task_status(book.cycle, [book.department_id], status=status)


def _update_task_status(cycle, department_ids, status):
    if not department_ids:
        return
    from budget_cycles.models import BudgetTask

    status_value = getattr(BudgetTask.Status, status.upper())
    BudgetTask.objects.filter(cycle=cycle, department_id__in=department_ids).update(status=status_value)


def _set_cycle_status(cycle, status):
    from budget_cycles.models import BudgetCycle

    status_value = getattr(BudgetCycle.Status, status.upper())
    if cycle.status == status_value:
        return
    cycle.status = status_value
    cycle.save(update_fields=['status', 'updated_at'])


def _notify_budget_anomalies(version, requester=None):
    from decimal import Decimal

    diff_payload = None
    if version.base_version_id:
        from .diff import compare_versions

        diff_payload = compare_versions(version.base_version, version)

    issues = []
    if version.base_version_id and diff_payload and diff_payload['summary']['total_changes'] >= 10:
        issues.append(f"本次送审共 {diff_payload['summary']['total_changes']} 项变更")
    if version.base_version_id and diff_payload:
        amount_delta = abs(sum(_change_amount_delta(change) for change in diff_payload['changes']))
        if amount_delta >= 100000:
            issues.append(f'本次金额波动达到 {amount_delta:.2f}')
    total_amount = sum((line.total_amount for line in version.lines.all()), Decimal('0'))
    if total_amount == Decimal('0'):
        issues.append('当前送审版本总金额为 0')

    if not issues:
        return

    recipients = []
    if requester and getattr(requester, 'is_authenticated', False):
        recipients.append(requester)
    approvers = [
        step.approver
        for step in ApprovalStep.objects.select_related('approver').filter(request__target_id=version.id)
    ]
    recipients.extend(approvers)
    create_notifications(
        recipients,
        category=Notification.Category.ANOMALY_ALERT,
        title=f'异常变更提醒: {request_title_for_version(version)}',
        message='；'.join(issues),
        target_type='budget_version',
        target_id=version.id,
        department=version.book.department,
        extra={
            'category': 'budget_anomaly',
            'issues': issues,
            'version_id': str(version.id),
            'book_id': str(version.book_id),
        },
    )


def _change_amount_delta(change):
    from decimal import Decimal

    if change['type'] in {'added', 'deleted'}:
        return Decimal(change.get('amount_delta') or '0')
    for field_change in change['field_changes']:
        if field_change['field'] == 'total_amount' and field_change['delta']:
            return Decimal(field_change['delta'])
    return Decimal('0')
