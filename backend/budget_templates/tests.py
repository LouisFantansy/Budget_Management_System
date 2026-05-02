from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User
from budget_cycles.models import BudgetCycle
from budgets.models import BudgetBook, BudgetLine, BudgetVersion
from orgs.models import Department

from .models import BudgetTemplate, TemplateField


class TemplateFieldAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='template-admin', password='pass')
        self.secondary_user = User.objects.create_user(username='template-secondary', password='pass')
        RoleAssignment.objects.create(user=self.user, role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN)
        self.department = Department.objects.create(name='Arch', code='Arch-TF', level=Department.Level.SECONDARY)
        RoleAssignment.objects.create(
            user=self.secondary_user,
            role=RoleAssignment.Role.SECONDARY_BUDGET_OWNER,
            department=self.department,
        )
        self.client.force_authenticate(self.user)
        self.cycle = BudgetCycle.objects.create(year=2027, name='2027 年度预算编制')
        self.template = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='OPEX 模板',
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            status=BudgetTemplate.Status.ACTIVE,
        )

    def test_template_fields_are_returned_by_order(self):
        TemplateField.objects.create(template=self.template, code='b', label='B', data_type=TemplateField.DataType.TEXT, order=20)
        TemplateField.objects.create(template=self.template, code='a', label='A', data_type=TemplateField.DataType.TEXT, order=10)

        response = self.client.get(reverse('templatefield-list'), {'template': str(self.template.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['code'] for item in response.data['results']], ['a', 'b'])

    def test_duplicate_template_field_code_is_rejected(self):
        TemplateField.objects.create(template=self.template, code='amount', label='金额', data_type=TemplateField.DataType.MONEY)

        response = self.client.post(
            reverse('templatefield-list'),
            {
                'template': str(self.template.id),
                'code': 'amount',
                'label': '重复金额',
                'data_type': TemplateField.DataType.MONEY,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_primary_budget_admin_can_create_template_field(self):
        response = self.client.post(
            reverse('templatefield-list'),
            {
                'template': str(self.template.id),
                'code': 'purchase_reason',
                'label': '采购原因',
                'data_type': TemplateField.DataType.TEXT,
                'input_type': TemplateField.InputType.TEXT,
                'required': True,
                'order': 30,
                'width': 200,
                'dashboard_enabled': True,
                'approval_included': True,
                'import_aliases': ['采购原因补充', 'purchase_reason'],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        field = TemplateField.objects.get(template=self.template, code='purchase_reason')
        self.assertEqual(field.width, 200)
        self.assertEqual(field.import_aliases, ['采购原因补充', 'purchase_reason'])

    def test_primary_budget_admin_can_create_formula_field(self):
        response = self.client.post(
            reverse('templatefield-list'),
            {
                'template': str(self.template.id),
                'code': 'auto_total',
                'label': '自动总额',
                'data_type': TemplateField.DataType.MONEY,
                'input_type': TemplateField.InputType.FORMULA,
                'formula': 'unit_price * total_quantity',
                'required': False,
                'order': 40,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(TemplateField.objects.filter(template=self.template, code='auto_total').exists())

    def test_formula_field_with_unknown_reference_is_rejected(self):
        response = self.client.post(
            reverse('templatefield-list'),
            {
                'template': str(self.template.id),
                'code': 'bad_formula',
                'label': '坏公式',
                'data_type': TemplateField.DataType.MONEY,
                'input_type': TemplateField.InputType.FORMULA,
                'formula': 'unknown_field * 10',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('formula', response.data)

    def test_select_field_requires_option_source(self):
        response = self.client.post(
            reverse('templatefield-list'),
            {
                'template': str(self.template.id),
                'code': 'project_type',
                'label': '项目类型',
                'data_type': TemplateField.DataType.OPTION,
                'input_type': TemplateField.InputType.SELECT,
                'order': 50,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('option_source', response.data)

    def test_registered_option_source_is_accepted(self):
        response = self.client.post(
            reverse('templatefield-list'),
            {
                'template': str(self.template.id),
                'code': 'cost_center',
                'label': '成本中心',
                'data_type': TemplateField.DataType.OPTION,
                'input_type': TemplateField.InputType.SELECT,
                'option_source': 'masterdata.cost_centers',
                'order': 60,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_unknown_registered_option_source_is_rejected(self):
        response = self.client.post(
            reverse('templatefield-list'),
            {
                'template': str(self.template.id),
                'code': 'bad_source',
                'label': '坏来源',
                'data_type': TemplateField.DataType.OPTION,
                'input_type': TemplateField.InputType.SELECT,
                'option_source': 'masterdata.unknown_source',
                'order': 70,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('option_source', response.data)

    def test_primary_budget_admin_can_update_template_field(self):
        field = TemplateField.objects.create(
            template=self.template,
            code='purchase_reason',
            label='采购原因',
            data_type=TemplateField.DataType.TEXT,
            required=False,
        )

        response = self.client.patch(
            reverse('templatefield-detail', args=[field.id]),
            {'label': '采购必要性', 'required': True, 'width': 220},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        field.refresh_from_db()
        self.assertEqual(field.label, '采购必要性')
        self.assertTrue(field.required)
        self.assertEqual(field.width, 220)

    def test_primary_budget_admin_can_update_field_visibility_rules(self):
        field = TemplateField.objects.create(
            template=self.template,
            code='secret_price',
            label='保密单价',
            data_type=TemplateField.DataType.MONEY,
        )

        response = self.client.patch(
            reverse('templatefield-detail', args=[field.id]),
            {
                'visible_rules': {'visible_to': ['primary']},
                'editable_rules': {'editable_by': ['primary']},
                'dashboard_enabled': True,
                'approval_included': False,
                'frozen': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        field.refresh_from_db()
        self.assertEqual(field.visible_rules, {'visible_to': ['primary']})
        self.assertEqual(field.editable_rules, {'editable_by': ['primary']})
        self.assertTrue(field.dashboard_enabled)
        self.assertFalse(field.approval_included)
        self.assertTrue(field.frozen)

    def test_secondary_budget_owner_cannot_manage_template_field(self):
        self.client.force_authenticate(self.secondary_user)

        response = self.client.post(
            reverse('templatefield-list'),
            {
                'template': str(self.template.id),
                'code': 'blocked_field',
                'label': '无权限字段',
                'data_type': TemplateField.DataType.TEXT,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_secondary_budget_owner_only_sees_visible_template_fields(self):
        visible_field = TemplateField.objects.create(
            template=self.template,
            code='shared_note',
            label='共享说明',
            data_type=TemplateField.DataType.TEXT,
        )
        hidden_field = TemplateField.objects.create(
            template=self.template,
            code='secret_price',
            label='保密单价',
            data_type=TemplateField.DataType.MONEY,
            visible_rules={'visible_to': ['primary']},
        )
        self.client.force_authenticate(self.secondary_user)

        response = self.client.get(reverse('templatefield-list'), {'template': str(self.template.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['code'] for item in response.data['results']], [visible_field.code])
        self.assertNotIn(hidden_field.code, [item['code'] for item in response.data['results']])

    def test_primary_budget_admin_can_delete_template_field(self):
        field = TemplateField.objects.create(
            template=self.template,
            code='temporary_note',
            label='临时说明',
            data_type=TemplateField.DataType.TEXT,
        )

        response = self.client.delete(reverse('templatefield-detail', args=[field.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TemplateField.objects.filter(id=field.id).exists())

    def test_cannot_delete_template_field_when_budget_lines_still_use_it(self):
        field = TemplateField.objects.create(
            template=self.template,
            code='purchase_reason',
            label='采购原因',
            data_type=TemplateField.DataType.TEXT,
        )
        book = BudgetBook.objects.create(
            cycle=self.cycle,
            department=self.department,
            expense_type=BudgetBook.ExpenseType.OPEX,
            template=self.template,
        )
        version = BudgetVersion.objects.create(book=book, status=BudgetVersion.Status.DRAFT)
        BudgetLine.objects.create(
            version=version,
            department=self.department,
            description='使用模板字段的预算行',
            dynamic_data={'purchase_reason': '扩容'},
        )

        response = self.client.delete(reverse('templatefield-detail', args=[field.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(TemplateField.objects.filter(id=field.id).exists())


class BudgetTemplateAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='template-admin', password='pass')
        RoleAssignment.objects.create(user=self.user, role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN)
        self.client.force_authenticate(self.user)
        self.cycle_2026 = BudgetCycle.objects.create(year=2026, name='2026 年度预算编制')
        self.cycle_2027 = BudgetCycle.objects.create(year=2027, name='2027 年度预算编制')
        self.template_2026 = BudgetTemplate.objects.create(
            cycle=self.cycle_2026,
            name='OPEX 模板',
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            schema_version=1,
            status=BudgetTemplate.Status.ACTIVE,
        )
        TemplateField.objects.create(
            template=self.template_2026,
            code='budget_no',
            label='预算编号',
            data_type=TemplateField.DataType.TEXT,
            order=10,
            width=180,
            frozen=True,
            dashboard_enabled=True,
            approval_included=True,
            import_aliases=['预算编号'],
        )
        TemplateField.objects.create(
            template=self.template_2026,
            code='project',
            label='Project',
            data_type=TemplateField.DataType.OPTION,
            input_type=TemplateField.InputType.PROJECT,
            order=20,
            width=200,
            option_source='masterdata.projects',
            dashboard_enabled=True,
            approval_included=False,
            import_aliases=['Project'],
        )
        TemplateField.objects.create(
            template=self.template_2026,
            code='purchase_reason',
            label='采购原因',
            data_type=TemplateField.DataType.TEXT,
            order=30,
            dashboard_enabled=False,
            approval_included=True,
        )

    def test_budget_template_returns_copied_from_name_and_fields(self):
        response = self.client.get(reverse('budgettemplate-detail', args=[self.template_2026.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['schema_version'], 1)
        self.assertEqual(response.data['fields'][0]['code'], 'budget_no')
        self.assertEqual(response.data['fields'][0]['width'], 180)
        self.assertEqual(response.data['fields'][0]['frozen'], True)
        self.assertTrue(response.data['fields'][0]['dashboard_enabled'])
        self.assertFalse(response.data['fields'][1]['approval_included'])

    def test_create_revision_clones_fields_and_increments_schema_version(self):
        response = self.client.post(reverse('budgettemplate-create-revision', args=[self.template_2026.id]), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['schema_version'], 2)
        self.assertEqual(response.data['copied_from'], self.template_2026.id)
        self.assertEqual(response.data['copied_from_name'], self.template_2026.name)
        self.assertEqual(response.data['fields'][0]['code'], 'budget_no')
        self.assertEqual(response.data['fields'][0]['width'], 180)
        self.assertTrue(BudgetTemplate.objects.filter(cycle=self.cycle_2026, expense_type=BudgetTemplate.ExpenseType.OPEX, schema_version=2).exists())
        self.assertEqual(BudgetTemplate.objects.get(id=response.data['id']).status, BudgetTemplate.Status.DRAFT)

    def test_activating_new_template_archives_previous_active_template(self):
        draft = BudgetTemplate.objects.create(
            cycle=self.cycle_2026,
            name='OPEX 模板',
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            schema_version=2,
            status=BudgetTemplate.Status.DRAFT,
        )

        response = self.client.patch(
            reverse('budgettemplate-detail', args=[draft.id]),
            {'status': BudgetTemplate.Status.ACTIVE},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.template_2026.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(draft.status, BudgetTemplate.Status.ACTIVE)
        self.assertEqual(self.template_2026.status, BudgetTemplate.Status.ARCHIVED)

    def test_schema_version_must_be_unique_per_cycle_and_expense_type(self):
        response = self.client.post(
            reverse('budgettemplate-list'),
            {
                'cycle': str(self.cycle_2026.id),
                'name': '重复模板',
                'expense_type': BudgetTemplate.ExpenseType.OPEX,
                'schema_version': 1,
                'status': BudgetTemplate.Status.DRAFT,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue('schema_version' in response.data or 'non_field_errors' in response.data)

    def test_bootstrap_from_previous_cycle_clones_latest_template(self):
        response = self.client.post(
            reverse('budgettemplate-bootstrap-from-previous'),
            {'cycle': str(self.cycle_2027.id)},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_count'], 1)
        cloned = BudgetTemplate.objects.get(cycle=self.cycle_2027, expense_type=BudgetTemplate.ExpenseType.OPEX)
        self.assertEqual(cloned.schema_version, 1)
        self.assertEqual(cloned.copied_from, self.template_2026)
        self.assertEqual(cloned.fields.count(), 3)
        self.assertTrue(cloned.fields.get(code='budget_no').frozen)

    def test_bootstrap_from_previous_cycle_returns_validation_when_previous_missing(self):
        isolated_base_cycle = BudgetCycle.objects.create(year=2024, name='2024 年度预算编制')

        response = self.client.post(
            reverse('budgettemplate-bootstrap-from-previous'),
            {'cycle': str(isolated_base_cycle.id)},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cycle', response.data)
