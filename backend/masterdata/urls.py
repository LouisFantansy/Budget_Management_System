from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet,
    CostCenterViewSet,
    GLAccountViewSet,
    OptionSourceRegistryEntryViewSet,
    ProductLineViewSet,
    ProjectCategoryViewSet,
    ProjectViewSet,
    PurchaseHistoryViewSet,
    RegionViewSet,
    VendorViewSet,
    option_source_catalog,
)

router = DefaultRouter()
router.register('categories', CategoryViewSet)
router.register('project-categories', ProjectCategoryViewSet)
router.register('product-lines', ProductLineViewSet)
router.register('projects', ProjectViewSet)
router.register('vendors', VendorViewSet)
router.register('regions', RegionViewSet)
router.register('cost-centers', CostCenterViewSet)
router.register('gl-accounts', GLAccountViewSet)
router.register('option-source-registry', OptionSourceRegistryEntryViewSet)
router.register('purchase-history', PurchaseHistoryViewSet)

urlpatterns = [
    path('option-sources/', option_source_catalog),
    *router.urls,
]
