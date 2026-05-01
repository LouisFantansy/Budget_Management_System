from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.access import can_approve_department
from budgets.models import BudgetBook, BudgetVersion

from .models import ApprovalRequest, ApprovalStep


@transaction.atomic
def approve_request(approval_request, approver, comment=''):
    approval_request = ApprovalRequest.objects.select_for_update().get(id=approval_request.id)
    if approval_request.status != ApprovalRequest.Status.PENDING:
        raise ValidationError({'status': '只有待审批请求可以审批。'})
    if not can_approve_department(approver, approval_request.department_id):
        raise ValidationError({'approver': '没有权限审批该部门请求。'})

    step = _get_pending_step(approval_request, approver)
    now = timezone.now()
    step.action = ApprovalStep.Action.APPROVED
    step.comment = comment
    step.acted_at = now
    step.save(update_fields=['action', 'comment', 'acted_at', 'updated_at'])

    if approval_request.steps.filter(action=ApprovalStep.Action.PENDING).exists():
        return approval_request

    approval_request.status = ApprovalRequest.Status.APPROVED
    approval_request.save(update_fields=['status', 'updated_at'])
    _apply_target_approval(approval_request, approver, now)
    return approval_request


@transaction.atomic
def reject_request(approval_request, approver, comment=''):
    approval_request = ApprovalRequest.objects.select_for_update().get(id=approval_request.id)
    if approval_request.status != ApprovalRequest.Status.PENDING:
        raise ValidationError({'status': '只有待审批请求可以退回。'})
    if not can_approve_department(approver, approval_request.department_id):
        raise ValidationError({'approver': '没有权限审批该部门请求。'})

    step = _get_pending_step(approval_request, approver)
    now = timezone.now()
    step.action = ApprovalStep.Action.REJECTED
    step.comment = comment
    step.acted_at = now
    step.save(update_fields=['action', 'comment', 'acted_at', 'updated_at'])

    approval_request.status = ApprovalRequest.Status.REJECTED
    approval_request.save(update_fields=['status', 'updated_at'])
    _apply_target_rejection(approval_request)
    return approval_request


def _get_pending_step(approval_request, approver):
    try:
        return approval_request.steps.select_for_update().get(
            node=approval_request.current_node,
            approver=approver,
            action=ApprovalStep.Action.PENDING,
        )
    except ApprovalStep.DoesNotExist as exc:
        raise ValidationError({'approver': '当前用户不是该节点待处理审批人。'}) from exc


def _apply_target_approval(approval_request, approver, approved_at):
    if approval_request.target_type != 'budget_version':
        return

    version = BudgetVersion.objects.select_for_update().select_related('book').get(id=approval_request.target_id)
    book = BudgetBook.objects.select_for_update().get(id=version.book_id)
    next_version_no = (
        BudgetVersion.objects.filter(book=book, status__in=[BudgetVersion.Status.APPROVED, BudgetVersion.Status.FINAL])
        .aggregate(max_version=Max('version_no'))['max_version']
        or 0
    ) + 1

    version.status = BudgetVersion.Status.APPROVED
    version.version_no = next_version_no
    version.approved_by = approver
    version.approved_at = approved_at
    version.save(update_fields=['status', 'version_no', 'approved_by', 'approved_at', 'updated_at'])

    book.status = BudgetBook.Status.APPROVED
    book.latest_approved_version = version
    book.current_draft = None
    book.save(update_fields=['status', 'latest_approved_version', 'current_draft', 'updated_at'])

    approval_request.submitted_version_label = f'V{next_version_no}'
    approval_request.save(update_fields=['submitted_version_label', 'updated_at'])


def _apply_target_rejection(approval_request):
    if approval_request.target_type != 'budget_version':
        return

    version = BudgetVersion.objects.select_for_update().select_related('book').get(id=approval_request.target_id)
    book = BudgetBook.objects.select_for_update().get(id=version.book_id)

    version.status = BudgetVersion.Status.DRAFT
    version.submitted_by = None
    version.submitted_at = None
    version.save(update_fields=['status', 'submitted_by', 'submitted_at', 'updated_at'])

    book.status = BudgetBook.Status.DRAFTING
    if book.current_draft_id == version.id:
        book.current_draft = version
    book.save(update_fields=['status', 'current_draft', 'updated_at'])
