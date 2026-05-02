from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User
from budget_cycles.models import BudgetCycle
from budget_templates.models import BudgetTemplate
from budgets.models import BudgetBook, BudgetLine, BudgetVersion
from orgs.models import Department

from .models import DemandSheet, DemandTemplate


class DemandSheetAPITests(APITestCase):
    def setUp(self):
        self.primary = Department.objects.create(name='SS', code='SS', level=Department.Level.PRIMARY)
        self.ss_public = Department.objects.create(
            name='SS public',
            code='SS_PUBLIC',
            level=Department.Level.SS_PUBLIC,
            parent=self.primary,
        )
        self.arch = Department.objects.create(name='Arch', code='Arch', level=Department.Level.SECONDARY, parent=self.primary)
        self.pve = Department.objects.create(name='PVE', code='PVE', level=Department.Level.SECONDARY, parent=self.primary)
        self.primary_admin = User.objects.create_user(username='primary-demand', password='pass')
        self.arch_owner = User.objects.create_user(username='arch-owner', password='pass')
        self.pve_owner = User.objects.create_user(username='pve-owner', password='pass')
        RoleAssignment.objects.create(user=self.primary_admin, role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN, department=self.primary)
        RoleAssignment.objects.create(
            user=self.arch_owner,
            role=RoleAssignment.Role.SECONDARY_BUDGET_OWNER,
            department=self.arch,
        )
        RoleAssignment.objects.create(
            user=self.pve_owner,
            role=RoleAssignment.Role.SECONDARY_BUDGET_OWNER,
            department=self.pve,
        )
        self.cycle = BudgetCycle.objects.create(year=2032, name='2032 年度预算编制')
        self.special_template = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='专题预算模板',
            expense_type=BudgetTemplate.ExpenseType.SPECIAL,
            status=BudgetTemplate.Status.ACTIVE,
        )
        self.standard_template = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='标准 OPEX 模板',
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            status=BudgetTemplate.Status.ACTIVE,
            schema_version=2,
        )
        self.special_template_v2 = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='专题预算模板 v2',
            expense_type=BudgetTemplate.ExpenseType.SPECIAL,
            status=BudgetTemplate.Status.DRAFT,
            schema_version=2,
        )
        self.demand_template = DemandTemplate.objects.create(
            cycle=self.cycle,
            name='集采软件需求',
            expense_type=DemandTemplate.ExpenseType.OPEX,
            status=DemandTemplate.Status.ACTIVE,
            target_mode=DemandTemplate.TargetMode.SECONDARY,
            target_department=self.primary,
            schema=[{'code': 'description', 'label': '需求描述'}, {'code': 'total_amount', 'label': '总金额'}],
        )

    def test_primary_admin_can_create_template_and_generate_secondary_special_lines(self):
        self.client.force_authenticate(self.primary_admin)
        create_response = self.client.post(
            reverse('demandsheet-list'),
            {
                'template': str(self.demand_template.id),
                'target_department': str(self.arch.id),
                'payload': [
                    {
                        'budget_no': 'DEM-ARCH-001',
                        'description': '年度 IDE License 集采',
                        'total_amount': '860000.00',
                        'unit_price': '4300.00',
                        'total_quantity': '200',
                        'monthly_plans': [{'month': 3, 'amount': '430000.00'}, {'month': 9, 'amount': '430000.00'}],
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        sheet_id = create_response.data['id']
        generate_response = self.client.post(
            reverse('demandsheet-generate-budget-lines', args=[sheet_id]),
            {'confirm': True, 'force_rebuild': True},
            format='json',
        )

        self.assertEqual(generate_response.status_code, status.HTTP_201_CREATED)
        sheet = DemandSheet.objects.get(id=sheet_id)
        book = BudgetBook.objects.get(id=generate_response.data['book_id'])
        line = BudgetLine.objects.get(version=book.current_draft, budget_no='DEM-ARCH-001')
        self.assertEqual(book.source_type, BudgetBook.SourceType.SPECIAL)
        self.assertEqual(book.department, self.arch)
        self.assertEqual(book.template, self.special_template)
        self.assertEqual(line.department, self.arch)
        self.assertEqual(line.source_ref_type, 'demand_sheet')
        self.assertFalse(line.editable_by_secondary)
        self.assertEqual(line.admin_annotations['source_department'], 'Arch')
        self.assertEqual(sheet.status, DemandSheet.Status.GENERATED)
        self.assertEqual(sheet.generated_line_count, 1)
        self.assertEqual(line.monthly_plans.count(), 2)

    def test_ss_public_template_generates_into_ss_public_book(self):
        template = DemandTemplate.objects.create(
            cycle=self.cycle,
            name='SS 公共采购',
            expense_type=DemandTemplate.ExpenseType.OPEX,
            status=DemandTemplate.Status.ACTIVE,
            target_mode=DemandTemplate.TargetMode.SS_PUBLIC,
            target_department=self.ss_public,
        )
        self.client.force_authenticate(self.primary_admin)
        sheet_response = self.client.post(
            reverse('demandsheet-list'),
            {
                'template': str(template.id),
                'target_department': str(self.ss_public.id),
                'payload': [
                    {'description': '统一采购测试平台服务', 'total_amount': '120000.00'},
                ],
            },
            format='json',
        )
        self.assertEqual(sheet_response.status_code, status.HTTP_201_CREATED)

        generate_response = self.client.post(
            reverse('demandsheet-generate-budget-lines', args=[sheet_response.data['id']]),
            {'confirm': True},
            format='json',
        )

        self.assertEqual(generate_response.status_code, status.HTTP_201_CREATED)
        book = BudgetBook.objects.get(id=generate_response.data['book_id'])
        line = book.current_draft.lines.get()
        self.assertEqual(book.department, self.ss_public)
        self.assertEqual(line.department, self.ss_public)

    def test_generate_budget_lines_prefers_latest_active_special_template(self):
        self.special_template.status = BudgetTemplate.Status.ARCHIVED
        self.special_template.save(update_fields=['status'])
        self.special_template_v2.status = BudgetTemplate.Status.ACTIVE
        self.special_template_v2.save(update_fields=['status'])

        self.client.force_authenticate(self.primary_admin)
        create_response = self.client.post(
            reverse('demandsheet-list'),
            {
                'template': str(self.demand_template.id),
                'target_department': str(self.arch.id),
                'payload': [{'description': '新专题条目', 'total_amount': '1000.00'}],
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        generate_response = self.client.post(
            reverse('demandsheet-generate-budget-lines', args=[create_response.data['id']]),
            {'confirm': True, 'force_rebuild': True},
            format='json',
        )

        self.assertEqual(generate_response.status_code, status.HTTP_201_CREATED)
        book = BudgetBook.objects.get(id=generate_response.data['book_id'])
        line = book.current_draft.lines.get()
        self.assertEqual(book.template, self.special_template_v2)
        self.assertEqual(line.admin_annotations['source_department'], 'Arch')
        self.assertEqual(line.admin_annotations['generated_for_department'], 'Arch')

    def test_secondary_owner_cannot_create_ss_public_sheet(self):
        template = DemandTemplate.objects.create(
            cycle=self.cycle,
            name='SS 公共专项',
            expense_type=DemandTemplate.ExpenseType.OPEX,
            status=DemandTemplate.Status.ACTIVE,
            target_mode=DemandTemplate.TargetMode.SS_PUBLIC,
            target_department=self.ss_public,
        )
        self.client.force_authenticate(self.arch_owner)

        response = self.client.post(
            reverse('demandsheet-list'),
            {
                'template': str(template.id),
                'target_department': str(self.ss_public.id),
                'payload': [{'description': '不应允许的 SS public 填报', 'total_amount': '5000.00'}],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_secondary_owner_can_generate_only_own_department_sheet(self):
        sheet = DemandSheet.objects.create(
            template=self.demand_template,
            target_department=self.arch,
            requested_by=self.primary_admin,
            payload=[{'description': '架构工具采购', 'total_amount': '8000.00'}],
        )

        self.client.force_authenticate(self.arch_owner)
        own_response = self.client.post(
            reverse('demandsheet-generate-budget-lines', args=[sheet.id]),
            {'confirm': True},
            format='json',
        )
        self.assertEqual(own_response.status_code, status.HTTP_201_CREATED)

        other_sheet = DemandSheet.objects.create(
            template=self.demand_template,
            target_department=self.pve,
            requested_by=self.primary_admin,
            payload=[{'description': 'PVE 工具采购', 'total_amount': '9000.00'}],
        )
        denied_response = self.client.post(
            reverse('demandsheet-generate-budget-lines', args=[other_sheet.id]),
            {'confirm': True},
            format='json',
        )
        self.assertEqual(denied_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_generate_rebuilds_same_sheet_lines_without_touching_other_sheets(self):
        other_template = DemandTemplate.objects.create(
            cycle=self.cycle,
            name='其他专题',
            expense_type=DemandTemplate.ExpenseType.OPEX,
            status=DemandTemplate.Status.ACTIVE,
            target_mode=DemandTemplate.TargetMode.SECONDARY,
            target_department=self.primary,
        )
        self.client.force_authenticate(self.primary_admin)
        first_sheet = DemandSheet.objects.create(
            template=self.demand_template,
            target_department=self.arch,
            requested_by=self.primary_admin,
            payload=[{'budget_no': 'DEM-1', 'description': '第一次需求', 'total_amount': '1000.00'}],
        )
        second_sheet = DemandSheet.objects.create(
            template=other_template,
            target_department=self.arch,
            requested_by=self.primary_admin,
            payload=[{'budget_no': 'DEM-2', 'description': '第二次需求', 'total_amount': '2000.00'}],
        )
        response_one = self.client.post(reverse('demandsheet-generate-budget-lines', args=[first_sheet.id]), {'confirm': True}, format='json')
        self.assertEqual(response_one.status_code, status.HTTP_201_CREATED)
        response_two = self.client.post(reverse('demandsheet-generate-budget-lines', args=[second_sheet.id]), {'confirm': True, 'force_rebuild': False}, format='json')
        self.assertEqual(response_two.status_code, status.HTTP_201_CREATED)

        first_sheet.payload = [{'budget_no': 'DEM-1B', 'description': '第一次需求更新', 'total_amount': '1800.00'}]
        first_sheet.save(update_fields=['payload', 'updated_at'])
        rebuild_response = self.client.post(
            reverse('demandsheet-generate-budget-lines', args=[first_sheet.id]),
            {'confirm': True, 'force_rebuild': True},
            format='json',
        )
        self.assertEqual(rebuild_response.status_code, status.HTTP_201_CREATED)
        book = BudgetBook.objects.get(id=rebuild_response.data['book_id'])
        draft = book.current_draft
        self.assertTrue(draft.lines.filter(budget_no='DEM-1B').exists())
        self.assertTrue(draft.lines.filter(budget_no='DEM-2').exists())
        self.assertFalse(draft.lines.filter(budget_no='DEM-1').exists())

    def test_locked_special_lines_cannot_be_modified_by_secondary(self):
        book = BudgetBook.objects.create(
            cycle=self.cycle,
            department=self.arch,
            expense_type=BudgetBook.ExpenseType.OPEX,
            source_type=BudgetBook.SourceType.SPECIAL,
            template=self.standard_template,
        )
        version = BudgetVersion.objects.create(book=book, status=BudgetVersion.Status.DRAFT)
        book.current_draft = version
        book.save(update_fields=['current_draft'])
        line = BudgetLine.objects.create(
            version=version,
            line_no=1,
            budget_no='LOCK-001',
            department=self.arch,
            description='锁定专题条目',
            total_amount='1000.00',
            editable_by_secondary=False,
            source_ref_type='demand_sheet',
        )
        self.client.force_authenticate(self.arch_owner)

        patch_response = self.client.patch(
            reverse('budgetline-detail', args=[line.id]),
            {'description': '非法修改专题条目'},
            format='json',
        )

        self.assertEqual(patch_response.status_code, status.HTTP_400_BAD_REQUEST)
        line.refresh_from_db()
        self.assertEqual(line.description, '锁定专题条目')
