from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.models import RoleAssignment, User
from approvals.models import ApprovalRequest
from budget_cycles.models import BudgetCycle, BudgetTask
from budget_templates.models import BudgetTemplate, TemplateField
from budgets.allocations import import_group_allocations
from budgets.models import BudgetBook, BudgetLine, BudgetMonthlyPlan, BudgetVersion
from budgets.services import create_revision_draft, submit_budget_version
from masterdata.models import Category, ProductLine, Project, ProjectCategory, PurchaseHistory, Vendor
from orgs.models import Department


class Command(BaseCommand):
    help = 'Seed a repeatable demo dataset for local development.'

    SECONDARY_DEPARTMENTS = [
        'Arch',
        'PVE',
        'PE',
        'STE',
        'PHE',
        'FTE',
        'cSSD_FW',
        'eSSD_FW',
        'Embedded_FW',
        'PDT',
    ]

    def handle(self, *args, **options):
        primary = self._department('SS', 'SS', Department.Level.PRIMARY)
        departments = {
            name: self._department(name, name, Department.Level.SECONDARY, parent=primary, sort_order=(index + 1) * 10)
            for index, name in enumerate(self.SECONDARY_DEPARTMENTS)
        }
        arch = departments['Arch']
        pve = departments['PVE']
        ss_public = self._department('SS_PUBLIC', 'SS public', Department.Level.SS_PUBLIC, parent=primary, sort_order=900)

        owner = self._user('budget-owner', '预算管理员', arch)
        approver = self._user('dept-head', '二级部门负责人', arch)
        primary_admin = self._user('primary-admin', '一级预算管理员', primary)
        RoleAssignment.objects.get_or_create(
            user=owner,
            role=RoleAssignment.Role.SECONDARY_BUDGET_OWNER,
            department=arch,
        )
        RoleAssignment.objects.get_or_create(
            user=approver,
            role=RoleAssignment.Role.SECONDARY_DEPT_HEAD,
            department=arch,
        )
        RoleAssignment.objects.get_or_create(
            user=primary_admin,
            role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN,
            department=primary,
        )

        cycle, _ = BudgetCycle.objects.update_or_create(
            year=2027,
            defaults={'name': '2027 年度预算编制', 'status': BudgetCycle.Status.ACTIVE},
        )
        template, _ = BudgetTemplate.objects.update_or_create(
            cycle=cycle,
            expense_type=BudgetTemplate.ExpenseType.OPEX,
            schema_version=1,
            defaults={'name': 'OPEX 标准模板', 'status': BudgetTemplate.Status.ACTIVE},
        )
        self._template_fields(template)

        cloud = self._category('CLOUD', 'Cloud Service', Category.Level.CATEGORY)
        software_cat = self._category('SOFTWARE', 'Software', Category.Level.CATEGORY)
        server = self._category('SERVER', 'Server', Category.Level.CATEGORY)
        product_category, _ = ProjectCategory.objects.update_or_create(code='PRODUCT', defaults={'name': '产品项目'})
        td_category, _ = ProjectCategory.objects.update_or_create(code='TD', defaults={'name': 'TD 项目'})
        public_line, _ = ProductLine.objects.update_or_create(code='COMMON', defaults={'name': '公共能力'})
        project, _ = Project.objects.update_or_create(
            code='TD-PLATFORM',
            defaults={'name': '平台 TD 项目', 'project_category': td_category, 'product_line': public_line},
        )
        vendor, _ = Vendor.objects.update_or_create(code='V-CLOUD', defaults={'name': '云资源供应商'})
        PurchaseHistory.objects.update_or_create(
            purchase_name='研发云测试资源包',
            vendor=vendor,
            defaults={'category': cloud, 'deal_price': Decimal('9800.00'), 'source': '2026 执行数据'},
        )

        self._book_with_version(cycle, arch, template, cloud, project, owner, approved=False)
        pve_book = self._book_with_version(cycle, pve, template, server, project, owner, approved=True)
        self._book_with_version(cycle, ss_public, template, software_cat, project, primary_admin, approved=True)
        self._group_allocation_example(cycle, primary_admin)
        self._pending_book(cycle, template, cloud, project, owner, approver)
        self._revision_example(pve_book, owner)
        for department in [*departments.values(), ss_public]:
            task_owner = owner if department == arch else primary_admin
            BudgetTask.objects.update_or_create(
                cycle=cycle,
                department=department,
                defaults={'owner': task_owner, 'status': BudgetTask.Status.DRAFTING},
            )

        self.stdout.write(self.style.SUCCESS('Demo data seeded. Users: budget-owner / dept-head / primary-admin, password: password'))

    def _department(self, code, name, level, parent=None, sort_order=0):
        department, _ = Department.objects.update_or_create(
            code=code,
            defaults={'name': name, 'level': level, 'parent': parent, 'sort_order': sort_order},
        )
        return department

    def _user(self, username, display_name, department):
        user, created = User.objects.update_or_create(
            username=username,
            defaults={'display_name': display_name, 'primary_department': department, 'is_staff': True},
        )
        if created:
            user.set_password('password')
            user.save(update_fields=['password'])
        return user

    def _category(self, code, name, level):
        category, _ = Category.objects.update_or_create(code=code, defaults={'name': name, 'level': level})
        return category

    def _template_fields(self, template):
        for order, (code, label, data_type) in enumerate(
            [
                ('budget_no', '预算编号', TemplateField.DataType.TEXT),
                ('category', 'Category', TemplateField.DataType.OPTION),
                ('project', 'Project', TemplateField.DataType.OPTION),
                ('description', '预算条目描述', TemplateField.DataType.TEXT),
                ('unit_price', '单价', TemplateField.DataType.MONEY),
                ('total_amount', '总金额', TemplateField.DataType.MONEY),
            ],
            start=1,
        ):
            TemplateField.objects.update_or_create(
                template=template,
                code=code,
                defaults={'label': label, 'data_type': data_type, 'order': order, 'dashboard_enabled': True},
            )

    def _book_with_version(self, cycle, department, template, category, project, user, approved=False):
        book, _ = BudgetBook.objects.update_or_create(
            cycle=cycle,
            department=department,
            expense_type=BudgetBook.ExpenseType.OPEX,
            source_type=BudgetBook.SourceType.SELF_BUILT,
            defaults={'template': template},
        )
        version_status = BudgetVersion.Status.APPROVED if approved else BudgetVersion.Status.DRAFT
        version, _ = BudgetVersion.objects.update_or_create(
            book=book,
            version_no=1 if approved else 0,
            defaults={'status': version_status, 'approved_by': user if approved else None},
        )
        book.status = BudgetBook.Status.APPROVED if approved and not book.current_draft_id else BudgetBook.Status.DRAFTING
        book.latest_approved_version = version if approved else None
        if not approved:
            book.current_draft = version
        book.save(update_fields=['status', 'latest_approved_version', 'current_draft', 'updated_at'])

        line, _ = BudgetLine.objects.update_or_create(
            version=version,
            budget_no=f'OPEX-{department.code}-001',
            defaults={
                'department': department,
                'line_no': 1,
                'category': category,
                'project': project,
                'description': f'{department.name} 研发资源预算',
                'unit_price': Decimal('10000.00'),
                'total_quantity': Decimal('12.00'),
                'total_amount': Decimal('120000.00'),
            },
        )
        for month in range(1, 13):
            BudgetMonthlyPlan.objects.update_or_create(
                line=line,
                month=month,
                defaults={'quantity': Decimal('1.00'), 'amount': Decimal('10000.00')},
            )
        return book

    def _pending_book(self, cycle, template, category, project, owner, approver):
        department = self._department('PE', 'PE', Department.Level.SECONDARY, parent=Department.objects.get(code='SS'), sort_order=30)
        RoleAssignment.objects.get_or_create(
            user=approver,
            role=RoleAssignment.Role.SECONDARY_DEPT_HEAD,
            department=department,
        )
        book, _ = BudgetBook.objects.update_or_create(
            cycle=cycle,
            department=department,
            expense_type=BudgetBook.ExpenseType.CAPEX,
            source_type=BudgetBook.SourceType.SELF_BUILT,
            defaults={'template': template, 'status': BudgetBook.Status.DRAFTING},
        )
        version, created = BudgetVersion.objects.get_or_create(
            book=book,
            version_no=0,
            defaults={'status': BudgetVersion.Status.DRAFT},
        )
        book.current_draft = version
        book.latest_approved_version = None
        book.save(update_fields=['current_draft', 'latest_approved_version', 'updated_at'])
        line, _ = BudgetLine.objects.update_or_create(
            version=version,
            budget_no='CAPEX-AI-001',
            defaults={
                'department': department,
                'line_no': 1,
                'category': category,
                'project': project,
                'description': '模型训练服务器',
                'unit_price': Decimal('85000.00'),
                'total_quantity': Decimal('4.00'),
                'total_amount': Decimal('340000.00'),
            },
        )
        for month in [3, 6, 9, 12]:
            BudgetMonthlyPlan.objects.update_or_create(
                line=line,
                month=month,
                defaults={'quantity': Decimal('1.00'), 'amount': Decimal('85000.00')},
            )
        has_pending_request = ApprovalRequest.objects.filter(
            target_type='budget_version',
            target_id=version.id,
            status=ApprovalRequest.Status.PENDING,
        ).exists()
        if created or (version.status == BudgetVersion.Status.DRAFT and not has_pending_request):
            submit_budget_version(version, owner, approver_ids=[approver.id], comment='种子数据自动送审')

    def _revision_example(self, book, owner):
        if not book.latest_approved_version_id:
            return
        draft = BudgetVersion.objects.filter(
            book=book,
            base_version=book.latest_approved_version,
            status=BudgetVersion.Status.DRAFT,
        ).order_by('created_at').first()
        if not draft:
            draft = create_revision_draft(book, requester=owner)
        elif book.current_draft_id != draft.id:
            book.current_draft = draft
            book.status = BudgetBook.Status.DRAFTING
            book.save(update_fields=['current_draft', 'status', 'updated_at'])
        line = draft.lines.order_by('line_no').first()
        if not line:
            return
        line.description = f'{line.description} - 修订示例'
        line.total_amount = Decimal('135000.00')
        line.save(update_fields=['description', 'total_amount', 'updated_at'])
        plan = line.monthly_plans.filter(month=1).first()
        if plan:
            plan.amount = Decimal('25000.00')
            plan.save(update_fields=['amount', 'updated_at'])

    def _group_allocation_example(self, cycle, requester):
        import_group_allocations(
            cycle,
            requester,
            source_name='seed-group-allocation.tsv',
            raw_text='\n'.join(
                [
                    '\t'.join(['预算部门', '预算编号', '预算条目描述', '总金额', '备注']),
                    '\t'.join(['Arch', 'ALLOC-ARCH-001', '集团云资源分摊', '60000.00', 'seed']),
                    '\t'.join(['PVE', 'ALLOC-PVE-001', '集团软件许可分摊', '40000.00', 'seed']),
                ]
            ),
        )
