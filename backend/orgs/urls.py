from rest_framework.routers import DefaultRouter

from .views import DepartmentViewSet

router = DefaultRouter()
router.register('departments', DepartmentViewSet)

urlpatterns = router.urls
