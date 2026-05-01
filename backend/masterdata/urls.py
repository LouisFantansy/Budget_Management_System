from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet,
    ProductLineViewSet,
    ProjectCategoryViewSet,
    ProjectViewSet,
    PurchaseHistoryViewSet,
    RegionViewSet,
    VendorViewSet,
)

router = DefaultRouter()
router.register('categories', CategoryViewSet)
router.register('project-categories', ProjectCategoryViewSet)
router.register('product-lines', ProductLineViewSet)
router.register('projects', ProjectViewSet)
router.register('vendors', VendorViewSet)
router.register('regions', RegionViewSet)
router.register('purchase-history', PurchaseHistoryViewSet)

urlpatterns = router.urls
