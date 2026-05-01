from accounts.models import RoleAssignment
from orgs.models import Department


PRIMARY_GLOBAL_ROLES = {
    RoleAssignment.Role.PRIMARY_BUDGET_ADMIN,
    RoleAssignment.Role.PRIMARY_BUDGET_REVIEWER,
    RoleAssignment.Role.PRIMARY_DEPT_HEAD,
}

BUDGET_EDIT_ROLES = {
    RoleAssignment.Role.SECONDARY_BUDGET_ADMIN,
    RoleAssignment.Role.SECONDARY_BUDGET_OWNER,
    RoleAssignment.Role.PRIMARY_BUDGET_ADMIN,
}

APPROVER_ROLES = {
    RoleAssignment.Role.SECONDARY_DEPT_HEAD,
    RoleAssignment.Role.PRIMARY_BUDGET_REVIEWER,
    RoleAssignment.Role.PRIMARY_DEPT_HEAD,
}


def is_global_budget_user(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.role_assignments.filter(role__in=PRIMARY_GLOBAL_ROLES).exists()


def accessible_department_ids(user):
    if not user or not user.is_authenticated:
        return []
    if is_global_budget_user(user):
        return list(Department.objects.values_list('id', flat=True))

    scoped_ids = list(
        user.role_assignments.exclude(department=None).values_list('department_id', flat=True).distinct()
    )
    if user.primary_department_id:
        scoped_ids.append(user.primary_department_id)
    return list(dict.fromkeys(scoped_ids))


def can_edit_department_budget(user, department_id):
    if is_global_budget_user(user):
        return True
    return _has_scoped_role(user, BUDGET_EDIT_ROLES, department_id)


def can_approve_department(user, department_id):
    if is_global_budget_user(user):
        return True
    return _has_scoped_role(user, APPROVER_ROLES, department_id)


def _has_scoped_role(user, roles, department_id):
    if not user or not user.is_authenticated:
        return False
    return user.role_assignments.filter(role__in=roles, department_id=department_id).exists()
