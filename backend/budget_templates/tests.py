from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User
from budget_cycles.models import BudgetCycle

from .models import BudgetTemplate, TemplateField


class TemplateFieldAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='template-admin', password='pass')
        RoleAssignment.objects.create(user=self.user, role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN)
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
