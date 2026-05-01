from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class AuthAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='primary-admin',
            password='password',
            display_name='一级预算管理员',
            email='primary@example.com',
        )

    def test_me_requires_authentication(self):
        response = self.client.get(reverse('auth-me'))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            reverse('auth-login'),
            {'username': 'primary-admin', 'password': 'wrong'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_me_and_logout_flow(self):
        login_response = self.client.post(
            reverse('auth-login'),
            {'username': 'primary-admin', 'password': 'password'},
            format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(login_response.data['username'], 'primary-admin')

        me_response = self.client.get(reverse('auth-me'))
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data['display_name'], '一级预算管理员')

        logout_response = self.client.post(reverse('auth-logout'))
        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)
        after_logout_response = self.client.get(reverse('auth-me'))
        self.assertEqual(after_logout_response.status_code, status.HTTP_403_FORBIDDEN)
