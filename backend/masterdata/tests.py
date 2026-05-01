from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User

from .models import Category, ProductLine, Project, ProjectCategory, PurchaseHistory, Region, Vendor


class MasterDataAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='primary-admin', password='password')
        RoleAssignment.objects.create(user=self.user, role=RoleAssignment.Role.PRIMARY_BUDGET_ADMIN)
        self.client.force_authenticate(self.user)

    def test_can_create_category(self):
        response = self.client.post(
            reverse('category-list'),
            {'code': 'CLOUD', 'name': 'Cloud Service', 'level': Category.Level.CATEGORY},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Category.objects.filter(code='CLOUD').exists())

    def test_can_update_vendor(self):
        vendor = Vendor.objects.create(code='AWS', name='Amazon')

        response = self.client.patch(
            reverse('vendor-detail', args=[vendor.id]),
            {'name': 'Amazon Web Services', 'sort_order': 10},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        vendor.refresh_from_db()
        self.assertEqual(vendor.name, 'Amazon Web Services')
        self.assertEqual(vendor.sort_order, 10)

    def test_can_delete_region(self):
        region = Region.objects.create(code='CN', name='China')

        response = self.client.delete(reverse('region-detail', args=[region.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Region.objects.filter(id=region.id).exists())

    def test_can_create_project_with_category_and_product_line(self):
        project_category = ProjectCategory.objects.create(code='PLATFORM', name='平台项目')
        product_line = ProductLine.objects.create(code='ENTERPRISE', name='企业盘')

        response = self.client.post(
            reverse('project-list'),
            {
                'code': 'TD',
                'name': 'TD 项目',
                'project_category': str(project_category.id),
                'product_line': str(product_line.id),
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(code='TD')
        self.assertEqual(project.project_category, project_category)
        self.assertEqual(project.product_line, product_line)

    def test_can_update_project_relations(self):
        original_category = ProjectCategory.objects.create(code='PUBLIC', name='公共能力')
        original_product_line = ProductLine.objects.create(code='CLIENT', name='客户端')
        target_category = ProjectCategory.objects.create(code='PRODUCT', name='产品项目')
        target_product_line = ProductLine.objects.create(code='DATACENTER', name='数据中心盘')
        project = Project.objects.create(
            code='ALPHA',
            name='Alpha 项目',
            project_category=original_category,
            product_line=original_product_line,
        )

        response = self.client.patch(
            reverse('project-detail', args=[project.id]),
            {
                'project_category': str(target_category.id),
                'product_line': str(target_product_line.id),
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.project_category, target_category)
        self.assertEqual(project.product_line, target_product_line)

    def test_purchase_history_suggest_returns_recommended_price(self):
        vendor = Vendor.objects.create(code='AWS', name='Amazon')
        category = Category.objects.create(code='CLOUD', name='Cloud Service', level=Category.Level.CATEGORY)
        PurchaseHistory.objects.create(
            purchase_name='研发云测试资源包',
            vendor=vendor,
            category=category,
            deal_price='100.00',
        )
        PurchaseHistory.objects.create(
            purchase_name='办公椅',
            vendor=vendor,
            category=category,
            deal_price='20.00',
        )

        response = self.client.get(reverse('purchasehistory-suggest'), {'q': '云测试'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['purchase_name'], '研发云测试资源包')
        self.assertEqual(response.data[0]['recommended_price'], '120.00')
