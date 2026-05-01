from rest_framework.routers import DefaultRouter

from .views import ApprovalRequestViewSet, ApprovalStepViewSet

router = DefaultRouter()
router.register('approval-requests', ApprovalRequestViewSet)
router.register('approval-steps', ApprovalStepViewSet)

urlpatterns = router.urls
