from rest_framework.routers import DefaultRouter

from .views import BudgetCycleViewSet, BudgetTaskViewSet

router = DefaultRouter()
router.register('cycles', BudgetCycleViewSet)
router.register('budget-tasks', BudgetTaskViewSet)

urlpatterns = router.urls
