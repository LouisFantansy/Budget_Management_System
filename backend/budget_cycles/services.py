from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from rest_framework.exceptions import ValidationError

from accounts.models import RoleAssignment, User
from budget_templates.models import BudgetTemplate
from budgets.models import BudgetBook, BudgetVersion
from orgs.models import Department

from .models import BudgetCycle, BudgetTask


@transaction.atomic
def distribute_cycle_tasks(cycle, requester=None, due_at=None):
    cycle = BudgetCycle.objects.select_for_update().get(id=cycle.id)
    if cycle.status in [BudgetCycle.Status.REVIEWING, BudgetCycle.Status.LOCKED, BudgetCycle.Status.ARCHIVED]:
        raise ValidationError({'status': '当前预算周期处于审核、锁定或归档状态，不能重新分发任务。'})

    templates = []
    for expense_type in [BudgetTemplate.ExpenseType.OPEX, BudgetTemplate.ExpenseType.CAPEX]:
        template = (
            cycle.templates.filter(
                status=BudgetTemplate.Status.ACTIVE,
                expense_type=expense_type,
            )
            .order_by('-schema_version', '-created_at')
            .first()
        )
        if template:
            templates.append(template)
    if not templates:
        raise ValidationError({'templates': '当前预算周期没有可分发的有效 OPEX/CAPEX 模板。'})

    departments = list(
        Department.objects.filter(
            is_active=True,
        ).filter(
            Q(level=Department.Level.SECONDARY) | Q(level=Department.Level.SS_PUBLIC)
        ).order_by('sort_order', 'code')
    )
    if not departments:
        raise ValidationError({'departments': '当前没有可分发的部门。'})

    created_tasks = 0
    updated_tasks = 0
    created_books = 0
    created_drafts = 0

    for department in departments:
        for template in templates:
            _, book_created, draft_created = ensure_department_budget_book(
                cycle,
                department,
                template,
                requester=requester,
            )
            created_books += int(book_created)
            created_drafts += int(draft_created)

        owner = resolve_task_owner(department)
        task, task_created = BudgetTask.objects.get_or_create(
            cycle=cycle,
            department=department,
            defaults={
                'owner': owner,
                'status': derive_task_status(cycle, department),
                'due_at': due_at,
            },
        )
        if task_created:
            created_tasks += 1
            continue

        updated_fields = []
        derived_status = derive_task_status(cycle, department, current_status=task.status)
        if task.status != derived_status:
            task.status = derived_status
            updated_fields.append('status')
        if owner and task.owner_id != owner.id:
            task.owner = owner
            updated_fields.append('owner')
        if due_at is not None and task.due_at != due_at:
            task.due_at = due_at
            updated_fields.append('due_at')
        if updated_fields:
            task.save(update_fields=[*updated_fields, 'updated_at'])
            updated_tasks += 1

    if cycle.status != BudgetCycle.Status.ACTIVE:
        cycle.status = BudgetCycle.Status.ACTIVE
        cycle.save(update_fields=['status', 'updated_at'])

    return {
        'cycle_id': str(cycle.id),
        'cycle_status': cycle.status,
        'department_count': len(departments),
        'template_count': len(templates),
        'created_tasks': created_tasks,
        'updated_tasks': updated_tasks,
        'created_books': created_books,
        'created_drafts': created_drafts,
    }


def ensure_department_budget_book(cycle, department, template, requester=None):
    source_type = (
        BudgetBook.SourceType.SS_PUBLIC
        if department.level == Department.Level.SS_PUBLIC
        else BudgetBook.SourceType.SELF_BUILT
    )
    book, book_created = BudgetBook.objects.get_or_create(
        cycle=cycle,
        department=department,
        expense_type=template.expense_type,
        source_type=source_type,
        defaults={
            'template': template,
            'status': BudgetBook.Status.DRAFTING,
        },
    )

    draft_created = False
    updated_fields = []
    if book.template_id != template.id and not book.versions.exists():
        book.template = template
        updated_fields.append('template')
    if not book.current_draft_id and not book.latest_approved_version_id:
        draft = BudgetVersion.objects.create(
            book=book,
            version_no=0,
            status=BudgetVersion.Status.DRAFT,
            submitted_by=requester if requester and requester.is_authenticated else None,
            notes='预算周期任务分发自动创建 Draft',
        )
        book.current_draft = draft
        book.status = BudgetBook.Status.DRAFTING
        updated_fields.extend(['current_draft', 'status'])
        draft_created = True
    if updated_fields:
        book.save(update_fields=[*updated_fields, 'updated_at'])
    return book, book_created, draft_created


def derive_task_status(cycle, department, current_status=None):
    if current_status in [
        BudgetTask.Status.PULLED_TO_PRIMARY,
        BudgetTask.Status.PRIMARY_REVIEW,
        BudgetTask.Status.FINAL_LOCKED,
        BudgetTask.Status.SECONDARY_REJECTED,
    ]:
        return current_status

    books = list(task_books_queryset(cycle, department))
    if not books:
        return BudgetTask.Status.NOT_STARTED

    current_drafts = [book.current_draft for book in books if book.current_draft_id]
    if any(draft and draft.status == BudgetVersion.Status.SUBMITTED for draft in current_drafts):
        return BudgetTask.Status.SECONDARY_REVIEW
    if current_drafts:
        return BudgetTask.Status.DRAFTING
    if any(book.latest_approved_version_id for book in books):
        return BudgetTask.Status.SECONDARY_APPROVED
    return BudgetTask.Status.NOT_STARTED


def task_budget_context(task):
    book = select_task_book(task.cycle, task.department)
    if not book:
        return {
            'book_id': '',
            'current_draft_id': '',
            'latest_approved_version_id': '',
            'source_type': '',
            'template_id': '',
            'expense_type': '',
            'version_label': '未开始',
            'amount': '0.00',
            'book_status': '',
        }

    version = book.current_draft or book.latest_approved_version
    total_amount = Decimal('0')
    if version:
        total_amount = version.lines.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    version_label = '未开始'
    if book.current_draft_id:
        version_label = 'Draft'
    elif book.latest_approved_version_id:
        version_label = f'V{book.latest_approved_version.version_no}'

    return {
        'book_id': str(book.id),
        'current_draft_id': str(book.current_draft_id) if book.current_draft_id else '',
        'latest_approved_version_id': str(book.latest_approved_version_id) if book.latest_approved_version_id else '',
        'source_type': book.source_type,
        'template_id': str(book.template_id),
        'expense_type': book.expense_type,
        'version_label': version_label,
        'amount': str(total_amount),
        'book_status': book.status,
    }


def resolve_task_owner(department):
    if department.level == Department.Level.SS_PUBLIC:
        primary_department = department.parent
        primary_admin = User.objects.filter(
            role_assignments__role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN,
        ).filter(
            Q(role_assignments__department=primary_department) | Q(role_assignments__department=None)
        ).distinct().order_by('id').first()
        return primary_admin

    owner = User.objects.filter(
        role_assignments__role=RoleAssignment.Role.SECONDARY_BUDGET_OWNER,
        role_assignments__department=department,
    ).distinct().order_by('id').first()
    if owner:
        return owner
    return User.objects.filter(
        role_assignments__role=RoleAssignment.Role.SECONDARY_BUDGET_ADMIN,
        role_assignments__department=department,
    ).distinct().order_by('id').first()


def select_task_book(cycle, department):
    books = list(task_books_queryset(cycle, department))
    if not books:
        return None
    return sorted(
        books,
        key=lambda book: (
            0 if book.current_draft_id else 1,
            0 if book.expense_type == BudgetBook.ExpenseType.OPEX else 1,
            0 if book.source_type in [BudgetBook.SourceType.SELF_BUILT, BudgetBook.SourceType.SS_PUBLIC] else 1,
            str(book.id),
        ),
    )[0]


def task_books_queryset(cycle, department):
    source_types = [BudgetBook.SourceType.SS_PUBLIC] if department.level == Department.Level.SS_PUBLIC else [BudgetBook.SourceType.SELF_BUILT]
    return BudgetBook.objects.filter(
        cycle=cycle,
        department=department,
        source_type__in=source_types,
        expense_type__in=[BudgetBook.ExpenseType.OPEX, BudgetBook.ExpenseType.CAPEX],
    ).select_related('template', 'current_draft', 'latest_approved_version')
