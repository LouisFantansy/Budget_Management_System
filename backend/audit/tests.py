from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User
from audit.models import AuditLog
from budget_cycles.models import BudgetCycle
from budget_templates.models import BudgetTemplate
from budgets.models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion
from demands.models import DemandSheet, DemandTemplate
from orgs.models import Department


class AuditAndLineageAPITests(APITestCase):
    def setUp(self):
        self.primary = Department.objects.create(name='SS', code='SS', level=Department.Level.PRIMARY)
        self.department = Department.objects.create(
            name='平台软件部',
            code='SW-AUDIT',
            level=Department.Level.SECONDARY,
            parent=self.primary,
        )
        self.ss_public = Department.objects.create(
            name='SS public',
            code='SS_PUBLIC',
            level=Department.Level.SS_PUBLIC,
            parent=self.primary,
        )
        self.owner = User.objects.create_user(username='audit-owner', password='pass')
        self.approver = User.objects.create_user(username='audit-head', password='pass')
        self.primary_admin = User.objects.create_user(username='audit-primary', password='pass')
        RoleAssignment.objects.create(
            user=self.owner,
            role=RoleAssignment.Role.SECONDARY_BUDGET_OWNER,
            department=self.department,
        )
        RoleAssignment.objects.create(
            user=self.approver,
            role=RoleAssignment.Role.SECONDARY_DEPT_HEAD,
            department=self.department,
        )
        RoleAssignment.objects.create(user=self.primary_admin, role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN)
        self.cycle = BudgetCycle.objects.create(year=2032, name='2032 年度预算编制')
        self.template = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='OPEX 模板',
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            status=BudgetTemplate.Status.ACTIVE,
        )
        self.special_template = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='专题模板',
            expense_type=BudgetTemplate.ExpenseType.SPECIAL,
            status=BudgetTemplate.Status.ACTIVE,
        )

    def test_submit_and_approve_create_audit_logs_and_anomaly_notification(self):
        book = BudgetBook.objects.create(
            cycle=self.cycle,
            department=self.department,
            expense_type=BudgetBook.ExpenseType.OPEX,
            template=self.template,
        )
        base = BudgetVersion.objects.create(book=book, version_no=1, status=BudgetVersion.Status.APPROVED)
        book.latest_approved_version = base
        book.save(update_fields=['latest_approved_version', 'updated_at'])
        BudgetLine.objects.create(
            version=base,
            department=self.department,
            line_no=1,
            budget_no='AUDIT-001',
            description='旧条目',
            total_amount='100.00',
        )
        revision = BudgetVersion.objects.create(book=book, base_version=base, status=BudgetVersion.Status.DRAFT)
        book.current_draft = revision
        book.save(update_fields=['current_draft', 'updated_at'])
        line = BudgetLine.objects.create(
            version=revision,
            department=self.department,
            line_no=1,
            budget_no='AUDIT-001',
            description='新条目',
            total_amount='200000.00',
        )
        BudgetMonthlyPlan.objects.create(line=line, month=1, quantity='1.00', amount='200000.00')

        self.client.force_authenticate(self.owner)
        submit_response = self.client.post(reverse('budgetversion-submit', args=[revision.id]), {}, format='json')
        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)

        submit_log = AuditLog.objects.get(action='version_submitted')
        self.assertEqual(submit_log.version_id, revision.id)
        self.assertEqual(submit_log.department, self.department)

        self.client.force_authenticate(self.approver)
        approve_response = self.client.post(
            reverse('approvalrequest-approve', args=[submit_response.data['approval_request_id']]),
            {},
            format='json',
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)

        self.assertTrue(AuditLog.objects.filter(action='approval_approved', version_id=revision.id).exists())
        anomaly_response = self.client.get(reverse('notification-list'), {'category': 'anomaly_alert'})
        self.assertEqual(anomaly_response.status_code, status.HTTP_200_OK)
        self.assertEqual(anomaly_response.data['count'], 1)

    def test_budget_line_lineage_returns_upstream_and_downstream(self):
        source_book = BudgetBook.objects.create(
            cycle=self.cycle,
            department=self.department,
            expense_type=BudgetBook.ExpenseType.OPEX,
            template=self.template,
        )
        approved = BudgetVersion.objects.create(book=source_book, version_no=1, status=BudgetVersion.Status.APPROVED)
        source_line = BudgetLine.objects.create(
            version=approved,
            department=self.department,
            line_no=1,
            budget_no='LINEAGE-001',
            description='源条目',
            total_amount='100.00',
        )

        primary_book = BudgetBook.objects.create(
            cycle=self.cycle,
            department=self.primary,
            expense_type=BudgetBook.ExpenseType.OPEX,
            source_type=BudgetBook.SourceType.PRIMARY_CONSOLIDATED,
            template=self.template,
        )
        draft = BudgetVersion.objects.create(book=primary_book, status=BudgetVersion.Status.DRAFT)
        primary_line = BudgetLine.objects.create(
            version=draft,
            department=self.department,
            line_no=1,
            budget_no='LINEAGE-PRIMARY-001',
            description='汇总条目',
            total_amount='100.00',
            admin_annotations={
                'source_book_id': str(source_book.id),
                'source_version_id': str(approved.id),
                'source_department': self.department.code,
            },
            source_ref_type='budget_version',
            source_ref_id=approved.id,
            editable_by_secondary=False,
        )

        self.client.force_authenticate(self.primary_admin)
        response = self.client.get(reverse('budgetline-lineage', args=[primary_line.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['source']['version_id'], str(approved.id))
        self.assertEqual(response.data['upstreams'][0]['kind'], 'budget_version')
        self.assertEqual(response.data['upstreams'][0]['version_id'], str(approved.id))
        self.assertEqual(response.data['downstreams'], [])
        self.assertEqual(source_line.budget_no, 'LINEAGE-001')

    def test_demand_generation_creates_audit_log(self):
        demand_template = DemandTemplate.objects.create(
            cycle=self.cycle,
            name='专题需求模板',
            expense_type=DemandTemplate.ExpenseType.OPEX,
            status=DemandTemplate.Status.ACTIVE,
            target_mode=DemandTemplate.TargetMode.SECONDARY,
            schema=[
                {'code': 'budget_no', 'label': '预算编号', 'data_type': 'text', 'input_type': 'text', 'required': True, 'order': 1},
                {'code': 'description', 'label': '描述', 'data_type': 'text', 'input_type': 'text', 'required': True, 'order': 2},
                {'code': 'unit_price', 'label': '单价', 'data_type': 'money', 'input_type': 'number', 'required': True, 'order': 3},
                {'code': 'total_quantity', 'label': '数量', 'data_type': 'number', 'input_type': 'number', 'required': True, 'order': 4},
                {'code': 'total_amount', 'label': '金额', 'data_type': 'money', 'input_type': 'number', 'required': True, 'order': 5},
            ],
        )
        sheet = DemandSheet.objects.create(
            template=demand_template,
            target_department=self.department,
            status=DemandSheet.Status.CONFIRMED,
            schema_snapshot=demand_template.schema,
            payload=[
                {
                    'budget_no': 'DEM-AUDIT-001',
                    'description': '专题条目',
                    'unit_price': '10.00',
                    'total_quantity': '2',
                    'total_amount': '20.00',
                }
            ],
        )

        self.client.force_authenticate(self.primary_admin)
        response = self.client.post(reverse('demandsheet-generate-budget-lines', args=[sheet.id]), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(AuditLog.objects.filter(action='demand_budget_generated', target_id=sheet.id).exists())

    def test_audit_logs_list_is_accessible(self):
        AuditLog.objects.create(category='system', action='seeded', target_type='system')
        self.client.force_authenticate(self.primary_admin)

        response = self.client.get(reverse('auditlog-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
