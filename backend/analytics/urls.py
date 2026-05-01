from rest_framework.routers import DefaultRouter

from .views import DashboardConfigViewSet

router = DefaultRouter()
router.register('dashboard-configs', DashboardConfigViewSet)

urlpatterns = router.urls
