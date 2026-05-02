from rest_framework.routers import DefaultRouter

from .views import DemandSheetViewSet, DemandTemplateViewSet

router = DefaultRouter()
router.register('demand-templates', DemandTemplateViewSet, basename='demandtemplate')
router.register('demand-sheets', DemandSheetViewSet, basename='demandsheet')

urlpatterns = router.urls

