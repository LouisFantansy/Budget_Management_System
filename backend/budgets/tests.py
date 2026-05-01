from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User
from approvals.models import ApprovalRequest, ApprovalStep
from budget_cycles.models import BudgetCycle
from budget_templates.models import BudgetTemplate, TemplateField
from orgs.models import Department

from .models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion


class BudgetApprovalFlowAPITests(APITestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name='平台软件部',
            code='SW',
            level=Department.Level.SECONDARY,
        )
        self.requester = User.objects.create_user(username='budget-owner', password='pass')
        self.approver = User.objects.create_user(username='dept-head', password='pass')
        RoleAssignment.objects.create(
            user=self.requester,
            role=RoleAssignment.Role.SECONDARY_BUDGET_OWNER,
            department=self.department,
        )
        RoleAssignment.objects.create(
            user=self.approver,
            role=RoleAssignment.Role.SECONDARY_DEPT_HEAD,
            department=self.department,
        )
        self.cycle = BudgetCycle.objects.create(year=2027, name='2027 年度预算编制')
        self.template = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='OPEX 模板',
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            status=BudgetTemplate.Status.ACTIVE,
        )
        self.book = BudgetBook.objects.create(
            cycle=self.cycle,
            department=self.department,
            expense_type=BudgetBook.ExpenseType.OPEX,
            template=self.template,
        )
        self.version = BudgetVersion.objects.create(book=self.book)
        self.book.current_draft = self.version
        self.book.save(update_fields=['current_draft'])
        self.line = BudgetLine.objects.create(
            version=self.version,
            department=self.department,
            line_no=1,
            budget_no='OPEX-001',
            description='研发云测试资源',
            total_amount='120000.00',
        )

    def test_submit_budget_version_creates_approval_request(self):
        self.client.force_authenticate(self.requester)

        response = self.client.post(
            reverse('budgetversion-submit', args=[self.version.id]),
            {'comment': '提交二级负责人审批'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.version.refresh_from_db()
        self.book.refresh_from_db()
        approval_request = ApprovalRequest.objects.get(id=response.data['approval_request_id'])
        self.assertEqual(self.version.status, BudgetVersion.Status.SUBMITTED)
        self.assertEqual(self.version.submitted_by, self.requester)
        self.assertEqual(self.book.status, BudgetBook.Status.REVIEWING)
        self.assertEqual(approval_request.target_id, self.version.id)
        self.assertEqual(approval_request.steps.count(), 1)
        self.assertEqual(approval_request.steps.get().approver, self.approver)

    def test_approving_request_promotes_submitted_version_to_v1(self):
        approval_request = self._submit_version()
        self.client.force_authenticate(self.approver)

        response = self.client.post(
            reverse('approvalrequest-approve', args=[approval_request.id]),
            {'comment': '同意'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.version.refresh_from_db()
        self.book.refresh_from_db()
        approval_request.refresh_from_db()
        step = approval_request.steps.get()
        self.assertEqual(approval_request.status, ApprovalRequest.Status.APPROVED)
        self.assertEqual(approval_request.submitted_version_label, 'V1')
        self.assertEqual(step.action, ApprovalStep.Action.APPROVED)
        self.assertEqual(self.version.status, BudgetVersion.Status.APPROVED)
        self.assertEqual(self.version.version_no, 1)
        self.assertEqual(self.version.approved_by, self.approver)
        self.assertEqual(self.book.status, BudgetBook.Status.APPROVED)
        self.assertEqual(self.book.latest_approved_version, self.version)
        self.assertIsNone(self.book.current_draft)

    def test_rejecting_request_returns_version_to_draft(self):
        approval_request = self._submit_version()
        self.client.force_authenticate(self.approver)

        response = self.client.post(
            reverse('approvalrequest-reject', args=[approval_request.id]),
            {'comment': '补充说明'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.version.refresh_from_db()
        self.book.refresh_from_db()
        approval_request.refresh_from_db()
        self.assertEqual(approval_request.status, ApprovalRequest.Status.REJECTED)
        self.assertEqual(self.version.status, BudgetVersion.Status.DRAFT)
        self.assertIsNone(self.version.submitted_by)
        self.assertEqual(self.book.status, BudgetBook.Status.DRAFTING)
        self.assertEqual(self.book.current_draft, self.version)

    def test_non_step_approver_cannot_approve_request(self):
        approval_request = self._submit_version()
        outsider = User.objects.create_user(username='outsider', password='pass')
        self.client.force_authenticate(outsider)

        response = self.client.post(reverse('approvalrequest-approve', args=[approval_request.id]), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.version.refresh_from_db()
        approval_request.refresh_from_db()
        self.assertEqual(self.version.status, BudgetVersion.Status.SUBMITTED)
        self.assertEqual(approval_request.status, ApprovalRequest.Status.PENDING)

    def test_approved_request_cannot_be_rejected_again(self):
        approval_request = self._submit_version()
        self.client.force_authenticate(self.approver)
        approve_response = self.client.post(reverse('approvalrequest-approve', args=[approval_request.id]), {}, format='json')
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)

        reject_response = self.client.post(reverse('approvalrequest-reject', args=[approval_request.id]), {}, format='json')

        self.assertEqual(reject_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.version.refresh_from_db()
        approval_request.refresh_from_db()
        self.assertEqual(self.version.status, BudgetVersion.Status.APPROVED)
        self.assertEqual(approval_request.status, ApprovalRequest.Status.APPROVED)

    def test_submitted_version_cannot_be_submitted_twice(self):
        self._submit_version()
        self.client.force_authenticate(self.requester)

        response = self.client.post(reverse('budgetversion-submit', args=[self.version.id]), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ApprovalRequest.objects.count(), 1)

    def test_submit_is_blocked_when_line_has_missing_required_dynamic_fields(self):
        TemplateField.objects.create(
            template=self.template,
            code='purchase_reason',
            label='采购原因',
            data_type=TemplateField.DataType.TEXT,
            required=True,
        )
        self.client.force_authenticate(self.requester)

        response = self.client.post(reverse('budgetversion-submit', args=[self.version.id]), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], '当前 Draft 存在未完成字段，不能送审。')
        self.assertIn(str(self.line.id), response.data['lines'])
        self.assertEqual(response.data['lines'][str(self.line.id)]['budget_no'], 'OPEX-001')
        self.assertEqual(response.data['lines'][str(self.line.id)]['dynamic_data']['purchase_reason'], '该字段必填。')

    def test_submitted_or_approved_version_lines_are_not_mutable(self):
        self._submit_version()
        self.client.force_authenticate(self.requester)

        patch_response = self.client.patch(
            reverse('budgetline-detail', args=[self.line.id]),
            {'description': '非法修改'},
            format='json',
        )
        create_response = self.client.post(
            reverse('budgetline-list'),
            {
                'version': str(self.version.id),
                'department': str(self.department.id),
                'description': '新增非法条目',
            },
            format='json',
        )
        delete_response = self.client.delete(reverse('budgetline-detail', args=[self.line.id]))

        self.assertEqual(patch_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(delete_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.line.refresh_from_db()
        self.assertEqual(self.line.description, '研发云测试资源')

    def test_submitted_or_approved_version_monthly_plans_are_not_mutable(self):
        monthly_plan = BudgetMonthlyPlan.objects.create(line=self.line, month=1, amount='10000.00')
        self._submit_version()
        self.client.force_authenticate(self.requester)

        patch_response = self.client.patch(
            reverse('budgetmonthlyplan-detail', args=[monthly_plan.id]),
            {'amount': '20000.00'},
            format='json',
        )
        create_response = self.client.post(
            reverse('budgetmonthlyplan-list'),
            {
                'line': str(self.line.id),
                'month': 2,
                'amount': '10000.00',
            },
            format='json',
        )
        delete_response = self.client.delete(reverse('budgetmonthlyplan-detail', args=[monthly_plan.id]))

        self.assertEqual(patch_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(delete_response.status_code, status.HTTP_400_BAD_REQUEST)
        monthly_plan.refresh_from_db()
        self.assertEqual(str(monthly_plan.amount), '10000.00')

    def test_draft_version_allows_line_create_update_and_monthly_plan_create(self):
        self.client.force_authenticate(self.requester)

        create_response = self.client.post(
            reverse('budgetline-list'),
            {
                'version': str(self.version.id),
                'department': str(self.department.id),
                'line_no': 2,
                'budget_no': 'OPEX-002',
                'description': '新增 Draft 条目',
                'unit_price': '2000.00',
                'total_quantity': '3.00',
                'total_amount': '6000.00',
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        line_id = create_response.data['id']
        patch_response = self.client.patch(
            reverse('budgetline-detail', args=[line_id]),
            {'description': '更新 Draft 条目', 'total_amount': '9000.00'},
            format='json',
        )
        plan_response = self.client.post(
            reverse('budgetmonthlyplan-list'),
            {
                'line': line_id,
                'month': 1,
                'quantity': '3.00',
                'amount': '9000.00',
            },
            format='json',
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(plan_response.status_code, status.HTTP_201_CREATED)
        line = BudgetLine.objects.get(id=line_id)
        self.assertEqual(line.description, '更新 Draft 条目')
        self.assertEqual(str(line.total_amount), '9000.00')
        self.assertEqual(line.monthly_plans.count(), 1)

    def test_template_dynamic_required_field_is_enforced_on_create(self):
        TemplateField.objects.create(
            template=self.template,
            code='purchase_reason',
            label='采购原因',
            data_type=TemplateField.DataType.TEXT,
            required=True,
        )
        self.client.force_authenticate(self.requester)

        response = self.client.post(
            reverse('budgetline-list'),
            {
                'version': str(self.version.id),
                'department': str(self.department.id),
                'description': '缺少动态必填字段',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['dynamic_data']['purchase_reason'], '该字段必填。')

    def test_template_dynamic_type_errors_are_reported_by_field(self):
        TemplateField.objects.create(
            template=self.template,
            code='estimated_price',
            label='预估单价',
            data_type=TemplateField.DataType.MONEY,
            required=True,
        )
        TemplateField.objects.create(
            template=self.template,
            code='need_date',
            label='需要日期',
            data_type=TemplateField.DataType.DATE,
        )
        self.client.force_authenticate(self.requester)

        response = self.client.post(
            reverse('budgetline-list'),
            {
                'version': str(self.version.id),
                'department': str(self.department.id),
                'description': '类型错误',
                'dynamic_data': {'estimated_price': 'not-a-number', 'need_date': '2027-99-99'},
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('estimated_price', response.data['dynamic_data'])
        self.assertIn('need_date', response.data['dynamic_data'])

    def test_patch_merges_dynamic_data_before_template_validation(self):
        TemplateField.objects.create(
            template=self.template,
            code='purchase_reason',
            label='采购原因',
            data_type=TemplateField.DataType.TEXT,
            required=True,
        )
        TemplateField.objects.create(
            template=self.template,
            code='estimated_price',
            label='预估单价',
            data_type=TemplateField.DataType.MONEY,
            required=True,
        )
        self.line.dynamic_data = {'purchase_reason': '扩容', 'estimated_price': '1000.00'}
        self.line.save(update_fields=['dynamic_data'])
        self.client.force_authenticate(self.requester)

        response = self.client.patch(
            reverse('budgetline-detail', args=[self.line.id]),
            {'dynamic_data': {'estimated_price': '1200.00'}},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.line.refresh_from_db()
        self.assertEqual(self.line.dynamic_data['purchase_reason'], '扩容')
        self.assertEqual(self.line.dynamic_data['estimated_price'], '1200.00')

    def test_dashboard_summary_uses_current_draft_when_requested(self):
        BudgetLine.objects.create(
            version=self.version,
            department=self.department,
            line_no=2,
            budget_no='OPEX-002',
            description='第二条',
            total_amount='30000.00',
        )
        self.client.force_authenticate(self.requester)

        response = self.client.get(
            reverse('budgetbook-dashboard-summary', args=[self.book.id]),
            {'version_context': 'current_draft'},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['line_count'], 2)
        self.assertEqual(str(response.data['total_amount']), '150000')

    def test_create_revision_draft_copies_approved_version_snapshot(self):
        BudgetMonthlyPlan.objects.create(line=self.line, month=1, quantity='1.00', amount='120000.00')
        approval_request = self._submit_version()
        self.client.force_authenticate(self.approver)
        approve_response = self.client.post(reverse('approvalrequest-approve', args=[approval_request.id]), {}, format='json')
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.requester)

        response = self.client.post(reverse('budgetbook-create-revision', args=[self.book.id]), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.book.refresh_from_db()
        draft = BudgetVersion.objects.get(id=response.data['id'])
        copied_line = draft.lines.get()
        self.assertEqual(draft.status, BudgetVersion.Status.DRAFT)
        self.assertEqual(draft.base_version, self.version)
        self.assertEqual(self.book.current_draft, draft)
        self.assertEqual(self.book.latest_approved_version, self.version)
        self.assertEqual(copied_line.description, self.line.description)
        self.assertEqual(copied_line.monthly_plans.count(), 1)
        self.line.refresh_from_db()
        self.assertEqual(self.line.version.status, BudgetVersion.Status.APPROVED)

    def test_revision_draft_can_be_approved_as_v2(self):
        approval_request = self._submit_version()
        self.client.force_authenticate(self.approver)
        approve_response = self.client.post(reverse('approvalrequest-approve', args=[approval_request.id]), {}, format='json')
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.requester)
        revision_response = self.client.post(reverse('budgetbook-create-revision', args=[self.book.id]), {}, format='json')
        self.assertEqual(revision_response.status_code, status.HTTP_201_CREATED)
        revision_id = revision_response.data['id']

        submit_response = self.client.post(reverse('budgetversion-submit', args=[revision_id]), {}, format='json')
        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(self.approver)
        second_approval = self.client.post(
            reverse('approvalrequest-approve', args=[submit_response.data['approval_request_id']]),
            {},
            format='json',
        )

        self.assertEqual(second_approval.status_code, status.HTTP_200_OK)
        revision = BudgetVersion.objects.get(id=revision_id)
        self.book.refresh_from_db()
        self.assertEqual(revision.status, BudgetVersion.Status.APPROVED)
        self.assertEqual(revision.version_no, 2)
        self.assertEqual(self.book.latest_approved_version, revision)
        self.assertIsNone(self.book.current_draft)

    def test_version_diff_detects_added_deleted_modified_and_monthly_changes(self):
        second_line = BudgetLine.objects.create(
            version=self.version,
            department=self.department,
            line_no=2,
            budget_no='OPEX-DELETE',
            description='待删除条目',
            total_amount='5000.00',
        )
        BudgetMonthlyPlan.objects.create(line=self.line, month=1, quantity='1.00', amount='120000.00')
        approval_request = self._submit_version()
        self.client.force_authenticate(self.approver)
        approve_response = self.client.post(reverse('approvalrequest-approve', args=[approval_request.id]), {}, format='json')
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.requester)
        revision_response = self.client.post(reverse('budgetbook-create-revision', args=[self.book.id]), {}, format='json')
        revision = BudgetVersion.objects.get(id=revision_response.data['id'])

        modified_line = revision.lines.get(budget_no='OPEX-001')
        modified_line.description = '研发云测试资源 - 扩容'
        modified_line.total_amount = '150000.00'
        modified_line.save(update_fields=['description', 'total_amount'])
        modified_plan = modified_line.monthly_plans.get(month=1)
        modified_plan.amount = '150000.00'
        modified_plan.save(update_fields=['amount'])
        revision.lines.get(budget_no=second_line.budget_no).delete()
        BudgetLine.objects.create(
            version=revision,
            department=self.department,
            line_no=3,
            budget_no='OPEX-ADD',
            description='新增条目',
            total_amount='7000.00',
        )

        response = self.client.get(
            reverse('budgetversion-diff', args=[revision.id]),
            {'base_version': str(self.version.id)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary'], {'added': 1, 'deleted': 1, 'modified': 1, 'total_changes': 3})
        changes_by_type = {change['type']: change for change in response.data['changes']}
        self.assertEqual(changes_by_type['added']['budget_no'], 'OPEX-ADD')
        self.assertEqual(changes_by_type['deleted']['budget_no'], 'OPEX-DELETE')
        self.assertEqual(changes_by_type['modified']['budget_no'], 'OPEX-001')
        modified_fields = {change['field']: change for change in changes_by_type['modified']['field_changes']}
        self.assertEqual(modified_fields['description']['old'], '研发云测试资源')
        self.assertEqual(modified_fields['total_amount']['delta'], '30000.00')
        self.assertEqual(changes_by_type['modified']['monthly_changes'][0]['amount_delta'], '30000.00')

    def test_cannot_create_revision_when_current_draft_exists(self):
        self.client.force_authenticate(self.requester)

        response = self.client.post(reverse('budgetbook-create-revision', args=[self.book.id]), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def _submit_version(self):
        self.client.force_authenticate(self.requester)
        response = self.client.post(reverse('budgetversion-submit', args=[self.version.id]), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return ApprovalRequest.objects.get(id=response.data['approval_request_id'])


class SeedDemoCommandTests(APITestCase):
    def test_seed_demo_is_idempotent_and_creates_complex_states(self):
        call_command('seed_demo', verbosity=0)
        call_command('seed_demo', verbosity=0)

        statuses = sorted(BudgetVersion.objects.values_list('status', flat=True))
        secondary_departments = set(
            Department.objects.filter(level=Department.Level.SECONDARY).values_list('code', flat=True)
        )
        self.assertEqual(BudgetBook.objects.count(), 4)
        self.assertEqual(Department.objects.get(code='SS').name, 'SS')
        self.assertEqual(
            secondary_departments,
            {'Arch', 'PVE', 'PE', 'STE', 'PHE', 'FTE', 'cSSD_FW', 'eSSD_FW', 'Embedded_FW', 'PDT'},
        )
        self.assertEqual(statuses, ['approved', 'approved', 'draft', 'draft', 'submitted'])
        self.assertEqual(BudgetVersion.objects.exclude(base_version=None).count(), 1)
        self.assertEqual(ApprovalRequest.objects.filter(status=ApprovalRequest.Status.PENDING).count(), 1)


class BudgetDataScopeAPITests(APITestCase):
    def setUp(self):
        self.software = Department.objects.create(name='平台软件部', code='SW-SCOPE', level=Department.Level.SECONDARY)
        self.hardware = Department.objects.create(name='硬件系统部', code='HW-SCOPE', level=Department.Level.SECONDARY)
        self.software_user = User.objects.create_user(username='software-user', password='pass')
        self.primary_user = User.objects.create_user(username='scope-primary-user', password='pass')
        RoleAssignment.objects.create(
            user=self.software_user,
            role=RoleAssignment.Role.SECONDARY_BUDGET_OWNER,
            department=self.software,
        )
        RoleAssignment.objects.create(
            user=self.primary_user,
            role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN,
        )
        self.cycle = BudgetCycle.objects.create(year=2028, name='2028 年度预算编制')
        self.template = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='OPEX 模板',
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            status=BudgetTemplate.Status.ACTIVE,
        )
        self.software_book = self._book(self.software)
        self.hardware_book = self._book(self.hardware)
        ApprovalRequest.objects.create(
            target_type='budget_version',
            target_id=self.software_book.latest_approved_version_id,
            title='软件审批',
            requester=self.software_user,
            department=self.software,
        )
        ApprovalRequest.objects.create(
            target_type='budget_version',
            target_id=self.hardware_book.latest_approved_version_id,
            title='硬件审批',
            requester=self.software_user,
            department=self.hardware,
        )

    def test_secondary_user_only_lists_own_department_budget_books(self):
        self.client.force_authenticate(self.software_user)

        response = self.client.get(reverse('budgetbook-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.software_book.id))

    def test_primary_user_lists_all_budget_books(self):
        self.client.force_authenticate(self.primary_user)

        response = self.client.get(reverse('budgetbook-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_secondary_user_only_lists_own_department_approval_requests(self):
        self.client.force_authenticate(self.software_user)

        response = self.client.get(reverse('approvalrequest-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], '软件审批')

    def test_secondary_user_cannot_create_line_for_other_department_book(self):
        self.client.force_authenticate(self.software_user)
        hardware_version = self.hardware_book.latest_approved_version
        hardware_version.status = BudgetVersion.Status.DRAFT
        hardware_version.save(update_fields=['status'])

        response = self.client.post(
            reverse('budgetline-list'),
            {
                'version': str(hardware_version.id),
                'department': str(self.hardware.id),
                'description': '越权新增',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(BudgetLine.objects.filter(description='越权新增').count(), 0)

    def test_secondary_user_cannot_submit_other_department_version(self):
        self.client.force_authenticate(self.software_user)
        hardware_version = self.hardware_book.latest_approved_version
        hardware_version.status = BudgetVersion.Status.DRAFT
        hardware_version.save(update_fields=['status'])

        response = self.client.post(reverse('budgetversion-submit', args=[hardware_version.id]), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_budget_editor_without_approver_role_cannot_approve_even_if_scoped(self):
        approval = ApprovalRequest.objects.get(title='软件审批')
        self.client.force_authenticate(self.software_user)

        response = self.client.post(reverse('approvalrequest-approve', args=[approval.id]), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        approval.refresh_from_db()
        self.assertEqual(approval.status, ApprovalRequest.Status.PENDING)

    def _book(self, department):
        book = BudgetBook.objects.create(
            cycle=self.cycle,
            department=department,
            expense_type=BudgetBook.ExpenseType.OPEX,
            template=self.template,
            status=BudgetBook.Status.APPROVED,
        )
        version = BudgetVersion.objects.create(book=book, status=BudgetVersion.Status.APPROVED, version_no=1)
        BudgetLine.objects.create(
            version=version,
            department=department,
            budget_no=f'{department.code}-001',
            description='Scoped line',
            total_amount='1000.00',
        )
        book.latest_approved_version = version
        book.save(update_fields=['latest_approved_version', 'updated_at'])
        return book
