from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.access import can_approve_department
from budgets.models import BudgetBook, BudgetVersion
from notifications.models import Notification
from notifications.services import create_notification

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
    Notification.objects.filter(
        recipient=approver,
        category=Notification.Category.APPROVAL_TODO,
        target_type='approval_request',
        target_id=approval_request.id,
        status=Notification.Status.UNREAD,
    ).update(status=Notification.Status.READ, read_at=now, updated_at=now)

    if approval_request.steps.filter(action=ApprovalStep.Action.PENDING).exists():
        return approval_request

    approval_request.status = ApprovalRequest.Status.APPROVED
    approval_request.save(update_fields=['status', 'updated_at'])
    _apply_target_approval(approval_request, approver, now)
    create_notification(
        recipient=approval_request.requester,
        category=Notification.Category.APPROVAL_RESULT,
        title=f'审批已通过: {approval_request.title}',
        message=f'{approver.display_name or approver.username} 已通过你的预算送审。',
        target_type='approval_request',
        target_id=approval_request.id,
        department=approval_request.department,
        extra={
            'approval_request_id': str(approval_request.id),
            'result': 'approved',
            'acted_by': approver.username,
        },
    )
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
    Notification.objects.filter(
        recipient=approver,
        category=Notification.Category.APPROVAL_TODO,
        target_type='approval_request',
        target_id=approval_request.id,
        status=Notification.Status.UNREAD,
    ).update(status=Notification.Status.READ, read_at=now, updated_at=now)

    approval_request.status = ApprovalRequest.Status.REJECTED
    approval_request.save(update_fields=['status', 'updated_at'])
    _apply_target_rejection(approval_request)
    create_notification(
        recipient=approval_request.requester,
        category=Notification.Category.APPROVAL_RESULT,
        title=f'审批已退回: {approval_request.title}',
        message=f'{approver.display_name or approver.username} 已退回你的预算送审，请根据意见修订后重新提交。',
        target_type='approval_request',
        target_id=approval_request.id,
        department=approval_request.department,
        extra={
            'approval_request_id': str(approval_request.id),
            'result': 'rejected',
            'acted_by': approver.username,
        },
    )
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
