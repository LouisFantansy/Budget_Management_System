from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import RoleAssignment, User

from .models import Category, Region, Vendor


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
