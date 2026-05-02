from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User
from budget_cycles.models import BudgetCycle
from budget_templates.models import BudgetTemplate
from budgets.models import BudgetBook, BudgetLine, BudgetVersion
from notifications.models import Notification
from orgs.models import Department


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.department = Department.objects.create(name='平台软件部', code='SW-NOTI', level=Department.Level.SECONDARY)
        self.owner = User.objects.create_user(username='notify-owner', password='pass')
        self.approver = User.objects.create_user(username='notify-head', password='pass')
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
        self.cycle = BudgetCycle.objects.create(year=2031, name='2031 年度预算编制')
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
        self.version = BudgetVersion.objects.create(book=self.book, status=BudgetVersion.Status.DRAFT)
        self.book.current_draft = self.version
        self.book.save(update_fields=['current_draft'])
        BudgetLine.objects.create(
            version=self.version,
            department=self.department,
            line_no=1,
            budget_no='NOTI-001',
            description='通知测试条目',
            total_amount='100.00',
        )

    def test_submit_generates_todo_notification_for_approver(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(reverse('budgetversion-submit', args=[self.version.id]), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notification = Notification.objects.get(recipient=self.approver, category=Notification.Category.APPROVAL_TODO)
        self.assertEqual(notification.department, self.department)
        self.assertEqual(notification.target_type, 'approval_request')
        self.assertEqual(notification.status, Notification.Status.UNREAD)

    def test_approve_generates_result_notification_for_requester(self):
        self.client.force_authenticate(self.owner)
        submit_response = self.client.post(reverse('budgetversion-submit', args=[self.version.id]), {}, format='json')
        approval_request_id = submit_response.data['approval_request_id']
        self.client.force_authenticate(self.approver)

        response = self.client.post(reverse('approvalrequest-approve', args=[approval_request_id]), {'comment': '通过'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification = Notification.objects.filter(
            recipient=self.owner,
            category=Notification.Category.APPROVAL_RESULT,
            extra__result='approved',
        ).latest('created_at')
        self.assertIn('已通过', notification.title)

    def test_reject_generates_result_notification_for_requester(self):
        self.client.force_authenticate(self.owner)
        submit_response = self.client.post(reverse('budgetversion-submit', args=[self.version.id]), {}, format='json')
        approval_request_id = submit_response.data['approval_request_id']
        self.client.force_authenticate(self.approver)

        response = self.client.post(reverse('approvalrequest-reject', args=[approval_request_id]), {'comment': '补充说明'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification = Notification.objects.filter(
            recipient=self.owner,
            category=Notification.Category.APPROVAL_RESULT,
            extra__result='rejected',
        ).latest('created_at')
        self.assertIn('已退回', notification.title)

    def test_user_can_list_summary_and_mark_notifications_read(self):
        Notification.objects.create(
            recipient=self.owner,
            category=Notification.Category.SYSTEM,
            title='系统提醒',
            message='请检查预算版本',
            department=self.department,
        )
        Notification.objects.create(
            recipient=self.owner,
            category=Notification.Category.SYSTEM,
            title='第二条提醒',
            message='请检查模板字段',
            department=self.department,
        )
        self.client.force_authenticate(self.owner)

        list_response = self.client.get(reverse('notification-list'))
        summary_response = self.client.get(reverse('notification-summary'))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(summary_response.status_code, status.HTTP_200_OK)
        self.assertEqual(summary_response.data['unread_count'], 2)

        notification_ids = [item['id'] for item in list_response.data['results']]
        mark_response = self.client.post(reverse('notification-mark-read'), {'ids': notification_ids[:1]}, format='json')

        self.assertEqual(mark_response.status_code, status.HTTP_200_OK)
        self.assertEqual(mark_response.data['marked_count'], 1)
        self.assertEqual(Notification.objects.filter(recipient=self.owner, status=Notification.Status.UNREAD).count(), 1)
