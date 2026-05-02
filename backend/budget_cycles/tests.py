from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User
from budget_templates.models import BudgetTemplate
from budgets.models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion
from orgs.models import Department

from .models import BudgetCycle, BudgetTask


class PrimaryConsolidatedPullAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='primary-admin', password='password')
        RoleAssignment.objects.create(user=self.user, role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN)
        self.client.force_authenticate(self.user)
        self.primary = Department.objects.create(name='SS', code='SS', level=Department.Level.PRIMARY)
        self.arch = Department.objects.create(name='Arch', code='Arch', level=Department.Level.SECONDARY, parent=self.primary)
        self.pve = Department.objects.create(name='PVE', code='PVE', level=Department.Level.SECONDARY, parent=self.primary)
        self.cycle = BudgetCycle.objects.create(year=2027, name='2027 年度预算编制')
        self.template = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='OPEX 模板',
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            status=BudgetTemplate.Status.ACTIVE,
        )
        self._approved_book(self.arch, 'ARCH-001', '1000.00')
        self._approved_book(self.pve, 'PVE-001', '2000.00')
        BudgetTask.objects.create(cycle=self.cycle, department=self.arch, status=BudgetTask.Status.SECONDARY_APPROVED)
        BudgetTask.objects.create(cycle=self.cycle, department=self.pve, status=BudgetTask.Status.SECONDARY_APPROVED)

    def test_primary_user_can_pull_primary_consolidated_book(self):
        response = self.client.post(
            reverse('budgetcycle-pull-primary-consolidated', args=[self.cycle.id]),
            {'expense_type': 'opex'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        book = BudgetBook.objects.get(
            cycle=self.cycle,
            department=self.primary,
            expense_type=BudgetBook.ExpenseType.OPEX,
            source_type=BudgetBook.SourceType.PRIMARY_CONSOLIDATED,
        )
        draft = book.current_draft
        self.assertEqual(draft.status, BudgetVersion.Status.DRAFT)
        self.assertEqual(draft.lines.count(), 2)
        line = draft.lines.order_by('line_no').first()
        self.assertEqual(line.source_ref_type, 'budget_version')
        self.assertFalse(line.editable_by_secondary)
        self.assertEqual(line.admin_annotations['source_department'], line.department.code)
        self.assertEqual(BudgetTask.objects.get(cycle=self.cycle, department=self.arch).status, BudgetTask.Status.PULLED_TO_PRIMARY)
        self.assertEqual(BudgetTask.objects.get(cycle=self.cycle, department=self.pve).status, BudgetTask.Status.PULLED_TO_PRIMARY)

    def _approved_book(self, department, budget_no, amount):
        book = BudgetBook.objects.create(
            cycle=self.cycle,
            department=department,
            expense_type=BudgetBook.ExpenseType.OPEX,
            source_type=BudgetBook.SourceType.SELF_BUILT,
            template=self.template,
            status=BudgetBook.Status.APPROVED,
        )
        version = BudgetVersion.objects.create(book=book, version_no=1, status=BudgetVersion.Status.APPROVED)
        line = BudgetLine.objects.create(
            version=version,
            line_no=1,
            budget_no=budget_no,
            department=department,
            description=f'{department.name} budget line',
            total_amount=amount,
        )
        BudgetMonthlyPlan.objects.create(line=line, month=1, amount=amount)
        book.latest_approved_version = version
        book.save(update_fields=['latest_approved_version', 'updated_at'])
        return book
