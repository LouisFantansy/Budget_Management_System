from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User
from budget_cycles.models import BudgetCycle
from budget_templates.models import BudgetTemplate
from budgets.models import BudgetBook, BudgetLine, BudgetVersion
from orgs.models import Department

from .models import ApprovalRequest


class ApprovalRequestDiffSummaryTests(APITestCase):
    def setUp(self):
        self.primary = Department.objects.create(name='SS', code='SS', level=Department.Level.PRIMARY)
        self.arch = Department.objects.create(name='Arch', code='Arch', level=Department.Level.SECONDARY, parent=self.primary)
        self.user = User.objects.create_user(username='dept-head', password='password')
        RoleAssignment.objects.create(user=self.user, role=RoleAssignment.Role.SECONDARY_DEPT_HEAD, department=self.arch)
        self.client.force_authenticate(self.user)
        self.cycle = BudgetCycle.objects.create(year=2027, name='2027 年度预算编制')
        self.template = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='OPEX 模板',
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            status=BudgetTemplate.Status.ACTIVE,
        )

    def test_approval_request_serializer_exposes_diff_summary(self):
        book = BudgetBook.objects.create(
            cycle=self.cycle,
            department=self.arch,
            expense_type=BudgetBook.ExpenseType.OPEX,
            template=self.template,
        )
        base = BudgetVersion.objects.create(book=book, version_no=1, status=BudgetVersion.Status.APPROVED)
        BudgetLine.objects.create(version=base, line_no=1, budget_no='ARCH-001', department=self.arch, description='旧条目', total_amount='100')
        submitted = BudgetVersion.objects.create(book=book, base_version=base, status=BudgetVersion.Status.SUBMITTED)
        BudgetLine.objects.create(version=submitted, line_no=1, budget_no='ARCH-001', department=self.arch, description='新条目', total_amount='150')
        BudgetLine.objects.create(version=submitted, line_no=2, budget_no='ARCH-002', department=self.arch, description='新增条目', total_amount='50')
        ApprovalRequest.objects.create(
            target_type='budget_version',
            target_id=submitted.id,
            title='Arch OPEX 送审',
            requester=self.user,
            department=self.arch,
        )

        response = self.client.get(reverse('approvalrequest-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        summary = response.data['results'][0]['diff_summary']
        self.assertEqual(summary['added'], 1)
        self.assertEqual(summary['modified'], 1)
        self.assertEqual(summary['deleted'], 0)
        self.assertEqual(summary['total_changes'], 2)
