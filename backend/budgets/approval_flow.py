from accounts.models import RoleAssignment, User
from rest_framework.exceptions import ValidationError

from .models import BudgetBook

SECONDARY_REVIEW_STAGE = 'secondary_review'
PRIMARY_REVIEW_STAGE = 'primary_review'
FINAL_REVIEW_STAGE = 'final_review'

APPROVAL_STAGE_LABELS = {
    SECONDARY_REVIEW_STAGE: '二级审批',
    PRIMARY_REVIEW_STAGE: '一级初审',
    FINAL_REVIEW_STAGE: '一级终审',
}

APPROVAL_STAGE_TITLES = {
    SECONDARY_REVIEW_STAGE: '待审批',
    PRIMARY_REVIEW_STAGE: '待初审',
    FINAL_REVIEW_STAGE: '待终审',
}


def is_primary_consolidated_book(book):
    return book.source_type == BudgetBook.SourceType.PRIMARY_CONSOLIDATED


def resolve_approval_nodes(version, approver_ids=None):
    if is_primary_consolidated_book(version.book):
        reviewers = _resolve_global_approvers(RoleAssignment.Role.PRIMARY_BUDGET_REVIEWER)
        final_approvers = _resolve_global_approvers(RoleAssignment.Role.PRIMARY_DEPT_HEAD)
        if not reviewers:
            raise ValidationError({'approver_ids': '未找到一级预算主管/主办，请先配置 PRIMARY_BUDGET_REVIEWER。'})
        if not final_approvers:
            raise ValidationError({'approver_ids': '未找到一级部门负责人，请先配置 PRIMARY_DEPT_HEAD。'})
        return [(1, reviewers), (2, final_approvers)]

    approvers = _resolve_secondary_approvers(version, approver_ids=approver_ids)
    if not approvers:
        raise ValidationError({'approver_ids': '未找到二级部门负责人，请指定审批人。'})
    return [(1, approvers)]


def approval_stage_for_node(book, node):
    if is_primary_consolidated_book(book):
        if int(node) <= 1:
            return PRIMARY_REVIEW_STAGE
        return FINAL_REVIEW_STAGE
    return SECONDARY_REVIEW_STAGE


def approval_stage_label(stage):
    return APPROVAL_STAGE_LABELS.get(stage, stage)


def request_title_for_version(version):
    if is_primary_consolidated_book(version.book):
        return f'{version.book.department.name} {version.book.get_expense_type_display()} 一级总表送审'
    return f'{version.book.department.name} {version.book.get_expense_type_display()} 预算送审'


def build_dashboard_context(version, node=1):
    return {
        'version_context': 'submitted_version',
        'version_id': str(version.id),
        'book_id': str(version.book_id),
        'approval_stage': approval_stage_for_node(version.book, node),
    }


def build_step_notification(version, requester, node, approval_request):
    stage = approval_stage_for_node(version.book, node)
    requester_name = requester.display_name or requester.username
    title = f"{APPROVAL_STAGE_TITLES.get(stage, '待审批')}: {request_title_for_version(version)}"
    if stage == PRIMARY_REVIEW_STAGE:
        message = f'{requester_name} 已提交 {version.book.department.name} {version.book.get_expense_type_display()} 一级总表，请完成初审。'
    elif stage == FINAL_REVIEW_STAGE:
        message = f'{version.book.department.name} {version.book.get_expense_type_display()} 一级总表已完成初审，请完成终审。'
    else:
        message = f'{requester_name} 已提交 {version.book.department.name} {version.book.get_expense_type_display()} 预算，请尽快处理。'
    return {
        'category': 'approval_todo',
        'title': title,
        'message': message,
        'target_type': 'approval_request',
        'target_id': approval_request.id,
        'department': version.book.department,
        'extra': {
            'approval_request_id': str(approval_request.id),
            'version_id': str(version.id),
            'book_id': str(version.book_id),
            'approval_stage': stage,
            'result': 'pending',
        },
    }


def source_department_ids_for_primary_version(version):
    return list(
        version.lines.exclude(department_id=version.book.department_id)
        .values_list('department_id', flat=True)
        .distinct()
    )


def _resolve_secondary_approvers(version, approver_ids=None):
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


def _resolve_global_approvers(role):
    return list(User.objects.filter(role_assignments__role=role).distinct())
