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
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(TemplateField.objects.filter(template=self.template, code='purchase_reason').exists())

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
            {'label': '采购必要性', 'required': True},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        field.refresh_from_db()
        self.assertEqual(field.label, '采购必要性')
        self.assertTrue(field.required)

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
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        field.refresh_from_db()
        self.assertEqual(field.visible_rules, {'visible_to': ['primary']})
        self.assertEqual(field.editable_rules, {'editable_by': ['primary']})

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
