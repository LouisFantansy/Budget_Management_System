from rest_framework.routers import DefaultRouter

from .views import (
    AllocationUploadViewSet,
    BudgetBookViewSet,
    BudgetLineViewSet,
    BudgetMonthlyPlanViewSet,
    BudgetVersionViewSet,
    ImportJobViewSet,
)

router = DefaultRouter()
router.register('budget-books', BudgetBookViewSet)
router.register('budget-versions', BudgetVersionViewSet)
router.register('budget-lines', BudgetLineViewSet)
router.register('budget-monthly-plans', BudgetMonthlyPlanViewSet)
router.register('import-jobs', ImportJobViewSet, basename='importjob')
router.register('allocation-uploads', AllocationUploadViewSet, basename='allocationupload')

urlpatterns = router.urls
