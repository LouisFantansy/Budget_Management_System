from rest_framework import decorators, response, viewsets

from accounts.access import accessible_department_ids, is_global_budget_user
from .models import ApprovalRequest, ApprovalStep
from .serializers import ApprovalRequestSerializer, ApprovalStepSerializer
from .services import approve_request, reject_request


class ApprovalRequestViewSet(viewsets.ModelViewSet):
    queryset = ApprovalRequest.objects.select_related('requester', 'department').prefetch_related('steps').all()
    serializer_class = ApprovalRequestSerializer
    filterset_fields = ['target_type', 'department', 'status', 'requester']
    search_fields = ['title']

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_global_budget_user(self.request.user):
            return queryset
        department_ids = accessible_department_ids(self.request.user)
        return queryset.filter(department_id__in=department_ids)

    @decorators.action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        approval_request = approve_request(
            self.get_object(),
            request.user,
            comment=request.data.get('comment', ''),
        )
        serializer = self.get_serializer(approval_request)
        return response.Response(serializer.data)

    @decorators.action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        approval_request = reject_request(
            self.get_object(),
            request.user,
            comment=request.data.get('comment', ''),
        )
        serializer = self.get_serializer(approval_request)
        return response.Response(serializer.data)


class ApprovalStepViewSet(viewsets.ModelViewSet):
    queryset = ApprovalStep.objects.select_related('request', 'approver').all()
    serializer_class = ApprovalStepSerializer
    filterset_fields = ['request', 'approver', 'action']

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_global_budget_user(self.request.user):
            return queryset
        department_ids = accessible_department_ids(self.request.user)
        return queryset.filter(request__department_id__in=department_ids)

# Create your views here.
