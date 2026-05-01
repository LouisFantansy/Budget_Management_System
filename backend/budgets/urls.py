from rest_framework.routers import DefaultRouter

from .views import BudgetBookViewSet, BudgetLineViewSet, BudgetMonthlyPlanViewSet, BudgetVersionViewSet, ImportJobViewSet

router = DefaultRouter()
router.register('budget-books', BudgetBookViewSet)
router.register('budget-versions', BudgetVersionViewSet)
router.register('budget-lines', BudgetLineViewSet)
router.register('budget-monthly-plans', BudgetMonthlyPlanViewSet)
router.register('import-jobs', ImportJobViewSet, basename='importjob')

urlpatterns = router.urls
