from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import RoleAssignmentViewSet, UserViewSet, login_view, logout_view, me_view

router = DefaultRouter()
router.register('users', UserViewSet)
router.register('role-assignments', RoleAssignmentViewSet)

urlpatterns = [
    path('auth/login/', login_view, name='auth-login'),
    path('auth/logout/', logout_view, name='auth-logout'),
    path('auth/me/', me_view, name='auth-me'),
    *router.urls,
]
