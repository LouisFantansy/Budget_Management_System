from rest_framework.routers import DefaultRouter

from .views import BudgetBookViewSet, BudgetLineViewSet, BudgetMonthlyPlanViewSet, BudgetVersionViewSet

router = DefaultRouter()
router.register('budget-books', BudgetBookViewSet)
router.register('budget-versions', BudgetVersionViewSet)
router.register('budget-lines', BudgetLineViewSet)
router.register('budget-monthly-plans', BudgetMonthlyPlanViewSet)

urlpatterns = router.urls
