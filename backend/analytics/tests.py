from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User
from budget_cycles.models import BudgetCycle
from budget_templates.models import BudgetTemplate
from budgets.models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion
from masterdata.models import Category, ProductLine, Project, ProjectCategory
from orgs.models import Department

from .models import DashboardConfig


class DashboardOverviewAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dashboard-user', password='pass')
        self.primary_user = User.objects.create_user(username='primary-user', password='pass')
        self.client.force_authenticate(self.user)
        self.cycle = BudgetCycle.objects.create(year=2027, name='2027 年度预算编制')
        self.opex_template = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='OPEX 模板',
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            status=BudgetTemplate.Status.ACTIVE,
        )
        self.capex_template = BudgetTemplate.objects.create(
            cycle=self.cycle,
            name='CAPEX 模板',
            expense_type=BudgetTemplate.ExpenseType.CAPEX,
            status=BudgetTemplate.Status.ACTIVE,
        )
        self.software = Department.objects.create(name='平台软件部', code='SW', level=Department.Level.SECONDARY)
        self.hardware = Department.objects.create(name='硬件系统部', code='HW', level=Department.Level.SECONDARY)
        RoleAssignment.objects.create(
            user=self.user,
            role=RoleAssignment.Role.SECONDARY_BUDGET_OWNER,
            department=self.software,
        )
        RoleAssignment.objects.create(
            user=self.primary_user,
            role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN,
        )
        self.cloud = Category.objects.create(code='CLOUD', name='Cloud Service', level=Category.Level.CATEGORY)
        self.server = Category.objects.create(code='SERVER', name='Server', level=Category.Level.CATEGORY)
        self.platform_category = ProjectCategory.objects.create(code='PLATFORM', name='平台项目')
        self.device_category = ProjectCategory.objects.create(code='DEVICE', name='设备项目')
        self.enterprise_line = ProductLine.objects.create(code='ENTERPRISE', name='企业盘')
        self.client_line = ProductLine.objects.create(code='CLIENT', name='客户端')
        self.td_project = Project.objects.create(
            code='TD',
            name='TD 项目',
            project_category=self.platform_category,
            product_line=self.enterprise_line,
        )
        self.lab_project = Project.objects.create(
            code='LAB',
            name='实验室升级',
            project_category=self.device_category,
            product_line=self.client_line,
        )

        self._book_with_version(
            self.software,
            self.cloud,
            approved_amount='1000.00',
            draft_amount='1500.00',
            expense_type=BudgetBook.ExpenseType.OPEX,
            template=self.opex_template,
            project=self.td_project,
            project_category=self.platform_category,
            product_line=self.enterprise_line,
        )
        self._book_with_version(
            self.hardware,
            self.server,
            approved_amount='2000.00',
            draft_amount=None,
            expense_type=BudgetBook.ExpenseType.CAPEX,
            template=self.capex_template,
            project=self.lab_project,
            project_category=self.device_category,
            product_line=self.client_line,
            month=2,
        )
        self._book_with_version(
            self.software,
            self.server,
            approved_amount='500.00',
            draft_amount=None,
            expense_type=BudgetBook.ExpenseType.CAPEX,
            template=self.capex_template,
            project=None,
            project_category=None,
            product_line=None,
            month=3,
            budget_no='SW-CAPEX',
        )

    def test_budget_overview_uses_latest_approved_by_default(self):
        self.client.force_authenticate(self.primary_user)
        response = self.client.get(reverse('dashboardconfig-budget-overview'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['version_context'], 'latest_approved')
        self.assertEqual(response.data['expense_type'], '')
        self.assertEqual(response.data['line_count'], 3)
        self.assertEqual(response.data['total_amount'], '3500')
        self.assertEqual(response.data['by_department'][0]['department_name'], '硬件系统部')
        self.assertEqual(response.data['by_department'][0]['total_amount'], '2000')
        categories = {row['category_name']: row['total_amount'] for row in response.data['by_category']}
        self.assertEqual(categories, {'Cloud Service': '1000', 'Server': '2500'})
        projects = {row['project_name']: row['total_amount'] for row in response.data['by_project']}
        self.assertEqual(projects, {'实验室升级': '2000', 'TD 项目': '1000', '未关联项目': '500'})
        project_categories = {
            row['project_category_name']: row['total_amount'] for row in response.data['by_project_category']
        }
        self.assertEqual(project_categories, {'平台项目': '1000', '设备项目': '2000', '未分类项目': '500'})
        product_lines = {row['product_line_name']: row['total_amount'] for row in response.data['by_product_line']}
        self.assertEqual(product_lines, {'企业盘': '1000', '客户端': '2000', '未关联产品线': '500'})
        expense_types = {row['expense_type']: row['total_amount'] for row in response.data['by_expense_type']}
        self.assertEqual(expense_types, {'capex': '2500', 'opex': '1000'})
        monthly = {row['month']: row['amount'] for row in response.data['monthly']}
        self.assertEqual(monthly, {1: '1000', 2: '2000', 3: '500'})

    def test_budget_overview_can_use_current_draft_context(self):
        response = self.client.get(reverse('dashboardconfig-budget-overview'), {'version_context': 'current_draft'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['version_context'], 'current_draft')
        self.assertEqual(response.data['line_count'], 1)
        self.assertEqual(response.data['total_amount'], '1500')
        self.assertEqual(response.data['by_department'][0]['department_name'], '平台软件部')
        self.assertEqual(response.data['monthly'][0]['amount'], '1500')

    def test_budget_overview_supports_expense_type_filter(self):
        self.client.force_authenticate(self.primary_user)

        response = self.client.get(reverse('dashboardconfig-budget-overview'), {'expense_type': 'capex'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['expense_type'], 'capex')
        self.assertEqual(response.data['line_count'], 2)
        self.assertEqual(response.data['total_amount'], '2500')
        self.assertEqual(len(response.data['by_expense_type']), 1)
        self.assertEqual(response.data['by_expense_type'][0]['expense_type'], 'capex')

    def test_secondary_user_only_sees_scoped_department_in_dashboard(self):
        response = self.client.get(reverse('dashboardconfig-budget-overview'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['line_count'], 2)
        self.assertEqual(response.data['total_amount'], '1500')
        self.assertEqual(response.data['by_department'][0]['department_name'], '平台软件部')

    def test_secondary_user_can_focus_authorized_department(self):
        response = self.client.get(
            reverse('dashboardconfig-budget-overview'),
            {'focus_department_id': str(self.software.id)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['line_count'], 2)
        self.assertEqual(response.data['by_department'][0]['department_name'], '平台软件部')

    def test_secondary_user_cannot_focus_other_department(self):
        response = self.client.get(
            reverse('dashboardconfig-budget-overview'),
            {'focus_department_id': str(self.hardware.id)},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('focus_department_id', response.data)

    def test_dashboard_drilldown_returns_rows_for_dimension(self):
        self.client.force_authenticate(self.primary_user)

        response = self.client.get(
            reverse('dashboardconfig-budget-drilldown'),
            {'dimension': 'project_category', 'value': str(self.platform_category.id)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dimension'], 'project_category')
        self.assertEqual(response.data['line_count'], 1)
        self.assertEqual(response.data['total_amount'], '1000')
        self.assertEqual(response.data['rows'][0]['project_name'], 'TD 项目')
        self.assertEqual(response.data['rows'][0]['expense_type'], 'opex')

    def test_dashboard_drilldown_supports_null_bucket(self):
        self.client.force_authenticate(self.primary_user)

        response = self.client.get(
            reverse('dashboardconfig-budget-drilldown'),
            {'dimension': 'project', 'value': '__none__'},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['line_count'], 1)
        self.assertEqual(response.data['rows'][0]['project_name'], '未关联项目')

    def test_dashboard_drilldown_supports_month_dimension(self):
        self.client.force_authenticate(self.primary_user)

        response = self.client.get(
            reverse('dashboardconfig-budget-drilldown'),
            {'dimension': 'month', 'value': '3'},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['line_count'], 1)
        self.assertEqual(response.data['rows'][0]['budget_no'], 'SW-CAPEX')

    def test_dashboard_drilldown_rejects_invalid_dimension(self):
        self.client.force_authenticate(self.primary_user)

        response = self.client.get(
            reverse('dashboardconfig-budget-drilldown'),
            {'dimension': 'invalid', 'value': 'x'},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('dimension', response.data)

    def test_anonymous_user_gets_empty_dashboard_scope(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse('dashboardconfig-budget-overview'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['line_count'], 0)
        self.assertEqual(response.data['total_amount'], '0')

    def test_user_can_create_personal_dashboard_config(self):
        response = self.client.post(
            reverse('dashboardconfig-list'),
            {
                'name': '我的 Draft 看板',
                'scope': DashboardConfig.Scope.PERSONAL,
                'version_context': 'current_draft',
                'config': {
                    'focus_department_id': str(self.software.id),
                    'expense_type': 'opex',
                },
                'is_default': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        config = DashboardConfig.objects.get(id=response.data['id'])
        self.assertEqual(config.owner, self.user)
        self.assertEqual(config.config['focus_department_id'], str(self.software.id))
        self.assertEqual(config.config['expense_type'], 'opex')
        self.assertTrue(config.is_default)

    def test_dashboard_config_rejects_invalid_expense_type(self):
        response = self.client.post(
            reverse('dashboardconfig-list'),
            {
                'name': '错误口径',
                'scope': DashboardConfig.Scope.PERSONAL,
                'version_context': 'latest_approved',
                'config': {'expense_type': 'special'},
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('config', response.data)

    def test_department_scope_requires_accessible_department(self):
        response = self.client.post(
            reverse('dashboardconfig-list'),
            {
                'name': '硬件共享',
                'scope': DashboardConfig.Scope.DEPARTMENT,
                'department': str(self.hardware.id),
                'version_context': 'latest_approved',
                'config': {},
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('department', response.data)

    def test_only_global_user_can_create_global_dashboard_config(self):
        response = self.client.post(
            reverse('dashboardconfig-list'),
            {
                'name': '全局视图',
                'scope': DashboardConfig.Scope.GLOBAL,
                'version_context': 'latest_approved',
                'config': {},
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('scope', response.data)

    def test_default_dashboard_config_is_unique_per_owner_scope(self):
        first = DashboardConfig.objects.create(
            name='默认 A',
            owner=self.user,
            scope=DashboardConfig.Scope.PERSONAL,
            version_context='latest_approved',
            is_default=True,
        )

        response = self.client.post(
            reverse('dashboardconfig-list'),
            {
                'name': '默认 B',
                'scope': DashboardConfig.Scope.PERSONAL,
                'version_context': 'current_draft',
                'config': {'focus_department_id': str(self.software.id)},
                'is_default': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        first.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(DashboardConfig.objects.get(id=response.data['id']).is_default)

    def test_apply_dashboard_config_returns_filtered_overview(self):
        dashboard_config = DashboardConfig.objects.create(
            name='软件 Draft OPEX',
            owner=self.user,
            scope=DashboardConfig.Scope.PERSONAL,
            version_context='current_draft',
            config={'focus_department_id': str(self.software.id), 'expense_type': 'opex'},
        )

        response = self.client.get(reverse('dashboardconfig-apply', args=[dashboard_config.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['config']['name'], '软件 Draft OPEX')
        self.assertEqual(response.data['overview']['version_context'], 'current_draft')
        self.assertEqual(response.data['overview']['expense_type'], 'opex')
        self.assertEqual(response.data['overview']['line_count'], 1)
        self.assertEqual(response.data['overview']['by_department'][0]['department_name'], '平台软件部')

    def test_non_global_user_only_lists_visible_configs(self):
        DashboardConfig.objects.create(
            name='我的配置',
            owner=self.user,
            scope=DashboardConfig.Scope.PERSONAL,
            version_context='latest_approved',
        )
        DashboardConfig.objects.create(
            name='软件共享',
            owner=self.primary_user,
            scope=DashboardConfig.Scope.DEPARTMENT,
            department=self.software,
            version_context='latest_approved',
        )
        DashboardConfig.objects.create(
            name='硬件共享',
            owner=self.primary_user,
            scope=DashboardConfig.Scope.DEPARTMENT,
            department=self.hardware,
            version_context='latest_approved',
        )
        DashboardConfig.objects.create(
            name='全局配置',
            owner=self.primary_user,
            scope=DashboardConfig.Scope.GLOBAL,
            version_context='latest_approved',
        )

        response = self.client.get(reverse('dashboardconfig-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {item['name'] for item in response.data['results']}
        self.assertEqual(names, {'我的配置', '软件共享'})

    def test_non_owner_cannot_update_shared_dashboard_config(self):
        shared = DashboardConfig.objects.create(
            name='软件共享',
            owner=self.primary_user,
            scope=DashboardConfig.Scope.DEPARTMENT,
            department=self.software,
            version_context='latest_approved',
        )

        response = self.client.patch(
            reverse('dashboardconfig-detail', args=[shared.id]),
            {'name': '软件共享 v2'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('permission', response.data)

    def _book_with_version(
        self,
        department,
        category,
        *,
        approved_amount,
        draft_amount=None,
        expense_type,
        template,
        project,
        project_category,
        product_line,
        month=1,
        budget_no=None,
    ):
        book = BudgetBook.objects.create(
            cycle=self.cycle,
            department=department,
            expense_type=expense_type,
            template=template,
        )
        approved = BudgetVersion.objects.create(book=book, status=BudgetVersion.Status.APPROVED, version_no=1)
        approved_line = BudgetLine.objects.create(
            version=approved,
            department=department,
            category=category,
            project=project,
            project_category=project_category,
            product_line=product_line,
            budget_no=budget_no or f'{department.code}-{expense_type.upper()}-APPROVED',
            description='Approved line',
            total_amount=approved_amount,
        )
        BudgetMonthlyPlan.objects.create(line=approved_line, month=month, amount=approved_amount)
        book.latest_approved_version = approved
        book.status = BudgetBook.Status.APPROVED
        if draft_amount:
            draft = BudgetVersion.objects.create(book=book, status=BudgetVersion.Status.DRAFT, base_version=approved)
            draft_line = BudgetLine.objects.create(
                version=draft,
                department=department,
                category=category,
                project=project,
                project_category=project_category,
                product_line=product_line,
                budget_no=f'{department.code}-{expense_type.upper()}-DRAFT',
                description='Draft line',
                total_amount=draft_amount,
            )
            BudgetMonthlyPlan.objects.create(line=draft_line, month=month, amount=draft_amount)
            book.current_draft = draft
            book.status = BudgetBook.Status.DRAFTING
        book.save(update_fields=['latest_approved_version', 'current_draft', 'status', 'updated_at'])
