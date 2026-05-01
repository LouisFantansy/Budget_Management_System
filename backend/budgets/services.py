from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import RoleAssignment, User
from approvals.models import ApprovalRequest, ApprovalStep

from .models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion


def _resolve_budget_approvers(version, approver_ids=None):
    if approver_ids:
        approvers = list(User.objects.filter(id__in=approver_ids))
        if len(approvers) != len(set(approver_ids)):
            raise ValidationError({'approver_ids': '审批人不存在或不完整。'})
        return approvers

    return list(
        User.objects.filter(
            role_assignments__role=RoleAssignment.Role.SECONDARY_DEPT_HEAD,
            role_assignments__department=version.book.department,
        ).distinct()
    )


@transaction.atomic
def submit_budget_version(version, requester, approver_ids=None, comment=''):
    version = BudgetVersion.objects.select_for_update().select_related('book', 'book__department').get(id=version.id)
    book = BudgetBook.objects.select_for_update().get(id=version.book_id)

    if version.status != BudgetVersion.Status.DRAFT:
        raise ValidationError({'status': '只有 Draft 版本可以送审。'})
    if book.current_draft_id and book.current_draft_id != version.id:
        raise ValidationError({'current_draft': '预算表已有其他当前 Draft。'})

    approvers = _resolve_budget_approvers(version, approver_ids)
    if not approvers:
        raise ValidationError({'approver_ids': '未找到二级部门负责人，请指定审批人。'})

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
        title=f'{book.department.name} {book.get_expense_type_display()} 预算送审',
        requester=requester,
        department=book.department,
        submitted_version_label='Draft',
        dashboard_context={
            'version_context': 'submitted_version',
            'version_id': str(version.id),
            'book_id': str(book.id),
        },
    )
    ApprovalStep.objects.bulk_create(
        [
            ApprovalStep(request=approval_request, node=1, approver=approver)
            for approver in approvers
        ]
    )
    return approval_request


@transaction.atomic
def create_revision_draft(book, requester=None, base_version=None):
    book = BudgetBook.objects.select_for_update().get(id=book.id)
    if book.current_draft_id:
        raise ValidationError({'current_draft': '预算表已有当前 Draft，不能重复创建修订。'})

    base_version = base_version or book.latest_approved_version
    if not base_version:
        raise ValidationError({'base_version': '没有可用于修订的 Approved 版本。'})
    if base_version.book_id != book.id or base_version.status != BudgetVersion.Status.APPROVED:
        raise ValidationError({'base_version': '只能基于本预算表的 Approved 版本创建修订。'})

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
    return draft
