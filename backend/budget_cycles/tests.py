from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User
from approvals.models import ApprovalRequest
from budget_templates.models import BudgetTemplate
from budgets.models import AllocationUpload, BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion
from orgs.models import Department

from .models import BudgetCycle, BudgetTask


class PrimaryConsolidatedPullAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='primary-admin', password='password')
        self.primary_reviewer = User.objects.create_user(username='primary-reviewer', password='password')
        self.primary_head = User.objects.create_user(username='ss-head', password='password')
        RoleAssignment.objects.create(user=self.user, role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN)
        self.client.force_authenticate(self.user)
        self.primary = Department.objects.create(name='SS', code='SS', level=Department.Level.PRIMARY)
        self.arch = Department.objects.create(name='Arch', code='Arch', level=Department.Level.SECONDARY, parent=self.primary)
        self.pve = Department.objects.create(name='PVE', code='PVE', level=Department.Level.SECONDARY, parent=self.primary)
        RoleAssignment.objects.create(
            user=self.primary_reviewer,
            role=RoleAssignment.Role.PRIMARY_BUDGET_REVIEWER,
            department=self.primary,
        )
        RoleAssignment.objects.create(
            user=self.primary_head,
            role=RoleAssignment.Role.PRIMARY_DEPT_HEAD,
            department=self.primary,
        )
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
        sync_response = self.client.get(reverse('budgetbook-sync-status', args=[book.id]))
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK)
        self.assertFalse(sync_response.data['has_updates'])

    def test_primary_user_can_import_group_allocation_and_pull_into_primary_book(self):
        upload_response = self.client.post(
            reverse('budgetcycle-import-group-allocation', args=[self.cycle.id]),
            {
                'source_name': 'group-allocation.tsv',
                'raw_text': '\n'.join(
                    [
                        '\t'.join(['预算部门', '预算编号', '预算条目描述', '总金额', '备注']),
                        '\t'.join(['Arch', 'ALLOC-ARCH-001', '集团云资源分摊', '3000.00', '财务导入']),
                    ]
                ),
            },
            format='json',
        )

        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(upload_response.data['status'], AllocationUpload.Status.SUCCESS)
        allocation_book = BudgetBook.objects.get(
            cycle=self.cycle,
            department=self.primary,
            expense_type=BudgetBook.ExpenseType.OPEX,
            source_type=BudgetBook.SourceType.GROUP_ALLOCATION,
        )
        self.assertEqual(allocation_book.current_draft.lines.count(), 1)
        allocation_line = allocation_book.current_draft.lines.get()
        self.assertEqual(allocation_line.department, self.arch)
        self.assertEqual(allocation_line.source_ref_type, 'group_allocation')

        pull_response = self.client.post(
            reverse('budgetcycle-pull-primary-consolidated', args=[self.cycle.id]),
            {'expense_type': 'opex'},
            format='json',
        )

        self.assertEqual(pull_response.status_code, status.HTTP_201_CREATED)
        primary_book = BudgetBook.objects.get(
            cycle=self.cycle,
            department=self.primary,
            expense_type=BudgetBook.ExpenseType.OPEX,
            source_type=BudgetBook.SourceType.PRIMARY_CONSOLIDATED,
        )
        self.assertEqual(primary_book.current_draft.lines.count(), 3)
        self.assertTrue(primary_book.current_draft.lines.filter(budget_no='ALLOC-ARCH-001', source_ref_type='group_allocation').exists())

    def test_group_allocation_import_with_unknown_department_fails(self):
        response = self.client.post(
            reverse('budgetcycle-import-group-allocation', args=[self.cycle.id]),
            {
                'source_name': 'bad.tsv',
                'raw_text': '\n'.join(
                    [
                        '\t'.join(['预算部门', '预算编号', '预算条目描述', '总金额']),
                        '\t'.join(['UNKNOWN', 'ALLOC-001', '错误分摊', '500.00']),
                    ]
                ),
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], AllocationUpload.Status.FAILED)
        self.assertEqual(response.data['error_rows'], 1)

    def test_primary_user_can_download_group_allocation_template(self):
        response = self.client.get(reverse('budgetcycle-group-allocation-template', args=[self.cycle.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode('utf-8')
        self.assertIn('预算部门', content)
        self.assertIn('集团云资源分摊', content)

    def test_sync_status_reports_when_secondary_department_has_new_approved_version(self):
        pull_response = self.client.post(
            reverse('budgetcycle-pull-primary-consolidated', args=[self.cycle.id]),
            {'expense_type': 'opex'},
            format='json',
        )
        self.assertEqual(pull_response.status_code, status.HTTP_201_CREATED)
        primary_book = BudgetBook.objects.get(
            cycle=self.cycle,
            department=self.primary,
            expense_type=BudgetBook.ExpenseType.OPEX,
            source_type=BudgetBook.SourceType.PRIMARY_CONSOLIDATED,
        )

        arch_book = BudgetBook.objects.get(
            cycle=self.cycle,
            department=self.arch,
            expense_type=BudgetBook.ExpenseType.OPEX,
            source_type=BudgetBook.SourceType.SELF_BUILT,
        )
        new_version = BudgetVersion.objects.create(book=arch_book, version_no=2, status=BudgetVersion.Status.APPROVED)
        BudgetLine.objects.create(
            version=new_version,
            line_no=1,
            budget_no='ARCH-002',
            department=self.arch,
            description='Arch new approved line',
            total_amount='1500.00',
        )
        arch_book.latest_approved_version = new_version
        arch_book.save(update_fields=['latest_approved_version', 'updated_at'])

        sync_response = self.client.get(reverse('budgetbook-sync-status', args=[primary_book.id]))

        self.assertEqual(sync_response.status_code, status.HTTP_200_OK)
        self.assertTrue(sync_response.data['has_updates'])
        self.assertEqual(sync_response.data['line_count'], 1)
        self.assertEqual(sync_response.data['departments'][0]['department_code'], 'Arch')

    def test_primary_consolidated_submission_flows_to_two_stage_approval_and_locks_cycle(self):
        pull_response = self.client.post(
            reverse('budgetcycle-pull-primary-consolidated', args=[self.cycle.id]),
            {'expense_type': 'opex'},
            format='json',
        )
        self.assertEqual(pull_response.status_code, status.HTTP_201_CREATED)
        primary_book = BudgetBook.objects.get(
            cycle=self.cycle,
            department=self.primary,
            expense_type=BudgetBook.ExpenseType.OPEX,
            source_type=BudgetBook.SourceType.PRIMARY_CONSOLIDATED,
        )
        draft = primary_book.current_draft

        submit_response = self.client.post(reverse('budgetversion-submit', args=[draft.id]), {}, format='json')

        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)
        approval_request = ApprovalRequest.objects.get(id=submit_response.data['approval_request_id'])
        self.assertEqual(approval_request.current_node, 1)
        self.assertEqual(approval_request.dashboard_context['approval_stage'], 'primary_review')
        self.assertEqual(approval_request.steps.count(), 2)
        self.assertEqual(approval_request.steps.filter(node=1).count(), 1)
        self.assertEqual(approval_request.steps.filter(node=2).count(), 1)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, BudgetCycle.Status.REVIEWING)
        self.assertEqual(BudgetTask.objects.get(cycle=self.cycle, department=self.arch).status, BudgetTask.Status.PRIMARY_REVIEW)
        self.assertEqual(BudgetTask.objects.get(cycle=self.cycle, department=self.pve).status, BudgetTask.Status.PRIMARY_REVIEW)

        self.client.force_authenticate(self.primary_reviewer)
        first_approve = self.client.post(reverse('approvalrequest-approve', args=[approval_request.id]), {}, format='json')

        self.assertEqual(first_approve.status_code, status.HTTP_200_OK)
        approval_request.refresh_from_db()
        primary_book.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(approval_request.status, ApprovalRequest.Status.PENDING)
        self.assertEqual(approval_request.current_node, 2)
        self.assertEqual(approval_request.dashboard_context['approval_stage'], 'final_review')
        self.assertEqual(draft.status, BudgetVersion.Status.SUBMITTED)
        self.assertEqual(primary_book.status, BudgetBook.Status.REVIEWING)

        self.client.force_authenticate(self.primary_head)
        final_approve = self.client.post(reverse('approvalrequest-approve', args=[approval_request.id]), {}, format='json')

        self.assertEqual(final_approve.status_code, status.HTTP_200_OK)
        approval_request.refresh_from_db()
        primary_book.refresh_from_db()
        final_version = BudgetVersion.objects.get(id=draft.id)
        self.cycle.refresh_from_db()
        self.assertEqual(approval_request.status, ApprovalRequest.Status.APPROVED)
        self.assertEqual(final_version.status, BudgetVersion.Status.FINAL)
        self.assertEqual(primary_book.status, BudgetBook.Status.LOCKED)
        self.assertEqual(primary_book.latest_approved_version, final_version)
        self.assertIsNone(primary_book.current_draft)
        self.assertEqual(self.cycle.status, BudgetCycle.Status.LOCKED)
        self.assertEqual(BudgetTask.objects.get(cycle=self.cycle, department=self.arch).status, BudgetTask.Status.FINAL_LOCKED)
        self.assertEqual(BudgetTask.objects.get(cycle=self.cycle, department=self.pve).status, BudgetTask.Status.FINAL_LOCKED)

    def test_primary_consolidated_rejection_returns_tasks_to_pulled_state(self):
        pull_response = self.client.post(
            reverse('budgetcycle-pull-primary-consolidated', args=[self.cycle.id]),
            {'expense_type': 'opex'},
            format='json',
        )
        self.assertEqual(pull_response.status_code, status.HTTP_201_CREATED)
        primary_book = BudgetBook.objects.get(
            cycle=self.cycle,
            department=self.primary,
            expense_type=BudgetBook.ExpenseType.OPEX,
            source_type=BudgetBook.SourceType.PRIMARY_CONSOLIDATED,
        )
        draft = primary_book.current_draft
        submit_response = self.client.post(reverse('budgetversion-submit', args=[draft.id]), {}, format='json')
        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)
        approval_request = ApprovalRequest.objects.get(id=submit_response.data['approval_request_id'])

        self.client.force_authenticate(self.primary_reviewer)
        reject_response = self.client.post(reverse('approvalrequest-reject', args=[approval_request.id]), {'comment': '补充'}, format='json')

        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)
        approval_request.refresh_from_db()
        primary_book.refresh_from_db()
        draft.refresh_from_db()
        self.cycle.refresh_from_db()
        self.assertEqual(approval_request.status, ApprovalRequest.Status.REJECTED)
        self.assertEqual(draft.status, BudgetVersion.Status.DRAFT)
        self.assertEqual(primary_book.status, BudgetBook.Status.DRAFTING)
        self.assertEqual(self.cycle.status, BudgetCycle.Status.ACTIVE)
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
