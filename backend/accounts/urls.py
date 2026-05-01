from rest_framework.routers import DefaultRouter

from .views import RoleAssignmentViewSet, UserViewSet

router = DefaultRouter()
router.register('users', UserViewSet)
router.register('role-assignments', RoleAssignmentViewSet)

urlpatterns = router.urls
