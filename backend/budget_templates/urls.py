from rest_framework.routers import DefaultRouter

from .views import BudgetTemplateViewSet, TemplateFieldViewSet

router = DefaultRouter()
router.register('budget-templates', BudgetTemplateViewSet)
router.register('template-fields', TemplateFieldViewSet)

urlpatterns = router.urls
